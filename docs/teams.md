# Teams

Retrieve list of teams for a season (including conference affiliation and coaching information).

**Endpoint**
```http
GET /api.php?endpoint=teams
```

## Parameters

| Name | Type | Required | Description |
|---|---|---:|---|
| `y` | integer | yes | Ending year of season (e.g., `2025` = 2024–25 season) |
| `c` | string | no | Conference short name |

## Example Requests
```http
GET /api.php?endpoint=teams&y=2025
GET /api.php?endpoint=teams&y=2025&c=BE
```

## Response Fields (observed in PDF)
- `Season` (integer)
- `TeamName` (string)
- `TeamID` (integer)
- `ConfShort` (string)
- `Coach` (string)
- `Arena` (string)
- `ArenaCity` (string)
- `ArenaState` (string)
