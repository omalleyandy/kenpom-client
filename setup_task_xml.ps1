# ===========================================================================
# Setup Windows Task Scheduler for Automated Odds Fetching (XML Method)
#
# This PowerShell script creates a scheduled task using XML to avoid
# PowerShell cmdlet XML format issues. The task:
# - Runs daily at 4:00 AM PST (7:00 AM EST)
# - Retries every 10 minutes if odds not available
# - Stops retrying after successful fetch or 2 hours
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
$deleteResult = schtasks /delete /tn $TaskName /f 2>&1
if ($LASTEXITCODE -eq 0) {
    Write-Host "Removed existing task." -ForegroundColor Yellow
} elseif ($LASTEXITCODE -eq 1) {
    Write-Host "No existing task found (this is OK)." -ForegroundColor Gray
} else {
    Write-Host "WARNING: Unexpected result when checking for existing task." -ForegroundColor Yellow
}

# Calculate dynamic start date (today at 4:00 AM, or tomorrow if already past 4:00 AM)
$now = Get-Date
$startTime = Get-Date -Hour 4 -Minute 0 -Second 0
if ($now -gt $startTime) {
    # If it's already past 4:00 AM today, start tomorrow
    $startTime = $startTime.AddDays(1)
}
$startBoundary = $startTime.ToString("yyyy-MM-ddTHH:mm:ss")

Write-Host "Task will start: $startBoundary" -ForegroundColor Cyan

# Create task using schtasks (more reliable than PowerShell cmdlets)
$xmlContent = @"
<?xml version="1.0" encoding="UTF-16"?>
<Task version="1.2" xmlns="http://schemas.microsoft.com/windows/2004/02/mit/task">
  <RegistrationInfo>
    <Description>$TaskDescription</Description>
  </RegistrationInfo>
  <Triggers>
    <CalendarTrigger>
      <StartBoundary>$startBoundary</StartBoundary>
      <Enabled>true</Enabled>
      <ScheduleByDay>
        <DaysInterval>1</DaysInterval>
      </ScheduleByDay>
    </CalendarTrigger>
  </Triggers>
  <Principals>
    <Principal id="Author">
      <UserId>$env:USERDOMAIN\$env:USERNAME</UserId>
      <LogonType>InteractiveToken</LogonType>
      <RunLevel>HighestAvailable</RunLevel>
    </Principal>
  </Principals>
  <Settings>
    <MultipleInstancesPolicy>IgnoreNew</MultipleInstancesPolicy>
    <DisallowStartIfOnBatteries>false</DisallowStartIfOnBatteries>
    <StopIfGoingOnBatteries>false</StopIfGoingOnBatteries>
    <AllowHardTerminate>true</AllowHardTerminate>
    <StartWhenAvailable>true</StartWhenAvailable>
    <RunOnlyIfNetworkAvailable>false</RunOnlyIfNetworkAvailable>
    <IdleSettings>
      <StopOnIdleEnd>false</StopOnIdleEnd>
      <RestartOnIdle>false</RestartOnIdle>
    </IdleSettings>
    <AllowStartOnDemand>true</AllowStartOnDemand>
    <Enabled>true</Enabled>
    <Hidden>false</Hidden>
    <RunOnlyIfIdle>false</RunOnlyIfIdle>
    <WakeToRun>false</WakeToRun>
    <ExecutionTimeLimit>PT2H</ExecutionTimeLimit>
    <Priority>7</Priority>
  </Settings>
  <Actions Context="Author">
    <Exec>
      <Command>$ScriptPath</Command>
      <WorkingDirectory>$ProjectRoot</WorkingDirectory>
    </Exec>
  </Actions>
</Task>
"@

# Save XML to temp file
$xmlPath = Join-Path $env:TEMP "task_$TaskName.xml"
try {
    $xmlContent | Out-File -FilePath $xmlPath -Encoding Unicode -ErrorAction Stop
    Write-Host "Created temporary XML file: $xmlPath" -ForegroundColor Gray
} catch {
    Write-Host "ERROR: Failed to create XML file: $_" -ForegroundColor Red
    exit 1
}

# Create task using schtasks
Write-Host "Creating scheduled task..." -ForegroundColor Yellow
$createResult = schtasks /create /tn $TaskName /xml $xmlPath /f 2>&1
$createExitCode = $LASTEXITCODE

# Clean up temp file
try {
    Remove-Item $xmlPath -Force -ErrorAction Stop
} catch {
    Write-Host "WARNING: Failed to remove temp file: $_" -ForegroundColor Yellow
}

# Validate task creation
if ($createExitCode -eq 0) {
    Write-Host "`nScheduled task created successfully!" -ForegroundColor Green
    
    # Verify task exists
    $verifyResult = schtasks /query /tn $TaskName /fo LIST 2>&1
    if ($LASTEXITCODE -eq 0) {
        Write-Host "Task verification: SUCCESS" -ForegroundColor Green
    } else {
        Write-Host "WARNING: Task created but verification failed." -ForegroundColor Yellow
    }
    
    Write-Host "`nTask Details:" -ForegroundColor Cyan
    Write-Host "  - Name: $TaskName"
    Write-Host "  - Runs daily at 4:00 AM PST"
    Write-Host "  - Retries every 10 minutes if odds not available"
    Write-Host "  - Stops after 2 hours or successful fetch"
    Write-Host "  - Logs saved to: $LogPath"
    Write-Host "  - Start time: $startBoundary"
    
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
} else {
    Write-Host "`nERROR: Failed to create scheduled task!" -ForegroundColor Red
    Write-Host "Exit code: $createExitCode" -ForegroundColor Red
    Write-Host "Error output: $createResult" -ForegroundColor Red
    Write-Host "`nTroubleshooting:" -ForegroundColor Yellow
    Write-Host "  1. Ensure you're running PowerShell as Administrator" -ForegroundColor White
    Write-Host "  2. Check that fetch_odds_scheduled.bat exists at: $ScriptPath" -ForegroundColor White
    Write-Host "  3. Verify Task Scheduler service is running" -ForegroundColor White
    exit 1
}
