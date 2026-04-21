"""
Clean Transfermarkt data for the Big 5 leagues, 2022-23 and 2023-24 seasons.

Run from the project root:
    python clean_transfermarkt.py

Output: data/cleaned/transfermarkt_cleaned.csv
"""

import pandas as pd
from pathlib import Path

RAW_DIR     = Path("data/raw/transfermarkt")
CLEANED_DIR = Path("data/cleaned")

TARGET_COMPS = {
    "GB1": "Premier League",
    "L1":  "Bundesliga",
    "ES1": "La Liga",
    "FR1": "Ligue 1",
    "IT1": "Serie A",
}

POSITION_MAP = {
    "Attack":   "Forward",
    "Midfield": "Midfielder",
    "Defender": "Defender",
}

# Season windows (Aug start)
SEASONS = {
    "2022-2023": ("2022-08-01", "2023-07-31"),
    "2023-2024": ("2023-08-01", "2024-07-31"),
}

print("Loading raw files...")
players    = pd.read_csv(RAW_DIR / "players.csv")
valuations = pd.read_csv(RAW_DIR / "player_valuations.csv")
valuations["date"] = pd.to_datetime(valuations["date"])
print(f"  players.csv:           {players.shape}")
print(f"  player_valuations.csv: {valuations.shape}")

# ── Build one valuation snapshot per player per season ────────────────────────

print("\nBuilding per-season valuation snapshots...")
season_frames = []

for season, (start, end) in SEASONS.items():
    sv = valuations[
        (valuations["date"] >= start) &
        (valuations["date"] <= end) &
        (valuations["player_club_domestic_competition_id"].isin(TARGET_COMPS))
    ].copy()

    latest = (
        sv.sort_values("date")
        .groupby("player_id")
        .last()
        .reset_index()[["player_id", "market_value_in_eur", "player_club_domestic_competition_id"]]
        .rename(columns={
            "market_value_in_eur":                    "market_value_eur",
            "player_club_domestic_competition_id":    "comp_id",
        })
    )
    latest["season"] = season
    season_frames.append(latest)
    print(f"  {season}: {len(latest)} player valuations")

val_all = pd.concat(season_frames, ignore_index=True)
val_all["league"] = val_all["comp_id"].map(TARGET_COMPS)

# ── Join player info ──────────────────────────────────────────────────────────

players_slim = players[[
    "player_id", "name", "date_of_birth",
    "country_of_citizenship", "position", "sub_position",
    "highest_market_value_in_eur",
]].rename(columns={
    "name":                    "player_name",
    "date_of_birth":           "dob",
    "country_of_citizenship":  "nationality",
    "highest_market_value_in_eur": "peak_value_eur",
})

tm = val_all.merge(players_slim, on="player_id", how="left")

# ── Derive columns ────────────────────────────────────────────────────────────

tm["dob"] = pd.to_datetime(tm["dob"], errors="coerce")
ref_dates = {"2022-2023": pd.Timestamp("2022-08-01"), "2023-2024": pd.Timestamp("2023-08-01")}
tm["age"] = tm.apply(
    lambda r: round((ref_dates[r["season"]] - r["dob"]).days / 365.25, 1)
    if pd.notna(r["dob"]) else None, axis=1
)

tm["market_value_m"] = (tm["market_value_eur"] / 1_000_000).round(3)
tm["position_group"] = tm["position"].map(POSITION_MAP).fillna("Midfielder")

# ── Filter ────────────────────────────────────────────────────────────────────

before = len(tm)
tm = tm[tm["market_value_eur"].notna() & (tm["market_value_eur"] > 0)]
print(f"\nDropped {before - len(tm)} with no market value")

before = len(tm)
tm = tm[tm["position"] != "Goalkeeper"]
print(f"Dropped {before - len(tm)} goalkeepers")

# ── Save ──────────────────────────────────────────────────────────────────────

out_cols = [
    "player_id", "player_name", "league", "season", "nationality",
    "age", "position", "position_group", "sub_position",
    "market_value_eur", "market_value_m", "peak_value_eur",
]
tm = tm[out_cols]

print(f"\nFinal shape: {tm.shape}")
print("Per season/league:")
print(tm.groupby(["season", "league"]).size().to_string())

out = CLEANED_DIR / "transfermarkt_cleaned.csv"
tm.to_csv(out, index=False)
print(f"\nSaved to {out}")
