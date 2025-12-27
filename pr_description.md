## Summary

This PR adds a GitHub Actions workflow for automated odds fetching and updates documentation to include both automation options.

### Key Changes

- **GitHub Actions Workflow** (`.github/workflows/odds_workflow.yaml`):
  - Automated workflow for fetching odds from overtime.ag
  - Runs daily at 4:00 AM PST (12:00 PM UTC) via cron schedule
  - Can be triggered manually via `workflow_dispatch`
  - Generates KenPom predictions and calculates betting edge
  - Uploads results as workflow artifacts

- **Documentation Updates**:
  - Updated `README.md` with GitHub Actions workflow setup instructions (Option 1)
  - Kept Windows Task Scheduler as Option 2 for local automation
  - Updated `CLAUDE.md` to document the new workflow file
  - Added setup instructions for GitHub Secrets
  - Documented workflow features and artifact downloads

### Files Changed

- `.github/workflows/odds_workflow.yaml` - New GitHub Actions workflow
- `odds_workflow.yaml` - Root workflow file (for reference)
- `README.md` - Updated with GitHub Actions documentation
- `CLAUDE.md` - Updated with workflow documentation

## Test Plan

1. **GitHub Actions Workflow**:
   - Add required GitHub Secrets: `OV_CUSTOMER_ID`, `OV_PASSWORD`, `KENPOM_API_KEY`
   - Trigger workflow manually via `workflow_dispatch`
   - Verify workflow completes successfully
   - Check that artifacts are uploaded correctly
   - Verify output files are generated in artifacts

2. **Documentation**:
   - Review README.md for accuracy of GitHub Actions setup
   - Verify CLAUDE.md includes all workflow details
   - Check that both automation options are clearly documented

## Notes

- The workflow uses `uv run python` for consistency with the project's dependency management
- The workflow runs in parallel with the existing Windows Task Scheduler option
- All changes are backward compatible
