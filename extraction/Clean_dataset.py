"""Genereaza data/processed/games_clean.csv din games.csv, fara a rula EDA.

Rulare din radacina repository-ului:
    python extraction/Clean_Dataset.py

Argumente optionale:
    python extraction/Clean_Dataset.py --data data/processed/games.csv
    python extraction/Clean_Dataset.py --clean-out data/processed/games_clean.csv

Scriptul reproduce exclusiv pasii din pipeline-ul EDA care influenteaza
continutul fisierului games_clean.csv:
  1. elimina sezoanele cu mai putin de MIN_SEASON_GAMES meciuri;
  2. marcheaza sezoanele scurtate ramase prin PARTIAL_SEASON;
  3. elimina din TRAIN doar meciurile din primele MIN_GAMES_PLAYED partide
     ale sezonului (validation/test raman complete);
  4. aplica preprocesarea calculata exclusiv pe TRAIN;
  5. selecteaza features pe TRAIN si scrie doar coloanele pastrate.

Nu genereaza grafice, rapoarte EDA, tabele, evaluari de modele sau alte
artefacte. Pentru a obtine acelasi fisier ca vechiul EDA, foloseste aceeasi
versiune de games.csv si aceleasi versiuni/configuratii de pandas si numpy.
"""
from __future__ import annotations

import argparse
from pathlib import Path
import pandas as pd


# ---------------------------------------------------------------------------
# Cai si configuratie: aceleasi valori ca in vechiul script EDA.
# ---------------------------------------------------------------------------
ROOT = Path(__file__).resolve().parent.parent
DATA_PATH = ROOT / "data" / "processed" / "games.csv"
CLEAN_PATH = ROOT / "data" / "processed" / "games_clean.csv"

MIN_GAMES_PLAYED = 5
REST_CAP = 5
WINSOR = None  # In EDA era dezactivata; pastrata explicit pentru claritate.
MIN_SEASON_GAMES = 100
NEAR_CONST = 0.995
CORR_THRESHOLD = 0.95
VIF_PROTECT = [
    "ELO",
    "SEASON_NET_RTG",
    "R10_NET_RTG",
    "R5_NET_RTG",
    "SEASON_WIN_PCT",
    "PREV_SRS",
]
EXCLUDE_BASES = ["GAMES_PLAYED"]
NON_FEATURE_BASES = ["SEASON_ID"]

ID_COLS = [
    "GAME_ID",
    "H_TEAM_ID",
    "A_TEAM_ID",
    "H_TEAM_ABBREVIATION",
    "A_TEAM_ABBREVIATION",
    "GAME_DATE",
    "SEASON",
    "SPLIT",
]
META_EXTRA = ["PARTIAL_SEASON"]
TARGETS = ["HOME_WIN", "MARGIN"]
SPLITS = ["train", "val", "test"]


# ---------------------------------------------------------------------------
# Incarcare si identificarea features-urilor
# ---------------------------------------------------------------------------
def load_data(path: Path) -> pd.DataFrame:
    if not path.exists():
        raise SystemExit(
            f"Nu exista fisierul de intrare: {path}\n"
            "Ruleaza mai intai extraction/Build_dataset.py pentru a genera games.csv."
        )

    df = pd.read_csv(path, parse_dates=["GAME_DATE"])
    required = ["GAME_ID", "GAME_DATE", "SEASON", "SPLIT", "HOME_WIN", "MARGIN"]
    missing = [column for column in required if column not in df.columns]
    if missing:
        raise SystemExit(f"Lipsesc coloane obligatorii din {path}: {missing}")

    return df.sort_values(["GAME_DATE", "GAME_ID"]).reset_index(drop=True)


def detect_bases(df: pd.DataFrame) -> list[str]:
    """Identifica bazele numerice existente in formele H_*, A_* si D_*.

    Pastreaza aceeasi regula ca EDA: SEASON_ID nu este tratat drept feature.
    """
    meta = set(ID_COLS + META_EXTRA + TARGETS)
    skipped = {f"{side}_{base}" for base in NON_FEATURE_BASES for side in "HAD"}
    numeric = [
        column
        for column in df.columns
        if column not in meta
        and column not in skipped
        and pd.api.types.is_numeric_dtype(df[column])
    ]

    numeric_set = set(numeric)
    bases: list[str] = []
    for column in numeric:
        if column.startswith("D_"):
            base = column[2:]
            if f"H_{base}" in numeric_set and f"A_{base}" in numeric_set:
                bases.append(base)
    return bases


