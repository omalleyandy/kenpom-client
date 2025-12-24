# Conferences

Retrieve list of conferences for a season.

**Endpoint**
```http
GET /api.php?endpoint=conferences
```

## Parameters

| Name | Type | Required | Description |
|---|---|---:|---|
| `y` | integer | yes | Ending year of season (e.g., `2025` = 2024–25 season) |

## Example Requests
```http
GET /api.php?endpoint=conferences&y=2025
```

## Response Fields (observed in PDF)
- `Season` (integer)
- `ConfID` (integer)
- `ConfShort` (string)
- `ConfLong` (string)
