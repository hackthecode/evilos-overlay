# Renders overlay layouts on the desktop for screenshots, then ALWAYS closes the test window (needs admin).
#   preview.ps1 -Ovl a.ovl,b.ovl -Out a.png,b.png [-Png EvilOS.png] [-Shots 1] [-Outline N] [-Keep]
# Each layout is installed as EvilOS.ovl in turn; at the end the real EvilOS.ovl/png from this folder is restored.
# -Outline N  sets RTSS [Font] OutlinePassCount for the run (restored afterwards unless -Keep)
param([Parameter(Mandatory)][string[]]$Ovl, [Parameter(Mandatory)][string[]]$Out, [string]$Png = "",
      [int]$Shots = 1, [int]$Outline = 0, [switch]$Keep)
$here = Split-Path -Parent $MyInvocation.MyCommand.Path
$rtss = 'C:\Program Files (x86)\RivaTuner Statistics Server'
$dst  = "$rtss\Plugins\Client\Overlays"
$log  = "$env:LOCALAPPDATA\EvilOS\update.log"
if (-not $Png) { $Png = "$here\EvilOS.png" }

Add-Type -Namespace W -Name Ini2 -MemberDefinition @'
[DllImport("kernel32.dll", CharSet=CharSet.Unicode)]
public static extern bool WritePrivateProfileString(string s, string k, string v, string f);
[DllImport("kernel32.dll", CharSet=CharSet.Unicode)]
public static extern int GetPrivateProfileInt(string s, string k, int d, string f);
'@
$glob = "$rtss\Profiles\Global"
$oldOutline = [W.Ini2]::GetPrivateProfileInt('Font', 'OutlinePassCount', 1, $glob)

function Restart-Rtss {
    Get-Process RTSS, RTSSHooksLoader, RTSSHooksLoader64, EncoderServer, EncoderServer64 -ErrorAction SilentlyContinue | Stop-Process -Force
    Start-Sleep 5
    Start-Process "$rtss\RTSS.exe" -WorkingDirectory $rtss
    Start-Sleep 3
}
function Close-Host { Get-Process DesktopOverlayHost, DesktopOverlayHost64 -ErrorAction SilentlyContinue | Stop-Process -Force }

try {
    if ($Outline -gt 0) { [W.Ini2]::WritePrivateProfileString('Font', 'OutlinePassCount', "$Outline", $glob) | Out-Null }
    Copy-Item $Png "$dst\EvilOS.png" -Force
    for ($i = 0; $i -lt $Ovl.Count; $i++) {
        try {
            Copy-Item $Ovl[$i] "$dst\EvilOS.ovl" -Force
            Restart-Rtss
            Start-Process "$rtss\DesktopOverlayHostLoader.exe" -WorkingDirectory $rtss
            Start-Sleep 9
            $o = $Out[$i]
            & 'C:\Python314\python.exe' -I -c "from PIL import ImageGrab; import time, os; b, e = os.path.splitext(r'$o')
for i in range($Shots):
    ImageGrab.grab(all_screens=True).crop((0,1440,1700,2000)).save(b + ('_%d' % i if i else '') + e); time.sleep(0.6)"
            # dump what RTSS OverlayEditor actually renders (hypertext) next to the screenshot
            & 'C:\Python314\python.exe' -I "$here\osd_dump.py" ([IO.Path]::ChangeExtension($o, '.txt'))
            "$(Get-Date -f s) preview OK $o" | Out-File $log -Append
        } finally { Close-Host }
    }
} catch {
    "$(Get-Date -f s) preview FAIL $_" | Out-File $log -Append
} finally {
    Close-Host
    if ($Outline -gt 0 -and -not $Keep) { [W.Ini2]::WritePrivateProfileString('Font', 'OutlinePassCount', "$oldOutline", $glob) | Out-Null }
    Copy-Item "$here\EvilOS.ovl" "$dst\EvilOS.ovl" -Force
    Copy-Item "$here\EvilOS.png" "$dst\EvilOS.png" -Force
    Restart-Rtss
    "$(Get-Date -f s) preview closed" | Out-File $log -Append
}
