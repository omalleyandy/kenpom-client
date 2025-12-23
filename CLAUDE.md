# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

KenPom Client is a Python API client for the KenPom basketball analytics API. It provides:
- Authenticated API access (Bearer token)
- Built-in rate limiting, retries, and caching
- Snapshot builders for creating historical datasets
- CLI for exporting data to CSV/JSON/Parquet
- Playwright integration for web scraping and browser automation

## Environment Setup

Required environment variable:
- `KENPOM_API_KEY` - Your KenPom API key (required)

Optional environment variables (with defaults):
- `KENPOM_BASE_URL` (default: `https://kenpom.com`)
- `KENPOM_TIMEOUT_SECONDS` (default: `20.0`)
- `KENPOM_MAX_RETRIES` (default: `5`)
- `KENPOM_BACKOFF_BASE_SECONDS` (default: `0.6`)
- `KENPOM_RATE_LIMIT_RPS` (default: `2.0`)
- `KENPOM_CACHE_DIR` (default: `.cache/kenpom`)
- `KENPOM_CACHE_TTL_SECONDS` (default: `21600` / 6 hours)
- `KENPOM_OUT_DIR` (default: `data`)

For overtime.ag odds scraping:
- `OV_CUSTOMER_ID` - overtime.ag customer ID (required for fetch-odds)
- `OV_PASSWORD` - overtime.ag password (required for fetch-odds)

For KenPom web scraping (HCA, etc.):
- `KENPOM_EMAIL` - KenPom account email (required for fetch-hca)
- `KENPOM_PASSWORD` - KenPom account password (required for fetch-hca)

Create a `.env` file in the project root with these values.

## Common Commands

### Initial Setup
```powershell
uv venv
uv sync
# Create .env file with KENPOM_API_KEY
```

### CLI Usage
```bash
# Fetch teams for a season
uv run kenpom teams --y 2025

# Fetch current ratings snapshot
uv run kenpom ratings --y 2025 --date 2025-01-15

# Fetch archived ratings for specific date (backtesting-safe)
uv run kenpom archive --date 2024-03-15

# Fetch game predictions for a date
uv run kenpom fanmatch --date 2025-01-15

# Fetch Home Court Advantage data (requires KENPOM_EMAIL/KENPOM_PASSWORD)
uv run fetch-hca
# Or via CLI:
uv run kenpom hca --y 2025

# Fetch Referee Ratings / FAA data (requires KENPOM_EMAIL/KENPOM_PASSWORD)
uv run fetch-refs

# Fetch game officials from ESPN and calculate crew FAA
uv run fetch-officials                    # Today's games
uv run fetch-officials --date 2025-01-15  # Specific date
uv run fetch-officials --game-id 401827093  # Specific game
```

### Testing
```bash
# Run all tests
uv run pytest

# Run specific test
uv run pytest tests/test_smoke_client.py
```

### Playwright (Web Scraping)
```bash
# Install browser binaries (one-time setup)
uv run playwright install chromium

# Install all browsers (optional)
uv run playwright install

# Take a screenshot
uv run python -c "from playwright.sync_api import sync_playwright; \
  p = sync_playwright().start(); \
  browser = p.chromium.launch(); \
  page = browser.new_page(); \
  page.goto('https://kenpom.com'); \
  page.screenshot(path='kenpom.png'); \
  browser.close()"
```

### Code Quality
```bash
# Format code
uv run ruff format .

# Check linting
uv run ruff check .

# Fix linting issues
uv run ruff check . --fix

# Type checking
pyrefly check
```

## Architecture

### Core Components

**KenPomClient** (`client.py`)
- Main API wrapper around `/api.php?endpoint=...`
- Handles authentication via Bearer token in headers
- Integrates rate limiting, caching, and retry logic
- Provides methods for all API endpoints: `teams()`, `conferences()`, `ratings()`, `archive()`, `fanmatch()`

**Settings** (`config.py`)
- Centralized configuration from environment variables
- Uses `from_env()` factory method to load settings
- All config uses dataclass with defaults

**HTTP Layer** (`http.py`)
- `RateLimiter`: Simple token bucket rate limiter (default 2 RPS)
- `request_json()`: Robust HTTP request wrapper with exponential backoff
- Classifies errors into `KenPomAuthError`, `KenPomRateLimitError`, `KenPomServerError`, `KenPomClientError`

**FileCache** (`cache.py`)
- Deterministic on-disk cache using SHA-256 hashes of request URLs
- TTL-based expiration (default 6 hours)
- Atomic writes using temp file + rename pattern

**Models** (`models.py`)
- Pydantic models for API responses
- Types: `Team`, `Conference`, `Rating`, `ArchiveRating`, `FanmatchGame`
- Field names match KenPom API response format (PascalCase)

**Snapshot Builders** (`snapshot.py`)
- `build_snapshot_from_ratings()`: Uses current-season ratings endpoint
- `build_snapshot_from_archive()`: Uses archive endpoint for backtesting-safe snapshots
- Returns pandas DataFrames with normalized schema

