"""Reads HWiNFO64 shared memory ("Global\\HWiNFO_SENS_SM2") - works without admin.

read() -> dict of EvilOS source name -> value (only what was found). Empty dict if HWiNFO SHM is off;
hwinfo_watchdog.py keeps it switched on.
"""
import ctypes
import struct

k32 = ctypes.windll.kernel32
k32.OpenFileMappingW.restype = ctypes.c_void_p
k32.MapViewOfFile.restype = ctypes.c_void_p
k32.MapViewOfFile.argtypes = [ctypes.c_void_p, ctypes.c_uint32, ctypes.c_uint32, ctypes.c_uint32, ctypes.c_size_t]
k32.UnmapViewOfFile.argtypes = [ctypes.c_void_p]
k32.CloseHandle.argtypes = [ctypes.c_void_p]

HDR = struct.Struct("<IIIqIIIIII")
T_TEMP, T_VOLT, T_FAN, T_CURR, T_POWER, T_CLOCK, T_USAGE, T_OTHER = range(1, 9)


def _s(b):
    return b.split(b"\0")[0].decode("cp1252", "replace")


def readings():
    """[(sensor_name, type, label, value)]"""
    h = k32.OpenFileMappingW(4, False, "Global\\HWiNFO_SENS_SM2")
    if not h:
        return []
    try:
        p = k32.MapViewOfFile(h, 4, 0, 0, 0)
        if not p:
            return []
        try:
            sig, _v, _r, _poll, off_s, sz_s, n_s, off_e, sz_e, n_e = HDR.unpack(ctypes.string_at(p, HDR.size))
            if sig != 0x53695748:                      # 'HWiS'
                return []
            sens = [_s(ctypes.string_at(p + off_s + i * sz_s + 8, 128)) for i in range(n_s)]
            data = ctypes.string_at(p + off_e, sz_e * n_e)
            out = []
            for i in range(n_e):
                e = data[i * sz_e:(i + 1) * sz_e]
                t, si, _rid = struct.unpack_from("<III", e)
                (val,) = struct.unpack_from("<d", e, 284)
                out.append((sens[si] if si < len(sens) else "", t, _s(e[12:140]), val))
            return out
        finally:
            k32.UnmapViewOfFile(p)
    finally:
        k32.CloseHandle(h)


def read():
    r = readings()
    if not r:
        return {}

    def find(sensor_prefix, typ, label, contains=False):
        for s, t, lab, v in r:
            if t == typ and s.startswith(sensor_prefix) and (label in lab if contains else lab == label):
                return v
        return None

    def all_of(sensor_part, typ, label_prefix):
        return [v for s, t, lab, v in r if t == typ and sensor_part in s and lab.startswith(label_prefix)]

    d = {
        "CPU temp": find("CPU [#0]", T_TEMP, "CPU (Tctl/Tdie)"),
        "CPU power": find("CPU [#0]", T_POWER, "CPU Package Power"),
        "GPU temp": find("dGPU", T_TEMP, "GPU Temperature"),
        "GPU hotspot": find("dGPU", T_TEMP, "GPU Hot Spot Temperature"),
        "VRAM temp": find("dGPU", T_TEMP, "GPU Memory Junction Temperature"),
        "GPU power": find("dGPU", T_POWER, "GPU Power"),
        "MB temp": find("", T_TEMP, "Motherboard"),
    }
    spd = all_of("DDR", T_TEMP, "SPD Hub")
    d["RAM temp"] = max(spd) if spd else None
    # motherboard fan headers (RPM only - this board's Nuvoton chip does not report duty % to HWiNFO)
    mobo = [(lab, v) for s, t, lab, v in r if t == T_FAN and not s.startswith(("dGPU", "iGPU"))]
    cpu = [v for lab, v in mobo if lab.upper().startswith("CPU")]
    sys_ = [v for lab, v in mobo if not lab.upper().startswith("CPU") and v > 0]
    d["CPU fan rpm"] = max(cpu) if cpu else None
    d["SYS fan rpm"] = sum(sys_) / len(sys_) if sys_ else None
    # GPU performance limiters (Yes/No flags). "Utilization" is normal at idle -> ignored.
    d["GPU lim power"] = find("dGPU", T_OTHER, "Performance Limit - Power")
    d["GPU lim thermal"] = find("dGPU", T_OTHER, "Performance Limit - Thermal")
    volt = [v for v in (find("dGPU", T_OTHER, "Performance Limit - Reliability Voltage"),
                        find("dGPU", T_OTHER, "Performance Limit - Max Operating Voltage")) if v is not None]
    d["GPU lim volt"] = max(volt) if volt else None
    # drives: summed throughput, busiest drive, hottest drive
    rd = [v for s, t, lab, v in r if s.startswith("Drive:") and lab == "Read Rate"]
    wr = [v for s, t, lab, v in r if s.startswith("Drive:") and lab == "Write Rate"]
    act = [v for s, t, lab, v in r if s.startswith("Drive:") and lab == "Total Activity"]
    dt = [v for s, t, lab, v in r if t == T_TEMP and s.startswith("S.M.A.R.T.") and lab.startswith("Drive Temperature")]
    d["Disk read"] = sum(rd) if rd else None
    d["Disk write"] = sum(wr) if wr else None
    d["Disk rate"] = sum(rd) + sum(wr) if rd or wr else None
    d["Disk active"] = max(act) if act else None
    d["Disk temp"] = max(dt) if dt else None
    # network: all adapters summed, HWiNFO reports KB/s -> Mbit/s
    dl = [v for s, t, lab, v in r if s.startswith("Network:") and lab == "Current DL rate"]
    ul = [v for s, t, lab, v in r if s.startswith("Network:") and lab == "Current UP rate"]
    d["Net down"] = sum(dl) * 8 / 1000 if dl else None
    d["Net up"] = sum(ul) * 8 / 1000 if ul else None
    return {k: v for k, v in d.items() if v is not None}


if __name__ == "__main__":
    print(read())
