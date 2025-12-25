# GitHub Repository Status

Run a comprehensive GitHub repository health check using the `gh` CLI.

## Instructions

Execute ALL of the following `gh` commands in parallel and present a formatted summary:

### 1. Repository Overview
```bash
gh repo view --json name,description,defaultBranchRef,stargazerCount,forkCount,openIssueCount --jq '{name, description, default_branch: .defaultBranchRef.name, stars: .stargazerCount, forks: .forkCount, open_issues: .openIssueCount}'
```

### 2. Open Pull Requests
```bash
gh pr list --state open --limit 10
```

### 3. Recently Merged PRs (last 5)
```bash
gh pr list --state merged --limit 5
```

### 4. Open Issues
```bash
gh issue list --state open --limit 10
```

### 5. Recent Workflow Runs
```bash
gh run list --limit 5
```

### 6. Current Branch Status
```bash
git branch -vv
```

## Output Format

Present the results in a clean, organized format:
- Use tables where appropriate
- Highlight any PRs awaiting review
- Note any failed workflow runs
- Show branches that are ahead/behind remote

If any command fails (e.g., no workflows configured), note it and continue with the others.
