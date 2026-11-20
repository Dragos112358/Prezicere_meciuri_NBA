"""Extrage game log-urile NBA (un rand per echipa per meci) cu nba_api.

Rulare (din radacina proiectului):
    pip install nba_api pandas
    python extraction/fetch_games.py
Salveaza un CSV brut per sezon in data/raw/. Sezoanele deja descarcate sunt sarite.
Pentru un sezon nou, creste LAST_YEAR si ruleaza din nou.
"""
import time
from pathlib import Path

import pandas as pd
from nba_api.stats.endpoints import leaguegamelog

FIRST_YEAR, LAST_YEAR = 1980, 2025   # 1980-81 ... 2025-26 (primul sezon cu 3-pointer)
RAW_DIR = Path("../data/raw")
RETRIES = 4


def season_str(y: int) -> str:
    return f"{y}-{str(y + 1)[-2:]}"


def fetch_season(season: str) -> pd.DataFrame:
    for attempt in range(1, RETRIES + 1):
        try:
            df = leaguegamelog.LeagueGameLog(
                season=season,
                season_type_all_star="Regular Season",
                timeout=60,
            ).get_data_frames()[0]
            if df.empty:
                raise ValueError("raspuns gol")
            df["SEASON"] = season
            return df
        except Exception as e:  # stats.nba.com mai da timeout-uri
            wait = 5 * attempt
            print(f"  [{season}] eroare ({e}); reincerc in {wait}s ({attempt}/{RETRIES})")
            time.sleep(wait)
    raise RuntimeError(f"Nu s-a putut descarca sezonul {season}")


def main():
    RAW_DIR.mkdir(parents=True, exist_ok=True)
    for y in range(FIRST_YEAR, LAST_YEAR + 1):
        season = season_str(y)
        out = RAW_DIR / f"game_log_{season}.csv"
        if out.exists():
            print(f"{season}: exista deja, sar peste")
            continue
        print(f"{season}: descarc...")
        df = fetch_season(season)
        df.to_csv(out, index=False)
        print(f"  salvat {len(df)} randuri -> {out}")
        time.sleep(2)


if __name__ == "__main__":
    main()