# Check PR Status

View CI/CD checks and status for a pull request.

## Arguments
- `$ARGUMENTS` - PR number or URL (optional, defaults to current branch's PR)

## Instructions

1. **Identify the PR**:
   - Use PR number from `$ARGUMENTS` if provided
   - Otherwise, find current branch's PR: `gh pr view --json number -q .number`

2. **Get PR status and checks**:
   ```bash
   gh pr view <number> --json state,statusCheckRollup,reviewDecision,mergeable,mergeStateStatus
   gh pr checks <number>
   ```

3. **Gather additional context**:
   - Get review status: `gh pr view <number> --json reviews`
   - Get comments: `gh pr view <number> --json comments`
   - Check if it can be merged: `gh pr view <number> --json mergeable`

4. **Present comprehensive status**:
   ```
   ## PR #<number>: <title>

   ### Overall Status
   - State: Open/Merged/Closed
   - Mergeable: Yes/No (reason if no)
   - Review Decision: Approved/Changes Requested/Pending

   ### CI Checks
   | Check | Status | Duration |
   |-------|--------|----------|
   | build | ✅ Pass | 2m 30s |
   | test | ❌ Fail | 5m 12s |
   | lint | ✅ Pass | 45s |

   ### Reviews
   - @reviewer1: Approved
   - @reviewer2: Requested changes

   ### Action Items
   - [ ] Fix failing test check
   - [ ] Address review comments
   ```

5. **If checks failed**, offer to:
   - Show the failing check's logs: `gh run view <run-id> --log-failed`
   - Re-run failed checks: `gh run rerun <run-id> --failed`

## Examples
- `/pr-checks` - Check current branch's PR
- `/pr-checks 123` - Check specific PR
- `/pr-checks https://github.com/owner/repo/pull/123` - Check PR by URL
