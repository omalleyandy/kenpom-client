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

REM Setup paths
set "PROJECT_ROOT=%~dp0"
set "LOGDIR=!PROJECT_ROOT!logs"
set "LOGFILE=!LOGDIR!\odds_fetch.log"
set "PYTHON_EXE=!PROJECT_ROOT!.venv\Scripts\python.exe"

REM Create logs directory if needed
if not exist "!LOGDIR!" mkdir "!LOGDIR!"

REM Verify Python exists
if not exist "!PYTHON_EXE!" (
    echo [%date% %time%] ERROR: Python not found at "!PYTHON_EXE!" >> "!LOGFILE!"
    echo [%date% %time%] Run 'uv venv' and 'uv sync' to create the virtual environment >> "!LOGFILE!"
    exit /b 1
)

REM Retry configuration: 12 attempts x 10 minutes = 2 hours
set MAX_ATTEMPTS=12
set RETRY_DELAY=600
set ATTEMPT=1

:RETRY_LOOP
echo. >> "!LOGFILE!"
echo [%date% %time%] ======================================== >> "!LOGFILE!"
echo [%date% %time%] Attempt !ATTEMPT! of !MAX_ATTEMPTS! >> "!LOGFILE!"
echo [%date% %time%] ======================================== >> "!LOGFILE!"

REM Run fetch-odds command
echo [%date% %time%] Fetching College Basketball odds from overtime.ag... >> "!LOGFILE!"
call "!PYTHON_EXE!" -m kenpom_client.cli fetch-odds >> "!LOGFILE!" 2>&1
set "FETCH_RESULT=!errorlevel!"

REM Check if odds were successfully fetched
if !FETCH_RESULT! equ 0 (
    echo [%date% %time%] SUCCESS: Odds fetched successfully >> "!LOGFILE!"

    REM Fetch fresh HCA data
    echo [%date% %time%] Fetching Home Court Advantage data from kenpom.com... >> "!LOGFILE!"
    call "!PYTHON_EXE!" -m kenpom_client.hca_scraper --headless >> "!LOGFILE!" 2>&1
    if !errorlevel! equ 0 (
        echo [%date% %time%] SUCCESS: HCA data fetched >> "!LOGFILE!"
    ) else (
        echo [%date% %time%] WARNING: HCA fetch failed - using existing snapshot or default 3.5 >> "!LOGFILE!"
    )

    REM Fetch fresh Referee Ratings
    echo [%date% %time%] Fetching Referee Ratings from kenpom.com... >> "!LOGFILE!"
    call "!PYTHON_EXE!" -m kenpom_client.ref_ratings_scraper --headless >> "!LOGFILE!" 2>&1
    if !errorlevel! equ 0 (
        echo [%date% %time%] SUCCESS: Referee ratings fetched >> "!LOGFILE!"
    ) else (
        echo [%date% %time%] WARNING: Referee ratings fetch failed - using existing snapshot >> "!LOGFILE!"
    )

    REM Run analyze_todays_games.py
    echo [%date% %time%] Generating game predictions... >> "!LOGFILE!"
    call "!PYTHON_EXE!" analyze_todays_games.py >> "!LOGFILE!" 2>&1
    if !errorlevel! equ 0 (
        echo [%date% %time%] SUCCESS: Predictions generated >> "!LOGFILE!"
    ) else (
        echo [%date% %time%] WARNING: Prediction generation failed >> "!LOGFILE!"
    )

    REM Run calculate_real_edge.py
    echo [%date% %time%] Calculating betting edges with Kelly Criterion... >> "!LOGFILE!"
    call "!PYTHON_EXE!" calculate_real_edge.py >> "!LOGFILE!" 2>&1
    if !errorlevel! equ 0 (
        echo [%date% %time%] SUCCESS: Betting edge analysis complete >> "!LOGFILE!"
    ) else (
        echo [%date% %time%] WARNING: Betting edge analysis failed >> "!LOGFILE!"
    )

    echo [%date% %time%] Workflow completed successfully >> "!LOGFILE!"
    exit /b 0
)

REM Odds not available - check if we should retry
echo [%date% %time%] WARNING: No odds available yet >> "!LOGFILE!"
if !ATTEMPT! lss !MAX_ATTEMPTS! (
    set /a ATTEMPT+=1
    echo [%date% %time%] Waiting 10 minutes before retry... >> "!LOGFILE!"
    timeout /t !RETRY_DELAY! /nobreak > nul
    goto RETRY_LOOP
)

echo [%date% %time%] ERROR: Max retry attempts reached - no odds found >> "!LOGFILE!"
exit /b 1