def season_coverage(df: pd.DataFrame) -> pd.DataFrame:
    """Calculeaza acoperirea pe sezon exact ca eda_coverage() din EDA."""
    games = df.groupby("SEASON").agg(
        games=("GAME_ID", "size"),
    )
    teams = pd.concat(
        [
            df[["SEASON", "H_TEAM_ID"]].set_axis(["SEASON", "team"], axis=1),
            df[["SEASON", "A_TEAM_ID"]].set_axis(["SEASON", "team"], axis=1),
        ],
        ignore_index=True,
    ).groupby("SEASON")["team"].nunique()

    games["teams"] = teams
    games["expected_82"] = games["teams"] * 82 // 2
    games["coverage"] = games["games"] / games["expected_82"]
    games["partial"] = games["coverage"] < 0.93
    return games


# ---------------------------------------------------------------------------
# Preprocesare: fit numai pe TRAIN, apoi aplicata separat pe fiecare split.
# ---------------------------------------------------------------------------
def extended_bases(bases: list[str]) -> list[str]:
    return bases + (["NO_PREV"] if any(base.startswith("PREV_") for base in bases) else [])


def stage1(df: pd.DataFrame, bases: list[str]) -> pd.DataFrame:
    """Cap REST_DAYS, creeaza NO_PREV si completeaza PREV_* cu mediana sezonului."""
    out = df.copy()

    if REST_CAP is not None:
        for side in "HA":
            column = f"{side}_REST_DAYS"
            if column in out.columns:
                out[column] = out[column].clip(upper=REST_CAP)
        if "D_REST_DAYS" in out.columns and {"H_REST_DAYS", "A_REST_DAYS"} <= set(out.columns):
            out["D_REST_DAYS"] = out["H_REST_DAYS"] - out["A_REST_DAYS"]

    previous_bases = [base for base in bases if base.startswith("PREV_")]
    if not previous_bases:
        return out

    # Indicatorul este calculat inainte de imputarea ratingurilor anterioare.
    for side in "HA":
        out[f"{side}_NO_PREV"] = out[[f"{side}_{base}" for base in previous_bases]].isna().any(axis=1).astype(int)
    out["D_NO_PREV"] = out["H_NO_PREV"] - out["A_NO_PREV"]

    # Mediana este calculata separat pe sezon, pe valorile gazda + oaspete
    # din splitul curent, exact ca in stage1() din EDA.
    for base in previous_bases:
        pooled = pd.concat(
            [
                out[["SEASON", f"H_{base}"]].set_axis(["SEASON", "value"], axis=1),
                out[["SEASON", f"A_{base}"]].set_axis(["SEASON", "value"], axis=1),
            ],
            ignore_index=True,
        )
        season_median = out["SEASON"].map(pooled.groupby("SEASON")["value"].median())
        for side in "HA":
            column = f"{side}_{base}"
            out[column] = out[column].fillna(season_median)

    return out


def fit_preprocessor(train: pd.DataFrame, bases: list[str]) -> dict:
    """Invata medianele doar pe train; winsorizarea era dezactivata in EDA."""
    train_stage1 = stage1(train, bases)
    bases_ext = extended_bases(bases)
    medians: dict[str, float] = {}

    for base in bases_ext:
        pooled = pd.concat([train_stage1[f"H_{base}"], train_stage1[f"A_{base}"]])
        medians[base] = float(pooled.median())

    return {
        "bases": bases,
        "bases_ext": bases_ext,
        "median": medians,
        "winsor": WINSOR,
        "rest_cap": REST_CAP,
    }


def apply_preprocessor(df: pd.DataFrame, state: dict) -> pd.DataFrame:
    """Aplica transformarile si medianele invatate pe TRAIN."""
    out = stage1(df, state["bases"])

    for base in state["bases_ext"]:
        for side in "HA":
            column = f"{side}_{base}"
            out[column] = out[column].fillna(state["median"][base])
        # Diferentele se recalculeaza dupa imputare, nu se pastreaza valorile vechi.
        out[f"D_{base}"] = out[f"H_{base}"] - out[f"A_{base}"]

    return out


