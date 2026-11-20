"""Scrape Basketball-Reference: statistici avansate pe JUCATOR si sezon (BPM, VORP, MP).

Rulare (din radacina proiectului):
    pip install requests lxml pandas
    python extraction/scrape_bref_players.py
Output: data/raw/bref_player_advanced.csv  (un rand per jucator per sezon)
HTML-ul brut e salvat in data/raw/bref_html/ (NBA_<an>_advanced.html) ca sa nu refaci cererile.
Valorile sunt FINALE pe sezon -> roster_features.py le foloseste doar pentru sezonul URMATOR (fara leakage).
"""
import time
from io import StringIO
from pathlib import Path

import pandas as pd
import requests

FIRST_YEAR, LAST_YEAR = 1980, 2025
ROOT = Path(__file__).resolve().parent.parent
RAW_DIR = ROOT / "data" / "raw"
HTML_DIR = RAW_DIR / "bref_html"
OUT = RAW_DIR / "bref_player_advanced.csv"
SLEEP = 4   # secunde intre cereri (limita BR ~20/min)
HEADERS = {"User-Agent": "Mozilla/5.0 (student project; IAPD Politehnica)"}


def season_str(y: int) -> str:
    return f"{y}-{str(y + 1)[-2:]}"


def get_html(start_year: int) -> str:
    path = HTML_DIR / f"NBA_{start_year + 1}_advanced.html"
    if path.exists():
        return path.read_text(encoding="utf-8")
    url = f"https://www.basketball-reference.com/leagues/NBA_{start_year + 1}_advanced.html"
    r = requests.get(url, headers=HEADERS, timeout=30)
    if r.status_code != 200:
        raise RuntimeError(f"{url} -> HTTP {r.status_code} (daca e 429/403: asteapta cateva minute "
                           f"sau salveaza pagina manual in {path})")
    path.write_text(r.text, encoding="utf-8")
    time.sleep(SLEEP)
    return r.text


def parse_players(html: str, season: str) -> pd.DataFrame:
    html = html.replace("<!--", "").replace("-->", "")
    for t in pd.read_html(StringIO(html)):
        t.columns = [c[-1] if isinstance(c, tuple) else c for c in t.columns]
        if {"Player", "MP", "BPM", "VORP"}.issubset(t.columns):
            t = t[t["Player"].astype(str) != "Player"].copy()      # randuri de antet repetate
            for c in ("MP", "BPM", "VORP"):
                t[c] = pd.to_numeric(t[c], errors="coerce")
            t = t.dropna(subset=["Player", "MP"])
            # jucatorii transferati apar de mai multe ori (TOT/2TM + cate un rand per echipa);
            # randul total are cel mai mare MP -> pastram un singur rand per jucator
            t = t.sort_values("MP", ascending=False).drop_duplicates("Player")
            t["Player"] = t["Player"].astype(str).str.replace("*", "", regex=False).str.strip()
            t.insert(0, "SEASON", season)
            return t[["SEASON", "Player", "MP", "BPM", "VORP"]].rename(columns={"Player": "PLAYER_NAME"})
    raise ValueError(f"Nu am gasit tabelul advanced pentru {season}")


def main():
    HTML_DIR.mkdir(parents=True, exist_ok=True)
    parts = []
    for y in range(FIRST_YEAR, LAST_YEAR + 1):
        season = season_str(y)
        try:
            parts.append(parse_players(get_html(y), season))
            print(f"{season}: ok ({len(parts[-1])} jucatori)")
        except Exception as e:
            print(f"{season}: SKIP - {e}")
    if not parts:
        raise SystemExit("Nu s-a extras nimic.")
    pd.concat(parts, ignore_index=True).to_csv(OUT, index=False)
    print(f"-> {OUT}")


if __name__ == "__main__":
    main()