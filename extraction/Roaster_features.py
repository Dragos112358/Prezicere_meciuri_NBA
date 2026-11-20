"""Features de lot (roster) si accidentari, calculate din sursele suplimentare.

Surse (toate optionale; ce lipseste se sare, restul pipeline-ului merge):
    data/raw/player_log_*.csv           <- fetch_players.py        (box score pe jucator, nba_api)
    data/raw/bref_player_advanced.csv   <- scrape_bref_players.py  (BPM din sezonul anterior)
    data/raw/injuries/injury_*.csv      <- fetch_injuries.py       (raport oficial NBA, din 2021-22)

Apel din build_dataset.py:   df = add_roster_features(df)     (df = un rand per echipa per meci)

Coloane adaugate pe (GAME_ID, TEAM_ID):
  ROS_*  -- derivate din box score. ATENTIE: "cine a lipsit" se stie abia DUPA meci -> proxy, nu informatie pre-meci.
    ROS_MISS_MIN   minute/meci (media ultimelor 10 aparitii) ale jucatorilor din rotatie care NU au jucat
    ROS_MISS_VAL   la fel, ponderat cu BPM din sezonul anterior: min/48 * max(BPM - (-2), 0)
    ROS_STAR_OUT   nr. de absenti cu >= 28 min/meci
    ROS_NEW_ROT    nr. de jucatori cu >= 15 min in acest meci care nu au aparut inca (>=2 ori) pentru echipa in sezon
                   (achizitii/trade-uri); 0 in primele 10 meciuri
    ROS_CONT       ponderea minutelor jucate de jucatori care erau la aceeasi echipa si in sezonul anterior
  INJ_*  -- din raportul oficial de accidentari (PRE-meci); NaN unde nu exista raport
    INJ_OUT_N / INJ_Q_N        nr. jucatori listati Out / Questionable+Doubtful
    INJ_OUT_MIN / INJ_Q_MIN    minute/meci ale celor din rotatie listati Out / Questionable+Doubtful
"""
import re
import unicodedata
from bisect import bisect_right
from collections import deque
from pathlib import Path

import numpy as np
import pandas as pd

RAW_DIR = Path("data/raw")
INJ_DIR = RAW_DIR / "injuries"
BPM_PATH = RAW_DIR / "bref_player_advanced.csv"

WINDOW = 10        # media minutelor pe ultimele 10 aparitii ale jucatorului la echipa
MIN_GAMES = 3      # cate meciuri ale echipei trebuie sa existe inainte sa calculam features
MIN_APPS = 2       # minim aparitii ca sa fie luat in calcul
ROT_MIN = 15.0     # prag de rotatie (minute/meci)
STAR_MIN = 28.0
REPL_BPM = -2.0    # BPM de nivel "inlocuitor"

OUT_STATUS = {"out"}
Q_STATUS = {"questionable", "doubtful"}


def norm_name(name) -> str:
    s = unicodedata.normalize("NFKD", str(name)).encode("ascii", "ignore").decode().lower()
    s = re.sub(r"[.'\-]", " ", s)
    s = re.sub(r"[^a-z ]", "", s)
    s = re.sub(r"\b(jr|sr|ii|iii|iv)\b", "", s)
    return re.sub(r"\s+", " ", s).strip()


def team_key(name) -> str:
    k = re.sub(r"[^a-z]", "", str(name).lower())
    return {"losangelesclippers": "laclippers"}.get(k, k)


def prior_season(season: str) -> str:
    y = int(season[:4]) - 1
    return f"{y}-{str(y + 1)[-2:]}"


def load_player_logs():
    files = sorted(RAW_DIR.glob("player_log_*.csv"))
    if not files:
        return None
    p = pd.concat((pd.read_csv(f) for f in files), ignore_index=True)
    p["GAME_DATE"] = pd.to_datetime(p["GAME_DATE"])
    p["MIN"] = pd.to_numeric(p["MIN"], errors="coerce").fillna(0)
    p = p[p["MIN"] > 0].copy()
    p["NAME_KEY"] = p["PLAYER_NAME"].map(norm_name)
    return p.sort_values(["GAME_DATE", "GAME_ID"]).reset_index(drop=True)


def load_bpm() -> dict:
    if not BPM_PATH.exists():
        print("bref_player_advanced.csv lipseste -> ROS_MISS_VAL foloseste BPM=0 (ruleaza scrape_bref_players.py)")
        return {}
    b = pd.read_csv(BPM_PATH)
    b["KEY"] = b["PLAYER_NAME"].map(norm_name)
    return {(s, k): v for s, k, v in zip(b["SEASON"], b["KEY"], b["BPM"]) if pd.notna(v)}


def load_injuries():
    """-> ({(YYYY-MM-DD, team_key): [(nume_normalizat, status), ...]}, {zile cu raport})"""
    files = sorted(INJ_DIR.glob("injury_*.csv")) if INJ_DIR.exists() else []
    inj, covered = {}, set()
    for f in files:
        ds = f.stem.replace("injury_", "")
        covered.add(ds)
        try:
            d = pd.read_csv(f)
        except pd.errors.EmptyDataError:
            continue
        if d.empty:
            continue
        d.columns = [c.strip().lower().replace(" ", "_") for c in d.columns]
        if not {"team", "player_name", "current_status"}.issubset(d.columns):
            print(f"{f.name}: coloane neasteptate {list(d.columns)} -> sar peste")
            continue
        for team, pl, st in zip(d["team"], d["player_name"], d["current_status"]):
            pl = str(pl)
            if "," in pl:                                # "Last, First" -> "First Last"
                last, first = pl.split(",", 1)
                pl = f"{first.strip()} {last.strip()}"
            inj.setdefault((ds, team_key(team)), []).append((norm_name(pl), str(st).strip().lower()))
    return inj, covered


