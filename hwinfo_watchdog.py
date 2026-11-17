"""EvilOS HWiNFO watchdog - keeps HWiNFO64 "Shared Memory Support" alive (RTSS reads fans/temps from it).

HWiNFO free switches shared memory off 12 h after it was enabled. Every 60 s this checks whether the
"Global\\HWiNFO_SENS_SM2" mapping still exists and is being updated; if not, it sets SensorsSM=1 in
HWiNFO64.INI and restarts HWiNFO (which turns shared memory back on and restarts the 12 h period).

Needs admin (HWiNFO runs elevated, INI lives in Program Files) -> scheduled task "EvilOS HWiNFO Watchdog".
  --once   check/fix one time and print the result
Log: %LOCALAPPDATA%\\EvilOS\\hwinfo_watchdog.log
"""
import ctypes
import os
import re
import struct
import subprocess
import sys
import time

HWINFO_DIR = r"C:\Program Files\HWiNFO64"
EXE = os.path.join(HWINFO_DIR, "HWiNFO64.EXE")
INI = os.path.join(HWINFO_DIR, "HWiNFO64.INI")
SHM = "Global\\HWiNFO_SENS_SM2"
CHECK_EVERY = 60
LOG_DIR = os.path.join(os.environ.get("LOCALAPPDATA", "."), "EvilOS")
LOG = os.path.join(LOG_DIR, "hwinfo_watchdog.log")
NO_WINDOW = 0x08000000

k32 = ctypes.windll.kernel32
k32.OpenFileMappingW.restype = ctypes.c_void_p
k32.MapViewOfFile.restype = ctypes.c_void_p
k32.MapViewOfFile.argtypes = [ctypes.c_void_p, ctypes.c_uint32, ctypes.c_uint32, ctypes.c_uint32, ctypes.c_size_t]
k32.UnmapViewOfFile.argtypes = [ctypes.c_void_p]
k32.CloseHandle.argtypes = [ctypes.c_void_p]


def log(msg):
    os.makedirs(LOG_DIR, exist_ok=True)
    try:
        if os.path.exists(LOG) and os.path.getsize(LOG) > 256_000:
            os.replace(LOG, LOG + ".old")
        with open(LOG, "a", encoding="utf-8") as f:
            f.write(time.strftime("%Y-%m-%d %H:%M:%S ") + msg + "\n")
    except OSError:
        pass


def shm_poll_time():
    """Returns the 'last update' timestamp from the SHM header, or None if the mapping is gone."""
    h = k32.OpenFileMappingW(4, False, SHM)          # FILE_MAP_READ
    if not h:
        return None
    try:
        p = k32.MapViewOfFile(h, 4, 0, 0, 0)
        if not p:
            return None
        try:
            sig, _ver, _rev, poll = struct.unpack("<IIIq", ctypes.string_at(p, 20))
            return poll if sig == 0x53695748 else None   # 'HWiS' ('DEAD' once HWiNFO stops exporting)
        finally:
            k32.UnmapViewOfFile(p)
    finally:
        k32.CloseHandle(h)


def shm_alive(wait=3.0):
    a = shm_poll_time()
    if a is None:
        return False
    time.sleep(wait)
    b = shm_poll_time()
    return b is not None and b != a


def hwinfo_running():
    out = subprocess.run(["tasklist", "/FI", "IMAGENAME eq HWiNFO64.EXE", "/NH"], capture_output=True, text=True,
                         creationflags=NO_WINDOW).stdout
    return "HWiNFO64" in out


def set_ini():
    try:
        with open(INI, encoding="utf-8-sig", errors="replace") as f:
            txt = f.read()
    except OSError:
        txt = "[Settings]\n"
    if re.search(r"(?mi)^SensorsSM\s*=\s*1\s*$", txt):
        return False
    if re.search(r"(?mi)^SensorsSM\s*=", txt):
        txt = re.sub(r"(?mi)^SensorsSM\s*=.*$", "SensorsSM=1", txt)
    elif "[Settings]" in txt:
        txt = txt.replace("[Settings]", "[Settings]\nSensorsSM=1", 1)
    else:
        txt = "[Settings]\nSensorsSM=1\n" + txt
    with open(INI, "w", encoding="utf-8", newline="\r\n") as f:
        f.write(txt.replace("\r\n", "\n"))
    return True


def restart_hwinfo():
    subprocess.run(["taskkill", "/IM", "HWiNFO64.EXE", "/F"], capture_output=True, creationflags=NO_WINDOW)
    time.sleep(3)
    os.startfile(EXE)                                 # ShellExecute: HWiNFO is uiAccess=true, CreateProcess fails
    for _ in range(60):                               # sensor init can take a while
        time.sleep(1)
        if shm_poll_time() is not None:
            return True
    return False


def check_and_fix():
    if shm_alive():
        return "ok"
    changed = set_ini()
    ok = restart_hwinfo()
    msg = f"shared memory was off -> {'INI fixed, ' if changed else ''}HWiNFO restarted -> {'ON' if ok else 'STILL OFF'}"
    log(msg)
    return msg


def main():
    mtx = k32.CreateMutexW(None, False, "Local\\EvilOS_HWiNFO_Watchdog")
    if k32.GetLastError() == 183:
        return
    _ = mtx
    log("watchdog started")
    time.sleep(30)                                    # let HWiNFO's own autostart finish first
    while True:
        try:
            check_and_fix()
        except Exception as e:  # noqa: BLE001
            log(f"error: {e}")
        time.sleep(CHECK_EVERY)


if __name__ == "__main__":
    if "--once" in sys.argv:
        r = check_and_fix()
        print(r)
        log("once: " + r)
    else:
        main()
