# Create Pull Request

Create a pull request for the current branch.

## Instructions

1. First, gather context by running these commands in parallel:
   ```bash
   git status
   git log origin/main..HEAD --oneline
   git diff origin/main...HEAD --stat
   ```

2. Check if the branch is pushed:
   ```bash
   git branch -vv | grep "^\*"
   ```

3. If not pushed, push the branch first:
   ```bash
   git push -u origin $(git branch --show-current)
   ```

4. Create the PR using `gh pr create`:
   - Generate a concise title from the commits
   - Write a summary with bullet points of changes
   - Include a test plan section
   - Use HEREDOC format for the body

## PR Body Format

```
## Summary
- <bullet points of changes>

## Test plan
- [ ] <testing steps>
```

After creation, display the PR URL.
