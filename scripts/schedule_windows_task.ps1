# Registers a Windows Task Scheduler task that runs the daily pipeline at the
# time configured in config/config.json (schedule.time). Run this once,
# elevated (Run as Administrator) is not required for a per-user task.
#
# Usage: powershell -File scripts\schedule_windows_task.ps1

$ErrorActionPreference = "Stop"
$root = Split-Path -Parent $PSScriptRoot
$config = Get-Content (Join-Path $root "config\config.json") | ConvertFrom-Json
$time = $config.schedule.time  # "HH:MM"

$python = Join-Path $root ".venv\Scripts\python.exe"
$action = New-ScheduledTaskAction -Execute $python -Argument "-m pipeline.run" -WorkingDirectory $root
$trigger = New-ScheduledTaskTrigger -Daily -At $time
$settings = New-ScheduledTaskSettingsSet -StartWhenAvailable -DontStopOnIdleEnd

Register-ScheduledTask -TaskName "WhatIsThisThing-DailyPipeline" `
    -Action $action -Trigger $trigger -Settings $settings `
    -Description "Runs the What Is This Thing? daily content pipeline" `
    -Force

Write-Host "Scheduled task 'WhatIsThisThing-DailyPipeline' registered for $time daily."
Write-Host "Manage it via Task Scheduler, or: Get-ScheduledTask -TaskName 'WhatIsThisThing-DailyPipeline'"
