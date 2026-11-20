"""Descarca raportul OFICIAL NBA de accidentari (PDF-uri), cu pachetul `nbainjuries`.

Rulare (din radacina proiectului, dupa fetch_games.py):
    pip install nbainjuries pandas
    # pachetul citeste PDF-urile cu tabula -> are nevoie de Java (JRE) instalat
    python extraction/fetch_injuries.py
Output: data/raw/injuries/injury_<YYYY-MM-DD>.csv  (o zi = un fisier; fisier gol = raport fara jucatori)
Se cer doar zilele in care au existat meciuri (luate din game_log_*.csv). Zilele deja descarcate sunt sarite,
iar zilele fara raport disponibil NU primesc fisier (la urmatoarea rulare se reincearca).
Raportul e cel de ~17:30 ET (inainte de meciurile serii) -> informatie cunoscuta PRE-meci.
"""
import time
from datetime import datetime
from pathlib import Path

import pandas as pd
from nbainjuries import injury

FIRST_SEASON = 2019                      # raportul oficial in forma PDF disponibil de la 2021-22 (verifica)
RAW_DIR = Path("../data/raw")
INJ_DIR = RAW_DIR / "injuries"
REPORT_TIMES = ((17, 30), (17, 0), (16, 0))   # ore incercate, in ordine
SLEEP = 1.0


def game_dates() -> list[str]:
    dates = set()
    for f in sorted(RAW_DIR.glob("game_log_*.csv")):
        if int(f.stem.split("_")[-1][:4]) < FIRST_SEASON:
            continue
        col = pd.read_csv(f, usecols=["GAME_DATE"])["GAME_DATE"].astype(str).str[:10]
        dates.update(col)
    return sorted(dates)


def fetch_day(ds: str):
    y, m, d = map(int, ds.split("-"))
    for hh, mm in REPORT_TIMES:
        try:
            df = injury.get_reportdata(datetime(y, m, d, hh, mm), return_df=True)
            if df is not None:
                return df
        except Exception:
            continue
    return None


def main():
    INJ_DIR.mkdir(parents=True, exist_ok=True)
    dates = game_dates()
    if not dates:
        raise SystemExit("Nu exista game_log_*.csv pentru sezoane >= %d. Ruleaza intai fetch_games.py" % FIRST_SEASON)
    ok = skipped = failed = 0
    for i, ds in enumerate(dates, 1):
        out = INJ_DIR / f"injury_{ds}.csv"
        if out.exists():
            skipped += 1
            continue
        df = fetch_day(ds)
        if df is None:
            failed += 1
            print(f"{ds}: raport indisponibil")
            continue
        df.to_csv(out, index=False)
        ok += 1
        if ok % 25 == 0:
            print(f"[{i}/{len(dates)}] {ds}: {len(df)} randuri (ok={ok}, esuate={failed})")
        time.sleep(SLEEP)
    print(f"Gata: descarcate={ok}, sarite={skipped}, indisponibile={failed}")


if __name__ == "__main__":
    main()