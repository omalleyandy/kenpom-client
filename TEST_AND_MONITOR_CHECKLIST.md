# Test and Workflow Monitoring Checklist

This checklist ensures all tests pass and the GitHub Actions workflow runs successfully after PR merge.

## Pre-Merge Checklist

### 1. Run Test Suite

**Command:**
```bash
uv run pytest -v
```

**Expected Output:**
- All tests should pass
- No errors or failures
- Reasonable execution time (< 30 seconds)

**If tests fail:**
- Review error messages
- Check if dependencies are installed: `uv sync`
- Verify Python version: `python --version` (should be >= 3.12.11)

**Test Files:**
- `tests/test_effort.py`
- `tests/test_matchup_features.py`
- `tests/test_prediction.py`
- `tests/test_smoke_client.py`
- `tests/test_snapshot_enrichment.py`

### 2. Verify Code Quality

**Linting:**
```bash
uv run ruff check .
```

**Formatting:**
```bash
uv run ruff format .
```

**Type Checking:**
```bash
pyrefly check
```

## Post-Merge Checklist

### 3. Monitor GitHub Actions Workflow

After the PR is merged, verify the workflow runs successfully:

**Check Workflow Status:**
```bash
# View recent workflow runs
gh run list --workflow=odds_workflow.yaml --limit 5

# View latest run details
gh run view --web
```

**Expected Results:**
- ✅ Workflow completes successfully
- ✅ All 9 steps pass (green checkmarks)
- ✅ Artifacts are uploaded
- ✅ No error messages in logs

**Manual Trigger (Optional):**
```bash
# Trigger workflow manually to test
gh workflow run odds_workflow.yaml

# Watch the workflow
gh run watch
```

### 4. Verify Workflow Artifacts

**List Artifacts:**
```bash
gh run view --json artifacts --jq '.artifacts[] | {name, sizeInBytes}'
```

**Download Artifacts:**
```bash
gh run download
```

**Expected Artifacts:**
- `odds-analysis-{run_number}/`
  - `overtime_*.csv` - Market odds from overtime.ag
  - `todays_game_predictions_*.csv` - Model predictions
  - `betting_edge_analysis_*.csv` - Edge calculations

### 5. Check Workflow Logs

**View Full Logs:**
```bash
gh run view --log
```

**View Specific Step:**
```bash
gh run view --log | grep -A 20 "Fetch odds"
```

**Verify:**
- No authentication errors
- Odds fetched successfully (or appropriate retry message)
- Predictions generated
- Edge calculations completed
- Artifacts uploaded

### 6. Verify PowerShell Scripts (Windows)

If testing on Windows:

**Test setup_task_xml.ps1:**
```powershell
# Run as Administrator
.\setup_task_xml.ps1
```

**Verify:**
- Task created successfully
- Dynamic start date calculated correctly
- Error handling works (test by removing batch script)
- Task verification passes

**Test Task:**
```powershell
Start-ScheduledTask -TaskName 'FetchOvertimeCollegeBasketballOdds'
Start-Sleep -Seconds 20
Get-Content logs\odds_fetch.log -Tail 50
```

## Troubleshooting

### Tests Fail

**Issue:** Import errors
- **Fix:** Run `uv sync` to install dependencies

**Issue:** Missing test data
- **Fix:** Check if API credentials are set in `.env`

**Issue:** Network errors
- **Fix:** Some tests require network access for API calls

### Workflow Fails

**Issue:** Missing GitHub Secrets
- **Fix:** Add `OV_CUSTOMER_ID`, `OV_PASSWORD`, `KENPOM_API_KEY` in Settings → Secrets

**Issue:** Playwright browser not installed
- **Fix:** Workflow should install automatically, but check "Install Playwright browsers" step

**Issue:** Odds not available
- **Fix:** Normal if run before 4:00 AM PST, workflow will retry on schedule

### PowerShell Script Fails

**Issue:** Not running as Administrator
- **Fix:** Right-click PowerShell → "Run as Administrator"

**Issue:** Batch script not found
- **Fix:** Ensure `fetch_odds_scheduled.bat` exists in project root

**Issue:** Task creation fails
- **Fix:** Check Task Scheduler service is running
- **Fix:** Try `setup_task_xml.ps1` instead (more reliable)

## Success Criteria

✅ All tests pass locally
✅ Code quality checks pass (linting, formatting, type checking)
✅ PR merged successfully
✅ GitHub Actions workflow runs successfully
✅ Workflow artifacts are generated and uploaded
✅ PowerShell scripts work correctly (if testing on Windows)

## Next Steps After Verification

1. **Document Results:** Note any issues or successes
2. **Update Documentation:** If workflow behavior differs from docs, update accordingly
3. **Monitor Daily:** Check workflow runs daily at 4:00 AM PST
4. **Review Artifacts:** Download and review betting edge analysis weekly

---

**Reference Documentation:**
- [RUN_TESTS.md](RUN_TESTS.md) - Detailed test running guide
- [docs/WORKFLOW_MONITORING.md](docs/WORKFLOW_MONITORING.md) - Workflow monitoring guide
- [docs/ODDS_WORKFLOW.md](docs/ODDS_WORKFLOW.md) - Complete odds workflow documentation
