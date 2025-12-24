@echo off
setlocal EnableDelayedExpansion
REM ===========================================================================
REM Scheduled Odds Fetcher for overtime.ag College Basketball
REM
REM This script runs via Windows Task Scheduler to automatically fetch
REM College Basketball odds from overtime.ag at 4:00 AM PST daily.
REM It will retry every 10 minutes if odds are not yet available.
REM
REM NOTE: Uses delayed expansion to handle paths with spaces (e.g., OneDrive)
REM ===========================================================================

REM Set working directory to project root (handle spaces in path)
cd /d "%~dp0"

REM Setup logging (quote all paths for spaces)
set "PROJECT_ROOT=%~dp0"
set "LOGFILE=!PROJECT_ROOT!logs\odds_fetch.log"
if not exist "!PROJECT_ROOT!logs" mkdir "!PROJECT_ROOT!logs"

REM Call main logic with output redirection
call :main >> "!LOGFILE!" 2>&1
exit /b !errorlevel!

:main
REM Retry configuration: 12 attempts x 10 minutes = 2 hours
set MAX_ATTEMPTS=12
set RETRY_DELAY=600
set ATTEMPT=1

REM Get absolute paths using batch file location (quoted for spaces)
set "UV_EXE=!USERPROFILE!\.local\bin\uv.exe"
set "PYTHON_EXE=!PROJECT_ROOT!.venv\Scripts\python.exe"

REM Verify Python exists
if not exist "!PYTHON_EXE!" (
    echo [%date% %time%] ERROR: Python not found at "!PYTHON_EXE!"
    echo [%date% %time%] Run 'uv venv' and 'uv sync' to create the virtual environment
    exit /b 1
)

:RETRY_LOOP
echo.
echo [%date% %time%] ========================================
echo [%date% %time%] Attempt !ATTEMPT! of !MAX_ATTEMPTS!
echo [%date% %time%] ========================================

REM Run fetch-odds command using call to properly handle paths with spaces
echo [%date% %time%] Fetching College Basketball odds from overtime.ag...
call "!PYTHON_EXE!" -m kenpom_client.cli fetch-odds
set "FETCH_RESULT=!errorlevel!"

REM Check if odds were successfully fetched
if !FETCH_RESULT! equ 0 (
    echo [%date% %time%] SUCCESS: Odds fetched successfully

    REM Fetch fresh HCA (Home Court Advantage) data for team-specific predictions
    REM This runs in headless mode - if CAPTCHA appears, falls back to existing snapshot
    echo [%date% %time%] Fetching Home Court Advantage data from kenpom.com...
    call "!PYTHON_EXE!" -m kenpom_client.hca_scraper --headless

    if !errorlevel! equ 0 (
        echo [%date% %time%] SUCCESS: HCA data fetched
    ) else (
        echo [%date% %time%] WARNING: HCA fetch failed - using existing snapshot or default 3.5
    )

    REM Fetch fresh Referee Ratings (FAA - Fouls Above Average) data
    REM This runs in headless mode - if CAPTCHA appears, falls back to existing snapshot
    echo [%date% %time%] Fetching Referee Ratings (FAA) from kenpom.com...
    call "!PYTHON_EXE!" -m kenpom_client.ref_ratings_scraper --headless

    if !errorlevel! equ 0 (
        echo [%date% %time%] SUCCESS: Referee ratings fetched
    ) else (
        echo [%date% %time%] WARNING: Referee ratings fetch failed - using existing snapshot
    )

    REM Run analyze_todays_games.py to generate predictions
    echo [%date% %time%] Generating game predictions...
    call "!PYTHON_EXE!" analyze_todays_games.py

    if !errorlevel! equ 0 (
        echo [%date% %time%] SUCCESS: Predictions generated
    ) else (
        echo [%date% %time%] WARNING: Prediction generation failed
    )

    REM Run calculate_real_edge.py for detailed betting edge analysis
    echo [%date% %time%] Calculating betting edges with Kelly Criterion...
    call "!PYTHON_EXE!" calculate_real_edge.py

    if !errorlevel! equ 0 (
        echo [%date% %time%] SUCCESS: Betting edge analysis complete
    ) else (
        echo [%date% %time%] WARNING: Betting edge analysis failed
    )

    REM Exit successfully - stop retrying
    echo [%date% %time%] Workflow completed successfully
    exit /b 0
) else (
    echo [%date% %time%] WARNING: No odds available yet

    REM Check if we should retry
    if !ATTEMPT! lss !MAX_ATTEMPTS! (
        set /a ATTEMPT+=1
        echo [%date% %time%] Waiting 10 minutes before retry...
        timeout /t !RETRY_DELAY! /nobreak
        goto RETRY_LOOP
    ) else (
        echo [%date% %time%] ERROR: Max retry attempts reached - no odds found
        exit /b 1
    )
)
