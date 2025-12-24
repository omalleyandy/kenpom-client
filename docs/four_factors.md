# Four Factors

Retrieve Four Factors for offense and defense (plus rating/tempo mirrors for convenience).

**Endpoint**
```http
GET /api.php?endpoint=four-factors
```

## Parameters

| Name | Type | Required | Description |
|---|---|---:|---|
| `y` | integer | conditional | Ending season year |
| `team_id` | integer | conditional | Team ID |
| `c` | string | no | Conference short name |
| `conf_only` | boolean | no | If true, returns conference-only stats |

**Rules**
- At least one of `y` or `team_id` is required.
- If `c` is used, `y` must also be provided.

## Example Requests
```http
GET /api.php?endpoint=four-factors&y=2025
GET /api.php?endpoint=four-factors&team_id=42
GET /api.php?endpoint=four-factors&y=2025&c=ACC
GET /api.php?endpoint=four-factors&y=2025&conf_only=true
```

## Response Fields (observed in PDF)
Metadata:
- `DataThrough` (string)
- `ConfOnly` (string; "true"/"false")
- `Season` (integer)
- `TeamName` (string)

Offense:
- `eFG_Pct`, `RankeFG_Pct`
- `TO_Pct`, `RankTO_Pct`
- `OR_Pct`, `RankOR_Pct`
- `FT_Rate`, `RankFT_Rate`

Defense:
- `Def_eFG_Pct`, `RankDef_eFG_Pct`
- `Def_TO_Pct`, `RankDef_TO_Pct`
- `Def_OR_Pct`, `RankDef_OR_Pct`
- `Def_FT_Rate`, `RankDef_FT_Rate`

Ratings mirrors:
- `OE`, `RankOE`
- `DE`, `RankDE`
- `Tempo`, `RankTempo`
- `AdjOE`, `RankAdjOE`
- `AdjDE`, `RankAdjDE`
- `AdjTempo`, `RankAdjTempo`