**CLI** (`cli.py`)
- Entry point: `kenpom` command (defined in `pyproject.toml`)
- Subcommands: `teams`, `ratings`, `archive`, `fanmatch`, `hca`
- Exports to CSV, JSON, and Parquet simultaneously

**HCA Scraper** (`hca_scraper.py`)
- Playwright-based scraper for kenpom.com/hca.php
- Extracts team-specific home court advantage values
- Authenticates with KENPOM_EMAIL/KENPOM_PASSWORD
- Outputs JSON and CSV snapshots to data/kenpom_hca_YYYY-MM-DD.{json,csv}
- Used by matchup.py and prediction.py for dynamic HCA (replaces hardcoded 3.5)

**Ref Ratings Scraper** (`ref_ratings_scraper.py`)
- Playwright-based scraper for kenpom.com/officials.php
- Extracts FAA (Fouls Above Average) ratings for all referees
- FAA measures how officials deviate from average foul-calling tendencies
  - Positive FAA = calls more fouls than average
  - Negative FAA = calls fewer fouls than average
- Authenticates with KENPOM_EMAIL/KENPOM_PASSWORD
- Outputs JSON and CSV snapshots to data/kenpom_ref_ratings_YYYY-MM-DD.{json,csv}
- Reference: https://kenpom.substack.com/p/a-path-to-slightly-more-consistent

**ESPN Officials Scraper** (`espn_officials_scraper.py`)
- Playwright-based scraper for ESPN gamecast pages
- Fetches officiating crew assignments for games on a given date
- Officials are typically posted 1-2 hours before tip-off
- Calculates combined crew FAA by matching refs to KenPom FAA ratings
- Includes team name normalization (ESPN → KenPom format)
- Outputs JSON and CSV snapshots to data/espn_officials_YYYY-MM-DD.{json,csv}
- Can run on-demand for specific games: `--game-id 401827093`

### Data Flow

1. CLI command → `Settings.from_env()` loads configuration
2. Creates `KenPomClient(settings)`
3. Client method called (e.g., `client.ratings(y=2025)`)
4. `KenPomClient._get()` checks cache first
5. If cache miss: `request_json()` handles HTTP with retries/backoff
6. Rate limiter enforces delays between requests
7. Response validated via Pydantic models
8. Result cached and returned
9. CLI exports DataFrame to multiple formats

### Key Design Patterns

**Caching Strategy**: All API responses cached by URL + params for 6 hours to minimize redundant requests

**Rate Limiting**: Client-side rate limiting (2 RPS default) prevents hitting server limits

**Retry Logic**: Exponential backoff with jitter for transient failures (5 retries default)

**Snapshot Types**:
- **Ratings snapshot**: Current season data with `team_id` lookup (not backtesting-safe)
- **Archive snapshot**: Point-in-time data for specific date (backtesting-safe)

**Error Handling**: HTTP errors classified into specific exception types for easier debugging

## Development Notes

### Line Length
This project uses 100-char line length (configured in `pyproject.toml`), not the global 88-char preference

### API Endpoint Patterns

All endpoints follow pattern: `GET /api.php?endpoint=<name>&<params>`

Required parameters vary by endpoint:
- `teams`: requires `y` (year)
- `conferences`: requires `y` (year)
- `ratings`: requires `y` OR `team_id`
- `archive`: requires `d` (YYYY-MM-DD) OR (`preseason=true` AND `y`)
- `fanmatch`: requires `d` (YYYY-MM-DD)

### Snapshot Differences

When adding snapshot functionality:
- **Ratings-based**: includes `team_id`, `wins`, `losses`, `tempo`, `sos` - use for current season tracking
- **Archive-based**: minimal schema, includes `preseason` flag - use for backtesting historical predictions

### Testing Philosophy

The project has minimal tests (`test_smoke_client.py`). When adding tests:
- Focus on integration tests that validate API contract
- Mock sparingly - prefer testing against real API with caching
- Test error handling paths (auth failures, rate limits, etc.)

### Playwright Usage

Playwright is available for scraping KenPom data not accessible via the API:

**When to use Playwright vs API:**
- Use API when data is available via endpoints (preferred - faster, cached, rate-limited)
- Use Playwright for data only on web pages (player stats, game details, historical data not in API)

**Best Practices:**
- Use headless mode for production (`headless=True`)
- Use headed mode for debugging and iteration (`headless=False`)
- Respect KenPom's rate limits - add delays between requests
- Cache scraped data to avoid redundant scraping
- Use authentication if needed (login with credentials)
- Take screenshots for debugging selector issues

**Common Patterns:**
```python
from playwright.sync_api import sync_playwright

# Sync API (simpler for scripts)
with sync_playwright() as p:
    browser = p.chromium.launch(headless=False)  # headed for debugging
    page = browser.new_page()
    page.goto("https://kenpom.com/index.php")
    # ... scraping logic ...
    browser.close()

# Async API (for concurrent scraping)
from playwright.async_api import async_playwright
async with async_playwright() as p:
    browser = await p.chromium.launch()
    page = await browser.new_page()
    # ... async scraping logic ...
    await browser.close()
```

