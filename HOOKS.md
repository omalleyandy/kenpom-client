# Development Hooks Guide

This project uses automated hooks to maintain code quality and streamline development workflows.

## Overview

Three types of hooks are configured:

1. **Git Pre-Commit Hook** - Validates code before commits
2. **Claude Code Post-Edit Hook** - Type checks after file edits
3. **Claude Code Session Start Hook** - Syncs environment on startup

## 1. Git Pre-Commit Hook

**Location:** `.git/hooks/pre-commit`

**Triggers:** Automatically runs before every `git commit`

**Validation Steps:**
1. Code formatting check (Ruff)
2. Linting (Ruff)
3. Type checking (Pyrefly) - warning only
4. Full test suite (Pytest)

**Duration:** ~30-60 seconds for full validation

### Usage

```powershell
# Normal commit - hook runs automatically
git add .
git commit -m "Your message"

# Bypass hook (not recommended)
git commit --no-verify -m "Your message"
```

### What Happens on Failure

- **Formatting issues** → Run `ruff format .` then retry commit
- **Linting issues** → Run `ruff check . --fix` then retry commit
- **Type errors** → Review and fix (or ignore if non-critical)
- **Test failures** → Fix failing tests then retry commit

## 2. Claude Code Post-Edit Hook

**Location:** `.claude/hooks/post-edit.ps1`

**Triggers:** After Claude Code edits any file

**Validation:**
- Runs full Pyrefly type check on entire project
- Non-blocking (warns but doesn't prevent edits)

### Configuration

Edit `.claude/hooks/config.json` to enable/disable:

```json
{
  "hooks": {
    "PostToolUse:Edit": {
      "enabled": true,  // Set to false to disable
      "blocking": false // Set to true to block on errors
    }
  }
}
```

## 3. Claude Code Session Start Hook

**Location:** `.claude/hooks/session-start.ps1`

**Triggers:** When starting a new Claude Code session

**Actions:**
1. Checks for remote git updates (doesn't auto-pull)
2. Syncs all dependencies with `uv sync --all-extras --dev`

### Configuration

Edit `.claude/hooks/session-start.ps1` to customize:

```powershell
# Auto-pull changes (currently disabled)
# Uncomment to enable:
# git pull origin main

# Change sync behavior
uv sync --all-extras --dev  # Full sync (current)
# uv sync --dev              # Dev dependencies only
# uv sync                    # Minimal sync
```

## Helper Scripts

### Full Validation

Run complete validation manually:

```powershell
# Check everything
powershell -ExecutionPolicy Bypass -File scripts/hooks/validate-all.ps1

# Auto-fix issues
powershell -ExecutionPolicy Bypass -File scripts/hooks/validate-all.ps1 -Fix

# Skip tests (faster)
powershell -ExecutionPolicy Bypass -File scripts/hooks/validate-all.ps1 -SkipTests
```

### Quick Check

Fast validation (format + lint only):

```powershell
powershell -ExecutionPolicy Bypass -File scripts/hooks/quick-check.ps1
```

## Disabling Hooks

### Temporarily Disable Git Hook

```powershell
# Single commit bypass
git commit --no-verify -m "Message"

# Rename hook to disable
mv .git/hooks/pre-commit .git/hooks/pre-commit.disabled
```

### Disable Claude Code Hooks

Edit `.claude/hooks/config.json`:

```json
{
  "hooks": {
    "PostToolUse:Edit": {
      "enabled": false  // Disable post-edit hook
    },
    "SessionStart": {
      "enabled": false  // Disable session start hook
    }
  }
}
```

## Troubleshooting

### Hook Not Running

**Git hooks:**
```powershell
# Check if executable
ls -l .git/hooks/pre-commit

# Make executable (if needed)
chmod +x .git/hooks/pre-commit
```

**Claude Code hooks:**
- Check `.claude/hooks/config.json` has `"enabled": true`
- Verify PowerShell execution policy allows scripts
- Check hook script paths are correct

### Hook Failing

```powershell
# Test hook manually
powershell -ExecutionPolicy Bypass -File .claude/hooks/post-edit.ps1 -EditedFile "test.py" -SessionId "test" -Cwd "."

# Check validation standalone
powershell -ExecutionPolicy Bypass -File scripts/hooks/validate-all.ps1
```

### Performance Issues

If pre-commit hook is too slow:

**Option 1: Run fewer checks**
Edit `.git/hooks/pre-commit` and comment out tests:

```bash
# 4. Running Tests
# echo "[4/4] Running test suite (pytest)..."
# if .venv/Scripts/pytest.exe -v; then
#     echo "${GREEN}[OK] All tests passed${NC}"
# ...
```

**Option 2: Run fast tests only**
```bash
# Instead of: .venv/Scripts/pytest.exe -v
.venv/Scripts/pytest.exe -v -k "not slow" --maxfail=1
```

**Option 3: Use quick-check script**
Replace validation in pre-commit with:
```bash
powershell -ExecutionPolicy Bypass -File scripts/hooks/quick-check.ps1
```

## Best Practices

1. **Let hooks run** - Don't bypass unless absolutely necessary
2. **Fix issues immediately** - Don't accumulate technical debt
3. **Run manual validation** - Before pushing or creating PRs
4. **Keep hooks fast** - Remove slow checks if blocking development
5. **Review type warnings** - Even if non-blocking, address them eventually

## Hook Execution Flow

```
┌─────────────────────────────────────────────────────────┐
│                    Development Workflow                  │
└─────────────────────────────────────────────────────────┘

Session Start
     │
     ├──> SessionStart Hook
     │         ├─> Check git remote
     │         └─> Sync dependencies (uv)
     │
Edit Files
     │
     ├──> PostEdit Hook (after Claude edits)
     │         └─> Run type check (pyrefly)
     │
Commit Changes
     │
     └──> Pre-Commit Hook
               ├─> Format check (ruff)
               ├─> Lint check (ruff)
               ├─> Type check (pyrefly)
               └─> Run tests (pytest)
```

## Summary

| Hook | Trigger | Duration | Blocking | Auto-Fix |
|------|---------|----------|----------|----------|
| **Pre-Commit** | `git commit` | 30-60s | Yes | No |
| **Post-Edit** | Claude edits file | 5-10s | No | No |
| **Session Start** | Session begins | 10-20s | No | Yes (deps) |

---

**Need help?** Check the troubleshooting section or run validation manually to diagnose issues.
