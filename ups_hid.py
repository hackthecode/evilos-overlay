"""EvilOS - APC/HID UPS reader (stdlib only, ctypes -> hid.dll).

Reads HID Power Device (page 0x84) / Battery System (page 0x85) feature values
by parsing the device's own report descriptor, so report IDs are not hard-coded.
"""
import ctypes
import ctypes.wintypes as wt

hid = ctypes.WinDLL("hid.dll")
setupapi = ctypes.WinDLL("setupapi.dll")
k32 = ctypes.WinDLL("kernel32.dll", use_last_error=True)

HIDP_STATUS_SUCCESS = 0x00110000
HidP_Feature = 2
HidP_Input = 0


class GUID(ctypes.Structure):
    _fields_ = [("Data1", wt.DWORD), ("Data2", wt.WORD), ("Data3", wt.WORD), ("Data4", ctypes.c_ubyte * 8)]


class SP_DEVICE_INTERFACE_DATA(ctypes.Structure):
    _fields_ = [("cbSize", wt.DWORD), ("InterfaceClassGuid", GUID), ("Flags", wt.DWORD), ("Reserved", ctypes.c_void_p)]


class HIDD_ATTRIBUTES(ctypes.Structure):
    _fields_ = [("Size", wt.ULONG), ("VendorID", wt.USHORT), ("ProductID", wt.USHORT), ("VersionNumber", wt.USHORT)]


class HIDP_CAPS(ctypes.Structure):
    _fields_ = [("Usage", wt.USHORT), ("UsagePage", wt.USHORT),
                ("InputReportByteLength", wt.USHORT), ("OutputReportByteLength", wt.USHORT),
                ("FeatureReportByteLength", wt.USHORT), ("Reserved", wt.USHORT * 17),
                ("NumberLinkCollectionNodes", wt.USHORT),
                ("NumberInputButtonCaps", wt.USHORT), ("NumberInputValueCaps", wt.USHORT),
                ("NumberInputDataIndices", wt.USHORT),
                ("NumberOutputButtonCaps", wt.USHORT), ("NumberOutputValueCaps", wt.USHORT),
                ("NumberOutputDataIndices", wt.USHORT),
                ("NumberFeatureButtonCaps", wt.USHORT), ("NumberFeatureValueCaps", wt.USHORT),
                ("NumberFeatureDataIndices", wt.USHORT)]


class _Range(ctypes.Structure):
    _fields_ = [("UsageMin", wt.USHORT), ("UsageMax", wt.USHORT), ("StringMin", wt.USHORT),
                ("StringMax", wt.USHORT), ("DesignatorMin", wt.USHORT), ("DesignatorMax", wt.USHORT),
                ("DataIndexMin", wt.USHORT), ("DataIndexMax", wt.USHORT)]


class _NotRange(ctypes.Structure):
    _fields_ = [("Usage", wt.USHORT), ("Reserved1", wt.USHORT), ("StringIndex", wt.USHORT),
                ("Reserved2", wt.USHORT), ("DesignatorIndex", wt.USHORT), ("Reserved3", wt.USHORT),
                ("DataIndex", wt.USHORT), ("Reserved4", wt.USHORT)]


class _U(ctypes.Union):
    _fields_ = [("Range", _Range), ("NotRange", _NotRange)]


class HIDP_VALUE_CAPS(ctypes.Structure):
    _fields_ = [("UsagePage", wt.USHORT), ("ReportID", ctypes.c_ubyte), ("IsAlias", ctypes.c_ubyte),
                ("BitField", wt.USHORT), ("LinkCollection", wt.USHORT), ("LinkUsage", wt.USHORT),
                ("LinkUsagePage", wt.USHORT), ("IsRange", ctypes.c_ubyte), ("IsStringRange", ctypes.c_ubyte),
                ("IsDesignatorRange", ctypes.c_ubyte), ("IsAbsolute", ctypes.c_ubyte),
                ("HasNull", ctypes.c_ubyte), ("Reserved", ctypes.c_ubyte), ("BitSize", wt.USHORT),
                ("ReportCount", wt.USHORT), ("Reserved2", wt.USHORT * 5), ("UnitsExp", wt.ULONG),
                ("Units", wt.ULONG), ("LogicalMin", wt.LONG), ("LogicalMax", wt.LONG),
                ("PhysicalMin", wt.LONG), ("PhysicalMax", wt.LONG), ("u", _U)]


