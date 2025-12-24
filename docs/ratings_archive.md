# Ratings Archive

Retrieve historical team ratings from specific dates (or preseason snapshots).

**Endpoint**
```http
GET /api.php?endpoint=archive
```

## Parameters

| Name | Type | Required | Description |
|---|---|---:|---|
| `d` | string | conditional | Date in `YYYY-MM-DD` format for archived ratings |
| `y` | integer | conditional | Ending season year (required with `preseason=true`) |
| `preseason` | boolean | no | If true, returns preseason ratings for year `y` |
| `team_id` | integer | no | Team ID |
| `c` | string | no | Conference short name |

**Rules**
- Either `d` is required, or both `preseason=true` and `y` are required.

## Example Requests
```http
GET /api.php?endpoint=archive&d=2025-02-15
GET /api.php?endpoint=archive&preseason=true&y=2025
GET /api.php?endpoint=archive&d=2025-03-01&team_id=45
```

## Response Fields (observed in PDF)
- `ArchiveDate` (string)
- `Season` (integer)
- `Preseason` (string; "true"/"false")
- `TeamName` (string)
- `Seed` (integer)
- `Event` (string)
- `ConfShort` (string)

Ratings at archive date:
- `AdjEM`, `RankAdjEM`
- `AdjOE`, `RankAdjOE`
- `AdjDE`, `RankAdjDE`
- `AdjTempo`, `RankAdjTempo`

Final ratings:
- `AdjEMFinal`, `RankAdjEMFinal`
- `AdjOEFinal`, `RankAdjOEFinal`
- `AdjDEFinal`, `RankAdjDEFinal`
- `AdjTempoFinal`, `RankAdjTempoFinal`

Deltas:
- `RankChg` (integer)
- `AdjEMChg` (float)
- `AdjTChg` (float)
