"""Construieste datasetul final: un rand per meci, features doar din meciurile ANTERIOARE.

Rulare (din oriunde; caile sunt relative la radacina proiectului):
    python extraction/Build_dataset.py
Input:  data/raw/game_log_*.csv
Output: data/processed/games.csv
"""
import re
from pathlib import Path

import numpy as np
import pandas as pd

# În loc de VAL_START, TEST_START fixe:
N_TEST_SEASONS = 1   # Câte sezoane la sfârșit merg în test (ex: ultimul sezon)
N_VAL_SEASONS = 1    # Câte sezoane merg în validare (ex: sezonul de dinainte de test)

ROOT = Path(__file__).resolve().parent.parent
RAW_DIR = ROOT / "data" / "raw"
OUT_PATH = ROOT / "data" / "processed" / "games.csv"
WINDOWS = (5, 10)
MIN_PERIODS = 3
BREF_PATH = RAW_DIR / "bref_team_ratings.csv"   # creat de scrape_bref.py (optional)
BREF_COLS = ["SRS", "ORtg", "DRtg", "Pace"]

# statistici per meci pe care facem medii mobile
STATS = ["PTS", "PTS_OPP", "FG_PCT", "FG3_PCT", "FT_PCT", "REB", "AST", "TOV",
         "EFG", "TOV_RATE", "FT_RATE", "OFF_RTG", "DEF_RTG", "NET_RTG", "POSS"]

# medii exponentiale (halflife in meciuri) pe un subset de statistici
EW_HALFLIFES = (5, 15)
EW_STATS = ["NET_RTG", "OFF_RTG", "DEF_RTG", "EFG", "TOV_RATE", "PTS"]

# medii pe tot sezonul pana la meci; shrinkage spre 0 (media ligii) cand sunt putine meciuri
SEASON_STATS = ["NET_RTG"]   # doar NET_RTG: e centrat pe 0, deci shrinkage spre 0 = spre media ligii
SEASON_SHRINK = 5

# Elo cu marja de victorie (varianta 538): K, avantaj gazda, revenire spre medie la inceput de sezon
ELO_INIT, ELO_K, ELO_HFA, ELO_REVERT = 1500.0, 20.0, 100.0, 0.25

# prefixele coloanelor care devin features in fisierul final (H_, A_, D_)
# (SEASON_* se listeaza explicit: prefixul "SEASON_" ar prinde si coloana SEASON_ID din game log)
# ROS_* provin din box-score-ul meciului curent (post-game).
# INJ_* sunt rapoarte zilnice (~16:00-17:30 ET); fara ora de start a fiecarui meci
# nu putem garanta ca raportul a fost publicat inainte de tip-off. Le excludem conservator.
FEATURE_PREFIXES = ("R5_", "R10_", "EW", "ELO", "SCHED_", "PREV_")
FEATURE_EXTRA = ["SEASON_WIN_PCT", "SEASON_NET_RTG", "GAMES_PLAYED", "REST_DAYS", "B2B"]

# cheie de franciza -> numele sub care apare (lowercase, fara punctuatie)
FRANCHISE_ALIASES = {
    "WIZARDS":   ["baltimore bullets", "capital bullets", "washington bullets", "washington wizards"],
    "GRIZZLIES": ["vancouver grizzlies", "memphis grizzlies"],
    "PELICANS":  ["new orleans hornets", "new orleans/oklahoma city hornets",
                  "new orleans oklahoma city hornets", "new orleans pelicans"],
    "THUNDER":   ["seattle supersonics", "oklahoma city thunder"],
    "NETS":      ["new jersey nets", "brooklyn nets"],
    "KINGS":     ["kansas city kings", "sacramento kings"],
    "CLIPPERS":  ["san diego clippers", "los angeles clippers", "la clippers"],
    "BOBCATS":   ["charlotte bobcats"],
}
_ALIAS_LOOKUP = {a: k for k, names in FRANCHISE_ALIASES.items() for a in names}


def load_raw() -> pd.DataFrame:
    files = sorted(RAW_DIR.glob("game_log_*.csv"))
    if not files:
        raise SystemExit("Nu exista fisiere in data/raw/. Ruleaza intai fetch_games.py")
    df = pd.concat((pd.read_csv(f) for f in files), ignore_index=True)
    df["GAME_DATE"] = pd.to_datetime(df["GAME_DATE"])
    # 3P% / FT% pot lipsi cand nu exista incercari (sezoane vechi)
    df[["FG3_PCT", "FT_PCT"]] = df[["FG3_PCT", "FT_PCT"]].fillna(0)
    need = ["FGM", "FGA", "FG3M", "FTA", "OREB", "TOV", "REB", "AST", "PTS", "FG_PCT"]
    n0 = len(df)
    df = df.dropna(subset=need)
    print(f"Randuri cu statistici lipsa eliminate: {n0 - len(df)}")
    return df


