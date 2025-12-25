# GitHub Actions Workflow Status

Check the status of GitHub Actions workflows.

## Instructions

### 1. List Available Workflows
```bash
gh workflow list
```

### 2. Recent Runs (all workflows)
```bash
gh run list --limit 10
```

### 3. Failed Runs Details
```bash
gh run list --status failure --limit 5
```

### 4. View Specific Run (if any failed)
For each failed run, get details:
```bash
gh run view <run-id> --log-failed
```

## Output Format

Present a summary table with:
| Workflow | Status | Branch | Duration | When |
|----------|--------|--------|----------|------|

Highlight:
- Any currently running workflows
- Recent failures with error summaries
- Success rate over last 10 runs

If there are failures, show the relevant log snippets to help diagnose issues.