# ---------------------------------------------------------------------------
# Selectia features-urilor care intra in games_clean.csv.
# Setul salvat este setul FULL: selectie manuala + near-constant + corelatie.
# Filtrul VIF era folosit doar pentru diff_reduced si NU modifica games_clean.
# ---------------------------------------------------------------------------
def drop_near_constant(data: pd.DataFrame) -> dict[str, str]:
    dropped: dict[str, str] = {}
    for column in data.columns:
        frequencies = data[column].value_counts(normalize=True, dropna=False)
        if data[column].nunique(dropna=True) <= 1:
            dropped[column] = "constanta"
        elif frequencies.iloc[0] >= NEAR_CONST:
            dropped[column] = f"aproape constanta ({frequencies.iloc[0]:.3f} aceeasi valoare)"
    return dropped


def correlation_filter(
    data: pd.DataFrame,
    target: pd.Series,
    threshold: float,
    protect: list[str] | None = None,
) -> tuple[list[str], dict[str, str]]:
    """Filtru greedy |r|, pastrand inainte features-urile protejate de EDA."""
    correlations = data.corr().abs()
    order = data.corrwith(target).abs().sort_values(ascending=False).index.tolist()

    protected = [f"D_{base}" for base in (protect or []) if f"D_{base}" in order]
    protected = sorted(protected, key=order.index)
    order = protected + [column for column in order if column not in protected]

    kept: list[str] = []
    dropped: dict[str, str] = {}
    for column in order:
        hit = [existing for existing in kept if correlations.loc[column, existing] > threshold]
        if hit:
            dropped[column] = f"|r|={correlations.loc[column, hit[0]]:.3f} cu {hit[0]}"
        else:
            kept.append(column)

    # Ordinea rezultatului este ordinea originala a coloanelor, ca in EDA.
    return [column for column in data.columns if column in kept], dropped


def select_full_features(train_processed: pd.DataFrame, bases_ext: list[str]) -> list[str]:
    """Returneaza bazele pastrate in setul FULL folosit la export."""
    remaining_bases = [base for base in bases_ext if base not in EXCLUDE_BASES]
    if not remaining_bases:
        raise SystemExit("Nu au ramas features dupa excluderile manuale.")

    difference_columns = [f"D_{base}" for base in remaining_bases]
    missing = [column for column in difference_columns if column not in train_processed.columns]
    if missing:
        raise SystemExit(f"Lipsesc coloane necesare selectiei de features: {missing}")

    data = train_processed[difference_columns]
    target = train_processed["MARGIN"]

    near_constant = drop_near_constant(data)
    data = data.drop(columns=list(near_constant))
    if data.empty:
        raise SystemExit("Toate features-urile au fost eliminate ca fiind constante/aproape constante.")

    kept_columns, _ = correlation_filter(data, target, CORR_THRESHOLD, VIF_PROTECT)
    if not kept_columns:
        raise SystemExit("Filtrul de corelatie nu a pastrat niciun feature.")

    return [column[2:] for column in kept_columns]