def clean_games(df: pd.DataFrame) -> pd.DataFrame:
    """Pastreaza doar meciurile cu exact 2 randuri: 1 acasa ("vs.") + 1 deplasare ("@")."""
    df = df.drop_duplicates(subset=["GAME_ID", "TEAM_ID"])
    is_home = df["MATCHUP"].str.contains("vs.", regex=False)
    chk = df.assign(h=is_home).groupby("GAME_ID").agg(n=("TEAM_ID", "size"), h=("h", "sum"))
    bad = chk[(chk["n"] != 2) | (chk["h"] != 1)].index
    print(f"Meciuri eliminate (home/away invalid): {len(bad)}")
    if len(bad):
        print(df[df["GAME_ID"].isin(bad)][["GAME_ID", "GAME_DATE", "MATCHUP"]]
              .sort_values("GAME_ID").head(10).to_string())
    return df[~df["GAME_ID"].isin(bad)].copy()


def add_game_stats(df: pd.DataFrame) -> pd.DataFrame:
    df["HOME"] = df["MATCHUP"].str.contains("vs.", regex=False).astype(int)
    df["WIN"] = (df["WL"] == "W").astype(int)
    df["POSS"] = df["FGA"] + 0.44 * df["FTA"] - df["OREB"] + df["TOV"]
    df["EFG"] = (df["FGM"] + 0.5 * df["FG3M"]) / df["FGA"]
    df["TOV_RATE"] = df["TOV"] / df["POSS"]
    df["FT_RATE"] = df["FTA"] / df["FGA"]
    # puncte primite = suma punctelor din meci - punctele proprii
    df["PTS_OPP"] = df.groupby("GAME_ID")["PTS"].transform("sum") - df["PTS"]
    df["OFF_RTG"] = 100 * df["PTS"] / df["POSS"]
    df["DEF_RTG"] = 100 * df["PTS_OPP"] / df["POSS"]
    df["NET_RTG"] = df["OFF_RTG"] - df["DEF_RTG"]
    return df


def _norm(name, season) -> str:
    """Cheie de franciza. `season` = 'YYYY-YY' al randului al carui nume e (nu sezonul anterior)."""
    s = re.sub(r"[^a-z0-9/ ]", "", str(name).lower().replace("*", "")).strip()
    if s == "charlotte hornets":   # ambiguu: franciza veche (<2004) vs fosta Bobcats (>=2014)
        return "PELICANS" if int(str(season)[:4]) < 2004 else "BOBCATS"
    return _ALIAS_LOOKUP.get(s, s)


def add_prev_season_ratings(df: pd.DataFrame) -> pd.DataFrame:
    """Ratinguri FINALE din sezonul anterior (Basketball-Reference) -> fara leakage."""
    if not BREF_PATH.exists():
        print("bref_team_ratings.csv lipseste -> sar peste (ruleaza scrape_bref.py)")
        return df
    b = pd.read_csv(BREF_PATH)
    # cheia se calculeaza INAINTE de rename, cu sezonul randului din Basketball-Reference
    b["KEY"] = [_norm(n, s) for n, s in zip(b["TEAM_NAME"], b["SEASON"])]
    b = b.rename(columns={"SEASON": "PRIOR_SEASON", **{c: f"PREV_{c.upper()}" for c in BREF_COLS}})
    prev_cols = [f"PREV_{c.upper()}" for c in BREF_COLS]

    start = df["SEASON"].str[:4].astype(int)
    df["PRIOR_SEASON"] = (start - 1).astype(str) + "-" + (start % 100).astype(str).str.zfill(2)
    # cheia jocului foloseste sezonul CURENT al randului (numele din game log e cel din acest sezon)
    df["KEY"] = [_norm(n, s) for n, s in zip(df["TEAM_NAME"], df["SEASON"])]
    df = df.merge(b[["PRIOR_SEASON", "KEY"] + prev_cols], on=["PRIOR_SEASON", "KEY"],
                  how="left", validate="many_to_one")
    miss = df[df["PREV_SRS"].isna()]
    print(f"Randuri fara rating din sezonul anterior: {len(miss)}")
    if len(miss):
        print(miss.groupby(["SEASON", "TEAM_NAME"]).size().head(15).to_string())
    return df


