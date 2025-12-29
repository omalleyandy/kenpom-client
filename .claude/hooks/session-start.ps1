# Claude Code Session Start Hook - Dependency Sync
# Runs when starting a new Claude Code session
# Syncs all dependencies and pulls latest changes

param(
    [string]$SessionId,
    [string]$Cwd
)

Write-Host "=== Session Start Hook: Initializing Environment ===" -ForegroundColor Cyan
Write-Host "Session ID: $SessionId"
Write-Host ""

# Change to project directory
Set-Location $Cwd

# 1. Git Pull (optional - update from remote)
Write-Host "[1/2] Checking for remote updates..." -ForegroundColor Yellow
git fetch --quiet
$LOCAL = git rev-parse @
$REMOTE = git rev-parse "@{u}"

if ($LOCAL -ne $REMOTE) {
    Write-Host "Remote changes detected - consider pulling latest" -ForegroundColor Yellow
    Write-Host "Run: git pull"
} else {
    Write-Host "[OK] Local is up to date with remote" -ForegroundColor Green
}
Write-Host ""

# 2. Sync Dependencies
Write-Host "[2/2] Syncing dependencies with uv..." -ForegroundColor Yellow
& uv sync --all-extras --dev

if ($LASTEXITCODE -eq 0) {
    Write-Host "[OK] Dependencies synced successfully" -ForegroundColor Green
} else {
    Write-Host "[WARNING] Dependency sync had issues" -ForegroundColor Yellow
}
Write-Host ""

Write-Host "=== Environment Ready ===" -ForegroundColor Green
Write-Host ""
exit 0