# ---------------------------------------------------------------------------
# Pipeline principal
# ---------------------------------------------------------------------------
def build_clean_dataset(data_path: Path, clean_path: Path) -> pd.DataFrame:
    df = load_data(data_path)
    bases = detect_bases(df)
    if not bases:
        raise SystemExit("Nu au fost identificate features numerice in formele H_*, A_* si D_*.")

    print(f"Dataset initial: {len(df):,} randuri x {df.shape[1]} coloane")
    print(f"Features de baza identificate: {len(bases)}")

    # 1. Sezoane cu prea putine meciuri: regula MIN_SEASON_GAMES din EDA.
    coverage = season_coverage(df)
    season_sizes = df.groupby("SEASON").size()
    tiny_seasons = season_sizes[season_sizes < MIN_SEASON_GAMES]
    if len(tiny_seasons):
        removed_games = int(tiny_seasons.sum())
        print(
            f"Sezoane eliminate (< {MIN_SEASON_GAMES} meciuri): "
            f"{tiny_seasons.to_dict()} ({removed_games:,} meciuri)"
        )
        df = df[~df["SEASON"].isin(tiny_seasons.index)].reset_index(drop=True)
    else:
        print("Nu exista sezoane sub pragul MIN_SEASON_GAMES.")

    # 2. Flag pentru sezoanele scurtate care au ramas in dataset.
    partial_seasons = [
        season
        for season in coverage.index[coverage["partial"]]
        if season not in tiny_seasons.index
    ]
    df["PARTIAL_SEASON"] = df["SEASON"].isin(partial_seasons).astype(int)
    print(f"Sezoane partiale pastrate: {partial_seasons or 'niciunul'}")

    # 3. Elimina inceputul sezonului DOAR din TRAIN; val/test raman complete.
    before_early_filter = len(df)
    if MIN_GAMES_PLAYED > 0 and "GAMES_PLAYED" in bases:
        early = (df["H_GAMES_PLAYED"] < MIN_GAMES_PLAYED) | (df["A_GAMES_PLAYED"] < MIN_GAMES_PLAYED)
        keep = ~(early & (df["SPLIT"] == "train"))
        removed_by_split = (
            df.loc[~keep].groupby("SPLIT").size().reindex(SPLITS).fillna(0).astype(int).to_dict()
        )
        df = df[keep].reset_index(drop=True)
        print(
            f"Meciuri eliminate de filtrul de inceput de sezon (doar train, "
            f"GAMES_PLAYED >= {MIN_GAMES_PLAYED} pentru ambele echipe): "
            f"{before_early_filter - len(df):,}; pe split: {removed_by_split}"
        )
    else:
        print("Filtrul de inceput de sezon nu a fost aplicat (GAMES_PLAYED lipseste sau pragul este dezactivat).")

    # 4. Pregateste spliturile in ordinea folosita de EDA.
    frames_raw = {
        split: df[df["SPLIT"] == split].reset_index(drop=True)
        for split in SPLITS
        if (df["SPLIT"] == split).any()
    }
    if "train" not in frames_raw:
        raise SystemExit("Nu exista randuri cu SPLIT == 'train'.")

    # 5. Fit pe TRAIN si aplicare pe fiecare split, exact ca in EDA.
    state = fit_preprocessor(frames_raw["train"], bases)
    processed = {
        split: apply_preprocessor(frame, state)
        for split, frame in frames_raw.items()
    }

    # 6. Selectie FULL numai pe train procesat.
    bases_ext = state["bases_ext"]
    kept_bases = select_full_features(processed["train"], bases_ext)

    # 7. Reconstruieste tabelul final si ordinea randurilor/coloanelor din EDA.
    full = pd.concat([processed[split] for split in processed], ignore_index=True)
    full = full.sort_values(["GAME_DATE", "GAME_ID"]).reset_index(drop=True)

    meta_columns = [column for column in ID_COLS + META_EXTRA if column in full.columns]
    output_columns = meta_columns + TARGETS
    output_columns += [f"{side}_{base}" for base in kept_bases for side in "HAD"]

    missing_output = [column for column in output_columns if column not in full.columns]
    if missing_output:
        raise SystemExit(f"Lipsesc coloane necesare la export: {missing_output}")

    clean = full[output_columns].copy()
    feature_columns = [
        column
        for column in clean.columns
        if column[:2] in ("H_", "A_", "D_") and column not in ID_COLS
    ]
    missing_values = int(clean[feature_columns].isna().sum().sum())
    if missing_values:
        raise SystemExit(
            f"Au ramas {missing_values} valori lipsa in features. "
            "Exportul a fost oprit pentru a nu genera un games_clean.csv incomplet."
        )

    clean_path.parent.mkdir(parents=True, exist_ok=True)
    clean.to_csv(clean_path, index=False)

    print("\nDataset curat generat cu succes:")
    print(f"  Fisier: {clean_path}")
    print(f"  Dimensiune: {clean.shape[0]:,} randuri x {clean.shape[1]} coloane")
    print(f"  Sezoane: {clean['SEASON'].nunique()}")
    print(f"  Features pastrate: {len(kept_bases)}")
    print(f"  Sezoane partiale marcate: {int(clean['PARTIAL_SEASON'].sum()) and partial_seasons or 'niciunul'}")
    print("  Splituri:")
    print(clean["SPLIT"].value_counts().reindex(SPLITS).fillna(0).astype(int).to_string())

    return clean


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Genereaza games_clean.csv fara grafice sau analize EDA."
    )
    parser.add_argument("--data", type=Path, default=DATA_PATH, help="Calea catre games.csv")
    parser.add_argument("--clean-out", type=Path, default=CLEAN_PATH, help="Calea de iesire games_clean.csv")
    args = parser.parse_args()

    build_clean_dataset(args.data, args.clean_out)


if __name__ == "__main__":
    main()
