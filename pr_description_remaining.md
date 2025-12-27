## Summary

This PR adds comprehensive documentation for workflow monitoring and testing, implements rest advantage and travel distance features, and significantly improves the PowerShell task scheduler scripts with better error handling and validation.

### Key Changes

- **Documentation**:
  - Added `RUN_TESTS.md` - Complete guide for running the test suite
  - Added `docs/WORKFLOW_MONITORING.md` - GitHub Actions workflow monitoring guide
  - Updated `README.md` with references to new documentation

- **PowerShell Script Improvements**:
  - Dynamic start date calculation (starts today or tomorrow at 4:00 AM)
  - Comprehensive error handling and validation
  - Administrator privilege checks
  - Batch script existence validation
  - Improved error messages with troubleshooting steps
  - Task verification after creation
  - Standardized output formatting and command references
  - Both `setup_scheduler.ps1` and `setup_task_xml.ps1` updated for consistency

- **Code Enhancements**:
  - Implemented rest advantage feature in `matchup.py` (uses GameContext)
  - Implemented travel distance calculation in `matchup.py` (state-based estimation)
  - Updated `calculate_matchup_features()` to accept optional GameContext parameter
  - All TODOs removed from matchup.py

### Files Changed

- `RUN_TESTS.md` - New test documentation (172 lines)
- `docs/WORKFLOW_MONITORING.md` - New workflow monitoring guide (186 lines)
- `setup_scheduler.ps1` - Enhanced with error handling (134 lines changed)
- `setup_task_xml.ps1` - Enhanced with error handling (133 lines changed)
- `src/kenpom_client/matchup.py` - Rest/travel features implemented (73 lines changed)
- `README.md` - Documentation references updated (6 lines)

## Test Plan

1. **PowerShell Scripts**:
   - Run `setup_task_xml.ps1` as Administrator
   - Verify task is created with dynamic start date
   - Test error handling by removing batch script
   - Verify task verification works correctly

2. **Documentation**:
   - Review `RUN_TESTS.md` for accuracy
   - Review `WORKFLOW_MONITORING.md` for completeness
   - Verify all referenced commands work

3. **Code Changes**:
   - Test `calculate_matchup_features()` with and without GameContext
   - Verify rest advantage calculation
   - Verify travel distance estimation

## Notes

- All changes are backward compatible
- PowerShell scripts now provide better user experience with clear error messages
- Travel distance uses state-based estimation (can be enhanced with geocoding later)
- Rest advantage requires GameContext to be provided (optional parameter)
- All TODOs have been addressed
