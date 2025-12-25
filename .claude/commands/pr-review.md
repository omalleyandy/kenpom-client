# Review Pull Request

Review a specific pull request.

## Usage
Provide a PR number as an argument: `/pr-review 23`

## Instructions

Run these commands for PR #$ARGUMENTS:

### 1. Get PR Details
```bash
gh pr view $ARGUMENTS
```

### 2. View PR Diff
```bash
gh pr diff $ARGUMENTS
```

### 3. Check CI Status
```bash
gh pr checks $ARGUMENTS
```

### 4. View Comments
```bash
gh api repos/{owner}/{repo}/pulls/$ARGUMENTS/comments --jq '.[] | {user: .user.login, body: .body, path: .path}'
```

## Output

Provide a summary including:
- PR title and description
- Files changed (grouped by type)
- CI status (pass/fail/pending)
- Any review comments
- Recommendation: approve, request changes, or needs discussion
