# BESS-Battery-analytics

# BESS Data Quality & Performance Analysis

# About the Project
This project focuses on analyzing Battery Energy Storage System (BESS) data using Python and Power BI. I used Python to clean the data, check for errors, and identify unusual readings. I then created Power BI dashboards to visualize battery performance and data quality.

# Tools Used
- Python (pandas, NumPy)
- Power BI

  
# What I Did
- Checked duplicate timestamps and missing time intervals.
- Converted grid frequency and temperature into standard units.
- Identified unusual frequency readings and invalid SOC values.
- Calculated daily data quality scores.
- Detected and measured periods with data quality issues.
- Explored the relationship between battery power and SOC.
- Built Power BI dashboards to show battery performance, efficiency, SOC, and data quality.


# What I Learned
This project helped me improve my Python data cleaning skills, understand battery operational data, and turn raw data into useful insights through Power BI.

## Note
The detected issues are potential data quality problems and do not necessarily indicate battery faults or safety risks.


## Power BI Dashboard

I created a two-page Power BI dashboard to understand how the battery performed and check the quality of the data.

### Page 1: Performance Overview


**Main results**

| Metric | What it tells us |

| 115.75K kWh charged | The total energy the battery took in |
| 89.66K kWh discharged | The total energy the battery sent out |
| 77.46% efficiency | For every 100 kWh charged, around 77 kWh was sent back |
| 46.56% average SOC | The battery was about half full on average |

**What I noticed**

- **Daily efficiency:** It changed from day to day, ranging from around 52% to 137%. Values above 100% need further checking, as the battery may also be using energy stored on previous days.
- **Battery level (SOC):** It stayed between around 37% and 66%, with peaks around 10 and 22 April.
- **Charged vs. discharged energy:** The battery usually took in more energy than it sent out. Day 11 was an exception.

The efficiency shown here is a simple comparison of energy charged and discharged. It does not account for changes in the battery's stored energy, so it should not be treated as the battery's true efficiency.

### Page 2: Data Quality and Outage



**Main results**

| Metric | What it tells us |
|---|---|
| 99.91 average quality score | The data quality was good overall |
| 1 outage | One possible data issue was identified |
| 39.75 minutes | The estimated duration of the issue |
| 50.00K average grid frequency | 50,000 mHz, which equals 50 Hz |

**What I found**

- **Possible outage:** On 3 April, between 06:33 and 07:13, the grid frequency and SOC readings were zero. This could mean that these signals were not recorded correctly during that period.
- **Daily data quality:** Most days scored 100. On 3 April, the score dropped to 97.24, matching the period with unusual readings.
- **FCR and battery power:** The two power signals followed similar patterns on several days, especially around 9–10 April and 22–24 April.

**How I handled the issue**

I treated the affected readings as missing data in the relevant calculations to avoid relying on values that might not be correct.

Overall, the dashboard helped me understand the battery's daily performance, spot unusual readings, and see where the data may need further investigation.





#Python codes that i used


import numpy as np
import pandas as pd


df = pd.read_csv("C:/Users/user/Bess Analytics/BESS.csv", sep=";", parse_dates=["DateAndTime"])

print(df.shape)               

print(df["DateAndTime"].min(), df["DateAndTime"].max())

print(df.describe().T)       

print(df.isna().sum())   

print("Duplicate rows:", df.duplicated().sum())



# 1. Timestamps: duplicates, order, gaps 
print("Duplicate timestamps:", df["DateAndTime"].duplicated().sum())

df = df.sort_values("DateAndTime").drop_duplicates("DateAndTime").set_index("DateAndTime")

steps = df.index.to_series().diff().dropna()

print("Gaps (step > 1 s):", (steps > pd.Timedelta("1s")).sum())

# 2. Unit conversion 
df["Grid_frequency_hz"] = df["Grid_frequency"] / 1000   # mHz -> Hz

df["Temperature_c"] = df["Temperature"] / 10            
# --- 3. Row-level quality flags -------------------------------------------
flags = pd.DataFrame(index=df.index)

flags["freq_dropout"] = df["Grid_frequency"] == 0                       

flags["freq_outlier"] = ~df["Grid_frequency_hz"].between(49, 51) & ~flags["freq_dropout"]

flags["freq_flatline"] = df["Grid_frequency"].rolling(60).std() == 0    # frozen for 60 s

flags["soc_range"] = ~df["SOC"].between(0, 100)

flags["soc_zero"] = df["SOC"] == 0

print("\nFlagged rows per check:")
print(flags.sum())

#  4. Daily quality score 
bad = flags.any(axis=1)

score = (100 * (1 - bad.groupby(df.index.date).mean())).round(2)

print("\nDaily quality score:")

print(score.to_string())

print("\nFlag percentage per day (days with problems only):")

print(flags.groupby(df.index.date).mean().mul(100).round(2).loc[lambda x: x.sum(axis=1) > 0])

#5. cleaned data 
clean = df.copy()

clean.loc[flags["freq_dropout"], ["Grid_frequency", "Grid_frequency_hz"]] = np.nan

clean.loc[flags["soc_zero"], "SOC"] = np.nan

clean.loc[bad, ["M5BAT_P", "M5BAT_Q", "FCR_P"]] = np.nan   

clean["valid"] = (~bad).astype(float)                      

m = clean[["M5BAT_P", "SOC"]].resample("1min").mean()

# 6. Energy consistency (hourly windows with a clear SOC change) 
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

# 7. Outage events 
event_id = (bad != bad.shift()).cumsum()

ev = bad.index.to_series().groupby(event_id).agg(start="min", end="max")

ev["is_bad"] = bad.groupby(event_id).first()

ev = ev[ev["is_bad"]].drop(columns="is_bad").reset_index(drop=True)

ev["duration_min"] = ((ev["end"] - ev["start"]).dt.total_seconds() + 1) / 60

print("\nQuality events:")

print(ev)

# 8. Save 
clean.resample("1min").mean().to_csv(OUT + "BESS_1min.csv")

score.rename("quality_score").to_csv(OUT + "daily_quality_score.csv")

ev.to_csv(OUT + "quality_events.csv", index=False)

print("\nSaved BESS_1min.csv, daily_quality_score.csv, quality_events.csv")

#  Look at 3 April 
if "2023-04-03" in df.index.strftime("%Y-%m-%d"):

    day = df.loc["2023-04-03"]
    
    bad_day = bad.loc["2023-04-03"]
    
    if bad_day.any():
        print("\nFirst bad row:", day.index[bad_day].min())
        print("Last bad row: ", day.index[bad_day].max())
        print(day[bad_day].head(10))



# Dax measures used

Total Discharged kWh = SUM(kpi_daily_energy[discharged_kwh])

Total Charged kWh = SUM(kpi_daily_energy[charged_kwh])

Efficiency Ratio = DIVIDE([Total Discharged kWh], [Total Charged kWh])

Avg SOC % = AVERAGE(kpi_daily_energy[avg_soc])

Avg Quality Score = AVERAGE(kpi_quality[quality_score])

Outage Count = COUNTROWS(quality_events)

Outage Minutes = SUM(quality_events[duration_min])

FCR Relative Error % = AVERAGE(kpi_fcr_tracking[relative_error])

Share Outside Band % = AVERAGE(kpi_frequency[share_outside_band])