def add_elo(df: pd.DataFrame) -> pd.DataFrame:
    """Elo cu marja de victorie si avantajul gazdei, parcurs cronologic.

    ELO = ratingul echipei INAINTE de meci (fara leakage). Intre sezoane ratingul
    revine partial spre 1500 (ELO_REVERT). Ajustarea pentru adversar vine natural:
    o victorie contra unei echipe puternice aduce mai multe puncte Elo.
    """
    g = df.sort_values(["GAME_DATE", "GAME_ID"])
    home = g[g["HOME"] == 1][["GAME_ID", "GAME_DATE", "SEASON", "TEAM_ID", "PTS"]]
    away = g[g["HOME"] == 0][["GAME_ID", "TEAM_ID", "PTS"]]
    games = (home.merge(away, on="GAME_ID", suffixes=("_H", "_A"), validate="one_to_one")
                 .sort_values(["GAME_DATE", "GAME_ID"]))

    rating, last_season = {}, {}

    def current(team, season):
        r = rating.get(team, ELO_INIT)
        if team in last_season and last_season[team] != season:
            r = ELO_INIT + (1 - ELO_REVERT) * (r - ELO_INIT)
        last_season[team] = season
        rating[team] = r
        return r

    out = []
    for gid, season, th, ta, ph, pa in zip(games["GAME_ID"], games["SEASON"], games["TEAM_ID_H"],
                                           games["TEAM_ID_A"], games["PTS_H"], games["PTS_A"]):
        rh, ra = current(th, season), current(ta, season)
        out.append((gid, th, rh))
        out.append((gid, ta, ra))
        diff = rh + ELO_HFA - ra
        exp_h = 1.0 / (1.0 + 10 ** (-diff / 400))
        mov = ph - pa
        home_won = mov > 0
        win_diff = diff if home_won else -diff
        mult = (abs(mov) + 3) ** 0.8 / (7.5 + 0.006 * win_diff)
        delta = ELO_K * mult * ((1.0 if home_won else 0.0) - exp_h)
        rating[th] = rh + delta
        rating[ta] = ra - delta

    elo = pd.DataFrame(out, columns=["GAME_ID", "TEAM_ID", "ELO"])
    return df.merge(elo, on=["GAME_ID", "TEAM_ID"], how="left", validate="one_to_one")


def _prior_in_window(dates: pd.Series, days: int) -> pd.Series:
    """Cate meciuri anterioare ale echipei sunt in ultimele `days` zile (data curenta exclusa).
    `dates` = datele unei singure echipe, sortate crescator."""
    d = dates.values.astype("datetime64[D]").astype("int64")
    left = np.searchsorted(d, d - days, side="left")
    return pd.Series(np.arange(len(d)) - left, index=dates.index)


def add_prior_features(df: pd.DataFrame) -> pd.DataFrame:
    df = df.sort_values(["TEAM_ID", "GAME_DATE", "GAME_ID"]).reset_index(drop=True)
    g = df.groupby("TEAM_ID")

    # medii mobile + exponentiale; shift(1) = meciul curent NU intra in propriul feature
    roll = {}
    for w in WINDOWS:
        for s in STATS:
            roll[f"R{w}_{s}"] = g[s].transform(
                lambda x: x.shift(1).rolling(w, min_periods=MIN_PERIODS).mean()
            )
    for h in EW_HALFLIFES:
        for s in EW_STATS:
            roll[f"EW{h}_{s}"] = g[s].transform(
                lambda x: x.shift(1).ewm(halflife=h, min_periods=MIN_PERIODS).mean()
            )
    df = pd.concat([df, pd.DataFrame(roll)], axis=1)

    # procent victorii + ratinguri pe sezon, doar din meciurile de dinainte
    gs = df.groupby(["TEAM_ID", "SEASON"])
    prior_games = gs.cumcount()
    prior_wins = gs["WIN"].cumsum() - df["WIN"]
    df["SEASON_WIN_PCT"] = (prior_wins / prior_games.where(prior_games > 0)).fillna(0.5)
    for s in SEASON_STATS:
        prior_sum = gs[s].cumsum() - df[s]
        df[f"SEASON_{s}"] = prior_sum / (prior_games + SEASON_SHRINK)
    df["GAMES_PLAYED"] = prior_games

    # zile de odihna / back-to-back
    g = df.groupby("TEAM_ID")
    rest = g["GAME_DATE"].diff().dt.days
    df["REST_DAYS"] = rest.fillna(7).clip(upper=7)
    df["B2B"] = (df["REST_DAYS"] == 1).astype(int)

    # program si oboseala (doar din meciuri anterioare)
    df["SCHED_GAMES_PREV3D"] = g["GAME_DATE"].transform(lambda x: _prior_in_window(x, 3))
    df["SCHED_GAMES_PREV7D"] = g["GAME_DATE"].transform(lambda x: _prior_in_window(x, 7))
    df["SCHED_3IN4"] = (df["SCHED_GAMES_PREV3D"] >= 2).astype(int)   # meci 3 in 4 seri
    # deplasari consecutive: cate meciuri la rand in deplasare au precedat meciul curent (0 daca joaca acasa)
    new_run = ((df["TEAM_ID"] != df["TEAM_ID"].shift()) | (df["SEASON"] != df["SEASON"].shift())
               | (df["HOME"] != df["HOME"].shift()))
    run_pos = df.groupby(new_run.cumsum()).cumcount()
    df["SCHED_ROAD_GAMES"] = run_pos.where(df["HOME"] == 0, 0)
    return df


