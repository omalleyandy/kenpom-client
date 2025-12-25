# List Pull Requests

List pull requests with optional filters.

## Arguments
- `$ARGUMENTS` - Filter options (optional): state, author, label, or search term

## Instructions

1. **Parse arguments** from `$ARGUMENTS`:
   - "open" / "closed" / "merged" / "all" → filter by state
   - "mine" → show only your PRs
   - "by <author>" → filter by author
   - "label <name>" → filter by label
   - Search term → search PR titles/bodies

2. **Build the gh pr list command**:
   - Default: `gh pr list --limit 20`
   - With state: `gh pr list --state <state>`
   - By author: `gh pr list --author <author>`
   - With search: `gh pr list --search "<term>"`
   - JSON for details: `gh pr list --json number,title,author,state,createdAt,updatedAt,labels,reviewDecision`

3. **Present results in a table**:
   ```
   ## Open Pull Requests

   | # | Title | Author | Created | Status |
   |---|-------|--------|---------|--------|
   | 123 | Fix bug in client | @user | 2d ago | Review Required |

   ## Summary
   - Total: X PRs
   - Needs review: Y
   - Approved: Z
   ```

4. **Highlight important info**:
   - PRs that need review
   - PRs with failing checks
   - Stale PRs (no activity in 7+ days)
   - Your PRs awaiting review

## Examples
- `/pr-list` - List open PRs
- `/pr-list all` - List all PRs including closed
- `/pr-list mine` - List your PRs
- `/pr-list by omalleyandy` - List PRs by specific author
- `/pr-list merged` - List recently merged PRs
