"""EvilOS sensor bridge -> RTSS OverlayEditor.

Publishes UPS (APC HID) + RAM clock values through the MSI Afterburner
hardware-monitoring shared memory format ("MAHMSharedMemory"), which RTSS
OverlayEditor reads as provider "MSI Afterburner". Afterburner itself is not
installed, so there is no conflict.

Run with pythonw (no console). Log: %LOCALAPPDATA%\\EvilOS\\bridge.log
"""
import ctypes
import mmap
import os
import struct
import sys
import time
import subprocess

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from ups_hid import UPS  # noqa: E402
import hwinfo_shm  # noqa: E402
from ping_stats import Pinger  # noqa: E402

FLT_MAX = 3.4028234663852886e38
MAX_PATH = 260
HDR = struct.Struct("<IIIIIiII")            # sig, ver, hdrsize, n, entsize, time32, ngpu, gpusize
ENT = struct.Struct(f"<{MAX_PATH}s{MAX_PATH}s{MAX_PATH}s{MAX_PATH}s{MAX_PATH}sfffIII")
SIG_MAHM = 0x4D41484D                        # 'MAHM'
SIG_DEAD = 0xDEAD
SRC_UPS, SRC_RAM, SRC_MISC = 0xF7, 0xF3, 0xFF
ONE_INSTANCE = "Local\\EvilOS_Bridge_Mutex"

# name, units, format, min, max, srcid
SOURCES = [
    ("UPS input voltage", "V", "%.0f", 0, 260, SRC_UPS),
    ("UPS load", "%", "%.0f", 0, 100, SRC_UPS),
    ("UPS power", "W", "%.0f", 0, 1320, SRC_UPS),
    ("UPS battery", "%", "%.0f", 0, 100, SRC_UPS),
    ("UPS runtime", "min", "%.0f", 0, 120, SRC_UPS),
    ("UPS on battery", "", "%.0f", 0, 1, SRC_UPS),
    ("UPS nominal power", "W", "%.0f", 0, 5000, SRC_UPS),
    ("RAM clock", "MT/s", "%.0f", 0, 10000, SRC_RAM),
    # from HWiNFO shared memory (hwinfo_shm.py; kept on by hwinfo_watchdog.py)
    ("CPU temp", "C", "%.0f", 0, 100, SRC_MISC),
    ("CPU power", "W", "%.0f", 0, 250, SRC_MISC),
    ("GPU temp", "C", "%.0f", 0, 100, SRC_MISC),
    ("GPU hotspot", "C", "%.0f", 0, 110, SRC_MISC),
    ("VRAM temp", "C", "%.0f", 0, 110, SRC_MISC),
    ("GPU power", "W", "%.0f", 0, 350, SRC_MISC),
    ("RAM temp", "C", "%.0f", 0, 90, SRC_MISC),
    ("MB temp", "C", "%.0f", 0, 90, SRC_MISC),
    ("CPU fan rpm", "RPM", "%.0f", 0, 3000, SRC_MISC),
    ("SYS fan rpm", "RPM", "%.0f", 0, 3000, SRC_MISC),
    ("GPU lim power", "", "%.0f", 0, 1, SRC_MISC),
    ("GPU lim thermal", "", "%.0f", 0, 1, SRC_MISC),
    ("GPU lim volt", "", "%.0f", 0, 1, SRC_MISC),
    ("Disk read", "MB/s", "%.0f", 0, 8000, SRC_MISC),
    ("Disk write", "MB/s", "%.0f", 0, 8000, SRC_MISC),
    ("Disk rate", "MB/s", "%.0f", 0, 8000, SRC_MISC),
    ("Disk active", "%", "%.0f", 0, 100, SRC_MISC),
    ("Disk temp", "C", "%.0f", 0, 90, SRC_MISC),
    ("Net down", "Mb/s", "%.1f", 0, 2500, SRC_MISC),
    ("Net up", "Mb/s", "%.1f", 0, 2500, SRC_MISC),
    # own ICMP pinger (ping_stats.py)
    ("Ping ms", "ms", "%.0f", 0, 1000, SRC_MISC),
    ("Ping jitter", "ms", "%.0f", 0, 500, SRC_MISC),
    ("Ping loss", "%", "%.0f", 0, 100, SRC_MISC),
    # 2 = bridge + HWiNFO OK, 1 = bridge OK but HWiNFO shared memory missing (missing entirely = bridge down)
    ("EvilOS status", "", "%.0f", 0, 2, SRC_MISC),
]
PING_HOST = "8.8.8.8"

LOG_DIR = os.path.join(os.environ.get("LOCALAPPDATA", "."), "EvilOS")
os.makedirs(LOG_DIR, exist_ok=True)
LOG = os.path.join(LOG_DIR, "bridge.log")


def log(msg):
    try:
        if os.path.exists(LOG) and os.path.getsize(LOG) > 512_000:
            os.replace(LOG, LOG + ".old")
        with open(LOG, "a", encoding="utf-8") as f:
            f.write(time.strftime("%Y-%m-%d %H:%M:%S ") + msg + "\n")
    except OSError:
        pass


