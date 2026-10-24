import pandas as pd

df = pd.read_csv("C:/Users/user/Bess Analytics/BESS.csv", sep=";", parse_dates=["DateAndTime"])
print(df.shape)                      
print(df["DateAndTime"].min(), df["DateAndTime"].max())
print(df.describe().T)               
print(df.isna().sum())        
   
print("Duplicate rows:", df.duplicated().sum())

