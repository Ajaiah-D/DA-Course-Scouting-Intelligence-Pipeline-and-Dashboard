"""
Composite scoring model — assigns each player a value-per-euro score.

Methodology:
  1. Normalize each metric 0-100 within position group (Forwards vs Forwards, etc.)
  2. Apply position-specific weights (documented below)
  3. Sum to composite score
  4. Apply league strength multiplier
  5. Divide by market value in millions → value score (higher = more undervalued)

Run from the project root:
    python score_players.py

Input:  data/final/merged.csv
Output: data/final/scored.csv
"""

from pathlib import Path

import numpy as np
import pandas as pd

FINAL_DIR = Path("data/final")

# ── League strength multipliers ───────────────────────────────────────────────
# Reward players performing in harder leagues.
# Scottish Premiership = 1.00 baseline. Bundesliga/Ligue 1 at top.

LEAGUE_MULTIPLIERS = {
    "Premier League": 1.08,  # highest overall competitiveness + transfer spend
    "La Liga":        1.06,  # top technical quality, deep talent pool
    "Serie A":        1.05,  # tactically demanding, strong defensively
    "Bundesliga":     1.04,  # high press-intensity, developing talent hub
    "Ligue 1":        1.00,  # baseline — PSG inflates top end, weaker depth
}

# ── Metric weights by position group ─────────────────────────────────────────
# Weights sum to 1.0 per position group.
# Each metric justified by role requirement.

WEIGHTS = {
    "Forward": {
        # Attacking output — primary job is to score and create
        "goals_p90":                    0.20,  # core output metric
        "assists_p90":                  0.10,  # creative contribution
        "xg_p90":                       0.12,  # quality of chances generated
        "xag_p90":                      0.08,  # chance creation quality
        # Athleticism proxies
        "progressive_carries_p90":      0.10,  # drives play forward
        "pressures_p90":                0.06,  # work rate off the ball
        "pressure_regains_p90":         0.04,  # press effectiveness
        # Technical
        "dribbles_completed_p90":       0.08,  # 1v1 ability
        "passes_into_final_third_p90":  0.05,  # line-breaking
        # Tactical
        "carries_into_penalty_area_p90":0.08,  # direct goal threat
        "touches_att_third_p90":        0.05,  # involvement in attack
        "aerial_win_pct":               0.04,  # physical presence
    },

    "Midfielder": {
        # Progression — midfielders move the ball and cover ground
        "progressive_passes_p90":       0.12,  # advances play
        "progressive_carries_p90":      0.10,  # carries into space
        "passes_into_final_third_p90":  0.10,  # penetrating distribution
        # Defensive contribution
        "pressures_p90":                0.10,  # engine/work rate
        "pressure_regains_p90":         0.08,  # press effectiveness
        "tackles_plus_interceptions_p90":0.08, # defensive actions
        # Technical
        "xag_p90":                      0.10,  # chance creation
        "dribbles_completed_p90":       0.06,  # carries under pressure
        "key_passes_p90":               0.08,  # direct creativity
        # Output
        "goals_p90":                    0.08,  # goal threat from midfield
        "aerial_win_pct":               0.05,  # duels — physical
        "ground_duel_win_pct":          0.05,  # duels — technical
    },

    "Defender": {
        # Defensive actions — primary job
        "tackles_won_p90":              0.15,  # winning the ball
        "interceptions_p90":            0.15,  # reading the game
        "tackles_plus_interceptions_p90":0.10, # combined defensive output
        "pressure_regains_p90":         0.08,  # press contribution
        "pressures_p90":                0.06,  # defensive work rate
        # Duels
        "aerial_win_pct":               0.12,  # crucial for CBs
        "ground_duel_win_pct":          0.10,  # 1v1 defending
        # Ball playing — modern defender requirement
        "progressive_passes_p90":       0.10,  # builds from back
        "progressive_carries_p90":      0.08,  # carries out of defence
        "passes_into_final_third_p90":  0.06,  # long range distribution
    },
}

