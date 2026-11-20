import pandas as pd
df = pd.read_csv("C:/Users/Gaby/Desktop/IAPD_NBA/data/processed/games_clean.csv", parse_dates=["GAME_DATE"])
print(df.shape)