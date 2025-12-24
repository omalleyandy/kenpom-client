# Fanmatch

Retrieve game predictions for a specific date, including predicted scores, win probabilities, tempo predictions, and thrill scores.

**Endpoint**
```http
GET /api.php?endpoint=fanmatch
```

## Parameters

| Name | Type | Required | Description |
|---|---|---:|---|
| `d` | string | yes | Date in `YYYY-MM-DD` format (e.g., `2024-11-24`) |

## Example Requests
```http
GET /api.php?endpoint=fanmatch&d=2024-11-24
```

## Response Fields (observed in PDF)
- `Season` (integer)
- `GameID` (integer)
- `DateOfGame` (string)
- `Visitor` (string)
- `Home` (string)
- `HomeRank` (integer)
- `VisitorRank` (integer)
- `HomePred` (float)
- `VisitorPred` (float)
- `HomeWP` (float)
- `PredTempo` (float)
- `ThrillScore` (float)
