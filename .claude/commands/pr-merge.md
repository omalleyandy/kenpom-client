# Merge Pull Request

Safely merge a pull request with checks.

## Usage
Provide a PR number as an argument: `/pr-merge 23`

## Instructions

For PR #$ARGUMENTS:

### 1. Pre-merge Checks (run in parallel)
```bash
gh pr view $ARGUMENTS --json state,mergeable,mergeStateStatus,reviewDecision
gh pr checks $ARGUMENTS
```

### 2. Verify Before Merge

Before merging, confirm:
- [ ] PR is approved (reviewDecision = APPROVED) or no reviews required
- [ ] All CI checks pass
- [ ] No merge conflicts (mergeable = MERGEABLE)

### 3. Merge Options

Ask the user which merge strategy to use:
- **Squash** (default): `gh pr merge $ARGUMENTS --squash`
- **Merge commit**: `gh pr merge $ARGUMENTS --merge`
- **Rebase**: `gh pr merge $ARGUMENTS --rebase`

### 4. Post-merge Cleanup

After successful merge:
```bash
git checkout main && git pull origin main
```

Optionally delete the local branch if it was merged.
