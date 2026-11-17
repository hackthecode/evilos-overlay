# Copies the regenerated EvilOS.ovl + EvilOS.png into RTSS and restarts it (needs admin)
$ErrorActionPreference = 'Stop'
$here = Split-Path -Parent $MyInvocation.MyCommand.Path
$rtss = 'C:\Program Files (x86)\RivaTuner Statistics Server'
$log  = "$env:LOCALAPPDATA\EvilOS\update.log"
try {
    Get-Process RTSS, RTSSHooksLoader, RTSSHooksLoader64, EncoderServer, EncoderServer64 -ErrorAction SilentlyContinue | Stop-Process -Force
    Start-Sleep 5
    Copy-Item "$here\EvilOS.ovl", "$here\EvilOS.png" "$rtss\Plugins\Client\Overlays\" -Force
    Start-Process "$rtss\RTSS.exe" -WorkingDirectory $rtss
    "$(Get-Date -f s) OK" | Out-File $log -Append
} catch {
    "$(Get-Date -f s) FAIL $_" | Out-File $log -Append
}