def _moved(app, season, pid, date, tid) -> bool:
    """True daca la data respectiva ultima aparitie a jucatorului in sezon a fost la ALTA echipa (trade/waive)."""
    seq = app.get((season, pid))
    if not seq:
        return False
    dates, tids = seq
    i = bisect_right(dates, date) - 1
    return i >= 0 and tids[i] != tid


def add_roster_features(df: pd.DataFrame) -> pd.DataFrame:
    plog = load_player_logs()
    if plog is None:
        print("player_log_*.csv lipsesc -> sar peste features de lot (ruleaza fetch_players.py)")
        return df
    bpm = load_bpm()
    inj, covered = load_injuries()
    print(f"Accidentari: {len(covered)} zile cu raport")

    tkeys = {(t, s): team_key(n)
             for t, s, n in df[["TEAM_ID", "SEASON", "TEAM_NAME"]].drop_duplicates().itertuples(index=False)}
    roster = plog.groupby(["TEAM_ID", "SEASON"])["PLAYER_ID"].agg(set).to_dict()
    app = {}
    for (s, pid), g in plog.groupby(["SEASON", "PLAYER_ID"]):           # plog e deja sortat cronologic
        app[(s, pid)] = (g["GAME_DATE"].tolist(), g["TEAM_ID"].tolist())

    rows = []
    bpm_hit = bpm_tot = 0
    for (tid, season), t in plog.groupby(["TEAM_ID", "SEASON"], sort=False):
        mins, dates, names, order = {}, {}, {}, []
        for gid, pid, m, nk, d in zip(t["GAME_ID"], t["PLAYER_ID"], t["MIN"], t["NAME_KEY"], t["GAME_DATE"]):
            if gid not in mins:
                mins[gid], dates[gid] = {}, d
                order.append(gid)
            mins[gid][pid] = m
            names[pid] = nk
        pseason = prior_season(season)
        prev_set = roster.get((tid, pseason), set())
        tk = tkeys.get((tid, season))
        hist, n_apps = {}, {}

        for k, gid in enumerate(order):
            cur, d = mins[gid], dates[gid]
            tot = sum(cur.values())
            r = {"GAME_ID": gid, "TEAM_ID": tid}
            r["ROS_CONT"] = (sum(m for p, m in cur.items() if p in prev_set) / tot) if prev_set and tot > 0 else np.nan

            if k >= MIN_GAMES:
                rot = {}
                for p, h in hist.items():
                    if len(h) >= MIN_APPS:
                        a = sum(h) / len(h)
                        if a >= ROT_MIN:
                            rot[p] = a
                absent = [p for p in rot if p not in cur and not _moved(app, season, p, d, tid)]
                val = 0.0
                for p in absent:
                    b = bpm.get((pseason, names[p]))
                    bpm_tot += 1
                    bpm_hit += b is not None
                    val += rot[p] / 48 * max((b if b is not None else 0.0) - REPL_BPM, 0.0)
                r["ROS_MISS_MIN"] = sum(rot[p] for p in absent)
                r["ROS_MISS_VAL"] = val
                r["ROS_STAR_OUT"] = sum(rot[p] >= STAR_MIN for p in absent)
                r["ROS_NEW_ROT"] = (sum(1 for p, m in cur.items() if m >= ROT_MIN and n_apps.get(p, 0) < MIN_APPS)
                                    if k >= WINDOW else 0)

                ds = d.strftime("%Y-%m-%d")
                if ds in covered and tk is not None:
                    lst = set(inj.get((ds, tk), []))
                    by_name = {names[p]: a for p, a in rot.items()}
                    r["INJ_OUT_N"] = sum(1 for _, st in lst if st in OUT_STATUS)
                    r["INJ_Q_N"] = sum(1 for _, st in lst if st in Q_STATUS)
                    r["INJ_OUT_MIN"] = sum(by_name.get(n, 0.0) for n, st in lst if st in OUT_STATUS)
                    r["INJ_Q_MIN"] = sum(by_name.get(n, 0.0) for n, st in lst if st in Q_STATUS)

            for p, m in cur.items():
                hist.setdefault(p, deque(maxlen=WINDOW)).append(m)
                n_apps[p] = n_apps.get(p, 0) + 1
            rows.append(r)

    feats = pd.DataFrame(rows)
    out = df.merge(feats, on=["GAME_ID", "TEAM_ID"], how="left", validate="one_to_one")
    print(f"Features de lot: {out['ROS_CONT'].notna().sum()} / {len(out)} randuri echipa-meci acoperite")
    if bpm_tot:
        print(f"BPM gasit pentru {bpm_hit / bpm_tot:.0%} dintre jucatorii absenti (restul: nume nepotrivite sau rookie)")
    if "INJ_OUT_N" in out:
        print(f"Raport de accidentari potrivit pe {out['INJ_OUT_N'].notna().sum()} randuri "
              f"(daca e 0 desi ai fisiere, verifica numele echipelor din raport vs TEAM_NAME)")
    return out