# Git Blame

Find who changed specific code and when.

## Arguments
- `$ARGUMENTS` - File path and optionally line numbers or search term (required)

## Instructions

1. **Parse arguments** from `$ARGUMENTS`:
   - File path (required): e.g., "src/client.py"
   - Line range (optional): e.g., "src/client.py:50-75" or "src/client.py:50"
   - Search term (optional): e.g., "src/client.py search def connect"

2. **Validate the file exists**:
   - Run `test -f <filepath>` to verify
   - If not found, search for similar files and suggest alternatives

3. **Run git blame**:
   - Full file: `git blame <file>`
   - Line range: `git blame -L <start>,<end> <file>`
   - With dates: `git blame --date=short <file>`

4. **If searching for specific code**:
   - First find line numbers: `grep -n "<search term>" <file>`
   - Then blame those specific lines

5. **Analyze and present**:
   ```
   ## File: <filepath>

   ## Blame Results
   [Formatted blame output showing: commit, author, date, line content]

   ## Summary
   - Primary contributors to this code
   - When this code was last modified
   - Related commits that might provide context
   ```

6. **Offer to dig deeper**:
   - Show full commit message for any commit: `git show <sha> --stat`
   - Show the PR that introduced a change: `gh pr list --search <sha>`

## Examples
- `/git-blame src/client.py` - Blame entire file
- `/git-blame src/client.py:50-75` - Blame specific lines
- `/git-blame src/client.py search "def connect"` - Find and blame specific function
