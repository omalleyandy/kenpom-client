# Daily Slate API

Output contract for daily game prediction tables.

## Schema Reference

| Schema | Path | Description |
|--------|------|-------------|
| Row | `schemas/daily_slate_row.json` | Single game prediction |
| Table | `schemas/daily_slate_table.json` | Array of predictions |

## Required Fields

| Field | Type | Description |
|-------|------|-------------|
| `date` | date | Game date (YYYY-MM-DD) |
| `season` | int | Season year (e.g., 2025) |
| `game_id` | string | Unique game identifier |
| `home` / `visitor` | string | Team names |
| `proj_home` / `proj_visitor` | number | Projected scores |
| `proj_total` | number | Projected total points |
| `proj_margin_home_minus_visitor` | number | Spread (positive = home favored) |
| `win_prob_home` / `win_prob_visitor` | number | Win probability [0,1] |
| `possessions` | number | Projected possessions |
| `method` | enum | `fanmatch`, `kenpom_model`, or `archive_backtest` |
| `feature_source_home` / `feature_source_visitor` | string | Snapshot file/cache key |
| `warnings` | array | Empty if clean; contains issue strings |

## Optional Trace Fields (fanmatch_*)

Include when `method=fanmatch` for debugging:

| Field | Description |
|-------|-------------|
| `fanmatch_raw_margin` | Original API margin |
| `fanmatch_raw_total` | Original API total |
| `fanmatch_hca_applied` | HCA value used |
| `fanmatch_tempo_home` | Home team tempo |
| `fanmatch_tempo_visitor` | Visitor team tempo |
