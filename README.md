# Scouting Intelligence Pipeline & Dashboard

End-to-end Python pipeline that merges FBref performance data with Transfermarkt valuations to identify statistically undervalued outfield players across Europe's Big 5 leagues — visualised in an interactive Tableau dashboard.

**[View Dashboard](https://public.tableau.com/app/profile/ajaiah.darlington/viz/ScoutingIntelligenceDashboard_17762156549180/Overview)**

---

## What It Does

- Merges four FBref stat tables (standard, shooting, passing, defending) across two seasons (2022-23, 2023-24) on Player / Club / League / Season keys, covering 3,008 outfield player-seasons after filtering out goalkeepers and anyone under 900 minutes
- Builds per-season Transfermarkt valuation snapshots from raw Kaggle data, taking each player's final recorded valuation within the August–July season window
- Joins the two datasets via a two-pass name matching strategy — exact first on normalised names, then fuzzy matching scoped within each league and season — (fuzzy matches accepted at score 85 or higher), achieving a 94.9% match rate (2,854 of 3,008 player-seasons)
- Scores every outfield player using a composite model: min-max normalisation within position group, position-specific metric weights, league strength multiplier, then divides by market value to produce a value-per-million score
- Exports a clean 40-column dashboard CSV, stripping pipeline internals and replacing raw counting stats with per-90 equivalents

---

## Architecture

```
data/raw/
  transfermarkt/          <- Kaggle dataset (players.csv, player_valuations.csv, etc.)
data/cleaned/
  {standard,shooting,passing,defending}_cleaned.xlsx
                          <- pre-cleaned FBref tables from the scouting-report project
                             (see "FBref input files" below)

         +------------------+     +----------------------+
         |  build_fbref.py  |     | clean_transfermarkt  |
         |  4 Excel files   |     | players + valuations |
         +--------+---------+     +----------+-----------+
                  |                          |
         fbref_cleaned.csv      transfermarkt_cleaned.csv
                  |                          |
                  +----------+---------------+
                     merge_datasets.py
                     (exact + fuzzy matching)
                             |
                        merged.csv
                             |
                     score_players.py
                     (composite scoring)
                             |
                        scored.csv
                             |
                    export_dashboard.py
                             |
                       dashboard.csv  -->  Tableau Public
```

---

## Key Engineering Decisions

**Season-scoped matching, not global**
The merge keys are `normalised_name + league + season` rather than just name. A global name match would incorrectly join a player's 2022-23 FBref stats to their 2023-24 Transfermarkt valuation. Scoping fuzzy matching within each `(league, season)` pair also dramatically reduces the candidate pool per player, cutting false positive risk.

**Two-pass matching with exact priority**
All 2,787 exact matches on normalised names are resolved first. Only the 221 remaining unmatched FBref records go through fuzzy matching. This keeps the slow `process.extractOne` loop as small as possible and avoids re-matching already-resolved names as TM candidates.

**Name normalisation: unidecode + token_sort_ratio**
`unidecode` strips diacritics before comparison (`Ñíguez → niguez`). `token_sort_ratio` handles word-order differences between datasets (`Bruno Silva` vs `Silva Bruno`). Using `token_sort_ratio` rather than `ratio` or `partial_ratio` was necessary because the two data sources use inconsistent name ordering.

**Low-confidence match logging**
Any fuzzy match below score 92 is printed at the end of the merge run for manual review. This surfaces candidates like `"Carlos Benavidez" → "carlos benitez"` (different surnames, score 87). One bad match was identified and dropped this way before scoring.

**Min-max normalisation within position group, not globally**
Defenders and forwards operate on completely different metric scales. Normalising `goals_p90` globally would compress all defender values toward zero relative to forwards. Each position group is normalised independently so a defender's `tackles_won_p90` is ranked against other defenders only.

**Weight redistribution for missing metrics**
Several metrics in the weight dictionaries were not available in the FBref source files (pressures, dribbles, carries into box, aerial win %). Rather than failing or producing artificially low scores, `score_group()` detects available columns at runtime and redistributes weights proportionally across what is present so scores always sum correctly.

**Transfermarkt valuation snapshots, not averages**
The pipeline takes the player's last recorded valuation within each season window rather than the average or peak. This reflects the market's most recent assessment at season end — the figure most comparable to what a buying club would reference.

**Position group from FBref codes, not Transfermarkt**
FBref encodes multi-position players (e.g. `FW,MF`) which is more granular than Transfermarkt's broad categories. Position group is derived once in `build_fbref.py` from FBref codes and carried through the pipeline. Transfermarkt's `position_group` column is excluded from the merge to avoid a column name collision that would otherwise split into `_x` and `_y` suffixes.

---

## Scoring Model

**Composite score:**
1. For each position group (Forward / Midfielder / Defender), each metric is min-max scaled 0–100 within that group
2. A weighted sum is computed using position-specific weights (weights sum to 1.0)
3. The result is multiplied by a league strength multiplier (Premier League 1.08 → Ligue 1 1.00)

**Value score:**
```
value_score = composite_score_adj / market_value_m
```
Higher = better performer relative to price.

**Limitations:**
- Several intended metrics were absent from the available FBref data (pressures, dribbles completed, aerial win %). Defenders are less affected by these gaps than forwards, which means raw value scores skew toward defenders in unfiltered output. The dashboard filters by position group to make comparisons fair.
- The raw value score surfaces very cheap players (< €0.5M) at the top regardless of quality. A minimum market value filter (€2M+) and age cap (≤ 27) are applied in the dashboard to surface actionable targets rather than squad-depth or retired players.
- League multipliers are manually set and subjective. They reflect a reasonable consensus on Big 5 league difficulty but are not derived from the data.

---

## Setup

**Requirements:** Python 3.10+

```bash
pip install -r requirements.txt
```

**Run the pipeline in order:**

```bash
python build_fbref.py           # merge FBref tables → data/cleaned/fbref_cleaned.csv
python clean_transfermarkt.py   # clean Transfermarkt → data/cleaned/transfermarkt_cleaned.csv
python merge_datasets.py        # join datasets → data/final/merged.csv
python score_players.py         # score players → data/final/scored.csv
python export_dashboard.py      # clean export → data/final/dashboard.csv
```

**Data sources required (not included in repo):**
- FBref Big 5 league tables as `data/cleaned/standard_cleaned.xlsx`, `shooting_cleaned.xlsx`, `passing_cleaned.xlsx`, `defending_cleaned.xlsx` (see below)
- Transfermarkt Kaggle dataset → `data/raw/transfermarkt/`

**FBref input files:**
FBref scraping is not part of this repo. The four `*_cleaned.xlsx` files that `build_fbref.py` reads are byte-identical to the cleaned outputs of the collaborative scouting-report project ([github.com/M4G1C14N5/scouting-report](https://github.com/M4G1C14N5/scouting-report), `cleaned_data/`). Copy `standard_cleaned.xlsx`, `shooting_cleaned.xlsx`, `passing_cleaned.xlsx` and `defending_cleaned.xlsx` from that folder into `data/cleaned/` before running the pipeline.

---

## Project Structure

```
├── build_fbref.py             # Load, merge, filter, compute per-90s for FBref data
├── clean_transfermarkt.py     # Build per-season valuation snapshots from Transfermarkt
├── merge_datasets.py          # Two-pass name matching to join both datasets
├── score_players.py           # Composite scoring model with position-specific weights
├── export_dashboard.py        # Strip internals, rename columns, export dashboard CSV
├── requirements.txt
├── notebooks/
│   ├── 01_cleaning.ipynb      # EDA for FBref cleaning decisions
│   ├── 02_transfermarkt.ipynb # EDA for Transfermarkt cleaning decisions
│   └── 03_merging.ipynb       # EDA for merge strategy
├── data/
│   ├── cleaned/               # Intermediate cleaned files (gitignored)
│   └── final/
│       └── dashboard.csv      # Dashboard-ready output (40 columns, 2,854 rows)
└── dashboard/                 # Placeholder for Tableau workbook exports
```

---

## Stack

| Layer | Technology |
|---|---|
| Data processing | Python, pandas, numpy |
| Name matching | fuzzywuzzy (token_sort_ratio), unidecode |
| Data sources | FBref (cleaned Excel tables from the scouting-report project), Transfermarkt (Kaggle) |
| Visualisation | Tableau Public |
| Version control | Git, GitHub |
