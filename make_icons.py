"""Draws EvilOS.png - 1024x128 sprite atlas (8 icons, 128x128 each) for the RTSS overlay.

Row 0 (y=0):   0 logo, 1 CPU, 2 GPU, 3 RAM, 4 VRAM, 5 UPS, 6 PING, 7 MAINS
Row 1 (y=128): 8 animation frames of a 6-blade fan (7.5 deg apart = one blade step)
Row 2 (y=256): 0 DISK, 1 CPU hot, 2 GPU hot, 3 status dot green, 4 amber, 5 red, 6 bar segment mask, 7 header strip
Row 3 (y=384): 0 NET, 1 CPU warn, 2 GPU warn, 3 RAM warn, 4 VRAM warn, 5 DISK warn (amber)
Style: hackthecode.github.io - neon red line art with glow, bone accents.
"""
import math
import os
from PIL import Image, ImageDraw, ImageFilter

S = 4                       # supersampling
C = 128 * S                 # cell size while drawing
RED = (255, 31, 51, 255)
BLOOD = (156, 15, 29, 255)
BONE = (236, 229, 221, 255)
DARK = (156, 15, 29, 90)
LW = 7 * S                  # main stroke


def P(*xy):
    """Scale 0..128 coordinates to the supersampled canvas."""
    return [v * S for v in xy]


def new():
    return Image.new("RGBA", (C, C), (0, 0, 0, 0))


def finish(line):
    """Compose glow + line art, downscale to 128."""
    glow = line.filter(ImageFilter.GaussianBlur(9 * S))
    r, g, b, a = glow.split()
    glow = Image.merge("RGBA", (r, g, b, a.point(lambda v: min(255, int(v * 1.6)))))
    out = Image.new("RGBA", (C, C), (0, 0, 0, 0))
    out.alpha_composite(glow)
    out.alpha_composite(line)
    return out.resize((128, 128), Image.LANCZOS)


def rrect(d, box, r, outline=RED, fill=None, w=LW):
    d.rounded_rectangle(P(*box), radius=r * S, outline=outline, fill=fill, width=w)


# ---------------------------------------------------------------- icons
def logo():
    im = new(); d = ImageDraw.Draw(im)
    cx, cy, R = 64, 70, 46
    hexa = [P(cx + R * math.cos(math.radians(a)), cy + R * math.sin(math.radians(a))) for a in range(-90, 270, 60)]
    d.polygon([tuple(p) for p in hexa], fill=DARK)
    d.line([tuple(p) for p in hexa + [hexa[0]]], fill=RED, width=LW, joint="curve")
    # horns
    d.polygon([tuple(P(*p)) for p in [(30, 40), (14, 4), (44, 30)]], fill=RED)
    d.polygon([tuple(P(*p)) for p in [(98, 40), (114, 4), (84, 30)]], fill=RED)
    # E
    for box in [(44, 44, 54, 96), (44, 44, 86, 54), (44, 65, 78, 75), (44, 86, 86, 96)]:
        d.rectangle(P(*box), fill=BONE)
    # glitch ticks
    d.rectangle(P(88, 58, 98, 61), fill=RED)
    d.rectangle(P(30, 80, 38, 83), fill=RED)
    return finish(im)


def cpu():
    im = new(); d = ImageDraw.Draw(im)
    rrect(d, (28, 28, 100, 100), 10, fill=DARK)
    rrect(d, (46, 46, 82, 82), 4, outline=BONE, w=5 * S)
    for i in range(4):
        o = 40 + i * 16
        for a, b, c_, e in [(o, 8, o, 26), (o, 102, o, 120), (8, o, 26, o), (102, o, 120, o)]:
            d.line(P(a, b, c_, e), fill=RED, width=5 * S)
    d.ellipse(P(36, 36, 42, 42), fill=BONE)
    return finish(im)


def gpu():
    im = new(); d = ImageDraw.Draw(im)
    rrect(d, (8, 30, 120, 92), 8, fill=DARK)
    for cx in (40, 88):
        d.ellipse(P(cx - 20, 41, cx + 20, 81), outline=BONE, width=4 * S)
        for k in range(5):
            a = math.radians(k * 72)
            d.line(P(cx, 61, cx + 15 * math.cos(a), 61 + 15 * math.sin(a)), fill=RED, width=4 * S)
        d.ellipse(P(cx - 4, 57, cx + 4, 65), fill=BONE)
    for x in range(24, 108, 10):            # PCIe fingers
        d.line(P(x, 94, x, 106), fill=RED, width=4 * S)
    return finish(im)


