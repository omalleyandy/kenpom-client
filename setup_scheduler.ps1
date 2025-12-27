# ===========================================================================
# Setup Windows Task Scheduler for Automated Odds Fetching
#
# This PowerShell script creates a scheduled task that:
# - Runs daily at 4:00 AM PST (7:00 AM EST)
# - Retries every 10 minutes if odds not available
# - Stops retrying after successful fetch or 2 hours
#
# NOTE: This script uses PowerShell cmdlets which may have XML format issues.
# For more reliable task creation, use setup_task_xml.ps1 instead.
# ===========================================================================

# Configuration
$TaskName = "FetchOvertimeCollegeBasketballOdds"
$TaskDescription = "Automatically fetch College Basketball odds from overtime.ag at 4:00 AM PST daily"
$ProjectRoot = Split-Path -Parent $MyInvocation.MyCommand.Path
$ScriptPath = Join-Path $ProjectRoot "fetch_odds_scheduled.bat"
$LogPath = Join-Path $ProjectRoot "logs\odds_fetch.log"

# Error handling: Check if script is running as administrator
$isAdmin = ([Security.Principal.WindowsPrincipal] [Security.Principal.WindowsIdentity]::GetCurrent()).IsInRole([Security.Principal.WindowsBuiltInRole]::Administrator)
if (-not $isAdmin) {
    Write-Host "WARNING: Not running as administrator. Task creation may fail." -ForegroundColor Yellow
    Write-Host "Consider running PowerShell as Administrator for best results." -ForegroundColor Yellow
    Write-Host "Alternatively, use setup_task_xml.ps1 which is more reliable." -ForegroundColor Yellow
}

# Validation: Check if batch script exists
if (!(Test-Path $ScriptPath)) {
    Write-Host "ERROR: Batch script not found at: $ScriptPath" -ForegroundColor Red
    Write-Host "Please ensure fetch_odds_scheduled.bat exists in the project root." -ForegroundColor Red
    exit 1
}

# Ensure logs directory exists
$LogDir = Split-Path -Parent $LogPath
if (!(Test-Path $LogDir)) {
    try {
        New-Item -ItemType Directory -Path $LogDir -Force | Out-Null
        Write-Host "Created logs directory: $LogDir" -ForegroundColor Green
    } catch {
        Write-Host "ERROR: Failed to create logs directory: $_" -ForegroundColor Red
        exit 1
    }
}

Write-Host "Creating scheduled task: $TaskName" -ForegroundColor Green
Write-Host "Script location: $ScriptPath" -ForegroundColor Cyan
Write-Host "Log location: $LogPath" -ForegroundColor Cyan

# Delete existing task if it exists
Write-Host "Checking for existing task..." -ForegroundColor Yellow
try {
    $ExistingTask = Get-ScheduledTask -TaskName $TaskName -ErrorAction SilentlyContinue
    if ($ExistingTask) {
        Write-Host "Removing existing task..." -ForegroundColor Yellow
        Unregister-ScheduledTask -TaskName $TaskName -Confirm:$false -ErrorAction Stop
        Write-Host "Existing task removed." -ForegroundColor Green
    } else {
        Write-Host "No existing task found (this is OK)." -ForegroundColor Gray
    }
} catch {
    Write-Host "WARNING: Error checking/removing existing task: $_" -ForegroundColor Yellow
}

# Calculate dynamic start date (today at 4:00 AM, or tomorrow if already past 4:00 AM)
$now = Get-Date
$startTime = Get-Date -Hour 4 -Minute 0 -Second 0
if ($now -gt $startTime) {
    # If it's already past 4:00 AM today, start tomorrow
    $startTime = $startTime.AddDays(1)
}

# Create trigger: Daily at 4:00 AM PST (adjust for your timezone)
$Trigger = New-ScheduledTaskTrigger -Daily -At $startTime
Write-Host "Task will start: $($startTime.ToString('yyyy-MM-dd HH:mm:ss'))" -ForegroundColor Cyan

# Create action: Run batch script and redirect output to log
$Action = New-ScheduledTaskAction `
    -Execute "cmd.exe" `
    -Argument "/c `"$ScriptPath`" >> `"$LogPath`" 2>&1" `
    -WorkingDirectory $ProjectRoot

# Task settings (without RestartInterval to avoid XML format issues)
$Settings = New-ScheduledTaskSettingsSet `
    -AllowStartIfOnBatteries `
    -DontStopIfGoingOnBatteries `
    -StartWhenAvailable `
    -ExecutionTimeLimit (New-TimeSpan -Hours 2) `
    -MultipleInstances IgnoreNew

# Create principal (run as current user)
$Principal = New-ScheduledTaskPrincipal -UserId $env:USERNAME -RunLevel Highest

# Register the task
Write-Host "Registering scheduled task..." -ForegroundColor Yellow
try {
    Register-ScheduledTask `
        -TaskName $TaskName `
        -Description $TaskDescription `
        -Trigger $Trigger `
        -Action $Action `
        -Settings $Settings `
        -Principal $Principal `
        -Force `
        -ErrorAction Stop
    
    Write-Host "`nScheduled task created successfully!" -ForegroundColor Green
    
    # Verify task exists
    try {
        $verifyTask = Get-ScheduledTask -TaskName $TaskName -ErrorAction Stop
        Write-Host "Task verification: SUCCESS" -ForegroundColor Green
    } catch {
        Write-Host "WARNING: Task created but verification failed: $_" -ForegroundColor Yellow
    }
    
    Write-Host "`nTask Details:" -ForegroundColor Cyan
    Write-Host "  - Name: $TaskName"
    Write-Host "  - Runs daily at 4:00 AM PST"
    Write-Host "  - Retries every 10 minutes if odds not available"
    Write-Host "  - Stops after 2 hours or successful fetch"
    Write-Host "  - Logs saved to: $LogPath"
    Write-Host "  - Start time: $($startTime.ToString('yyyy-MM-dd HH:mm:ss'))"
    
    Write-Host "`nUseful Commands:" -ForegroundColor Yellow
    Write-Host "  Test task now:" -ForegroundColor White
    Write-Host "    Start-ScheduledTask -TaskName '$TaskName'" -ForegroundColor Gray
    Write-Host "  View task status:" -ForegroundColor White
    Write-Host "    Get-ScheduledTask -TaskName '$TaskName' | Get-ScheduledTaskInfo" -ForegroundColor Gray
    Write-Host "  View logs:" -ForegroundColor White
    Write-Host "    Get-Content logs\odds_fetch.log -Tail 50" -ForegroundColor Gray
    Write-Host "  Disable task:" -ForegroundColor White
    Write-Host "    Disable-ScheduledTask -TaskName '$TaskName'" -ForegroundColor Gray
    Write-Host "  Remove task:" -ForegroundColor White
    Write-Host "    Unregister-ScheduledTask -TaskName '$TaskName' -Confirm:`$false" -ForegroundColor Gray
} catch {
    Write-Host "`nERROR: Failed to create scheduled task!" -ForegroundColor Red
    Write-Host "Error: $_" -ForegroundColor Red
    Write-Host "`nTroubleshooting:" -ForegroundColor Yellow
    Write-Host "  1. Ensure you're running PowerShell as Administrator" -ForegroundColor White
    Write-Host "  2. Check that fetch_odds_scheduled.bat exists at: $ScriptPath" -ForegroundColor White
    Write-Host "  3. Verify Task Scheduler service is running" -ForegroundColor White
    Write-Host "  4. Try using setup_task_xml.ps1 instead (more reliable)" -ForegroundColor White
    exit 1
}
