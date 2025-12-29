# Quick Validation Script
# Fast checks only - for rapid feedback during development
# Runs: format check + lint (no tests, no type check)

Write-Host "=== Quick Validation ===" -ForegroundColor Cyan
Write-Host ""

$ErrorCount = 0

# 1. Format Check
Write-Host "[1/2] Format Check..." -ForegroundColor Yellow
& .venv\Scripts\ruff.exe format . --check

if ($LASTEXITCODE -ne 0) {
    Write-Host "[FAIL] Formatting issues" -ForegroundColor Red
    $ErrorCount++
} else {
    Write-Host "[OK] Formatting passed" -ForegroundColor Green
}
Write-Host ""

# 2. Lint Check
Write-Host "[2/2] Lint Check..." -ForegroundColor Yellow
& .venv\Scripts\ruff.exe check .

if ($LASTEXITCODE -ne 0) {
    Write-Host "[FAIL] Linting issues" -ForegroundColor Red
    $ErrorCount++
} else {
    Write-Host "[OK] Linting passed" -ForegroundColor Green
}
Write-Host ""

if ($ErrorCount -eq 0) {
    Write-Host "Quick check PASSED" -ForegroundColor Green
    exit 0
} else {
    Write-Host "Quick check FAILED" -ForegroundColor Red
    exit 1
}
