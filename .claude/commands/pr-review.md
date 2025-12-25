# Review Pull Request

Review the specified pull request (or current branch's PR if none specified).

## Arguments
- `$ARGUMENTS` - PR number or URL (optional, defaults to current branch's PR)

## Instructions

1. **Identify the PR**: If a PR number/URL is provided in `$ARGUMENTS`, use that. Otherwise, find the PR for the current branch using `gh pr view`.

2. **Gather PR context**:
   - Run `gh pr view <number> --json title,body,author,state,baseRefName,headRefName,additions,deletions,changedFiles,reviews,comments`
   - Run `gh pr diff <number>` to see all changes

3. **Analyze the changes**:
   - Summarize what the PR does based on title, description, and diff
   - Identify the files changed and categorize them (source, tests, docs, config)
   - Look for potential issues: bugs, security concerns, performance problems
   - Check for missing tests if code was added/modified
   - Verify code style consistency

4. **Provide a structured review**:
   ```
   ## PR Summary
   [Brief description of what this PR accomplishes]

   ## Changes Overview
   - Files changed: X
   - Additions: +Y lines
   - Deletions: -Z lines

   ## Analysis
   [Detailed analysis of the changes]

   ## Potential Issues
   [Any concerns or suggestions]

   ## Recommendation
   [Approve / Request Changes / Comment]
   ```

5. **If requested**, add review comments using `gh pr review <number> --comment --body "..."`
