# KenPom API Documentation (LLM-Optimized)

This folder contains:
- One Markdown file per endpoint
- One JSON Schema per endpoint (draft-07 style)

## Auth
All requests require a Bearer token:

```
Authorization: Bearer <KENPOM_API_KEY>
```

## Base URL
```
https://kenpom.com
```

## Files
- `docs/*.md` — endpoint docs
- `schemas/*.schema.json` — response schemas
- `.env` — environment variables
