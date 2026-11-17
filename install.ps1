# EvilOS overlay installer for RivaTuner Statistics Server (needs admin)
$ErrorActionPreference = 'Stop'
$here = Split-Path -Parent $MyInvocation.MyCommand.Path
$rtss = 'C:\Program Files (x86)\RivaTuner Statistics Server'
$pyw  = 'C:\Python314\pythonw.exe'

Add-Type -Namespace W -Name Ini -MemberDefinition @'
[DllImport("kernel32.dll", CharSet=CharSet.Unicode)]
public static extern bool WritePrivateProfileString(string s, string k, string v, string f);
'@

Write-Host "[EvilOS] Stopping RTSS..." -ForegroundColor Red
Get-Process RTSS, RTSSHooksLoader, RTSSHooksLoader64, EncoderServer, EncoderServer64 -ErrorAction SilentlyContinue | Stop-Process -Force
Start-Sleep 5

Write-Host "[EvilOS] Installing overlay layout..."
Copy-Item "$here\EvilOS.ovl", "$here\EvilOS.png" "$rtss\Plugins\Client\Overlays\" -Force
[W.Ini]::WritePrivateProfileString('Settings', 'Layout', 'EvilOS.ovl', "$rtss\Plugins\Client\OverlayEditor.cfg") | Out-Null

Write-Host "[EvilOS] Enabling OverlayEditor plugin + RTSS settings..."
$cfg = "$rtss\Profiles\Config"
[W.Ini]::WritePrivateProfileString('Settings', 'EnablePlugins', '1', $cfg) | Out-Null
[W.Ini]::WritePrivateProfileString('Settings', 'StartMinimized', '1', $cfg) | Out-Null
[W.Ini]::WritePrivateProfileString('Plugins', 'OverlayEditor.dll', '1', $cfg) | Out-Null
[W.Ini]::WritePrivateProfileString('Plugins', 'HotkeyHandler.dll', '1', $cfg) | Out-Null

# Global profile: OSD on, top-left, no RTSS own background (the layout draws its own panel)
$glob = "$rtss\Profiles\Global"
if (-not (Test-Path $glob)) { Copy-Item "$rtss\ProfileTemplates\Global" $glob }
[W.Ini]::WritePrivateProfileString('OSD', 'EnableOSD', '1', $glob) | Out-Null
[W.Ini]::WritePrivateProfileString('OSD', 'EnableBgnd', '0', $glob) | Out-Null
[W.Ini]::WritePrivateProfileString('OSD', 'EnableFill', '0', $glob) | Out-Null
[W.Ini]::WritePrivateProfileString('OSD', 'PositionX', '12', $glob) | Out-Null
[W.Ini]::WritePrivateProfileString('OSD', 'PositionY', '12', $glob) | Out-Null

Write-Host "[EvilOS] Autostart: RTSS (scheduled task, highest privileges)..."
$act = New-ScheduledTaskAction -Execute "$rtss\RTSS.exe" -WorkingDirectory $rtss
$trg = New-ScheduledTaskTrigger -AtLogOn -User $env:USERNAME
$set = New-ScheduledTaskSettingsSet -AllowStartIfOnBatteries -DontStopIfGoingOnBatteries -ExecutionTimeLimit 0
$pri = New-ScheduledTaskPrincipal -UserId $env:USERNAME -RunLevel Highest -LogonType Interactive
Register-ScheduledTask -TaskName 'EvilOS RTSS' -Action $act -Trigger $trg -Settings $set -Principal $pri -Force | Out-Null

Write-Host "[EvilOS] Autostart: sensor bridge (UPS -> RTSS)..."
Set-ItemProperty 'HKCU:\Software\Microsoft\Windows\CurrentVersion\Run' -Name 'EvilOS Bridge' `
    -Value "`"$pyw`" -I `"$here\evilos_bridge.py`""
if (-not (Get-CimInstance Win32_Process -Filter "Name='pythonw.exe'" | ? CommandLine -match 'evilos_bridge')) {
    Start-Process $pyw -ArgumentList '-I', "`"$here\evilos_bridge.py`"" -WindowStyle Hidden
}

Write-Host "[EvilOS] HWiNFO shared-memory watchdog (temps / fans)..."
& "$here\setup_watchdog.ps1"

Write-Host "[EvilOS] Starting RTSS..."
Start-Process "$rtss\RTSS.exe" -WorkingDirectory $rtss
Write-Host "`n[EvilOS] DONE. Open a game - the overlay shows in the top-left corner." -ForegroundColor Red
Start-Sleep 4
