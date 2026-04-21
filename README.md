# Scouting Intelligence Pipeline and Dashboard

A football scouting analytics project that identifies undervalued outfield players across 7 secondary European leagues by combining FBref performance data with Transfermarkt market valuations.

## Objective

Surface players whose on-pitch output — measured via per-90 metrics — exceeds what their current market value suggests, enabling smarter recruitment decisions in lower-profile leagues.

## Leagues Covered

Secondary European leagues (e.g. Eredivisie, Scottish Premiership, Belgian Pro League, Austrian Bundesliga, Swiss Super League, Portuguese Liga Portugal 2, and others).

## Project Structure

```
data/
  raw/
    fbref/           # Raw FBref CSV exports (standard stats, shooting, passing, etc.)
    transfermarkt/   # Raw Transfermarkt valuation data
  cleaned/           # Standardized, filtered datasets
  final/             # Merged and scored output ready for analysis
notebooks/           # Step-by-step Jupyter notebooks
dashboard/           # Visualization and dashboard assets
```

## Pipeline Overview

1. **01_cleaning.ipynb** — Load FBref CSVs, standardize columns, filter by minutes played, convert to per-90 stats
2. **02_transfermarkt.ipynb** — Load and clean Transfermarkt valuations
3. **03_merging.ipynb** — Fuzzy-match player names across sources and merge datasets
4. **04_scoring.ipynb** — Build composite performance scores and flag undervalued players
5. **05_dashboard.ipynb** — Visualize findings

## Setup

```bash
pip install -r requirements.txt
```
