# Create Pull Request

Create a pull request for the current branch with an auto-generated description.

## Arguments
- `$ARGUMENTS` - Base branch (optional, defaults to main/master)

## Instructions

1. **Check current state**:
   - Run `git status` to verify clean working directory
   - Run `git branch --show-current` to get current branch name
   - Verify you're not on main/master

2. **Determine base branch**:
   - Use `$ARGUMENTS` if provided
   - Otherwise, detect default branch: `gh repo view --json defaultBranchRef -q .defaultBranchRef.name`

3. **Gather commit information**:
   - Run `git log <base>..HEAD --oneline` to list commits being merged
   - Run `git diff <base>...HEAD --stat` for file change summary
   - Run `git diff <base>...HEAD` to see full diff

4. **Push branch if needed**:
   - Check if remote tracking exists: `git rev-parse --abbrev-ref @{upstream}`
   - If not, push with: `git push -u origin <branch-name>`

5. **Generate PR content**:
   - Create a concise, descriptive title from the changes
   - Write a summary section with bullet points describing key changes
   - Add a test plan section suggesting how to verify the changes
   - Include any breaking changes or migration notes if applicable

6. **Create the PR**:
   ```bash
   gh pr create --title "..." --body "$(cat <<'EOF'
   ## Summary
   - [Key changes as bullet points]

   ## Test Plan
   - [Verification steps]
   EOF
   )"
   ```

7. **Report the PR URL** to the user
