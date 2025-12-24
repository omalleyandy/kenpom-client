# KenPom Client

A Python API client and MCP server for KenPom basketball analytics. Get direct access to efficiency ratings, game predictions, and advanced stats through Claude or the command line.

## Features

- **MCP Server**: 11 tools for interactive analysis with Claude
- **Full API Coverage**: All 9 KenPom API endpoints
- **Smart Analytics**: Matchup comparisons, top team rankings
- **Resilience**: Rate limiting, retries, and caching built-in
- **Multi-Format Export**: CSV, JSON, and Parquet

## Quick Start

```bash
cd kenpom-client
uv venv && uv sync
cp .env.example .env  # Add your KENPOM_API_KEY
```

## MCP Server Setup (Claude Code)

The MCP server lets Claude directly query KenPom data during conversations.

### Step 1: Project Configuration

The `.mcp.json` file is already included in this project:

```json
{
  "mcpServers": {
    "kenpom": {
      "command": "uv",
      "args": [
        "--directory",
        "C:/Users/omall/Documents/python_projects/kenpom-client",
        "run",
        "kenpom-mcp"
      ]
    }
  }
}
```

### Step 2: Enable Project MCP Servers

Add this to your Claude Code settings (`~/.claude/settings.json`):

```json
{
  "enableAllProjectMcpServers": true
}
```

Or manually approve the server when prompted by Claude Code.

### Step 3: Restart Claude Code

Start a new session in the `kenpom-client` directory. The MCP server will load automatically.

### Available MCP Tools

| Tool | Description |
|------|-------------|
| `kenpom_ratings` | Current efficiency ratings (AdjOE, AdjDE, AdjEM) |
| `kenpom_predictions` | Game predictions with spreads and win probability |
| `kenpom_matchup` | Head-to-head comparison of two teams |
| `kenpom_top_teams` | Top N teams by any metric |
| `kenpom_fourfactors` | Four Factors analytics (eFG%, TO%, OR%, FT Rate) |
| `kenpom_pointdist` | Point distribution (% from FT, 2P, 3P) |
| `kenpom_height` | Height, experience, and continuity |
| `kenpom_miscstats` | Shooting %, blocks, steals, assists |
| `kenpom_teams` | Team rosters with coach and arena |
| `kenpom_conferences` | Conference list |
| `kenpom_archive` | Historical ratings from past dates |

### Example Queries

Once configured, ask Claude naturally:

- "What are Duke's efficiency ratings?"
- "Compare Auburn and Alabama head-to-head"
- "Show me the top 10 teams by AdjEM"
- "What games are predicted for today?"
- "Which teams have the best four factors on offense?"

## CLI Commands

For batch data collection and ML pipelines:

```bash
# Core data
uv run kenpom teams --y 2025
uv run kenpom conferences --y 2025
uv run kenpom ratings --y 2025 --date 2024-12-21

# Game predictions
uv run kenpom fanmatch --date 2024-12-21

# Advanced analytics
uv run kenpom fourfactors --y 2025
uv run kenpom pointdist --y 2025
uv run kenpom height --y 2025
uv run kenpom miscstats --y 2025

# Historical data
uv run kenpom archive --date 2024-12-21

# Real market odds (overtime.ag)
uv run fetch-odds
```

## Output File Naming

All files follow: `kenpom_{data_type}_{identifiers}.{ext}`

| Command | Example Output |
|---------|----------------|
| `teams` | `kenpom_teams_2025.csv` |
| `conferences` | `kenpom_conferences_2025.csv` |
| `ratings` | `kenpom_ratings_2025_2024-12-21.csv` |
| `fanmatch` | `kenpom_predictions_2024-12-21.csv` |
| `fourfactors` | `kenpom_fourfactors_2025.csv` |
| `pointdist` | `kenpom_pointdist_2025.csv` |
| `height` | `kenpom_height_2025.csv` |
| `miscstats` | `kenpom_miscstats_2025.csv` |
| `archive` | `kenpom_archive_2024-12-21.csv` |

Each command exports three formats: `.csv`, `.json`, and `.parquet`