def ram():
    im = new(); d = ImageDraw.Draw(im)
    rrect(d, (6, 36, 122, 86), 6, fill=DARK)
    for x in (14, 40, 70, 96):
        d.rectangle(P(x, 46, x + 18, 68), outline=BONE, width=4 * S)
    for x in range(12, 118, 7):             # contacts
        if 58 <= x <= 66:
            continue
        d.line(P(x, 78, x, 86), fill=RED, width=3 * S)
    d.rectangle(P(58, 76, 68, 90), fill=(0, 0, 0, 0))
    d.line(P(6, 100, 122, 100), fill=BLOOD, width=3 * S)
    return finish(im)


def vram():
    im = new(); d = ImageDraw.Draw(im)
    for i, y in enumerate((22, 50, 78)):
        rrect(d, (26, y, 102, y + 22), 4, outline=RED if i != 1 else BONE, fill=DARK, w=5 * S)
        for x in range(34, 98, 10):
            d.line(P(x, y + 22, x, y + 27), fill=RED, width=3 * S)
    d.line(P(12, 12, 12, 116), fill=BLOOD, width=4 * S)
    d.line(P(116, 12, 116, 116), fill=BLOOD, width=4 * S)
    return finish(im)


def ups():
    im = new(); d = ImageDraw.Draw(im)
    rrect(d, (14, 34, 106, 94), 10, fill=DARK)
    d.rectangle(P(106, 52, 116, 76), fill=RED)
    bolt = [(70, 38), (44, 68), (62, 68), (54, 90), (82, 58), (64, 58)]
    d.polygon([tuple(P(*p)) for p in bolt], fill=BONE)
    return finish(im)


def ping():
    im = new(); d = ImageDraw.Draw(im)
    cx, cy = 64, 100
    for i, r in enumerate((26, 50, 74)):
        d.arc(P(cx - r, cy - r, cx + r, cy + r), 220, 320, fill=RED if i < 2 else BONE, width=LW)
    d.ellipse(P(cx - 9, cy - 9, cx + 9, cy + 9), fill=RED)
    d.line(P(cx, cy, cx + 44, cy - 66), fill=BLOOD, width=3 * S)   # radar sweep
    return finish(im)


def mains():
    im = new(); d = ImageDraw.Draw(im)
    rrect(d, (30, 40, 98, 86), 12, fill=DARK)
    for x in (48, 80):
        d.line(P(x, 14, x, 40), fill=BONE, width=LW)
    d.line(P(64, 86, 64, 104), fill=RED, width=LW)
    d.arc(P(64, 92, 112, 124), 180, 270, fill=RED, width=LW)
    d.polygon([tuple(P(*p)) for p in [(68, 46), (54, 66), (64, 66), (58, 80), (74, 60), (64, 60)]], fill=BONE)
    return finish(im)


def fan(phase):
    """One frame of the fan; phase 0..1 = rotation by one blade step (60 deg)."""
    im = new(); d = ImageDraw.Draw(im)
    rrect(d, (8, 8, 120, 120), 18, fill=DARK, w=5 * S)
    for x, y in ((20, 20), (108, 20), (20, 108), (108, 108)):
        d.ellipse(P(x - 4, y - 4, x + 4, y + 4), fill=BONE)
    cx = cy = 64
    d.ellipse(P(cx - 51, cy - 51, cx + 51, cy + 51), fill=(10, 3, 5, 255), outline=BLOOD, width=4 * S)
    r0, r1 = 13, 47
    for b in range(6):
        base = b * 60 + phase * 60
        lead, trail = [], []
        for i in range(13):
            t = i / 12
            r = r0 + (r1 - r0) * t
            a = base + 38 * t                       # swept blade
            w = 16 + 18 * t                         # wider at the tip
            lead.append((cx + r * math.cos(math.radians(a)), cy + r * math.sin(math.radians(a))))
            trail.append((cx + r * math.cos(math.radians(a + w)), cy + r * math.sin(math.radians(a + w))))
        poly = [tuple(P(*p)) for p in lead + trail[::-1]]
        d.polygon(poly, fill=RED, outline=(10, 3, 5, 255), width=2 * S)
    d.ellipse(P(cx - 14, cy - 14, cx + 14, cy + 14), fill=(20, 6, 9, 255), outline=BONE, width=4 * S)
    d.ellipse(P(cx - 4, cy - 4, cx + 4, cy + 4), fill=RED)
    return finish(im)


def disk():
    im = new(); d = ImageDraw.Draw(im)
    rrect(d, (10, 40, 118, 88), 6, fill=DARK)                       # M.2 stick
    d.rectangle(P(18, 50, 44, 78), outline=BONE, width=4 * S)        # controller
    for x in (52, 76):                                               # NAND
        d.rectangle(P(x, 50, x + 18, 78), outline=RED, width=4 * S)
    for y in range(46, 86, 6):                                       # edge contacts
        d.line(P(112, y, 120, y), fill=RED, width=2 * S)
    d.ellipse(P(100, 58, 108, 66), fill=(76, 255, 122, 255))         # activity LED
    d.ellipse(P(4, 58, 12, 70), outline=BLOOD, width=3 * S)          # screw notch
    return finish(im)


