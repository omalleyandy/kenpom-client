# Height

Retrieve team height statistics (including average height, effective height, and position-specific heights). Also includes team experience, bench strength, and continuity.

**Endpoint**
```http
GET /api.php?endpoint=height
```

## Parameters

| Name | Type | Required | Description |
|---|---|---:|---|
| `y` | integer | conditional | Ending season year |
| `team_id` | integer | conditional | Team ID |
| `c` | string | no | Conference short name |

## Example Requests
```http
GET /api.php?endpoint=height&y=2025
GET /api.php?endpoint=height&team_id=47
GET /api.php?endpoint=height&y=2025&c=WCC
```

## Response Fields (observed in PDF)
Metadata:
- `DataThrough` (string)
- `Season` (integer)
- `TeamName` (string)
- `ConfShort` (string)

Height:
- `AvgHgt`, `AvgHgtRank`
- `HgtEff`, `HgtEffRank`
- `Hgt5`, `Hgt5Rank` (center)
- `Hgt4`, `Hgt4Rank` (power forward)
- `Hgt3`, `Hgt3Rank` (small forward)
- `Hgt2`, `Hgt2Rank` (shooting guard)
- `Hgt1`, `Hgt1Rank` (point guard)

Other:
- `Exp`, `ExpRank`
- `Bench`, `BenchRank`
- `Continuity`, `RankContinuity`
