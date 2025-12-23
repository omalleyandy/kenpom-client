@echo off
REM ===========================================================================
REM Scheduled Odds Fetcher for overtime.ag College Basketball
REM
REM This script runs via Windows Task Scheduler to automatically fetch
REM College Basketball odds from overtime.ag at 4:00 AM PST daily.
REM It will retry every 10 minutes if odds are not yet available.
REM ===========================================================================

REM Set working directory to project root
cd /d %~dp0

REM Setup logging
set LOGFILE=%~dp0logs\odds_fetch.log
if not exist "%~dp0logs" mkdir "%~dp0logs"

REM Call main logic with output redirection
call :main >> "%LOGFILE%" 2>&1
exit /b %errorlevel%

:main
REM Retry configuration: 12 attempts x 10 minutes = 2 hours
set MAX_ATTEMPTS=12
set RETRY_DELAY=600
set ATTEMPT=1

REM Get absolute paths using batch file location
set PROJECT_ROOT=%~dp0
set UV_EXE=%USERPROFILE%\.local\bin\uv.exe
set PYTHON_EXE=%PROJECT_ROOT%.venv\Scripts\python.exe

:RETRY_LOOP
echo.
echo [%date% %time%] ========================================
echo [%date% %time%] Attempt %ATTEMPT% of %MAX_ATTEMPTS%
echo [%date% %time%] ========================================

REM Activate virtual environment and run fetch-odds command
echo [%date% %time%] Fetching College Basketball odds from overtime.ag...
"%PYTHON_EXE%" -m kenpom_client.cli fetch-odds

REM Check if odds were successfully fetched
if %errorlevel% equ 0 (
    echo [%date% %time%] SUCCESS: Odds fetched successfully

    REM Optional: Run analyze_todays_games.py to generate predictions
    echo [%date% %time%] Generating game predictions...
    "%PYTHON_EXE%" analyze_todays_games.py

    if %errorlevel% equ 0 (
        echo [%date% %time%] SUCCESS: Predictions generated
    ) else (
        echo [%date% %time%] WARNING: Prediction generation failed
    )

    REM Run calculate_real_edge.py for detailed betting edge analysis
    echo [%date% %time%] Calculating betting edges with Kelly Criterion...
    "%PYTHON_EXE%" calculate_real_edge.py

    if %errorlevel% equ 0 (
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
    if %ATTEMPT% lss %MAX_ATTEMPTS% (
        set /a ATTEMPT+=1
        echo [%date% %time%] Waiting 10 minutes before retry...
        timeout /t %RETRY_DELAY% /nobreak
        goto RETRY_LOOP
    ) else (
        echo [%date% %time%] ERROR: Max retry attempts reached - no odds found
        exit /b 1
    )
)