def to_match_rows(df: pd.DataFrame) -> pd.DataFrame:
    feat_cols = [c for c in df.columns if c.startswith(FEATURE_PREFIXES)] + FEATURE_EXTRA
    keep = ["GAME_ID", "TEAM_ID", "TEAM_ABBREVIATION", "PTS"] + feat_cols

    home = df[df["HOME"] == 1][keep + ["GAME_DATE", "SEASON"]]
    away = df[df["HOME"] == 0][keep]
    home = home.rename(columns={c: f"H_{c}" for c in keep if c != "GAME_ID"})
    away = away.rename(columns={c: f"A_{c}" for c in keep if c != "GAME_ID"})
    m = home.merge(away, on="GAME_ID", validate="one_to_one")

    # Tintele
    m["HOME_WIN"] = (m["H_PTS"] > m["A_PTS"]).astype(int)
    m["MARGIN"] = m["H_PTS"] - m["A_PTS"]

    # Diferente home - away
    diffs = pd.DataFrame({f"D_{c}": m[f"H_{c}"] - m[f"A_{c}"] for c in feat_cols})
    m = pd.concat([m, diffs], axis=1).copy()

    # --- IMPĂRȚIRE DINAMICĂ CRONOLOGICĂ ---
    # Sortăm toate sezoanele unice în ordine cronologică
    all_seasons = sorted(m["SEASON"].unique())

    if len(all_seasons) < (N_TEST_SEASONS + N_VAL_SEASONS + 1):
        raise SystemExit("Prea puține sezoane în dataset pentru a asigura train/val/test!")

    test_seasons = set(all_seasons[-N_TEST_SEASONS:])
    val_seasons = set(all_seasons[-(N_TEST_SEASONS + N_VAL_SEASONS): -N_TEST_SEASONS])

    m["SPLIT"] = "train"
    m.loc[m["SEASON"].isin(val_seasons), "SPLIT"] = "val"
    m.loc[m["SEASON"].isin(test_seasons), "SPLIT"] = "test"

    # Scoatem meciurile de început (feature-uri incomplete)
    m = m.dropna(subset=["H_R5_NET_RTG", "A_R5_NET_RTG", "H_R10_NET_RTG", "A_R10_NET_RTG"])
    # PTS-urile finale sunt rezultatul meciului, nu feature
    m = m.drop(columns=["H_PTS", "A_PTS"])

    print(f"Sezoane alocate -> Train: {all_seasons[:-(N_TEST_SEASONS + N_VAL_SEASONS)]}")
    print(f"Sezoane alocate -> Val: {list(val_seasons)}")
    print(f"Sezoane alocate -> Test: {list(test_seasons)}")

    return m.sort_values("GAME_DATE").reset_index(drop=True)


def main():
    df = load_raw()
    df = clean_games(df)
    df = add_game_stats(df)
    df = add_prev_season_ratings(df)
    df = add_elo(df)
    df = add_prior_features(df)
    m = to_match_rows(df)
    OUT_PATH.parent.mkdir(parents=True, exist_ok=True)
    m.to_csv(OUT_PATH, index=False)
    print(f"{len(m)} meciuri, {m.shape[1]} coloane -> {OUT_PATH}")
    print(m["SPLIT"].value_counts().to_string())
    print(f"Home win rate: {m['HOME_WIN'].mean():.3f}")


if __name__ == "__main__":
    main()
