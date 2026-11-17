# Registers the "EvilOS HWiNFO Watchdog" logon task (highest privileges) and starts it. Needs admin.
$ErrorActionPreference = 'Stop'
$here = Split-Path -Parent $MyInvocation.MyCommand.Path
$pyw  = 'C:\Python314\pythonw.exe'
$log  = "$env:LOCALAPPDATA\EvilOS\update.log"
try {
    $act = New-ScheduledTaskAction -Execute $pyw -Argument "-I `"$here\hwinfo_watchdog.py`"" -WorkingDirectory $here
    $trg = New-ScheduledTaskTrigger -AtLogOn -User $env:USERNAME
    $set = New-ScheduledTaskSettingsSet -AllowStartIfOnBatteries -DontStopIfGoingOnBatteries -ExecutionTimeLimit 0
    $pri = New-ScheduledTaskPrincipal -UserId $env:USERNAME -RunLevel Highest -LogonType Interactive
    Register-ScheduledTask -TaskName 'EvilOS HWiNFO Watchdog' -Action $act -Trigger $trg -Settings $set -Principal $pri -Force | Out-Null
    Start-ScheduledTask -TaskName 'EvilOS HWiNFO Watchdog'
    "$(Get-Date -f s) watchdog OK" | Out-File $log -Append
} catch {
    "$(Get-Date -f s) watchdog FAIL $_" | Out-File $log -Append
}
