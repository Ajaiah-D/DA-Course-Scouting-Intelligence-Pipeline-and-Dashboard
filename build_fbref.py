"""
Merge the 4 FBref stat files, filter to 2022-23 and 2023-24 seasons,
apply 900-minute minimum, clean columns, and compute per-90 stats.

Run from the project root:
    python build_fbref.py

Output: data/cleaned/fbref_cleaned.csv
"""

from pathlib import Path
import numpy as np
import pandas as pd

CLEANED_DIR = Path("data/cleaned")
SEASONS     = ["2022-2023", "2023-2024"]
MIN_MINUTES = 900

# ── Load ──────────────────────────────────────────────────────────────────────

print("Loading FBref files...")
standard  = pd.read_excel(CLEANED_DIR / "standard_cleaned.xlsx")
shooting  = pd.read_excel(CLEANED_DIR / "shooting_cleaned.xlsx")
passing   = pd.read_excel(CLEANED_DIR / "passing_cleaned.xlsx")
defending = pd.read_excel(CLEANED_DIR / "defending_cleaned.xlsx")

for name, df in [("standard", standard), ("shooting", shooting),
                 ("passing", passing), ("defending", defending)]:
    print(f"  {name}: {df.shape}")

# ── Filter to target seasons ──────────────────────────────────────────────────

print(f"\nFiltering to seasons: {SEASONS}")
standard  = standard[standard["Season"].isin(SEASONS)].copy()
shooting  = shooting[shooting["Season"].isin(SEASONS)].copy()
passing   = passing[passing["Season"].isin(SEASONS)].copy()
defending = defending[defending["Season"].isin(SEASONS)].copy()
print(f"  Rows after season filter: {len(standard)}")

# ── Merge keys ────────────────────────────────────────────────────────────────

MERGE_ON = ["Player", "Squad", "League", "Season"]

# Columns to bring in from each table (exclude identity cols already in standard)
SHOOTING_COLS = MERGE_ON + [
    "shots_total", "shots_on_target", "shots_on_target_pct",
    "shots_total_per_90", "shots_on_target_per_90",
    "goals_per_shot", "goals_per_shot_on_target",
    "avg_shot_distance", "npxg_per_shot",
    "goals_minus_xg", "nonpen_goals_minus_npxg",
]

PASSING_COLS = MERGE_ON + [
    "passes_completed_total", "passes_attempted_total", "passes_completion_pct_total",
    "passes_completion_pct_short", "passes_completion_pct_medium", "passes_completion_pct_long",
    "progressive_passing_distance", "expected_assisted_goals", "expected_assists",
    "key_passes", "passes_into_final_third", "passes_into_penalty_area",
    "crosses_into_penalty_area", "progressive_passes",
]

DEFENDING_COLS = MERGE_ON + [
    "tackles_total", "tackles_won", "tackles_def_3rd", "tackles_mid_3rd", "tackles_att_3rd",
    "dribblers_tackled", "dribbles_challenged", "dribblers_tackled_pct",
    "challenges_lost", "blocks_total", "blocks_shots", "blocks_passes",
    "interceptions", "tackles_plus_interceptions", "clearances", "errors_leading_to_shot",
]

print("\nMerging stat tables...")
df = standard.merge(shooting[SHOOTING_COLS],   on=MERGE_ON, how="left", suffixes=("", "_sh"))
df = df.merge(passing[PASSING_COLS],           on=MERGE_ON, how="left", suffixes=("", "_pa"))
df = df.merge(defending[DEFENDING_COLS],       on=MERGE_ON, how="left", suffixes=("", "_df"))
print(f"  Merged shape: {df.shape}")

# ── Clean up columns ──────────────────────────────────────────────────────────

# Standardise column names
df.columns = (
    df.columns
    .str.strip()
    .str.lower()
    .str.replace(r"[^a-z0-9]+", "_", regex=True)
    .str.strip("_")
)

# Rename for clarity
df = df.rename(columns={
    "player":   "player_name",
    "squad":    "club",
    "league":   "league",
    "season":   "season",
    "nation":   "nation",
    "position": "position",
    "age":      "age",
    "born":     "born",
    "minutes":  "minutes",
})

# Parse nation — "nl NED" → "NED"
df["nation"] = df["nation"].str.extract(r"([A-Z]{2,3})$")

# Infer position group from FBref position codes
def position_group(pos):
    if pd.isna(pos):
        return "Midfielder"
    pos = str(pos).upper()
    if any(x in pos for x in ["FW", "LW", "RW", "CF", "ST"]):
        return "Forward"
    if any(x in pos for x in ["DF", "CB", "LB", "RB", "WB"]):
        return "Defender"
    return "Midfielder"

df["position_group"] = df["position"].apply(position_group)
df["is_versatile"]   = df["position"].str.contains(",", na=False)

# ── Remove GKs and apply minutes filter ──────────────────────────────────────

before = len(df)
df = df[~df["position"].str.upper().str.contains("GK", na=False)]
print(f"\nRemoved {before - len(df)} GK rows")

before = len(df)
df["minutes"] = pd.to_numeric(df["minutes"], errors="coerce")
df = df[df["minutes"] >= MIN_MINUTES].copy()
print(f"After {MIN_MINUTES}+ min filter: {len(df)} player-seasons (removed {before - len(df)})")

# ── Per-90 conversions ────────────────────────────────────────────────────────

print("\nComputing per-90 stats...")
minutes = df["minutes"].replace(0, np.nan)

COUNTING_STATS = [
    "goals", "assists", "xg", "npxg", "xag",
    "progressive_carries", "progressive_passes", "progressive_passes_received",
    "shots_total", "shots_on_target",
    "passes_completed_total", "passes_into_final_third",
    "passes_into_penalty_area", "key_passes",
    "tackles_total", "tackles_won", "interceptions",
    "tackles_plus_interceptions", "clearances",
    "blocks_total",
]

for stat in COUNTING_STATS:
    if stat in df.columns:
        df[stat] = pd.to_numeric(df[stat], errors="coerce")
        df[f"{stat}_p90"] = (df[stat] / minutes * 90).round(3)

# Constructed metrics
if all(c in df.columns for c in ["tackles_won", "tackles_total", "interceptions"]):
    denom = df["tackles_total"] + df["interceptions"]
    numer = df["tackles_won"]   + df["interceptions"]
    df["ground_duel_win_pct"] = (numer / denom.replace(0, np.nan) * 100).round(1)

# ── Final check ───────────────────────────────────────────────────────────────

print(f"\nFinal shape: {df.shape}")
print("Season distribution:")
print(df["season"].value_counts().to_string())
print("\nLeague distribution:")
print(df["league"].value_counts().to_string())
print("\nPosition group distribution:")
print(df["position_group"].value_counts().to_string())
print("\nNull check (cols with >10 nulls):")
null_counts = df.isnull().sum()
print(null_counts[null_counts > 10].to_string())

# ── Save ──────────────────────────────────────────────────────────────────────

out = CLEANED_DIR / "fbref_cleaned.csv"
df.to_csv(out, index=False)
print(f"\nSaved to {out}")
