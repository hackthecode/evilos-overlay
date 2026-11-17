"""Generates EvilOS.ovl (+ finishes EvilOS.png) - RTSS OverlayEditor layout, hackthecode.github.io theme (v8).

Run make_icons.py first (sprite rows 0-3), then this script: it also renders the panel background sprite
(rounded corners, shadow, zebra bands, header gradient + glow, border) into EvilOS.png below the icon rows.

Geometry
  X: negative = character columns (13 px each at FontHeight -11 / ZoomRatio 2), positive = pixel units.
  Y: positive pixel units. 1 unit = 2 screen px (ZoomRatio 2). A text row would be ~14.5 units.
  ExtentOrigin: 0 TL 1 TC 2 TR / 3 ML 4 C 5 MR / 6 BL 7 BC 8 BR
  Empty background layers are at least one text row tall unless Size is small (Size=20).
  Graph layers must keep the default Size - <G> width/height scale with the layer Size.
  Images stretch to the layer extent; the panel sprite is drawn at exactly 1:1.
Tags
  <G=src,w,h,margin,min,max,FLAGS_HEX> (1 filled, 8 bar, 10 bgnd)   <I=w,h,sx,sy,sw,sh> (0,0 = fit extent)
  <AI=src,w,h,min,max,sx,sy,sw,sh,frames,perRow,0> + layer RefreshPeriod=16
  Dynamic colour: c0,min,max,c1,min,max,...,(source,flags) - flag 1 = BLEND between adjacent CLOSED ranges
  (SDK\\Plugins\\Client\\OverlayEditor\\DynamicColor.cpp). Max 5 ranges.
  Formula key(vk) = HotkeyHandler press counter (+0x80000000 while held) -> Scroll Lock parity = layout mode.
Data
  HAL (CPU/GPU/RAM), bridge via MAHM (UPS, HWiNFO temps/fans/power/disks/net, own pinger, status).
  hwinfo_watchdog.py keeps HWiNFO shared memory on. Never use LibreHardwareMonitor (WinRing0, Defender).
RULE: never use the bare <C> colour pop in text - inside games it pops to BLACK. Units always come last.
"""
import ctypes
import json
import os
import re
import subprocess
import sys

from PIL import Image, ImageDraw, ImageFilter

HERE = os.path.dirname(os.path.abspath(__file__))

# ---- palette (AARRGGBB) ----------------------------------------------------------------------------
RED, BLOOD, BONE, DIM = "FFFF1F33", "FF9C0F1D", "FFECE5DD", "FF94848A"
AMBER, GREEN, HOT = "FFFFB020", "FF4CFF7A", "FFFF6B7A"
MODEL = "D9ECE5DD"          # component names
LBL = "FFC4162A"            # labels: darker red than values so numbers lead
W = 38                      # vertical panel width in columns
COL_U = 6.5                 # one column in pixel units
PW_PX = W * 13              # panel width in screen px (494)
VAL, SMALL, TINY, LABEL = 85, 60, 65, 72   # text sizes (%)
FAN_FRAMES = 8
SCROLL_LOCK = 0x91          # toggles vertical <-> horizontal layout

ICON = {"logo": 0, "CPU": 1, "GPU": 2, "RAM": 3, "VRAM": 4, "UPS": 5, "PING": 6, "PWR": 7}
ICON2 = {"DISK": 0, "CPU hot": 1, "GPU hot": 2, "dot green": 3, "dot amber": 4, "dot red": 5, "segmask": 6}
ICON3 = {"NET": 0, "CPU warn": 1, "GPU warn": 2, "RAM warn": 3, "VRAM warn": 4, "DISK warn": 5}
SPRITE_Y = 512              # panel sprites start below the 4 icon rows

PS_QUERY = (
    "$c=(Get-CimInstance Win32_Processor)[0];"
    "$m=@(Get-CimInstance Win32_PhysicalMemory);"
    "@{cpu=$c.Name;gpu=@(Get-CimInstance Win32_VideoController|%{$_.Name});"
    "part=$m[0].PartNumber;mods=$m.Count;cap=($m|Measure-Object Capacity -Sum).Sum;"
    "type=$m[0].SMBIOSMemoryType}|ConvertTo-Json -Compress")
RAM_BRANDS = [("CMK", "VENGEANCE"), ("CMH", "VENGEANCE RGB"), ("CMT", "DOMINATOR"),
              ("CMP", "DOMINATOR"), ("F5-", "G.SKILL"), ("KF5", "KINGSTON FURY")]


