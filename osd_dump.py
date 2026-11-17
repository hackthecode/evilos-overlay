"""Dumps the hypertext RTSS OverlayEditor currently renders (RTSSSharedMemoryV2, owner RTSSOverlayEditor).
usage: osd_dump.py [out.txt]"""
import ctypes
import struct
import sys

k = ctypes.windll.kernel32
k.OpenFileMappingW.restype = ctypes.c_void_p
k.MapViewOfFile.restype = ctypes.c_void_p
k.MapViewOfFile.argtypes = [ctypes.c_void_p, ctypes.c_uint, ctypes.c_uint, ctypes.c_uint, ctypes.c_size_t]
h = k.OpenFileMappingW(4, False, "RTSSSharedMemoryV2")
text = "RTSSSharedMemoryV2 not found"
if h:
    p = k.MapViewOfFile(h, 4, 0, 0, 0)
    sig, ver, appsz, appoff, appn, osdsz, osdoff, osdn = struct.unpack("<8I", ctypes.string_at(p, 32))
    text = "no RTSSOverlayEditor slot"
    for i in range(osdn):
        e = ctypes.string_at(p + osdoff + i * osdsz, osdsz)
        if e[256:512].startswith(b"RTSSOverlayEditor"):
            text = e[266752:266752 + 32768].split(b"\0")[0].decode("cp1252", "replace")
if len(sys.argv) > 1:
    open(sys.argv[1], "w", encoding="utf-8").write(text)
else:
    print(text)
