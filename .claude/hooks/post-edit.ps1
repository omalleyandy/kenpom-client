# Claude Code Post-Edit Hook - Full Type Checking
# Runs after Claude Code edits files
# Triggers full project type checking with Pyrefly

param(
    [string]$EditedFile,
    [string]$SessionId,
    [string]$Cwd
)

Write-Host "=== Post-Edit Hook: Running Type Check ===" -ForegroundColor Cyan
Write-Host "Edited file: $EditedFile"
Write-Host ""

# Change to project directory
Set-Location $Cwd

# Run full type check
Write-Host "Running Pyrefly type checker..." -ForegroundColor Yellow
& .venv\Scripts\pyrefly.exe check

if ($LASTEXITCODE -eq 0) {
    Write-Host "[OK] Type checking passed" -ForegroundColor Green
    exit 0
} else {
    Write-Host "[WARNING] Type errors detected - review above" -ForegroundColor Yellow
    # Don't block the edit, just inform
    exit 0
}
