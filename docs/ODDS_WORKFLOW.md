# Overtime.ag Odds Fetching Workflow

Complete guide for automating College Basketball odds fetching from overtime.ag and integrating with KenPom predictions for betting edge analysis.

## Table of Contents
- [Overview](#overview)
- [Prerequisites](#prerequisites)
- [Setup](#setup)
- [Manual Usage](#manual-usage)
- [Automated Scheduling](#automated-scheduling)
- [Workflow](#workflow)
- [Troubleshooting](#troubleshooting)

## Overview

This workflow automates the process of:
1. Fetching College Basketball odds from overtime.ag (4:00 AM PST daily)
2. Generating KenPom predictions for today's games
3. Calculating betting edge by comparing model predictions vs market odds
4. Identifying value opportunities with expected value (EV) calculations

**Key Timing**: College Basketball and College Extra odds become available at **4:00 AM PST** each day. Once games tip off, they are removed from the boards.

## Prerequisites

### 1. overtime.ag Credentials
Add your credentials to `.env` file:
```bash
OV_CUSTOMER_ID=your_customer_id_here
OV_PASSWORD=your_password_here
```

### 2. KenPom API Key
Required for generating predictions:
```bash
KENPOM_API_KEY=your_kenpom_api_key_here
```

### 3. Playwright Browser
Install Chromium browser for web scraping:
```bash
uv run playwright install chromium
```

## Setup

### Quick Setup (Recommended)
Run the PowerShell setup script as Administrator:
```powershell
# Right-click PowerShell and "Run as Administrator"
cd C:\Users\omall\Documents\python_projects\kenpom-client
Set-ExecutionPolicy -Scope Process -ExecutionPolicy Bypass
.\setup_scheduler.ps1
```

This creates a Windows Task Scheduler task that:
- Runs daily at 4:00 AM PST
- Retries every 10 minutes if odds aren't available yet
- Stops after successful fetch or 2 hours
- Logs all output to `logs/odds_fetch.log`

### Manual Setup
If you prefer manual control, see [Manual Usage](#manual-usage) below.

## Manual Usage

### 1. Fetch Odds Only
```bash
# Run the fetch-odds command
uv run fetch-odds
```

This will:
- Log in to overtime.ag
- Navigate to College Basketball section
- Scrape all available games with spreads, moneylines, and totals
- Export to `data/overtime_odds.csv`

### 2. Generate KenPom Predictions
```bash
# Fetch latest KenPom snapshot with enrichment
uv run kenpom ratings --y 2025 --date $(date +%Y-%m-%d) --four-factors --point-dist --sigma

# Generate predictions for today's games
python analyze_todays_games.py
```

This creates `data/todays_game_predictions_YYYY-MM-DD.csv` with:
- Baseline predictions (simple margin formula)
- Enhanced predictions (with context modifiers)
- Game-specific variance (sigma_game)
- Win probabilities
- Matchup features

### 3. Calculate Betting Edge
```bash
# Analyze edge using real market odds
python calculate_real_edge.py
```

This compares your model predictions against overtime.ag odds and identifies:
- Point spread value (2+ points edge = STRONG)
- Moneyline value (5%+ probability edge = STRONG)
- Expected value (EV) for each bet
- Kelly Criterion bet sizing recommendations

## Automated Scheduling

The scheduled task runs the complete workflow automatically:

```batch
fetch_odds_scheduled.bat
  ├── Fetch odds from overtime.ag
  ├── Generate KenPom predictions
  └── Export ready for edge analysis
```

### View Task Status
```powershell
Get-ScheduledTask -TaskName "FetchOvertimeCollegeBasketballOdds" | Get-ScheduledTaskInfo
```

### Test Task Now
```powershell
Start-ScheduledTask -TaskName "FetchOvertimeCollegeBasketballOdds"
```

### View Logs
```bash
tail -f logs/odds_fetch.log
```

### Disable/Enable Task
```powershell
# Disable
Disable-ScheduledTask -TaskName "FetchOvertimeCollegeBasketballOdds"

# Enable
Enable-ScheduledTask -TaskName "FetchOvertimeCollegeBasketballOdds"
```

### Remove Task
```powershell
Unregister-ScheduledTask -TaskName "FetchOvertimeCollegeBasketballOdds" -Confirm:$false
```

## Workflow

### Daily Automated Flow

```
4:00 AM PST - Task Scheduler triggers
     ↓
4:00-6:00 AM - Retry every 10 min until odds available
     ↓
ODDS FOUND → fetch-odds command runs
     ↓
overtime_odds.csv created in data/
     ↓
KenPom snapshot fetched (if needed)
     ↓
analyze_todays_games.py runs
     ↓
todays_game_predictions_YYYY-MM-DD.csv created
     ↓
READY FOR EDGE ANALYSIS
```

### Manual Review Flow

```
8:00 AM - Review predictions and odds
     ↓
python calculate_real_edge.py
     ↓
Review betting_edge_analysis_YYYY-MM-DD.csv
     ↓
Identify STRONG/MODERATE opportunities
     ↓
Place bets before 10:00 AM (lines move)
     ↓
Track Closing Line Value (CLV)
```

## File Outputs

After running the complete workflow, you'll have:

```
data/
├── overtime_odds.csv                           # Market odds from overtime.ag
├── kenpom_ratings_2025_YYYY-MM-DD_enriched.csv # KenPom snapshot
├── todays_game_predictions_YYYY-MM-DD.csv      # Model predictions
└── betting_edge_analysis_YYYY-MM-DD.csv        # Edge calculations

logs/
└── odds_fetch.log                              # Automated fetch logs
```

## Betting Guidelines

### 1. Edge Identification
- **STRONG spread**: 2+ points difference between model and market
- **STRONG moneyline**: 5%+ probability edge
- **Minimum EV**: Only bet opportunities with EV > 2%

### 2. Bet Sizing
- Use **1/4 Kelly Criterion** (never full Kelly)
- Maximum 3% of bankroll per bet
- Higher EV = higher bet size (within limits)

### 3. Line Shopping
- Check multiple sportsbooks for best line
- 0.5 point difference can add 2-3% to EV
- overtime.ag is your **official reference**

### 4. Tracking
- **CLV (Closing Line Value)** is the key metric
- Track bets in spreadsheet with:
  - Bet details, stake, odds, result
  - Closing line value
  - Running CLV and profit/loss
- Positive CLV over 100+ bets = winning strategy

### 5. Data Freshness
- Check for injury updates before betting
- Model doesn't know about late scratches
- Odds become stale as game approaches

## Troubleshooting

### No Odds Found
**Symptom**: `Extracted 0 games from Angular scope`

**Solutions**:
1. Check if it's before 4:00 AM PST (odds not available yet)
2. Verify overtime.ag credentials in `.env`
3. Check if all games have already tipped off (run earlier)
4. Try running manually with headed browser

### Login Failed
**Symptom**: `Login failed` error

**Solutions**:
1. Verify `OV_CUSTOMER_ID` and `OV_PASSWORD` in `.env`
2. Check if account is active
3. Try logging in manually at overtime.ag/sports

### Playwright Errors
**Symptom**: Browser launch failures

**Solutions**:
```bash
# Reinstall Playwright browsers
uv run playwright install chromium

# Update Playwright
uv add --upgrade-package playwright
```

### Team Name Mismatches
**Symptom**: Can't merge overtime.ag odds with KenPom predictions

**Solutions**:
1. Check team name differences (e.g., "UNC" vs "North Carolina")
2. Add team name mappings in merge logic
3. Use fuzzy matching for team names

## Next Steps

1. **Setup Task Scheduler**:
   ```powershell
   .\setup_scheduler.ps1
   ```

2. **Test the workflow manually**:
   ```bash
   uv run fetch-odds
   python analyze_todays_games.py
   ```

3. **Wait for 4:00 AM PST tomorrow** and check logs

4. **Review predictions and identify value**:
   ```bash
   python calculate_real_edge.py
   ```

5. **Track results** in spreadsheet for CLV analysis

---

**Questions or Issues?** Check `logs/odds_fetch.log` or review [Troubleshooting](#troubleshooting).