# ---- real hardware names ---------------------------------------------------------------------------
def detect():
    names = {"CPU": "CPU", "GPU": "GPU", "RAM": "DDR", "UPS": "APC UPS"}
    try:
        j = json.loads(subprocess.run(["powershell", "-NoProfile", "-Command", PS_QUERY],
                                      capture_output=True, text=True, timeout=60).stdout)
        cpu = re.sub(r"\s+\d+-Core.*|\s+Processor.*", "", j["cpu"]).strip()
        names["CPU"] = re.sub(r"\(\w+\)", "", cpu).upper()
        gpu = next((g for g in j["gpu"] if re.search("NVIDIA|Radeon RX|Arc", g)), j["gpu"][0])
        names["GPU"] = gpu.replace("GeForce ", "").upper()
        part = (j["part"] or "").strip().upper()
        brand = next((b for p, b in RAM_BRANDS if part.startswith(p)), "")
        ddr = {34: "DDR5", 26: "DDR4"}.get(j["type"], "DDR")
        per = j["cap"] // j["mods"] // 2 ** 30
        names["RAM"] = f"{brand} {ddr} {j['mods']}x{per}GB".strip()
    except Exception as e:
        print("hardware detection failed:", e)
    try:
        sys.path.insert(0, HERE)
        import ups_hid
        u, buf = ups_hid.UPS(), ctypes.create_unicode_buffer(256)
        ups_hid.hid.HidD_GetProductString(ctypes.c_void_p(u.handle), buf, 512)
        m = re.search(r"([A-Z]{2,4}\d{3,5}[A-Z]?)", buf.value)
        names["UPS"] = "APC " + (m.group(1) if m else buf.value.split(" FW")[0]).upper()
    except Exception as e:
        print("UPS name detection failed:", e)
    return names


NAMES = detect()
DEG = "°"


def rgb(c):
    return c[2:]            # dynamic colour ranges use RRGGBB


def blend(src, stops):
    """Smooth colour ramp. stops = [(value, colour), ...] ascending, 2-4 stops.
    Below the first stop: first colour, above the last: last colour, blended in between."""
    parts = [f"{rgb(stops[0][1])},,{stops[0][0]}"]
    for (v0, c0), (v1, _c1) in zip(stops, stops[1:]):
        parts.append(f"{rgb(c0)},{v0},{v1}")
    parts.append(f"{rgb(stops[-1][1])},{stops[-1][0]},")
    return ",".join(parts) + f"({src},1)"


def thr(src, warn, crit, lo=None):
    """bone -> amber -> red, blended."""
    return blend(src, [(lo if lo is not None else warn - 20, BONE), (warn, AMBER), (crit, RED)])


def thr_low(src, crit, warn, hi):
    """red -> amber -> bone for values where LOW is bad (battery)."""
    return blend(src, [(crit, RED), (warn, AMBER), (hi, BONE)])


def net_col(src, good, bad):
    """green -> amber -> red (network quality)."""
    return blend(src, [(good, GREEN), ((good + bad) / 2, AMBER), (bad, RED)])


def img(name):
    if name in ICON2:
        return f"<I=0,0,{ICON2[name] * 128},256,128,128>"
    if name in ICON3:
        return f"<I=0,0,{ICON3[name] * 128},384,128,128>"
    return f"<I=0,0,{ICON[name] * 128},0,128,128>"


def unit(u):
    return f"<S=-72><C={DIM}>{u}<S>"   # last thing in a layer; size pop is safe, colour pop is not