## Critical Constraints

### Package Management
- ONLY use `uv`, NEVER `pip`
- Installation: `uv add package`
- Dev dependencies: `uv add --dev package`

### Authentication
- KenPom API uses Bearer token authentication
- Token passed in `Authorization: Bearer <API_KEY>` header
- Missing/invalid token returns 401/403

### Rate Limiting
- Default: 2 requests per second
- Configurable via `KENPOM_RATE_LIMIT_RPS`
- Client-side enforcement prevents server 429 errors

### Caching
- Cache directory: `.cache/kenpom/` (gitignored)
- Cache key: SHA-256 hash of full request URL with sorted params
- TTL: 6 hours default
- Corrupt cache files silently ignored

## Automated Odds Fetching Workflow

### Overview
The project includes automated scraping of real market odds from overtime.ag using Playwright. The workflow runs daily at 4:00 AM PST via Windows Task Scheduler.

### Key Files

**overtime_scraper.py** ([src/kenpom_client/overtime_scraper.py](src/kenpom_client/overtime_scraper.py))
- Playwright-based scraper for overtime.ag
- Uses AngularJS scope extraction to get game data
- CSS selectors: `#img_Basketball` and `label[for='gl_Basketball_College_Basketball_G']`
- Handles authentication with OV_CUSTOMER_ID and OV_PASSWORD
- Extracts: spreads, moneylines, totals, game times

**fetch_odds_scheduled.bat** ([fetch_odds_scheduled.bat](fetch_odds_scheduled.bat))
- Windows batch script for Task Scheduler
- Retry logic: 12 attempts x 10 minutes = 2 hours
- Uses Python directly: `python -m kenpom_client.cli fetch-odds`
- Avoids uv run to prevent file locking issues with MCP server

**setup_task_xml.ps1** ([setup_task_xml.ps1](setup_task_xml.ps1))
- Creates Windows scheduled task using schtasks command
- Runs daily at 4:00 AM PST
- Uses XML template to avoid PowerShell cmdlet format issues

**calculate_real_edge.py** ([calculate_real_edge.py](calculate_real_edge.py))
- Calculates betting edge by comparing model predictions to market odds
- Analyzes both point spreads and moneylines
- Includes Kelly Criterion bet sizing recommendations
- Exports detailed analysis to `data/betting_edge_analysis_YYYY-MM-DD.csv`
- Uses dynamic dates (runs for today's games automatically)

### Critical Implementation Details

**Path Resolution**:
- uv is installed at system level: `%USERPROFILE%\.local\bin\uv.exe`
- NOT in virtual environment: `.venv\Scripts\` does not contain uv.exe
- Python executable is in venv: `.venv\Scripts\python.exe`

**File Locking Issue**:
- DO NOT use `uv run fetch-odds` in scheduled tasks
- The MCP server locks `kenpom-mcp.exe`, preventing uv from syncing
- ALWAYS use: `python -m kenpom_client.cli fetch-odds`

**Timing**:
- Odds become available at 4:00 AM PST
- Games are removed from the board after tip-off
- Retry logic handles early morning runs when odds not yet posted

**Workflow**:
1. Scrape odds from overtime.ag
2. Save to `data/overtime_ncaab_odds_YYYY-MM-DD.csv`
3. Automatically run `analyze_todays_games.py`
4. Generate predictions with KenPom + market odds
5. Run `calculate_real_edge.py` for detailed betting edge analysis
6. Output betting opportunities with Kelly Criterion sizing to `data/betting_edge_analysis_YYYY-MM-DD.csv`
7. Log everything to `logs/odds_fetch.log`

### Testing the Workflow

Manual test:
```bash
uv run fetch-odds
```

Test scheduled task:
```powershell
Start-ScheduledTask -TaskName 'FetchOvertimeCollegeBasketballOdds'
Start-Sleep -Seconds 20
Get-Content logs\odds_fetch.log -Tail 50
```

### Troubleshooting

**Issue**: uv.exe not found
- **Cause**: Using wrong path (venv instead of system)
- **Fix**: Use `%USERPROFILE%\.local\bin\uv.exe`

**Issue**: kenpom-mcp.exe locked
- **Cause**: MCP server running, uv trying to sync
- **Fix**: Use `python -m kenpom_client.cli fetch-odds` instead of `uv run`

**Issue**: Task Scheduler XML error
- **Cause**: PowerShell cmdlets create malformed XML
- **Fix**: Use `setup_task_xml.ps1` with schtasks command

**Issue**: Logs not appearing
- **Cause**: Output redirection in Task Scheduler not working
- **Fix**: Batch script handles logging internally with `call :main >> "%LOGFILE%" 2>&1`