## Configuration

Set in `.env`:

| Variable | Required | Default | Description |
|----------|----------|---------|-------------|
| `KENPOM_API_KEY` | Yes | - | Your KenPom API key |
| `KENPOM_RATE_LIMIT_RPS` | No | `2.0` | Requests per second |
| `KENPOM_CACHE_TTL_SECONDS` | No | `21600` | Cache TTL (6 hours) |
| `KENPOM_MAX_RETRIES` | No | `5` | Max retry attempts |
| `KENPOM_OUT_DIR` | No | `data` | Output directory |
| `OV_CUSTOMER_ID` | For odds | - | overtime.ag customer ID |
| `OV_PASSWORD` | For odds | - | overtime.ag password |

## Automated Odds Fetching (Windows)

The project includes automated scraping of real market odds from overtime.ag for NCAA Basketball games.

### Setup

1. **Install Playwright browser**:
   ```bash
   uv run playwright install chromium
   ```

2. **Add credentials to `.env`**:
   ```
   OV_CUSTOMER_ID=your_customer_id
   OV_PASSWORD=your_password
   ```

3. **Set up Windows Task Scheduler** (runs daily at 4:00 AM PST):
   ```powershell
   powershell -File setup_task_xml.ps1
   ```

### Manual Usage

Fetch current odds and generate predictions:
```bash
uv run fetch-odds
```

This will:
1. Scrape NCAA Basketball odds from overtime.ag
2. Save odds to CSV in `data/` directory
3. Automatically generate game predictions using KenPom data

### Automated Workflow

The scheduled task runs daily at 4:00 AM PST with automatic retry logic:
- Retries every 10 minutes if odds not yet available
- Stops after 2 hours or successful fetch
- Logs all activity to `logs/odds_fetch.log`

**View logs**:
```powershell
Get-Content logs\odds_fetch.log -Tail 50
```

**Manage task**:
```powershell
# Check status
schtasks /query /tn "FetchOvertimeCollegeBasketballOdds" /fo LIST

# Run manually
Start-ScheduledTask -TaskName 'FetchOvertimeCollegeBasketballOdds'

# Stop task
Stop-ScheduledTask -TaskName 'FetchOvertimeCollegeBasketballOdds'

# Delete task
schtasks /delete /tn "FetchOvertimeCollegeBasketballOdds" /f
```

See [docs/ODDS_WORKFLOW.md](docs/ODDS_WORKFLOW.md) for complete documentation.

## Project Structure

```
kenpom-client/
├── src/kenpom_client/
│   ├── mcp_server.py         # MCP server (11 tools)
│   ├── client.py             # API wrapper
│   ├── cli.py                # Command-line interface
│   ├── overtime_scraper.py   # overtime.ag odds scraper
│   ├── models.py             # Pydantic models
│   ├── config.py             # Settings
│   ├── cache.py              # File-based caching
│   ├── http.py               # Rate limiting & retries
│   └── exceptions.py         # Custom exceptions
├── docs/                     # API documentation
│   ├── _index.md             # Documentation index
│   ├── ratings.md            # Ratings endpoint
│   ├── ratings_archive.md    # Archive endpoint
│   ├── fanmatch.md           # FanMatch endpoint
│   ├── four_factors.md       # Four Factors endpoint
│   ├── height.md             # Height endpoint
│   ├── misc_stats.md         # Misc Stats endpoint
│   ├── point_distribution.md # Point Distribution endpoint
│   ├── teams.md              # Teams endpoint
│   ├── conferences.md        # Conferences endpoint
│   ├── ODDS_WORKFLOW.md      # Automated odds fetching guide
│   └── DAILY_SLATE_API.md    # Daily slate output contract
├── schemas/                  # JSON Schemas
│   ├── ratings.schema.json
│   ├── ratings_archive.schema.json
│   ├── fanmatch.schema.json
│   ├── four_factors.schema.json
│   ├── height.schema.json
│   ├── misc_stats.schema.json
│   ├── point_distribution.schema.json
│   ├── teams.schema.json
│   ├── conferences.schema.json
│   ├── daily_slate_row.json
│   └── daily_slate_table.json
├── fetch_odds_scheduled.bat  # Windows scheduled task script
├── setup_task_xml.ps1        # Task Scheduler setup
├── .mcp.json                 # MCP server configuration
├── data/                     # Output directory (gitignored)
├── logs/                     # Task logs (gitignored)
├── .cache/                   # API cache (gitignored)
└── .env                      # API keys (gitignored)
```