# ---- data sources -------------------------------------------------------------------------------------
STUB, TIMER = {"Provider": "HAL", "ID": "Stub"}, {"Provider": "HAL", "ID": "Timer"}
sources = [
    ("CPU usage", "%", "%.0f", "", {"Provider": "HAL", "ID": "CPU usage"}),
    ("CPU clock", "MHz", "%.0f", "", {"Provider": "HAL", "ID": "CPU clock"}),
    ("GPU1 usage", "%", "%.0f", "", {"Provider": "HAL", "ID": "GPU1 usage"}),
    ("GPU1 clock", "MHz", "%.0f", "", {"Provider": "HAL", "ID": "GPU1 clock"}),
    ("GPU1 memory usage", "GB", "%.1f", "x / 1024", {"Provider": "HAL", "ID": "GPU1 memory usage"}),
    ("GPU1 memory usage percent", "%", "%.0f", "", {"Provider": "HAL", "ID": "GPU1 memory usage percent"}),
    ("GPU1 total memory", "GB", "%.0f", "x / 1024", {"Provider": "HAL", "ID": "GPU1 total memory"}),
    ("GPU1 fan speed", "%", "%.0f", "", {"Provider": "HAL", "ID": "GPU1 fan speed"}),
    ("GPU1 fan tachometer", "RPM", "%.0f", "", {"Provider": "HAL", "ID": "GPU1 fan tachometer"}),
    ("RAM usage percent", "%", "%.0f", "", {"Provider": "HAL", "ID": "RAM usage percent"}),
    # layout mode: Scroll Lock press count parity (HotkeyHandler.dll must be enabled)
    ("Mode V", "", "", f"(key({SCROLL_LOCK}) % 2) == 0", STUB),
    ("Mode H", "", "", '"Mode V" == 0', STUB),
]
for n, u in [("RAM clock", "MT/s"), ("UPS input voltage", "V"), ("UPS load", "%"), ("UPS power", "W"),
             ("UPS battery", "%"), ("UPS runtime", "min"), ("UPS on battery", ""),
             ("CPU temp", "C"), ("CPU power", "W"), ("GPU temp", "C"), ("GPU hotspot", "C"), ("VRAM temp", "C"),
             ("GPU power", "W"), ("RAM temp", "C"), ("MB temp", "C"), ("CPU fan rpm", "RPM"), ("SYS fan rpm", "RPM"),
             ("GPU lim power", ""), ("GPU lim thermal", ""), ("GPU lim volt", ""), ("Disk rate", "MB/s"),
             ("Disk active", "%"), ("Disk temp", "C"), ("Ping ms", "ms"), ("Ping jitter", "ms"), ("Ping loss", "%"),
             ("EvilOS status", ""), ("Net down", "Mb/s"), ("Net up", "Mb/s")]:
    sources.append((n, u, "%.1f" if n.startswith("Net") else "%.0f", "",
                    {"Provider": "MSI Afterburner", "SrcId": "FFFFFFFF", "Gpu": "FFFFFFFF", "SrcName": n}))
# fan animation phase: frames advance proportionally to RPM (2000 RPM = 30 frames/s)
for key, src in (("CPU", "CPU fan rpm"), ("SYS", "SYS fan rpm"), ("GPU", "GPU1 fan tachometer")):
    sources.append((f"Fan anim {key}", "", "", f'("{src}" * x / 66667) % {FAN_FRAMES}', TIMER))
# alerts (0/1). The frame blinks for any of them, the header only for a power cut.
for n, fx in (("Alert batt", '"UPS on battery" > 0'), ("Alert cpu", '"CPU temp" > 90'),
              ("Alert gpu", '("GPU temp" > 85) + ("GPU hotspot" > 100) > 0'), ("Alert loss", '"Ping loss" > 5'),
              ("Alert ram", '"RAM usage percent" > 95'),
              ("Alert any", '("Alert batt" + "Alert cpu" + "Alert gpu" + "Alert loss" + "Alert ram") > 0'),
              # GPU limiter badge: one at a time, thermal > power > voltage
              ("Lim T", '"GPU lim thermal" > 0'),
              ("Lim P", '("GPU lim power" > 0) * ("GPU lim thermal" == 0)'),
              ("Lim V", '("GPU lim volt" > 0) * ("GPU lim power" == 0) * ("GPU lim thermal" == 0)'),
              ("Status ok", '"EvilOS status" == 2'), ("Status warn", '"EvilOS status" == 1'),
              # amber icons when approaching a limit
              ("CPU warn", '"CPU temp" > 75'),
              ("GPU warn", '("GPU temp" > 72) + ("GPU hotspot" > 88) > 0'),
              ("RAM warn", '"RAM usage percent" > 80'),
              ("VRAM warn", '("GPU1 memory usage percent" > 85) + ("VRAM temp" > 90) > 0'),
              ("DISK warn", '("Disk temp" > 60) + ("Disk active" > 90) > 0')):
    sources.append((n, "", "", fx, STUB))
for n, fx in (("Blink", '("Alert any" > 0) * ((x % 1000) < 500)'), ("Blink batt", '("Alert batt" > 0) * ((x % 1000) < 500)'),
              ("CPU hot pulse", '("CPU temp" > 85) * ((x % 800) < 400)'),
              ("GPU hot pulse", '(("GPU temp" > 80) + ("GPU hotspot" > 95) > 0) * ((x % 800) < 400)')):
    sources.append((n, "", "", fx, TIMER))
SRC = {s[0]: s for s in sources}


def vis_src(visible, mode):
    """VisibilitySource for a layer in layout `mode` (V/H): combines its own condition with the mode."""
    if not visible:
        return f"Mode {mode}"
    name = f"{visible} @{mode}"
    if name not in SRC:
        _n, u, f, fx, prov = SRC[visible]
        # stubs: reference the condition by name; timers: keep their own clock so blinking stays smooth
        # RTSS validates a formula once at load time, when every source is still FLT_MAX; a product of two
        # FLT_MAX values overflows and the formula is then ignored forever -> only multiply comparisons (0/1).
        fx2 = (f'("{visible}" > 0) * ("Mode {mode}" > 0)' if prov is STUB
               else f'(({fx}) > 0) * ("Mode {mode}" > 0)')
        s = (name, u, f, fx2, prov)
        sources.append(s)
        SRC[name] = s
    return name