def ram_clock():
    """Configured memory speed in MT/s (static, read once)."""
    try:
        out = subprocess.run(
            ["powershell", "-NoProfile", "-Command",
             "(Get-CimInstance Win32_PhysicalMemory | Measure-Object ConfiguredClockSpeed -Maximum).Maximum"],
            capture_output=True, text=True, timeout=30, creationflags=0x08000000).stdout.strip()
        return float(out)
    except Exception as e:  # noqa: BLE001
        log(f"RAM clock read failed: {e}")
        return FLT_MAX


def si(ups, name):
    """Read a value whose units are SI volt/watt (HID unit exponent 7 == base unit)."""
    c, _ = ups.values[name]
    v = ups.read(name)
    if v is None:
        return None
    raw = v / (10 ** _exp(c.UnitsExp)) if _exp(c.UnitsExp) else v
    return raw * (10 ** (_exp(c.UnitsExp) - 7)) if c.Units & 0xFFFF == 0xD121 else raw


def _exp(e):
    e &= 0xF
    return e - 16 if e > 7 else e


class UpsReader:
    def __init__(self):
        self.ups = None
        self.nominal = None
        self.next_try = 0

    def _connect(self):
        if self.ups or time.time() < self.next_try:
            return self.ups is not None
        try:
            self.ups = UPS()
            self.nominal = si(self.ups, "UPS.PowerConverter.ConfigActivePower") \
                if "UPS.PowerConverter.ConfigActivePower" in self.ups.values else 1320.0
            log(f"UPS connected: {self.ups.path} nominal={self.nominal} W")
        except Exception as e:  # noqa: BLE001
            self.ups = None
            self.next_try = time.time() + 10
            log(f"UPS not available: {e}")
        return self.ups is not None

    def read(self):
        if not self._connect():
            return {}
        u = self.ups
        try:
            def first(*names):
                for n in names:
                    if n in u.values:
                        v = si(u, n)
                        if v is not None:
                            return v
                return None

            volt = first("UPS.Input.Voltage")
            load = first("UPS.PowerConverter.PercentLoad", "UPS.PowerSummary.PercentLoad", "UPS.Output.PercentLoad")
            batt = first("UPS.PowerSummary.RemainingCapacity", "UPS.Battery.RemainingCapacity")
            rt = first("UPS.PowerSummary.RunTimeToEmpty", "UPS.Battery.RunTimeToEmpty")
            ac = first("UPS.PowerSummary.ACPresent")
            if volt is None and load is None and batt is None:
                raise OSError("all reads failed")
            res = {
                "UPS input voltage": volt,
                "UPS load": load,
                "UPS power": (load * self.nominal / 100.0) if load is not None and self.nominal else None,
                "UPS battery": batt,
                "UPS runtime": rt / 60.0 if rt is not None else None,
                "UPS on battery": (0.0 if ac else 1.0) if ac is not None else None,
                "UPS nominal power": self.nominal,
            }
            return res
        except Exception as e:  # noqa: BLE001
            log(f"UPS read error, reconnecting: {e}")
            try:
                ctypes.windll.kernel32.CloseHandle(ctypes.c_void_p(u.handle))
            except Exception:  # noqa: BLE001
                pass
            self.ups = None
            self.next_try = time.time() + 5
            return {}


def main():
    k32 = ctypes.windll.kernel32
    k32.CreateMutexW.restype = ctypes.c_void_p
    mtx = k32.CreateMutexW(None, False, ONE_INSTANCE)
    if k32.GetLastError() == 183:  # ERROR_ALREADY_EXISTS
        return
    _ = mtx

    size = HDR.size + ENT.size * len(SOURCES)
    shm = mmap.mmap(-1, size, tagname="MAHMSharedMemory")
    static = {"RAM clock": ram_clock()}
    reader = UpsReader()
    pinger = Pinger(PING_HOST)
    pinger.start()
    log(f"bridge started, {len(SOURCES)} sources, shm {size} bytes")

    def enc(s):
        return s.encode("cp1252", "replace")

    try:
        while True:
            vals = dict(static)
            vals.update(reader.read())
            vals.update(pinger.stats())
            hw = {}
            try:
                hw = hwinfo_shm.read()
            except Exception as e:  # noqa: BLE001
                log(f"HWiNFO read error: {e}")
            vals.update(hw)
            vals["EvilOS status"] = 2.0 if hw else 1.0
            buf = bytearray(HDR.pack(SIG_MAHM, 0x00020000, HDR.size, len(SOURCES), ENT.size,
                                     int(time.time()) & 0x7FFFFFFF, 0, 0))
            for name, units, fmt, mn, mx, sid in SOURCES:
                v = vals.get(name)
                buf += ENT.pack(enc(name), enc(units), enc(name), enc(units), enc(fmt),
                                float(v) if v is not None else FLT_MAX, float(mn), float(mx),
                                1, 0xFFFFFFFF, sid)
            shm.seek(0)
            shm.write(bytes(buf))
            time.sleep(1.0)
    finally:
        shm.seek(0)
        shm.write(struct.pack("<I", SIG_DEAD))
        shm.close()


if __name__ == "__main__":
    if "--once" in sys.argv:
        r = UpsReader()
        print({"RAM clock": ram_clock(), **r.read(), **hwinfo_shm.read()})
    else:
        main()
