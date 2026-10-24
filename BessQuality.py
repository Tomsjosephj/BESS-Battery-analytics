import numpy as np
import pandas as pd

PATH = "C:/Users/user/Bess Analytics/BESS.csv"
OUT = "C:/Users/user/Bess Analytics/"

df = pd.read_csv(PATH, sep=";", parse_dates=["DateAndTime"])

# --- 1. Timestamps: duplicates, order, gaps -------------------------------
print("Duplicate timestamps:", df["DateAndTime"].duplicated().sum())
df = df.sort_values("DateAndTime").drop_duplicates("DateAndTime").set_index("DateAndTime")
steps = df.index.to_series().diff().dropna()
print("Gaps (step > 1 s):", (steps > pd.Timedelta("1s")).sum())

# --- 2. Unit conversion (units confirmed by the dataset's data table) -----
df["Grid_frequency_hz"] = df["Grid_frequency"] / 1000   # mHz -> Hz
df["Temperature_c"] = df["Temperature"] / 10            # 0.1 degC -> degC (ambient)

# --- 3. Row-level quality flags -------------------------------------------
flags = pd.DataFrame(index=df.index)
flags["freq_dropout"] = df["Grid_frequency"] == 0                       # 0 Hz is impossible
flags["freq_outlier"] = ~df["Grid_frequency_hz"].between(49, 51) & ~flags["freq_dropout"]
flags["freq_flatline"] = df["Grid_frequency"].rolling(60).std() == 0    # frozen for 60 s
flags["soc_range"] = ~df["SOC"].between(0, 100)
flags["soc_zero"] = df["SOC"] == 0

print("\nFlagged rows per check:")
print(flags.sum())

# --- 4. Daily quality score (UTC days) ------------------------------------
bad = flags.any(axis=1)
score = (100 * (1 - bad.groupby(df.index.date).mean())).round(2)
print("\nDaily quality score:")
print(score.to_string())

print("\nFlag percentage per day (days with problems only):")
print(flags.groupby(df.index.date).mean().mul(100).round(2).loc[lambda x: x.sum(axis=1) > 0])

# --- 5. Build cleaned data ------------------------------------------------
clean = df.copy()
clean.loc[flags["freq_dropout"], ["Grid_frequency", "Grid_frequency_hz"]] = np.nan
clean.loc[flags["soc_zero"], "SOC"] = np.nan
clean.loc[bad, ["M5BAT_P", "M5BAT_Q", "FCR_P"]] = np.nan   # not trustworthy during outage
clean["valid"] = (~bad).astype(float)                       # 1 = passed all checks

m = clean[["M5BAT_P", "SOC"]].resample("1min").mean()

# --- 6. Energy consistency (hourly windows with a clear SOC change) -------
h = m.resample("1h").agg(
    e_kwh=("M5BAT_P", lambda s: s.sum() / 60),
    soc_start=("SOC", "first"),
    soc_end=("SOC", "last"),
).dropna()
h["dsoc"] = h["soc_end"] - h["soc_start"]
h = h[h["dsoc"].abs() >= 5]
h["implied_capacity_kwh"] = h["e_kwh"] / (-h["dsoc"] / 100)
h = h[h["implied_capacity_kwh"] > 0]
print("\nImplied capacity (kWh), plausibility check only (SOC is calculated):")
print(h["implied_capacity_kwh"].describe())

# --- 7. Outage events -----------------------------------------------------
event_id = (bad != bad.shift()).cumsum()
ev = bad.index.to_series().groupby(event_id).agg(start="min", end="max")
ev["is_bad"] = bad.groupby(event_id).first()
ev = ev[ev["is_bad"]].drop(columns="is_bad").reset_index(drop=True)
ev["duration_min"] = ((ev["end"] - ev["start"]).dt.total_seconds() + 1) / 60
print("\nQuality events:")
print(ev)

# --- 8. Save --------------------------------------------------------------
clean.resample("1min").mean().to_csv(OUT + "BESS_1min.csv")
score.rename("quality_score").to_csv(OUT + "daily_quality_score.csv")
ev.to_csv(OUT + "quality_events.csv", index=False)
print("\nSaved BESS_1min.csv, daily_quality_score.csv, quality_events.csv")

# --- 9. Look at 3 April ---------------------------------------------------
if "2023-04-03" in df.index.strftime("%Y-%m-%d"):
    day = df.loc["2023-04-03"]
    bad_day = bad.loc["2023-04-03"]
    if bad_day.any():
        print("\nFirst bad row:", day.index[bad_day].min())
        print("Last bad row: ", day.index[bad_day].max())
        print(day[bad_day].head(10))