def hot(icon_fn):
    """White-hot / amber re-tint of an icon with a stronger glow (shown pulsing when overheating)."""
    base = icon_fn()
    px = base.load()
    out = Image.new("RGBA", base.size, (0, 0, 0, 0)); po = out.load()
    for y in range(base.height):
        for x in range(base.width):
            r, g, b, a = px[x, y]
            if a == 0:
                continue
            L = max(r, g, b) / 255
            po[x, y] = (255, int(120 + 125 * L), int(20 + 180 * L * L), int(255 * (a / 255) ** 1.8))
    glow = out.filter(ImageFilter.GaussianBlur(5))
    res = Image.new("RGBA", base.size, (0, 0, 0, 0))
    res.alpha_composite(glow); res.alpha_composite(glow); res.alpha_composite(out)
    return res


def warn(icon_fn):
    """Amber re-tint of an icon (approaching the limit)."""
    base = icon_fn()
    px = base.load()
    out = Image.new("RGBA", base.size, (0, 0, 0, 0)); po = out.load()
    for y in range(base.height):
        for x in range(base.width):
            r, g, b, a = px[x, y]
            if a == 0:
                continue
            L = max(r, g, b) / 255
            po[x, y] = (255, int(110 + 90 * L), int(10 + 60 * L * L), a)
    return out


def dot(color):
    im = new(); d = ImageDraw.Draw(im)
    d.ellipse(P(40, 40, 88, 88), fill=color)
    d.ellipse(P(52, 50, 68, 62), fill=(255, 255, 255, 140))           # highlight
    return finish(im)


def net():
    im = new(); d = ImageDraw.Draw(im)
    rrect(d, (10, 14, 118, 114), 14, fill=DARK, w=5 * S)
    # download arrow (red) / upload arrow (bone)
    d.line(P(46, 30, 46, 92), fill=RED, width=LW)
    d.polygon([tuple(P(*p)) for p in [(28, 74), (64, 74), (46, 100)]], fill=RED)
    d.line(P(82, 36, 82, 98), fill=BONE, width=LW)
    d.polygon([tuple(P(*p)) for p in [(64, 54), (100, 54), (82, 28)]], fill=BONE)
    return finish(im)


def segment_mask():
    """Dark gaps that turn a plain bar graph into 10 LED segments (stretched over the bar)."""
    im = Image.new("RGBA", (128, 128), (0, 0, 0, 0)); d = ImageDraw.Draw(im)
    for k in range(1, 10):
        x = round(128 * k / 10)
        d.rectangle((x - 2, 0, x + 2, 127), fill=(8, 4, 5, 255))
    return im


def header_strip():
    """Header background: blood gradient left -> void right, glowing red line at the bottom."""
    im = Image.new("RGBA", (128, 128), (0, 0, 0, 0)); px = im.load()
    for x in range(128):
        t = x / 127
        c = (int(52 - 40 * t), int(9 - 4 * t), int(15 - 8 * t))
        for y in range(128):
            px[x, y] = c + (255,)
    glow = Image.new("RGBA", (128, 128), (0, 0, 0, 0)); g = ImageDraw.Draw(glow)
    g.rectangle((0, 116, 127, 123), fill=(255, 31, 51, 255))
    glow = glow.filter(ImageFilter.GaussianBlur(6))
    im.alpha_composite(glow); im.alpha_composite(glow)
    d = ImageDraw.Draw(im)
    d.rectangle((0, 119, 127, 122), fill=(255, 31, 51, 255))
    return im


icons = [logo, cpu, gpu, ram, vram, ups, ping, mains]
atlas = Image.new("RGBA", (1024, 512), (0, 0, 0, 0))
for i, fn in enumerate(icons):
    atlas.alpha_composite(fn(), (i * 128, 0))
for i in range(8):
    atlas.alpha_composite(fan(i / 8), (i * 128, 128))
row2 = [disk(), hot(cpu), hot(gpu), dot((76, 255, 122, 255)), dot((255, 176, 32, 255)), dot((255, 31, 51, 255)),
        segment_mask(), header_strip()]
for i, im in enumerate(row2):
    atlas.alpha_composite(im, (i * 128, 256))
for i, im in enumerate([net(), warn(cpu), warn(gpu), warn(ram), warn(vram), warn(disk)]):
    atlas.alpha_composite(im, (i * 128, 384))
here = os.path.dirname(os.path.abspath(__file__))
atlas.save(os.path.join(here, "EvilOS.png"))
# preview on the site's void background
prev = Image.new("RGBA", (1024, 512), (5, 5, 6, 255))
prev.alpha_composite(atlas)
prev.save(os.path.join(here, "EvilOS_preview.png"))
print("ok")
