# Point Distribution

Retrieve the percentage of points scored from free throws, two-point field goals, and three-point field goals (for offense and defense).

**Endpoint**
```http
GET /api.php?endpoint=pointdist
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
GET /api.php?endpoint=pointdist&y=2025
GET /api.php?endpoint=pointdist&team_id=23
GET /api.php?endpoint=pointdist&y=2025&c=B10
GET /api.php?endpoint=pointdist&y=2025&conf_only=true
```

## Response Fields (observed in PDF)
Metadata:
- `DataThrough` (string)
- `ConfOnly` (string; "true"/"false")
- `Season` (integer)
- `TeamName` (string)
- `ConfShort` (string)

Offense:
- `OffFT`, `RankOffFT`
- `OffFG2`, `RankOffFG2`
- `OffFG3`, `RankOffFG3`

Defense:
- `DefFT`, `RankDefFT`
- `DefFG2`, `RankDefFG2`
- `DefFG3`, `RankDefFG3`
