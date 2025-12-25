# Git Diff

Show and analyze changes between commits, branches, or working directory.

## Arguments
- `$ARGUMENTS` - What to diff (optional): branch names, commit SHAs, file paths, or "staged"

## Instructions

1. **Parse arguments** from `$ARGUMENTS`:
   - Empty → show unstaged changes (`git diff`)
   - "staged" → show staged changes (`git diff --staged`)
   - Single ref (e.g., "main") → diff current HEAD against that ref
   - Two refs (e.g., "main..feature") → diff between refs
   - File path → filter diff to that file
   - Commit SHA → show that specific commit's changes

2. **Run appropriate git diff command**:
   - `git diff` - unstaged changes
   - `git diff --staged` - staged changes
   - `git diff <ref>` - compare HEAD to ref
   - `git diff <ref1>..<ref2>` - compare two refs
   - `git diff <ref> -- <file>` - filtered to specific file
   - `git show <sha>` - show specific commit

3. **Analyze the diff**:
   - Summarize files changed with additions/deletions
   - Highlight significant changes
   - Note any potential issues (large files, sensitive data, etc.)

4. **Present results**:
   ```
   ## Diff Summary
   - Files changed: X
   - Insertions: +Y
   - Deletions: -Z

   ## Files Modified
   [List of files with change type]

   ## Detailed Changes
   [Analysis of significant changes]
   ```

## Examples
- `/git-diff` - Show unstaged changes
- `/git-diff staged` - Show staged changes
- `/git-diff main` - Compare current branch to main
- `/git-diff main..feature` - Compare two branches
- `/git-diff abc123` - Show specific commit
- `/git-diff src/client.py` - Diff specific file