class HIDP_LINK_COLLECTION_NODE(ctypes.Structure):
    _fields_ = [("LinkUsage", wt.USHORT), ("LinkUsagePage", wt.USHORT), ("Parent", wt.USHORT),
                ("NumberOfChildren", wt.USHORT), ("NextSibling", wt.USHORT), ("FirstChild", wt.USHORT),
                ("bits", wt.ULONG), ("UserContext", ctypes.c_void_p)]


k32.CreateFileW.restype = wt.HANDLE
k32.CreateFileW.argtypes = [wt.LPCWSTR, wt.DWORD, wt.DWORD, ctypes.c_void_p, wt.DWORD, wt.DWORD, wt.HANDLE]
setupapi.SetupDiGetClassDevsW.restype = ctypes.c_void_p
setupapi.SetupDiGetClassDevsW.argtypes = [ctypes.POINTER(GUID), wt.LPCWSTR, wt.HWND, wt.DWORD]
setupapi.SetupDiEnumDeviceInterfaces.argtypes = [ctypes.c_void_p, ctypes.c_void_p, ctypes.POINTER(GUID), wt.DWORD,
                                                 ctypes.POINTER(SP_DEVICE_INTERFACE_DATA)]
setupapi.SetupDiGetDeviceInterfaceDetailW.argtypes = [ctypes.c_void_p, ctypes.POINTER(SP_DEVICE_INTERFACE_DATA),
                                                      ctypes.c_void_p, wt.DWORD, ctypes.POINTER(wt.DWORD), ctypes.c_void_p]
setupapi.SetupDiDestroyDeviceInfoList.argtypes = [ctypes.c_void_p]
hid.HidP_GetUsageValue.argtypes = [ctypes.c_int, wt.USHORT, wt.USHORT, wt.USHORT, ctypes.POINTER(wt.ULONG),
                                   ctypes.c_void_p, ctypes.c_char_p, wt.ULONG]
hid.HidP_GetUsageValue.restype = wt.LONG

INVALID_HANDLE = wt.HANDLE(-1).value

# Power Device page (0x84) collections / usages
COLL = {0x10: "PowerSupply", 0x12: "Battery", 0x16: "PowerConverter", 0x1A: "Input", 0x1C: "Output",
        0x24: "PowerSummary", 0x04: "UPS"}
USAGE_84 = {0x30: "Voltage", 0x31: "Current", 0x32: "Frequency", 0x33: "ApparentPower", 0x34: "ActivePower",
            0x35: "PercentLoad", 0x36: "Temperature", 0x40: "ConfigVoltage", 0x42: "ConfigFrequency",
            0x43: "ConfigApparentPower", 0x44: "ConfigActivePower", 0x53: "LowVoltageTransfer",
            0x54: "HighVoltageTransfer"}
USAGE_85 = {0x66: "RemainingCapacity", 0x68: "RunTimeToEmpty", 0x67: "FullChargeCapacity",
            0x83: "DesignCapacity", 0x2C: "CapacityMode", 0xD0: "ACPresent", 0x44: "Charging", 0x45: "Discharging"}


def _hid_paths(vid):
    guid = GUID()
    hid.HidD_GetHidGuid(ctypes.byref(guid))
    h = setupapi.SetupDiGetClassDevsW(ctypes.byref(guid), None, None, 0x12)  # PRESENT|INTERFACEDEVICE
    out, i = [], 0
    try:
        while True:
            d = SP_DEVICE_INTERFACE_DATA()
            d.cbSize = ctypes.sizeof(d)
            if not setupapi.SetupDiEnumDeviceInterfaces(h, None, ctypes.byref(guid), i, ctypes.byref(d)):
                break
            i += 1
            need = wt.DWORD()
            setupapi.SetupDiGetDeviceInterfaceDetailW(h, ctypes.byref(d), None, 0, ctypes.byref(need), None)
            buf = ctypes.create_string_buffer(need.value)
            ctypes.cast(buf, ctypes.POINTER(wt.DWORD))[0] = 8  # cbSize on x64
            if setupapi.SetupDiGetDeviceInterfaceDetailW(h, ctypes.byref(d), buf, need, None, None):
                path = ctypes.wstring_at(ctypes.addressof(buf) + 4)
                if f"vid_{vid:04x}" in path.lower():
                    out.append(path)
    finally:
        setupapi.SetupDiDestroyDeviceInfoList(h)
    return out


