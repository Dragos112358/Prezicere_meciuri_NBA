"""Scrape Basketball-Reference: ratinguri de echipa pe sezon (SRS, ORtg, DRtg, Pace).

Rulare (din radacina proiectului):
    pip install requests lxml pandas
    python extraction/scrape_bref.py
Output: data/raw/bref_team_ratings.csv  (un rand per echipa per sezon)
HTML-ul brut e salvat in data/raw/bref_html/ ca sa nu refaci cererile.
Valorile sunt FINALE pe sezon -> build_dataset.py le foloseste doar pentru sezonul URMATOR (fara leakage).
"""
import time
from io import StringIO
from pathlib import Path

import pandas as pd
import requests

FIRST_YEAR, LAST_YEAR = 1980, 2025          # sezonul de start (1980 = 1980-81)
ROOT = Path(__file__).resolve().parent.parent
RAW_DIR = ROOT / "data" / "raw"
HTML_DIR = RAW_DIR / "bref_html"
OUT = RAW_DIR / "bref_team_ratings.csv"
WANT = ["SRS", "ORtg", "DRtg", "Pace"]
SLEEP = 4   # secunde intre cereri (limita BR ~20/min)
HEADERS = {"User-Agent": "Mozilla/5.0 (student project; IAPD Politehnica)"}


def season_str(y: int) -> str:
    return f"{y}-{str(y + 1)[-2:]}"


def get_html(start_year: int) -> str:
    path = HTML_DIR / f"NBA_{start_year + 1}.html"
    if path.exists():
        return path.read_text(encoding="utf-8")
    url = f"https://www.basketball-reference.com/leagues/NBA_{start_year + 1}.html"
    r = requests.get(url, headers=HEADERS, timeout=30)
    if r.status_code != 200:
        raise RuntimeError(f"{url} -> HTTP {r.status_code} (daca e 429/403: asteapta cateva minute sau salveaza pagina manual in {path})")
    path.write_text(r.text, encoding="utf-8")
    time.sleep(SLEEP)
    return r.text


def parse_ratings(html: str, season: str) -> pd.DataFrame:
    # unele tabele sunt in comentarii HTML -> le "dezcomentam"
    html = html.replace("<!--", "").replace("-->", "")
    for t in pd.read_html(StringIO(html)):
        t.columns = [c[-1] if isinstance(c, tuple) else c for c in t.columns]
        if {"Team", "SRS", "ORtg", "DRtg", "Pace"}.issubset(t.columns):
            t = t[["Team"] + WANT].copy()
            t = t[t["Team"].astype(str) != "League Average"]
            t["Team"] = t["Team"].astype(str).str.replace("*", "", regex=False).str.strip()
            for c in WANT:
                t[c] = pd.to_numeric(t[c], errors="coerce")
            t = t.dropna(subset=["Team", "SRS"])
            t.insert(0, "SEASON", season)
            return t.rename(columns={"Team": "TEAM_NAME"})
    raise ValueError(f"Nu am gasit tabelul de ratinguri pentru {season}")


def main():
    HTML_DIR.mkdir(parents=True, exist_ok=True)
    parts = []
    for y in range(FIRST_YEAR, LAST_YEAR + 1):
        season = season_str(y)
        try:
            parts.append(parse_ratings(get_html(y), season))
            print(f"{season}: ok ({len(parts[-1])} echipe)")
        except Exception as e:
            print(f"{season}: SKIP - {e}")
    if not parts:
        raise SystemExit("Nu s-a extras nimic.")
    pd.concat(parts, ignore_index=True).to_csv(OUT, index=False)
    print(f"-> {OUT}")


if __name__ == "__main__":
    main()