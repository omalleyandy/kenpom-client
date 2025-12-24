# Miscellaneous Stats

Retrieve misc team statistics including shooting percentages, block/steal rates, assist rates, and related “opponent” versions.

**Endpoint**
```http
GET /api.php?endpoint=misc-stats
```

## Parameters

| Name | Type | Required | Description |
|---|---|---:|---|
| `y` | integer | conditional | Ending season year |
| `team_id` | integer | conditional | Team ID |
| `c` | string | no | Conference short name |
| `conf_only` | boolean | no | If true, returns conference-only stats |

## Example Requests
```http
GET /api.php?endpoint=misc-stats&y=2025
GET /api.php?endpoint=misc-stats&team_id=12
GET /api.php?endpoint=misc-stats&y=2025&c=ACC
GET /api.php?endpoint=misc-stats&y=2025&conf_only=true
```

## Response Fields (observed in PDF; selected)
Metadata:
- `DataThrough` (string)
- `ConfOnly` (string; "true"/"false")
- `Season` (integer)
- `TeamName` (string)
- `ConfShort` (string)

Offense:
- `FG3Pct`, `RankFG3Pct`
- `FG2Pct`, `RankFG2Pct`
- `FTPct`, `RankFTPct`
- `BlockPct`, `RankBlockPct`
- `StlRate`, `RankStlRate`
- `NSTRate`, `RankNSTRate` (non-steal turnover rate)
- `ARate`, `RankARate` (assist rate)
- `pFG3Rate`, `RankpFG3Rate` (3PA rate)
- `AdjOE`, `RankAdjOE`

Defense (opponent):
- `OppFG3Pct`, `RankOppFG3Pct`
- `OppFG2Pct`, `RankOppFG2Pct`
- `OppFTPct`, `RankOppFTPct`
- `OppBlockPct`, `RankOppBlockPct`
- `OppStlRate`, `RankOppStlRate`
- `OppNSTRate`, `RankOppNSTRate`
- `OppARate`, `RankOppARate`
- `OpppFG3Rate`, `RankOpppFG3Rate`
- `AdjDE`, `RankAdjDE`