## Programmatic Usage

```python
from kenpom_client.client import KenPomClient
from kenpom_client.config import Settings

settings = Settings.from_env()
client = KenPomClient(settings)

# Get ratings
ratings = client.ratings(y=2025)
for team in ratings[:5]:
    print(f"{team.TeamName}: AdjEM {team.AdjEM}")

# Get predictions
games = client.fanmatch(d="2024-12-21")
for game in games:
    spread = game.HomePred - game.VisitorPred
    print(f"{game.Visitor} @ {game.Home}: {spread:+.1f}")

# Compare teams
four_factors = client.four_factors(y=2025)
height_data = client.height(y=2025)
misc_stats = client.misc_stats(y=2025)

client.close()
```

## API Endpoints Reference

| Endpoint | Method | Description |
|----------|--------|-------------|
| Ratings | `ratings(y, team_id, c)` | Current season efficiency ratings |
| Archive | `archive(d, preseason, y)` | Historical point-in-time ratings |
| Four Factors | `four_factors(y)` | eFG%, TO%, OR%, FT Rate |
| Point Dist | `point_distribution(y)` | Scoring breakdown by shot type |
| Height | `height(y)` | Height, experience, continuity |
| Misc Stats | `misc_stats(y)` | Shooting %, blocks, steals, assists |
| FanMatch | `fanmatch(d)` | Game predictions and spreads |
| Teams | `teams(y, c)` | Team rosters with arena info |
| Conferences | `conferences(y)` | Conference metadata |

## Documentation

Full API documentation and JSON schemas are available in the `docs/` and `schemas/` directories.

**API Endpoints**: See [docs/_index.md](docs/_index.md) for the complete documentation index.

| Endpoint | Docs | Schema |
|----------|------|--------|
| Ratings | [ratings.md](docs/ratings.md) | [ratings.schema.json](schemas/ratings.schema.json) |
| Archive | [ratings_archive.md](docs/ratings_archive.md) | [ratings_archive.schema.json](schemas/ratings_archive.schema.json) |
| FanMatch | [fanmatch.md](docs/fanmatch.md) | [fanmatch.schema.json](schemas/fanmatch.schema.json) |
| Four Factors | [four_factors.md](docs/four_factors.md) | [four_factors.schema.json](schemas/four_factors.schema.json) |
| Height | [height.md](docs/height.md) | [height.schema.json](schemas/height.schema.json) |
| Misc Stats | [misc_stats.md](docs/misc_stats.md) | [misc_stats.schema.json](schemas/misc_stats.schema.json) |
| Point Dist | [point_distribution.md](docs/point_distribution.md) | [point_distribution.schema.json](schemas/point_distribution.schema.json) |
| Teams | [teams.md](docs/teams.md) | [teams.schema.json](schemas/teams.schema.json) |
| Conferences | [conferences.md](docs/conferences.md) | [conferences.schema.json](schemas/conferences.schema.json) |

**Workflows & Contracts**:
| Document | Description |
|----------|-------------|
| [ODDS_WORKFLOW.md](docs/ODDS_WORKFLOW.md) | Automated odds fetching workflow |
| [DAILY_SLATE_API.md](docs/DAILY_SLATE_API.md) | Daily slate output contract |
| [daily_slate_row.json](schemas/daily_slate_row.json) | JSON Schema: single prediction |
| [daily_slate_table.json](schemas/daily_slate_table.json) | JSON Schema: prediction array |

## Development

```bash
uv run ruff format .      # Format
uv run ruff check .       # Lint
pyrefly check             # Type check
uv run pytest             # Test
```