# ---- layers --------------------------------------------------------------------------------------------
layers = []
MODE = "V"


def layer(name, text, x, y, ex, ey, origin=0, color=None, bgnd=None, size=None, border=None, bsize=0,
          refresh=None, visible=None):
    d = {"Name": f"[{MODE}] {name}", "Text": text, "PositionX": x, "PositionY": y, "ExtentX": ex, "ExtentY": ey,
         "ExtentOrigin": origin, "FixedAlignment": 1}
    if size:
        d["Size"] = size
    if color:
        d["TextColor"] = color
    if bgnd:
        d["BgndColor"] = bgnd
    if border:
        d["BorderColor"], d["BorderSize"] = border, bsize
    if refresh:
        d["RefreshPeriod"] = refresh
    d["VisibilitySource"] = vis_src(visible, MODE)
    layers.append(d)


def txt(name, text, col, y, width, h, origin=3, color=None, size=VAL, visible=None):
    layer(name, text, -col, y, -width, h, origin=origin, color=color, size=size, visible=visible)


def cell(name, text, col, y, width, h, color=None, size=VAL, visible=None):
    """Right-aligned value cell occupying columns col..col+width-1."""
    txt(name, text, col, y, width, h, origin=5, color=color, size=size, visible=visible)


def pre(name, text, col, y, h, size=SMALL):
    """Small dim prefix at the left edge of a value cell (separate layer so the value keeps its size)."""
    txt(f"{name} prefix", f"<C={DIM}>{text}", col, y, 3, h, size=size)


def icon_px(name, x_u, y, side, visible=None, refresh=None, text=None):
    layer(f"{name} icon" + (f" ({visible})" if visible else ""), text or img(name), x_u, y, side, side,
          visible=visible, refresh=refresh, size=20)


def icon(name, col, y, side, visible=None, refresh=None, text=None):
    layer(f"{name} icon" + (f" ({visible})" if visible else ""), text or img(name), -col, y, side, side,
          visible=visible, refresh=refresh, size=20)


