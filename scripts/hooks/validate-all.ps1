# Standalone Validation Script
# Can be run manually or called by hooks
# Performs full validation: format, lint, type check, tests

param(
    [switch]$Fix,
    [switch]$SkipTests
)

Write-Host "=== Full Project Validation ===" -ForegroundColor Cyan
Write-Host ""

$ErrorCount = 0

# 1. Formatting
Write-Host "[1/4] Code Formatting Check..." -ForegroundColor Yellow
if ($Fix) {
    & .venv\Scripts\ruff.exe format .
    Write-Host "[OK] Code formatted" -ForegroundColor Green
} else {
    & .venv\Scripts\ruff.exe format . --check
    if ($LASTEXITCODE -ne 0) {
        Write-Host "[FAIL] Formatting issues found - run with -Fix to auto-format" -ForegroundColor Red
        $ErrorCount++
    } else {
        Write-Host "[OK] Formatting passed" -ForegroundColor Green
    }
}
Write-Host ""

# 2. Linting
Write-Host "[2/4] Linting Check..." -ForegroundColor Yellow
if ($Fix) {
    & .venv\Scripts\ruff.exe check . --fix
} else {
    & .venv\Scripts\ruff.exe check .
}

if ($LASTEXITCODE -ne 0) {
    Write-Host "[FAIL] Linting issues found - run with -Fix to auto-fix" -ForegroundColor Red
    $ErrorCount++
} else {
    Write-Host "[OK] Linting passed" -ForegroundColor Green
}
Write-Host ""

# 3. Type Checking
Write-Host "[3/4] Type Checking..." -ForegroundColor Yellow
& .venv\Scripts\pyrefly.exe check

if ($LASTEXITCODE -ne 0) {
    Write-Host "[WARNING] Type errors found (non-blocking)" -ForegroundColor Yellow
} else {
    Write-Host "[OK] Type checking passed" -ForegroundColor Green
}
Write-Host ""

# 4. Tests
if (-not $SkipTests) {
    Write-Host "[4/4] Running Tests..." -ForegroundColor Yellow
    & .venv\Scripts\pytest.exe -v

    if ($LASTEXITCODE -ne 0) {
        Write-Host "[FAIL] Tests failed" -ForegroundColor Red
        $ErrorCount++
    } else {
        Write-Host "[OK] All tests passed" -ForegroundColor Green
    }
    Write-Host ""
} else {
    Write-Host "[4/4] Skipping tests (--SkipTests flag)" -ForegroundColor Yellow
    Write-Host ""
}

# Summary
Write-Host "=== Validation Complete ===" -ForegroundColor Cyan
if ($ErrorCount -eq 0) {
    Write-Host "Status: PASSED" -ForegroundColor Green
    exit 0
} else {
    Write-Host "Status: FAILED ($ErrorCount issues)" -ForegroundColor Red
    exit 1
}