class UPS:
    def __init__(self, vid=0x051D):
        self.handle = None
        for path in _hid_paths(vid):
            # access=0 would block feature reads; use R/W with full sharing (hidbatt keeps it open too)
            hnd = k32.CreateFileW(path, 0xC0000000, 3, None, 3, 0, None)
            if hnd in (None, INVALID_HANDLE):
                hnd = k32.CreateFileW(path, 0, 3, None, 3, 0, None)
            if hnd in (None, INVALID_HANDLE):
                continue
            self.handle, self.path = hnd, path
            break
        if self.handle is None:
            raise OSError("UPS HID device not found")
        self.pp = ctypes.c_void_p()
        hid.HidD_GetPreparsedData(wt.HANDLE(self.handle), ctypes.byref(self.pp))
        self.caps = HIDP_CAPS()
        hid.HidP_GetCaps(self.pp, ctypes.byref(self.caps))
        n = wt.ULONG(self.caps.NumberLinkCollectionNodes)
        nodes = (HIDP_LINK_COLLECTION_NODE * n.value)()
        hid.HidP_GetLinkCollectionNodes(nodes, ctypes.byref(n), self.pp)
        self.nodes = nodes
        cnt = wt.USHORT(self.caps.NumberFeatureValueCaps)
        vc = (HIDP_VALUE_CAPS * cnt.value)()
        hid.HidP_GetValueCaps(HidP_Feature, vc, ctypes.byref(cnt), self.pp)
        self.values = {}  # name -> (cap, usage)
        for c in vc[:cnt.value]:
            usages = range(c.u.Range.UsageMin, c.u.Range.UsageMax + 1) if c.IsRange else [c.u.NotRange.Usage]
            for u in usages:
                name = self._name(c, u)
                if name and name not in self.values:
                    self.values[name] = (c, u)

    def _coll_path(self, idx):
        parts = []
        while True:
            nd = self.nodes[idx]
            parts.append(COLL.get(nd.LinkUsage, f"{nd.LinkUsagePage:02X}:{nd.LinkUsage:02X}") if nd.LinkUsagePage == 0x84
                         else f"{nd.LinkUsagePage:02X}:{nd.LinkUsage:02X}")
            if idx == 0:
                break
            idx = nd.Parent
        return ".".join(reversed(parts))

    def _name(self, c, u):
        if c.UsagePage == 0x84:
            un = USAGE_84.get(u, f"84:{u:02X}")
        elif c.UsagePage == 0x85:
            un = USAGE_85.get(u, f"85:{u:02X}")
        else:
            un = f"{c.UsagePage:02X}:{u:02X}"
        return f"{self._coll_path(c.LinkCollection)}.{un}"

    def read(self, name):
        c, u = self.values[name]
        buf = ctypes.create_string_buffer(self.caps.FeatureReportByteLength)
        buf[0] = bytes([c.ReportID])
        if not hid.HidD_GetFeature(wt.HANDLE(self.handle), buf, len(buf)):
            return None
        v = wt.ULONG()
        st = hid.HidP_GetUsageValue(HidP_Feature, c.UsagePage, c.LinkCollection, u, ctypes.byref(v), self.pp,
                                    buf, len(buf)) & 0xFFFFFFFF
        if st != HIDP_STATUS_SUCCESS:
            return None
        raw = v.value
        if c.LogicalMin < 0 and c.BitSize < 32 and raw >= (1 << (c.BitSize - 1)):
            raw -= 1 << c.BitSize
        exp = c.UnitsExp & 0xF
        if exp > 7:
            exp -= 16
        return raw * (10 ** exp) if exp else raw

    def find(self, *suffixes):
        """First existing value whose name ends with one of the suffixes (in priority order)."""
        for s in suffixes:
            for name in self.values:
                if name.endswith(s):
                    val = self.read(name)
                    if val is not None:
                        return val
        return None


if __name__ == "__main__":
    u = UPS()
    print(u.path)
    for name in sorted(u.values):
        c, _ = u.values[name]
        print(f"{name:55s} rid={c.ReportID:3d} exp={c.UnitsExp:2d} units={c.Units:08X} -> {u.read(name)}")
