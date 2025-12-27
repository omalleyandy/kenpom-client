# GitHub Actions Workflow Monitoring Guide

This guide explains how to monitor and verify the GitHub Actions workflow for automated odds fetching.

## Workflow Overview

The `odds_workflow.yaml` workflow runs daily at 4:00 AM PST (12:00 PM UTC) and:
1. Fetches odds from overtime.ag
2. Generates KenPom predictions
3. Calculates betting edge
4. Uploads results as artifacts

## Monitoring Workflow Runs

### View Workflow Status

1. **GitHub Web Interface**:
   - Go to: `https://github.com/omalleyandy/kenpom-client/actions`
   - Click on "Fetch Odds and Calculate Edge" workflow
   - View recent runs and their status

2. **Command Line**:
   ```bash
   # List recent workflow runs
   gh run list --workflow=odds_workflow.yaml --limit 10
   
   # View details of latest run
   gh run view --web
   
   # Watch a running workflow
   gh run watch
   ```

### Check Workflow Status

```bash
# Get status of latest workflow run
gh run list --workflow=odds_workflow.yaml --limit 1

# View logs of latest run
gh run view --log
```

## Verifying Successful Runs

### 1. Check Workflow Completion

A successful run should show:
- ✅ All steps completed (green checkmarks)
- ✅ Artifacts uploaded
- ✅ No error messages in logs

### 2. Verify Artifacts

```bash
# List artifacts from latest run
gh run view --json artifacts --jq '.artifacts[] | {name, sizeInBytes}'

# Download artifacts
gh run download
```

Expected artifacts:
- `odds-analysis-{run_number}/`
  - `overtime_*.csv` - Market odds
  - `todays_game_predictions_*.csv` - Model predictions
  - `betting_edge_analysis_*.csv` - Edge calculations

### 3. Check Workflow Logs

```bash
# View full logs
gh run view --log

# View logs for specific step
gh run view --log | grep -A 20 "Fetch odds"
```

## Troubleshooting Failed Runs

### Common Issues

1. **Missing GitHub Secrets**:
   - Error: `OV_CUSTOMER_ID`, `OV_PASSWORD`, or `KENPOM_API_KEY` not found
   - Fix: Add secrets in Settings → Secrets and variables → Actions

2. **Playwright Browser Not Installed**:
   - Error: Browser executable not found
   - Fix: Workflow should install automatically, but check "Install Playwright browsers" step

3. **Odds Not Available**:
   - Error: `Extracted 0 games from Angular scope`
   - Fix: Normal if run before 4:00 AM PST, workflow will retry on schedule

4. **Rate Limiting**:
   - Error: Too many requests to KenPom API
   - Fix: Check rate limit settings, workflow includes delays

### Debugging Steps

1. **Check Workflow Logs**:
   ```bash
   gh run view --log > workflow_log.txt
   ```

2. **Re-run Failed Workflow**:
   ```bash
   gh workflow run odds_workflow.yaml
   ```

3. **Check Secret Configuration**:
   - Verify all required secrets are set
   - Ensure secret names match exactly (case-sensitive)

## Manual Workflow Trigger

### Via GitHub Web Interface

1. Go to Actions → "Fetch Odds and Calculate Edge"
2. Click "Run workflow"
3. Select branch (usually `main`)
4. Click "Run workflow"

### Via Command Line

```bash
# Trigger workflow manually
gh workflow run odds_workflow.yaml

# Check status
gh run watch
```

## Monitoring Best Practices

### Daily Checks

1. **Morning Review** (after 4:00 AM PST):
   - Check if workflow ran successfully
   - Verify artifacts were uploaded
   - Review any error messages

2. **Weekly Review**:
   - Check workflow success rate
   - Review artifact sizes (ensure data is being generated)
   - Verify predictions are reasonable

### Setting Up Notifications

1. **GitHub Notifications**:
   - Go to Settings → Notifications
   - Enable notifications for workflow runs
   - Choose email or web notifications

2. **Workflow Status Badge** (Optional):
   Add to README.md:
   ```markdown
   ![Workflow Status](https://github.com/omalleyandy/kenpom-client/workflows/Fetch%20Odds%20and%20Calculate%20Edge/badge.svg)
   ```

## Success Criteria

A successful workflow run should:

✅ Complete all 9 steps without errors
✅ Generate at least one CSV file in artifacts
✅ Complete within 120 minutes (timeout limit)
✅ Show "Success" status in GitHub Actions

## Workflow Schedule

- **Schedule**: Daily at 4:00 AM PST (12:00 PM UTC)
- **Manual Trigger**: Available via `workflow_dispatch`
- **Timeout**: 120 minutes
- **Retry**: Not automatic (relies on next scheduled run)

## Next Steps After Successful Run

1. Download artifacts from GitHub Actions
2. Review `betting_edge_analysis_*.csv` for value opportunities
3. Compare predictions to closing lines for CLV tracking
4. Update betting spreadsheet with results

---

**Questions?** Check workflow logs or review [ODDS_WORKFLOW.md](ODDS_WORKFLOW.md) for detailed workflow documentation.
