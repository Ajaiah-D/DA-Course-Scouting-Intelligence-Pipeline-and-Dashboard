"""
Produces a clean, dashboard-ready CSV from scored.csv.
Drops pipeline internals and raw counting stats that have per-90 equivalents.
Renames columns to human-readable labels.

Run: python export_dashboard.py
Output: data/final/dashboard.csv
"""

from pathlib import Path
import pandas as pd

src = Path("data/final/scored.csv")
out = Path("data/final/dashboard.csv")

df = pd.read_csv(src)

# ── Keep only these columns (in display order) ────────────────────────────────

KEEP = [
    # Identity
    "player_name", "club", "league", "season", "nation", "nationality",
    # Profile
    "position_group", "sub_position", "position", "age",
    # Playing time
    "matches_played", "starts", "minutes",
    # Scoring KPIs
    "composite_score_adj", "value_score", "market_value_m", "peak_value_eur",
    # Attacking per-90
    "goals_p90", "assists_p90", "xg_p90", "xag_p90",
    "npxg_p90", "shots_total_p90", "shots_on_target_p90",
    # Progression per-90
    "progressive_carries_p90", "progressive_passes_p90",
    "passes_into_final_third_p90", "passes_into_penalty_area_p90",
    "progressive_passes_received_p90",
    # Creativity per-90
    "key_passes_p90", "passes_completed_total_p90",
    # Defensive per-90
    "tackles_won_p90", "interceptions_p90", "tackles_plus_interceptions_p90",
    "tackles_total_p90", "clearances_p90", "blocks_total_p90",
    "ground_duel_win_pct",
    # Discipline
    "yellow_cards", "red_cards",
]

# Only keep columns that actually exist in the file
KEEP = [c for c in KEEP if c in df.columns]
df = df[KEEP].copy()

# ── Rename to human-readable labels ──────────────────────────────────────────

RENAME = {
    "player_name":                      "Player Name",
    "club":                             "Club",
    "league":                           "League",
    "season":                           "Season",
    "nation":                           "Nation",
    "nationality":                      "Nationality",
    "position_group":                   "Position Group",
    "sub_position":                     "Sub Position",
    "position":                         "Position Code",
    "age":                              "Age",
    "matches_played":                   "Matches Played",
    "starts":                           "Starts",
    "minutes":                          "Minutes",
    "composite_score_adj":              "Composite Score",
    "value_score":                      "Value Score",
    "market_value_m":                   "Market Value (M)",
    "peak_value_eur":                   "Peak Value (EUR)",
    "goals_p90":                        "Goals P90",
    "assists_p90":                      "Assists P90",
    "xg_p90":                           "xG P90",
    "xag_p90":                          "xAG P90",
    "npxg_p90":                         "npxG P90",
    "shots_total_p90":                  "Shots P90",
    "shots_on_target_p90":              "Shots on Target P90",
    "progressive_carries_p90":          "Progressive Carries P90",
    "progressive_passes_p90":           "Progressive Passes P90",
    "passes_into_final_third_p90":      "Passes Into Final Third P90",
    "passes_into_penalty_area_p90":     "Passes Into Box P90",
    "progressive_passes_received_p90":  "Progressive Passes Received P90",
    "key_passes_p90":                   "Key Passes P90",
    "passes_completed_total_p90":       "Pass Completion P90",
    "tackles_won_p90":                  "Tackles Won P90",
    "interceptions_p90":                "Interceptions P90",
    "tackles_plus_interceptions_p90":   "Tackles + Interceptions P90",
    "tackles_total_p90":                "Tackles Total P90",
    "clearances_p90":                   "Clearances P90",
    "blocks_total_p90":                 "Blocks P90",
    "ground_duel_win_pct":              "Ground Duel Win %",
    "yellow_cards":                     "Yellow Cards",
    "red_cards":                        "Red Cards",
}

df = df.rename(columns=RENAME)

df.to_csv(out, index=False)
print(f"Saved {len(df)} rows, {df.shape[1]} columns to {out}")
print(f"\nColumns ({df.shape[1]}):")
for c in df.columns:
    print(f"  {c}")
