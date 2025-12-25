# Git Log History

Show formatted git history with various filter options.

## Arguments
- `$ARGUMENTS` - Filter options (optional): number of commits, branch name, file path, author, date range, or search term

## Instructions

1. **Parse arguments** from `$ARGUMENTS`:
   - Number (e.g., "20") → show that many commits
   - Branch name (e.g., "main", "feature/xyz") → show commits on that branch
   - File path (e.g., "src/client.py") → show commits touching that file
   - "by <author>" → filter by author
   - "since <date>" or "until <date>" → date range filter
   - "search <term>" → search commit messages

2. **Build the git log command** based on filters:
   - Default: `git log --oneline -20`
   - With graph: `git log --oneline --graph --all -20` (for visualizing branches)
   - Detailed: `git log --format="%h %ad | %s [%an]" --date=short -20`

3. **Execute and display** the formatted output

4. **Provide context**:
   - Explain any merge commits or branch points
   - Highlight important commits (breaking changes, major features)
   - If viewing a file's history, note when it was created

## Examples
- `/git-log` - Show last 20 commits
- `/git-log 50` - Show last 50 commits
- `/git-log src/client.py` - Show commits for specific file
- `/git-log by andy` - Show commits by author containing "andy"
- `/git-log since 2025-01-01` - Show commits since date
- `/git-log search "fix bug"` - Search commit messages
- `/git-log graph` - Show visual branch graph