def seg_bar(name, src, y, h, warn, low_is_bad=False):
    """10-segment LED bar: bar graph + gap-mask sprite on top; colour blends with the value."""
    by = y + (h - 5) // 2
    if low_is_bad:
        col = blend(src, [(20, RED), (50, BLOOD)])
    else:
        col = blend(src, [(warn * 4 // 10, BLOOD), (warn, RED), (100, HOT)])
    layer(f"{name} bar", f"<G={src},-7,5,0,0,100,18>", -30, by, -7, 5, color=col)
    layer(f"{name} bar seg", img("segmask"), -30, by, -7, 5, size=20)


def block(name, y, model, usage_src, warn_crit, hot=None, warn=None, label=None):
    """Compact component block: small model line (7u) over a value line (12u); big icon spans both."""
    icon(name, 1, y + 1, 17)
    if warn:
        icon(name, 1, y + 1, 17, visible=warn, text=img(f"{name} warn"))
    if hot:
        icon(name, 1, y + 1, 17, visible=hot, refresh=100, text=img(f"{name} hot"))
    txt(f"{name} title", f"<C={LBL}>{label or name}  <C={MODEL}>{model}", 6, y, 24, 8, size=SMALL)
    vy = y + 7
    if usage_src:
        cell(f"{name} usage", f"%{usage_src}%{unit('%')}", 6, vy, 4, 12, thr(usage_src, *warn_crit))
        seg_bar(name, usage_src, vy, 12, warn_crit[0])
    return vy


def single(name, y, h=12, label=None, warn=None):
    icon(name, 2, y + (h - 11) // 2, 11)
    if warn:
        icon(name, 2, y + (h - 11) // 2, 11, visible=warn, text=img(f"{name} warn"))
    txt(f"{name} label", f"<C={LBL}>{label or name}", 6, y, 4, h, size=LABEL)


def temp_cell(name, src, col, y, h, warn, crit):
    cell(f"{name} temp", f"%{src}%{unit(DEG)}", col, y, 5, h, thr(src, warn, crit))


def spark(name, src, y, lo, hi, warn, crit):
    layer(f"{name} spark", f"<G={src},-7,6,0,{lo},{hi},0>", -30, y + 1, -7, 6,
          color=blend(src, [(warn - 15, BLOOD), (warn, AMBER), (crit, RED)]))


# =========================================================================================================
# VERTICAL panel (default; Scroll Lock toggles)
# =========================================================================================================
MODE = "V"
Y, y = {}, 0
for key, h in (("header", 14), ("sub", 10), ("frame", 11), ("cpu", 19), ("gpu", 19), ("vram", 12), ("ram", 19),
               ("disk", 12), ("net", 12), ("fans", 13), ("ups", 19), ("pwr", 12), ("ping", 12), ("pad", 2)):
    Y[key] = (y, h)
    y += h
TOTAL = y
BANDS = (("frame",), ("gpu", "vram"), ("disk", "net"), ("ups", "pwr"))
SHADOW_PX = 10
SPR_W, SPR_H = PW_PX + SHADOW_PX, TOTAL * 2 + SHADOW_PX

# background sprite (panel, shadow, bands, header, border) drawn 1:1; alarm border sprite next to it
layer("Panel sprite", f"<I=0,0,0,{SPRITE_Y},{SPR_W},{SPR_H}>", 0, 0, SPR_W // 2, SPR_H // 2, size=20)
hy, hh = Y["header"]
layer("Header alarm", "", 6, hy + 1, PW_PX // 2 - 12, hh - 2, bgnd="B0FF1F33", visible="Blink batt", refresh=100,
      size=20)
icon("logo", 1, hy + 1, 12)
txt("Title", f"<C={BONE}>EVIL<C={RED}>//<C={BONE}>OS", 3, hy, 9, hh, size=100)
txt("Clock", f"<C={DIM}>%Time24%", 15, hy, 8, hh, origin=4, size=80)
for n, vis in (("dot red", None), ("dot amber", "Status warn"), ("dot green", "Status ok")):
    layer(f"Status {n}", img(n), -24, hy + 3, 8, 8, size=20, visible=vis)
cell("FPS", f"<FR>{unit(' FPS')}", 28, hy, 9, hh, size=100,
     color=blend("Framerate", [(30, RED), (50, AMBER), (60, BONE)]))

# sub-header: game / API / resolution, replaced by alerts when something is wrong
sy, sh = Y["sub"]
txt("Game", f"<C={BONE}><EXE><C={BLOOD}>  ·  <C={DIM}><API><C={BLOOD}>  ·  <C={DIM}><RES>", 1, sy, 36, sh,
    size=TINY)
layer("Alert bg", "", 1, sy, PW_PX // 2 - 2, sh, bgnd="FFB0101F", visible="Alert any", size=20)
for col, src, text in ((1, "Alert batt", "ON BATTERY"), (9, "Alert cpu", "CPU HOT"), (15, "Alert gpu", "GPU HOT"),
                       (21, "Alert loss", "PACKET LOSS"), (30, "Alert ram", "RAM FULL")):
    txt(f"{src} text", f"<C={BONE}>{text}", col, sy, 9, sh, size=TINY, visible=src)

# frame pacing
fy, fh = Y["frame"]
txt("FT label", f"<C={LBL}>FRAME", 1, fy, 5, fh, size=SMALL)
cell("FT value", f"<FT>{unit(' ms')}", 6, fy, 8, fh, blend("Frametime", [(12, BONE), (20, AMBER), (34, RED)]))
layer("FT spikes", "<G=Frametime,-22,9,0,25,60,1>", -15, fy + 1, -22, 9, color=rgb(AMBER))
layer("FT graph", "<G=Frametime,-22,9,0,0,50,0>", -15, fy + 1, -22, 9, color=rgb(RED))

# CPU
y0, _ = Y["cpu"]
vy = block("CPU", y0, NAMES["CPU"], "CPU usage", (75, 90), hot="CPU hot pulse", warn="CPU warn")
spark("CPU temp", "CPU temp", y0, 30, 95, 75, 88)
cell("CPU clock", f"<C={BONE}>%CPU clock%{unit(' MHz')}", 10, vy, 8, 12)
temp_cell("CPU", "CPU temp", 18, vy, 12, 75, 88)
cell("CPU power", f"<C={BONE}>%CPU power%{unit('W')}", 23, vy, 6, 12)

# GPU
y0, _ = Y["gpu"]
vy = block("GPU", y0, NAMES["GPU"], "GPU1 usage", (75, 90), hot="GPU hot pulse", warn="GPU warn")
spark("GPU temp", "GPU temp", y0, 30, 90, 72, 83)
for vis, t, c in (("Lim T", "THERMAL", RED), ("Lim P", "PWR LIM", AMBER), ("Lim V", "VOLT LIM", AMBER)):
    cell(f"GPU badge {vis}", f"<C={c}>{t}", 24, y0, 5, 8, size=55, visible=vis)
cell("GPU clock", f"<C={BONE}>%GPU1 clock%{unit(' MHz')}", 10, vy, 8, 12)
temp_cell("GPU", "GPU temp", 18, vy, 12, 72, 83)
cell("GPU power", f"<C={BONE}>%GPU power%{unit('W')}", 23, vy, 6, 12)

y0, h = Y["vram"]
single("VRAM", y0, h, warn="VRAM warn")
cell("VRAM used", f"<C={BONE}>%GPU1 memory usage%<C={DIM}>/%GPU1 total memory%{unit('G')}", 10, y0, 8, h)
temp_cell("VRAM", "VRAM temp", 18, y0, h, 85, 95)
cell("VRAM pct", f"%GPU1 memory usage percent%{unit('%')}", 23, y0, 6, h, thr("GPU1 memory usage percent", 80, 92))
seg_bar("VRAM", "GPU1 memory usage percent", y0, h, 80)

# RAM
y0, _ = Y["ram"]
vy = block("RAM", y0, NAMES["RAM"], "RAM usage percent", (80, 92), warn="RAM warn")
cell("RAM clock", f"<C={BONE}>%RAM clock%{unit(' MT/s')}", 10, vy, 8, 12)
temp_cell("RAM", "RAM temp", 18, vy, 12, 60, 75)
pre("MB", "MB", 24, vy, 12)
cell("MB temp", f"%MB temp%{unit(DEG)}", 25, vy, 4, 12, thr("MB temp", 60, 75))

# disks / network
y0, h = Y["disk"]
single("DISK", y0, h, warn="DISK warn")
cell("Disk rate", f"<C={BONE}>%Disk rate%{unit(' MB/s')}", 10, y0, 8, h)
temp_cell("Disk", "Disk temp", 18, y0, h, 60, 70)
cell("Disk active", f"%Disk active%{unit('%')}", 23, y0, 6, h, thr("Disk active", 70, 95))
seg_bar("Disk", "Disk active", y0, h, 70)

y0, h = Y["net"]
single("NET", y0, h)
pre("DL", "DL", 10, y0, h)
cell("Net down", f"<C={BONE}>%Net down%{unit(' Mb')}", 10, y0, 8, h)
pre("UL", "UL", 19, y0, h)
cell("Net up", f"<C={BONE}>%Net up%{unit(' Mb/s')}", 19, y0, 10, h)
layer("Net graph", "<G=Net down,-7,9,0,0,100,1>", -30, y0 + 1, -7, 9, color=rgb(RED))

# fans: pixel X so icon / label / value never touch
y0, h = Y["fans"]
for gcol, key, val in ((1, "CPU", f"<C={BONE}>%CPU fan rpm%{unit(' rpm')}"),
                       (13, "SYS", f"<C={BONE}>%SYS fan rpm%{unit(' rpm')}"),
                       (25, "GPU", f"<C={BONE}>%GPU1 fan speed%{unit('%')}")):
    gx = round(gcol * COL_U)
    icon_px(f"Fan {key}", gx, y0, 13, refresh=16,
            text=f"<AI=Fan anim {key},0,0,0,{FAN_FRAMES - 1},0,128,128,128,{FAN_FRAMES},{FAN_FRAMES},0>")
    layer(f"Fan {key} label", f"<C={LBL}>{key}", gx + 16, y0, 20, h, origin=3, size=LABEL)
    layer(f"Fan {key} value", val, gx + 34, y0, 40, h, origin=5, size=VAL)

# UPS / power
y0, _ = Y["ups"]
vy = block("UPS", y0, NAMES["UPS"], None, None)
cell("UPS status", f"<IF UPS on battery><C={RED}>ON BATTERY<ELSE><C={GREEN}>ONLINE<IF>", 26, y0, 11, 8, size=SMALL)
cell("UPS battery", f"%UPS battery%{unit('%')}", 6, vy, 4, 12, thr_low("UPS battery", 20, 50, 80))
cell("UPS runtime", f"<C={BONE}>%UPS runtime%{unit(' min left')}", 10, vy, 13, 12)
seg_bar("UPS", "UPS battery", vy, 12, 30, low_is_bad=True)

y0, h = Y["pwr"]
single("PWR", y0, h)
cell("Mains voltage", f"%UPS input voltage%{unit('V')}", 10, y0, 8, h,
     blend("UPS input voltage", [(200, RED), (210, BONE), (250, BONE), (258, RED)]))
cell("Power watts", f"%UPS power%{unit('W')}", 18, y0, 5, h, thr("UPS load", 60, 85))
cell("Load pct", f"%UPS load%{unit('%')}", 23, y0, 6, h, thr("UPS load", 60, 85))
seg_bar("Load", "UPS load", y0, h, 60)

# ping
y0, h = Y["ping"]
single("PING", y0, h)
cell("Ping value", f"%Ping ms%{unit(' ms')}", 10, y0, 8, h, net_col("Ping ms", 40, 100))
pre("Jitter", "±", 18, y0, h, size=LABEL)
cell("Ping jitter", "%Ping jitter%", 18, y0, 5, h, net_col("Ping jitter", 3, 20))
cell("Ping loss", f"%Ping loss%{unit('% loss')}", 23, y0, 6, h, net_col("Ping loss", 0.5, 5))
layer("Ping graph", "<G=Ping ms,-7,9,0,0,100,0>", -30, y0 + 1, -7, 9,
      color=net_col("Ping ms", 40, 100))

# blinking alarm border (sprite next to the panel sprite)
layer("Frame alarm", f"<I=0,0,{SPR_W},{SPRITE_Y},{SPR_W},{SPR_H}>", 0, 0, SPR_W // 2, SPR_H // 2, size=20,
      visible="Blink", refresh=100)

# =========================================================================================================
# HORIZONTAL bar (Scroll Lock): one 14-unit line along the top edge
# =========================================================================================================
MODE = "H"
HW, HH = 116, 14
layer("Bar bg", "", 0, 0, -HW, HH, bgnd="EB050506", border="CC9C0F1D", bsize=1, size=20)
layer("Bar accent", "", 0, 0, 2, HH, bgnd=RED, size=20)
layer("Bar alarm", "", 0, 0, -HW, HH, border="FFFF1F33", bsize=3, visible="Blink", refresh=100, size=20)
icon("logo", 1, 1, 12)


def hcell(name, text, col, width, color=None, size=VAL, origin=5, visible=None):
    layer(name, text, -col, 0, -width, HH, origin=origin, color=color, size=size, visible=visible)


def hicon(name, col, warn=None, hot=None):
    icon(name, col, 2, 10)
    if warn:
        icon(name, col, 2, 10, visible=warn, text=img(f"{name} warn"))
    if hot:
        icon(name, col, 2, 10, visible=hot, refresh=100, text=img(f"{name} hot"))


hcell("FPS", f"<FR>{unit(' FPS')}", 3, 8, blend("Framerate", [(30, RED), (50, AMBER), (60, BONE)]), size=100)
hcell("FT", f"<FT>{unit(' ms')}", 11, 7, blend("Frametime", [(12, BONE), (20, AMBER), (34, RED)]))
hicon("CPU", 19, warn="CPU warn", hot="CPU hot pulse")
hcell("CPU usage", f"%CPU usage%{unit('%')}", 21, 4, thr("CPU usage", 75, 90))
hcell("CPU temp", f"%CPU temp%{unit(DEG)}", 25, 4, thr("CPU temp", 75, 88))
hicon("GPU", 30, warn="GPU warn", hot="GPU hot pulse")
hcell("GPU usage", f"%GPU1 usage%{unit('%')}", 32, 4, thr("GPU1 usage", 75, 90))
hcell("GPU temp", f"%GPU temp%{unit(DEG)}", 36, 4, thr("GPU temp", 72, 83))
hcell("GPU power", f"<C={BONE}>%GPU power%{unit('W')}", 40, 5)
hicon("VRAM", 46, warn="VRAM warn")
hcell("VRAM", f"<C={BONE}>%GPU1 memory usage%<C={DIM}>/%GPU1 total memory%{unit('G')}", 48, 8)
hicon("RAM", 57, warn="RAM warn")
hcell("RAM", f"%RAM usage percent%{unit('%')}", 59, 4, thr("RAM usage percent", 80, 92))
hicon("NET", 64)
hcell("NET", f"<C={BONE}>%Net down%{unit(' Mb')}", 66, 8)
hicon("PING", 75)
hcell("PING", f"%Ping ms%{unit(' ms')}", 77, 6, net_col("Ping ms", 40, 100))
hicon("PWR", 84)
hcell("UPS W", f"%UPS power%{unit('W')}", 86, 5, thr("UPS load", 60, 85))
hcell("UPS st", f"<IF UPS on battery><C={RED}>BATTERY<ELSE><C={GREEN}>ONLINE<IF>", 92, 8, size=SMALL)
hcell("Clock", f"<C={DIM}>%Time24%", 101, 9, size=80)
for n, vis in (("dot red", None), ("dot amber", "Status warn"), ("dot green", "Status ok")):
    layer(f"Status {n}", img(n), -111, 3, 8, 8, size=20, visible=vis)


# =========================================================================================================
# panel sprites -> EvilOS.png
# =========================================================================================================
def rounded_mask(w, h, r):
    m = Image.new("L", (w, h), 0)
    ImageDraw.Draw(m).rounded_rectangle((0, 0, w - 1, h - 1), radius=r, fill=255)
    return m


def panel_sprites():
    pw, ph, r = PW_PX, TOTAL * 2, 10
    bg = Image.new("RGBA", (SPR_W, SPR_H), (0, 0, 0, 0))
    # soft drop shadow
    sh = Image.new("RGBA", (SPR_W, SPR_H), (0, 0, 0, 0))
    ImageDraw.Draw(sh).rounded_rectangle((4, 6, pw + 3, ph + 5), radius=r, fill=(0, 0, 0, 150))
    bg.alpha_composite(sh.filter(ImageFilter.GaussianBlur(3)))
    # panel body
    body = Image.new("RGBA", (pw, ph), (5, 5, 6, 235))
    d = ImageDraw.Draw(body)
    for keys in BANDS:
        y0 = Y[keys[0]][0] * 2
        y1 = y0 + sum(Y[k][1] for k in keys) * 2
        d.rectangle((0, y0, pw, y1 - 1), fill=(13, 6, 8, 240))
    sy0, sh_u = Y["sub"]
    d.rectangle((0, sy0 * 2, pw, (sy0 + sh_u) * 2 - 1), fill=(10, 5, 6, 245))
    hy0, hh_u = Y["header"]
    hpx = (hy0 + hh_u) * 2
    for x in range(pw):                                     # header gradient blood -> void
        t = x / (pw - 1)
        d.line((x, 0, x, hpx - 3), fill=(int(56 - 42 * t), int(9 - 4 * t), int(16 - 8 * t), 250))
    d.rectangle((0, 0, 4, hpx - 3), fill=(255, 31, 51, 255))    # left accent
    glow = Image.new("RGBA", (pw, ph), (0, 0, 0, 0))
    ImageDraw.Draw(glow).rectangle((0, hpx - 3, pw, hpx - 1), fill=(255, 31, 51, 255))
    body.alpha_composite(glow.filter(ImageFilter.GaussianBlur(3)))
    body.alpha_composite(glow)
    mask = rounded_mask(pw, ph, r)
    body.putalpha(Image.composite(body.split()[3], Image.new("L", (pw, ph), 0), mask))
    bg.alpha_composite(body)
    ImageDraw.Draw(bg).rounded_rectangle((0, 0, pw - 1, ph - 1), radius=r, outline=(156, 15, 29, 210), width=1)
    alarm = Image.new("RGBA", (SPR_W, SPR_H), (0, 0, 0, 0))
    ImageDraw.Draw(alarm).rounded_rectangle((0, 0, pw - 1, ph - 1), radius=r, outline=(255, 31, 51, 255), width=4)
    return bg, alarm


atlas_path = os.path.join(HERE, "EvilOS.png")
base = Image.open(atlas_path).convert("RGBA").crop((0, 0, 1024, SPRITE_Y))
bg, alarm = panel_sprites()
assert SPR_W * 2 <= 1024, "panel sprites do not fit side by side"
atlas = Image.new("RGBA", (1024, SPRITE_Y + SPR_H), (0, 0, 0, 0))
atlas.alpha_composite(base)
atlas.alpha_composite(bg, (0, SPRITE_Y))
atlas.alpha_composite(alarm, (SPR_W, SPRITE_Y))
atlas.save(atlas_path)

# ---- write .ovl ---------------------------------------------------------------------------------------------
out = ["[Master]", "Implementation=2", "FontFace=JetBrainsMono NF", "FontHeight=-11", "FontWeight=700",
       "ZoomRatio=2",
       "[Settings]", "Name=EvilOS", "RefreshPeriod=1000", "LockUserSettings=1", "EmbeddedImage=EvilOS.png",
       "[General]", f"Sources={len(sources)}", "Tables=0", f"Layers={len(layers)}"]
for i, (n, u, f, fx, prov) in enumerate(sources):
    out += [f"[Source{i}]", f"Name={n}", f"Units={u}", f"Format={f}", f"Formula={fx}"]
    out += [f"{k}={v}" for k, v in prov.items()]
for i, d in enumerate(layers):
    out.append(f"[Layer{i}]")
    out += [f"{k}={v}" for k, v in d.items()]

dst = os.path.join(HERE, "EvilOS.ovl")
with open(dst, "w", encoding="cp1252", newline="\r\n") as fh:
    fh.write("\n".join(out) + "\n")
print(NAMES)
print(dst, len(sources), "sources", len(layers), "layers", f"panel {PW_PX}x{TOTAL * 2}px")
