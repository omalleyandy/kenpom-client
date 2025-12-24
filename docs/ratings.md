# Ratings

Retrieve team ratings, strength of schedule, tempo, and possession length data.

**Endpoint**
```http
GET /api.php?endpoint=ratings
```

## Parameters

| Name | Type | Required | Description |
|---|---|---:|---|
| `y` | integer | conditional | Ending year of season (e.g. `2025` = 2024–25 season) |
| `team_id` | integer | conditional | Team ID (see Teams endpoint) |
| `c` | string | no | Conference short name |

**Rules**
- At least one of `y` or `team_id` is required.
- If `c` is used, `y` must also be provided.

## Example Requests
```http
GET /api.php?endpoint=ratings&y=2025
GET /api.php?endpoint=ratings&team_id=73&y=2025
GET /api.php?endpoint=ratings&c=B12&y=2025
GET /api.php?endpoint=ratings&team_id=73
```

## Response Fields (observed in PDF)

Core identifiers:
- `DataThrough` (string)
- `Season` (integer)
- `TeamName` (string)
- `Seed` (integer, if applicable)
- `ConfShort` (string)
- `Coach` (string)
- `Wins` (integer)
- `Losses` (integer)
- `Event` (string; tournament event/round)

Efficiency:
- `AdjEM` (float), `RankAdjEM` (integer)
- `AdjOE` (float), `RankAdjOE` (integer)
- `OE` (float), `RankOE` (integer)
- `AdjDE` (float), `RankAdjDE` (integer)
- `DE` (float), `RankDE` (integer)

Tempo:
- `Tempo` (float), `RankTempo` (integer)
- `AdjTempo` (float), `RankAdjTempo` (integer)

Luck / SOS:
- `Luck` (float), `RankLuck` (integer)
- `SOS` (float), `RankSOS` (integer)
- `SOSO` (float), `RankSOSO` (integer)
- `SOSD` (float), `RankSOSD` (integer)
- `NCSOS` (float), `RankNCSOS` (integer)

Possession length:
- `APL_Off` (float), `RankAPL_Off` (integer)
- `APL_Def` (float), `RankAPL_Def` (integer)
- `ConfAPL_Off` (float), `RankConfAPL_Off` (integer)
- `ConfAPL_Def` (float), `RankConfAPL_Def` (integer)
