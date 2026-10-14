"""
Merge FBref performance data with Transfermarkt valuations using fuzzy name matching.
Matches on normalised name + league + season.

Run from the project root:
    python merge_datasets.py

Input:  data/cleaned/fbref_cleaned.csv
        data/cleaned/transfermarkt_cleaned.csv
Output: data/final/merged.csv
"""

from pathlib import Path

import numpy as np
import pandas as pd
from fuzzywuzzy import fuzz, process
from unidecode import unidecode

CLEANED_DIR    = Path("data/cleaned")
FINAL_DIR      = Path("data/final")
FINAL_DIR.mkdir(parents=True, exist_ok=True)

FUZZY_THRESHOLD = 85  # minimum match score (0-100) to accept a fuzzy match


# ── Name normalisation ────────────────────────────────────────────────────────

def normalise(name: str) -> str:
    """Transliterate to ASCII (strips accents), lowercase, trim outer whitespace.

    Punctuation, hyphens and inner spaces are kept. Missing values become "".
    """
    if pd.isna(name):
        return ""
    return unidecode(str(name)).lower().strip()


# ── Load ──────────────────────────────────────────────────────────────────────

print("Loading cleaned datasets...")
fbref = pd.read_csv(CLEANED_DIR / "fbref_cleaned.csv")
tm    = pd.read_csv(CLEANED_DIR / "transfermarkt_cleaned.csv")
print(f"  FBref:         {len(fbref)} player-seasons")
print(f"  Transfermarkt: {len(tm)} player-seasons")

fbref["name_norm"] = fbref["player_name"].apply(normalise)
tm["name_norm"]    = tm["player_name"].apply(normalise)

# Columns to bring in from Transfermarkt (excluding player_name and position_group — keep FBref's)
TM_COLS = [
    "player_id", "name_norm", "league", "season",
    "market_value_eur", "market_value_m", "peak_value_eur",
    "nationality", "sub_position",
]

# ── Pass 1: Exact match on normalised name + league + season ──────────────────

print("\nPass 1: exact name match within league + season...")
merged_exact = fbref.merge(
    tm[TM_COLS],
    on=["name_norm", "league", "season"],
    how="inner"
)
merged_exact["match_type"]  = "exact"
merged_exact["fuzzy_score"] = 100

print(f"  Exact matches: {len(merged_exact)}")

# Track which (name_norm, league, season) combos are matched
matched_keys = set(zip(merged_exact["name_norm"], merged_exact["league"], merged_exact["season"]))
fbref_unmatched = fbref[
    ~fbref.apply(lambda r: (r["name_norm"], r["league"], r["season"]) in matched_keys, axis=1)
].copy()
print(f"  Still unmatched: {len(fbref_unmatched)}")


# ── Pass 2: Fuzzy match within league + season ────────────────────────────────

print(f"\nPass 2: fuzzy match (threshold={FUZZY_THRESHOLD}) — may take 2-3 minutes...")

fuzzy_rows = []

for (league, season) in sorted(fbref_unmatched[["league", "season"]].drop_duplicates().itertuples(index=False)):
    fb_sub = fbref_unmatched[
        (fbref_unmatched["league"] == league) &
        (fbref_unmatched["season"] == season)
    ]
    tm_sub = tm[
        (tm["league"] == league) &
        (tm["season"] == season) &
        (~tm.apply(lambda r: (r["name_norm"], r["league"], r["season"]) in matched_keys, axis=1))
    ]

    if tm_sub.empty:
        print(f"  {league} {season}: no TM candidates, skipping")
        continue

    tm_names  = tm_sub["name_norm"].tolist()
    tm_lookup = tm_sub.drop_duplicates("name_norm").set_index("name_norm")

    matched = 0
    for _, row in fb_sub.iterrows():
        result = process.extractOne(
            row["name_norm"], tm_names, scorer=fuzz.token_sort_ratio
        )
        if result and result[1] >= FUZZY_THRESHOLD:
            tm_name = result[0]
            score   = result[1]
            if tm_name not in tm_lookup.index:
                continue
            tm_row = tm_lookup.loc[tm_name]
            if isinstance(tm_row, pd.DataFrame):
                tm_row = tm_row.iloc[0]

            r = row.to_dict()
            r["player_id"]        = tm_row.get("player_id")
            r["market_value_eur"] = tm_row.get("market_value_eur")
            r["market_value_m"]   = tm_row.get("market_value_m")
            r["peak_value_eur"]   = tm_row.get("peak_value_eur")
            r["nationality"]      = tm_row.get("nationality")
            r["sub_position"]     = tm_row.get("sub_position")
            r["tm_name_matched"]  = tm_name
            r["match_type"]       = "fuzzy"
            r["fuzzy_score"]      = score
            fuzzy_rows.append(r)
            matched += 1

    print(f"  {league} {season}: unmatched {len(fb_sub):>4} -> fuzzy matched {matched:>4}")

merged_fuzzy = pd.DataFrame(fuzzy_rows)


# ── Combine ───────────────────────────────────────────────────────────────────

print("\nCombining...")
merged = pd.concat([merged_exact, merged_fuzzy], ignore_index=True)

# If a player-season matched multiple TM records keep highest score
merged = merged.sort_values("fuzzy_score", ascending=False)
merged = merged.drop_duplicates(subset=["player_name", "league", "season"], keep="first")

# Drop players with no market value — can't score without it
before = len(merged)
merged = merged[merged["market_value_eur"].notna() & (merged["market_value_eur"] > 0)]
print(f"  Dropped {before - len(merged)} with no market value")

print(f"\n{'='*60}")
print(f"Total matched: {len(merged)} player-seasons")
print(f"  Exact:  {(merged['match_type'] == 'exact').sum()}")
print(f"  Fuzzy:  {(merged['match_type'] == 'fuzzy').sum()}")
print(f"  Match rate: {len(merged)/len(fbref)*100:.1f}% of FBref player-seasons")
print(f"\nBy league + season:")
print(merged.groupby(["league", "season"]).size().to_string())

# ── Low-confidence spot check ─────────────────────────────────────────────────

low = merged[merged["fuzzy_score"] < 92].sort_values("fuzzy_score")
if len(low):
    print(f"\nLow-confidence fuzzy matches to review (score < 92): {len(low)}")
    print(low[["player_name", "tm_name_matched", "fuzzy_score", "club", "league", "season"]].to_string())

# ── Save ──────────────────────────────────────────────────────────────────────

out = FINAL_DIR / "merged.csv"
merged.to_csv(out, index=False)
print(f"\nSaved {len(merged)} player-seasons, {merged.shape[1]} columns to {out}")