# ── Helpers ───────────────────────────────────────────────────────────────────

def minmax_scale(series: pd.Series) -> pd.Series:
    """Scale a series to 0-100. Returns 50 if all values are identical."""
    mn, mx = series.min(), series.max()
    if mx == mn:
        return pd.Series(50.0, index=series.index)
    return (series - mn) / (mx - mn) * 100


def score_group(df: pd.DataFrame, weights: dict) -> pd.Series:
    """
    Normalize each metric within the group then compute weighted sum.
    Missing metrics are skipped and weights redistributed proportionally.
    """
    available = {m: w for m, w in weights.items() if m in df.columns}
    total_weight = sum(available.values())

    score = pd.Series(0.0, index=df.index)
    for metric, weight in available.items():
        col = pd.to_numeric(df[metric], errors="coerce").fillna(0)
        normalized = minmax_scale(col)
        score += normalized * (weight / total_weight)  # redistribute if metrics missing

    return score


# ── Main ──────────────────────────────────────────────────────────────────────

print("Loading merged dataset...")
df = pd.read_csv(FINAL_DIR / "merged.csv")
print(f"  {len(df)} players")

# Fill position_group from FBref position where TM position_group is missing
if "position_group" not in df.columns or df["position_group"].isna().all():
    def infer_group(pos):
        if pd.isna(pos):
            return "Midfielder"
        pos = str(pos).upper()
        if any(x in pos for x in ["FW", "LW", "RW", "ST", "CF"]):
            return "Forward"
        if any(x in pos for x in ["DF", "CB", "LB", "RB", "WB"]):
            return "Defender"
        return "Midfielder"
    df["position_group"] = df["position"].apply(infer_group)
else:
    mask = df["position_group"].isna()
    def infer_group(pos):
        if pd.isna(pos): return "Midfielder"
        pos = str(pos).upper()
        if any(x in pos for x in ["FW", "LW", "RW", "ST", "CF"]): return "Forward"
        if any(x in pos for x in ["DF", "CB", "LB", "RB", "WB"]): return "Defender"
        return "Midfielder"
    df.loc[mask, "position_group"] = df.loc[mask, "position"].apply(infer_group)

print("\nPosition group distribution:")
print(df["position_group"].value_counts().to_string())

# ── Score each position group separately ─────────────────────────────────────

print("\nScoring...")
df["composite_score"] = np.nan

for group, weights in WEIGHTS.items():
    mask = df["position_group"] == group
    if mask.sum() == 0:
        continue
    df.loc[mask, "composite_score"] = score_group(df[mask], weights)
    print(f"  {group:<12} {mask.sum():>4} players scored")

# ── League strength multiplier ────────────────────────────────────────────────

df["league_multiplier"] = df["league"].map(LEAGUE_MULTIPLIERS).fillna(1.0)
df["composite_score_adj"] = (df["composite_score"] * df["league_multiplier"]).round(2)

# ── Value score: composite / market value in millions ────────────────────────

df["market_value_m"] = pd.to_numeric(df["market_value_m"], errors="coerce")
df["value_score"] = (df["composite_score_adj"] / df["market_value_m"]).round(3)

# ── Versatility flag ──────────────────────────────────────────────────────────

if "position" in df.columns:
    df["is_versatile"] = df["position"].str.contains(",", na=False)

# ── Summary ───────────────────────────────────────────────────────────────────

print(f"\n{'='*60}")
print("Composite score summary (adjusted):")
print(df.groupby("position_group")["composite_score_adj"].describe().round(2).to_string())

print("\nValue score summary:")
print(df["value_score"].describe().round(3).to_string())

print("\nTop 20 by value score:")
top = df.nlargest(20, "value_score")[
    ["player_name", "club", "league", "position_group",
     "composite_score_adj", "market_value_m", "value_score"]
]
print(top.to_string(index=False))

# ── Save ──────────────────────────────────────────────────────────────────────

out = FINAL_DIR / "scored.csv"
df.to_csv(out, index=False)
print(f"\nSaved {len(df)} players to {out}")
