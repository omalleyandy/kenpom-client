# ===========================================================================
# Setup Windows Task Scheduler for Automated Odds Fetching
#
# This PowerShell script creates a scheduled task that:
# - Runs daily at 4:00 AM PST (7:00 AM EST)
# - Retries every 10 minutes if odds not available
# - Stops retrying after successful fetch or 2 hours
# ===========================================================================

# Require administrator privileges
#Requires -RunAsAdministrator

# Configuration
$TaskName = "FetchOvertimeCollegeBasketballOdds"
$TaskDescription = "Automatically fetch College Basketball odds from overtime.ag at 4:00 AM PST daily"
$ProjectRoot = Split-Path -Parent $MyInvocation.MyCommand.Path
$ScriptPath = Join-Path $ProjectRoot "fetch_odds_scheduled.bat"
$LogPath = Join-Path $ProjectRoot "logs\odds_fetch.log"

# Ensure logs directory exists
$LogDir = Split-Path -Parent $LogPath
if (!(Test-Path $LogDir)) {
    New-Item -ItemType Directory -Path $LogDir -Force | Out-Null
}

Write-Host "Creating scheduled task: $TaskName" -ForegroundColor Green
Write-Host "Script location: $ScriptPath" -ForegroundColor Cyan
Write-Host "Log location: $LogPath" -ForegroundColor Cyan

# Delete existing task if it exists
$ExistingTask = Get-ScheduledTask -TaskName $TaskName -ErrorAction SilentlyContinue
if ($ExistingTask) {
    Write-Host "Removing existing task..." -ForegroundColor Yellow
    Unregister-ScheduledTask -TaskName $TaskName -Confirm:$false
}

# Create trigger: Daily at 4:00 AM PST (adjust for your timezone)
$Trigger = New-ScheduledTaskTrigger -Daily -At "4:00AM"

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
Register-ScheduledTask `
    -TaskName $TaskName `
    -Description $TaskDescription `
    -Trigger $Trigger `
    -Action $Action `
    -Settings $Settings `
    -Principal $Principal `
    -Force

Write-Host "`nScheduled task created successfully!" -ForegroundColor Green
Write-Host "`nTask Details:" -ForegroundColor Cyan
Write-Host "  - Runs daily at 4:00 AM PST"
Write-Host "  - Retries every 10 minutes if odds not available"
Write-Host "  - Stops after 2 hours or successful fetch"
Write-Host "  - Logs saved to: $LogPath"

Write-Host "`nTo test the task now, run:" -ForegroundColor Yellow
Write-Host "  Start-ScheduledTask -TaskName '$TaskName'" -ForegroundColor White

Write-Host "`nTo view task status:" -ForegroundColor Yellow
Write-Host "  Get-ScheduledTask -TaskName '$TaskName' | Get-ScheduledTaskInfo" -ForegroundColor White

Write-Host "`nTo disable the task:" -ForegroundColor Yellow
Write-Host "  Disable-ScheduledTask -TaskName '$TaskName'" -ForegroundColor White

Write-Host "`nTo remove the task:" -ForegroundColor Yellow
Write-Host "  Unregister-ScheduledTask -TaskName '$TaskName' -Confirm:`$false" -ForegroundColor White
