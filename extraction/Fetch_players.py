"""Extrage box score-ul pe JUCATOR per meci (un rand per jucator per meci) cu nba_api.

Rulare (din radacina proiectului):
    pip install nba_api pandas
    python extraction/fetch_players.py
Salveaza un CSV per sezon in data/raw/player_log_<sezon>.csv. Sezoanele existente sunt sarite.
Folosit de roster_features.py pentru: cine a jucat, minute, absente din rotatie, schimbari de lot.
"""
import time
from pathlib import Path

import pandas as pd
from nba_api.stats.endpoints import leaguegamelog

FIRST_YEAR, LAST_YEAR = 1980, 2025   # 1996-97 ... 2025-26 (date de jucatori consistente de aici)
ROOT = Path(__file__).resolve().parent.parent
RAW_DIR = ROOT / "data" / "raw"
RETRIES = 4


def season_str(y: int) -> str:
    return f"{y}-{str(y + 1)[-2:]}"


def fetch_season(season: str) -> pd.DataFrame:
    for attempt in range(1, RETRIES + 1):
        try:
            df = leaguegamelog.LeagueGameLog(
                season=season,
                season_type_all_star="Regular Season",
                player_or_team_abbreviation="P",   # P = player, T = team
                timeout=60,
            ).get_data_frames()[0]
            if df.empty:
                raise ValueError("raspuns gol")
            df["SEASON"] = season
            return df
        except Exception as e:
            wait = 5 * attempt
            print(f"  [{season}] eroare ({e}); reincerc in {wait}s ({attempt}/{RETRIES})")
            time.sleep(wait)
    raise RuntimeError(f"Nu s-a putut descarca sezonul {season}")


def main():
    RAW_DIR.mkdir(parents=True, exist_ok=True)
    for y in range(FIRST_YEAR, LAST_YEAR + 1):
        season = season_str(y)
        out = RAW_DIR / f"player_log_{season}.csv"
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