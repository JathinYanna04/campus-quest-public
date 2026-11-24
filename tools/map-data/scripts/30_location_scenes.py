#!/usr/bin/env python3
"""Agent C: location scene backgrounds (192x288), finale, cake/flame/smoke sprites.

Run: tools/map-data/.venv/bin/python tools/map-data/scripts/30_location_scenes.py
Outputs public/assets/locations/*.png + locations.json and
tools/map-data/output/locations_review.png. Only palette colours are used.
"""
import json
import math
import random
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont

ROOT = Path(__file__).resolve().parents[3]
TOOLS = ROOT / "tools" / "map-data"
OUT = ROOT / "public" / "assets" / "locations"
REVIEW = TOOLS / "output" / "locations_review.png"
PAL = {k: tuple(int(v[i:i + 2], 16) for i in (1, 3, 5))
       for k, v in json.loads((TOOLS / "palette.json").read_text())["colors"].items()}
FONT = str(TOOLS / "fonts" / "silkscreen_Silkscreen-Regular.ttf")
FONTB = str(TOOLS / "fonts" / "silkscreen_Silkscreen-Bold.ttf")
W, H = 192, 288
FLOOR_TOP, FLOOR_BOTTOM = 200, 272
BASE = 198  # where walls meet the floor


def C(n):
    return PAL[n]


class Canvas:
    def __init__(self, w=W, h=H, bg="sky-pale", alpha=False):
        mode = "RGBA" if alpha else "RGB"
        fill = (0, 0, 0, 0) if alpha else C(bg)
        self.im = Image.new(mode, (w, h), fill)
        self.d = ImageDraw.Draw(self.im)
        self.d.fontmode = "1"
        self.alpha = alpha

    def col(self, n):
        return C(n) + ((255,) if self.alpha else ())

    def rect(self, x0, y0, x1, y1, c):
        if x1 < x0 or y1 < y0:
            return
        self.d.rectangle([x0, y0, x1, y1], fill=self.col(c))

    def px(self, x, y, c):
        if 0 <= x < self.im.width and 0 <= y < self.im.height:
            self.im.putpixel((x, y), self.col(c))

    def line(self, pts, c, w=1):
        self.d.line(pts, fill=self.col(c), width=w)

    def poly(self, pts, c):
        self.d.polygon(pts, fill=self.col(c))

    def ellipse(self, x0, y0, x1, y1, c):
        self.d.ellipse([x0, y0, x1, y1], fill=self.col(c))

    def dither(self, x0, y0, x1, y1, c, step=2, off=0):
        for y in range(y0, y1 + 1):
            for x in range(x0, x1 + 1):
                if (x + y + off) % step == 0 and (y % 2 == 0 or step == 2):
                    self.px(x, y, c)

    def text(self, x, y, s, c, size=8, bold=False):
        f = ImageFont.truetype(FONTB if bold else FONT, size)
        self.d.text((x, y), s, font=f, fill=self.col(c))

    def tsize(self, s, size=8, bold=False):
        f = ImageFont.truetype(FONTB if bold else FONT, size)
        b = self.d.textbbox((0, 0), s, font=f)
        return b[2] - b[0], b[3] - b[1], b[0], b[1]


# ---------------------------------------------------------------- shared bits

def sky(cv, y0=0, y1=120, top="sky", mid="sky-pale", seed=1):
    cv.rect(0, y0, W - 1, y1, mid)
    split = y0 + (y1 - y0) * 2 // 5
    cv.rect(0, y0, W - 1, split, top)
    cv.dither(0, split + 1, W - 1, split + 6, top)
    rnd = random.Random(seed)
    for _ in range(3):
        cloud(cv, rnd.randint(0, W - 30), rnd.randint(y0 + 6, max(y0 + 7, split + 10)))


def cloud(cv, x, y):
    cv.ellipse(x, y + 3, x + 26, y + 11, "white")
    cv.ellipse(x + 6, y, x + 18, y + 9, "white")
    cv.rect(x + 3, y + 10, x + 24, y + 11, "cream")


def tree(cv, cx, base, r=14, trunk=18, dark="green-dark", mid="green", light="grass"):
    cv.rect(cx - 2, base - trunk, cx + 1, base, "brown")
    cv.rect(cx - 2, base - 7, cx + 1, base, "white")
    cv.rect(cx + 1, base - trunk, cx + 1, base, "brown-dark")
    cy = base - trunk - r + 4
    cv.ellipse(cx - r, cy - r, cx + r, cy + r, dark)
    cv.ellipse(cx - r + 2, cy - r, cx + r - 4, cy + r - 4, mid)
    cv.ellipse(cx - r + 4, cy - r + 2, cx + 2, cy - 2, light)
    cv.ellipse(cx - r + 1, cy - 2, cx - 2, cy + r - 2, mid)
    cv.px(cx - 4, cy - r + 5, "grass-light")
    cv.px(cx - 6, cy - r + 7, "grass-light")


def palm(cv, cx, base, h=40):
    for i in range(h):
        x = cx + int(math.sin(i / 9) * 2)
        cv.rect(x, base - i, x + 2, base - i, "tan" if i % 4 else "brown")
    tx, ty = cx + int(math.sin(h / 9) * 2) + 1, base - h
    for dx, dy in ((-14, 6), (14, 6), (-10, -6), (10, -6), (0, -9), (-16, 1), (16, 1)):
        cv.line([(tx, ty), (tx + dx, ty + dy)], "green", 2)
        cv.line([(tx, ty - 1), (tx + dx, ty + dy - 1)], "grass", 1)


def bush(cv, x, y, w=18, h=10):
    cv.ellipse(x, y, x + w, y + h, "green")
    cv.ellipse(x + 2, y, x + w - 5, y + h - 4, "grass")
    cv.px(x + 5, y + 2, "grass-light")
    cv.px(x + 9, y + 1, "grass-light")


def flowers(cv, x, y, w, rnd):
    for _ in range(w // 3):
        cv.px(x + rnd.randint(0, w), y + rnd.randint(0, 3), rnd.choice(["pink-pale", "yellow", "coral", "white"]))


def window(cv, x, y, w=12, h=14, frame="cream", glass="sky", deep="blue"):
    cv.rect(x - 1, y - 1, x + w, y + h, frame)
    cv.rect(x, y, x + w - 1, y + h - 1, glass)
    cv.rect(x, y + h // 2, x + w - 1, y + h - 1, deep)
    cv.line([(x + 1, y + h - 3), (x + 5, y + 1)], "sky-pale")
    cv.rect(x + w // 2, y, x + w // 2, y + h - 1, frame)
    cv.rect(x - 1, y + h, x + w, y + h + 1, "grey-light")


def sign(cv, text, cx, y, bg="blue-dark", fg="white", border="ink", trim="yellow", size=8,
         bold=False, padx=5, pady=3, lines=None, posts=0):
    lines = lines or [text]
    sizes = [cv.tsize(t, size, bold) for t in lines]
    tw = max(s[0] for s in sizes)
    lh = max(s[1] for s in sizes) + 2
    w = tw + padx * 2
    h = lh * len(lines) + pady * 2 - 2
    x0 = cx - w // 2
    if posts:
        for px_ in (x0 + 4, x0 + w - 6):
            cv.rect(px_, y + h, px_ + 1, y + h + posts, "brown-dark")
    cv.rect(x0 - 1, y - 1, x0 + w, y + h, border)
    cv.rect(x0, y, x0 + w - 1, y + h - 1, bg)
    cv.rect(x0 + 1, y + 1, x0 + w - 2, y + 1, trim)
    cv.rect(x0 + 1, y + h - 2, x0 + w - 2, y + h - 2, trim)
    cv.rect(x0 + w, y + 1, x0 + w, y + h, "plum" if border != "plum" else "ink")
    for i, (t, s) in enumerate(zip(lines, sizes)):
        tx = cx - s[0] // 2 - s[2]
        ty = y + pady + i * lh - s[3]
        cv.text(tx, ty, t, fg, size, bold)
    return x0, y, x0 + w, y + h


def paving(cv, top=BASE, a="sand-light", b="cream", grout="sand", kerb=True):
    cv.rect(0, top, W - 1, H - 1, a)
    for y in range(top + 4, H, 10):
        cv.rect(0, y, W - 1, y, grout)
        off = 0 if (y // 10) % 2 else 8
        for x in range(off, W, 16):
            cv.rect(x, y - 9 if y - 9 > top else top, x, y, grout)
            if (x + y) % 3 == 0:
                cv.rect(x + 2, y + 2, x + 6, y + 3, b)
    if kerb:
        for x in range(0, W, 8):
            cv.rect(x, top, x + 3, top + 2, "yellow")
            cv.rect(x + 4, top, x + 7, top + 2, "white")
        cv.rect(0, top + 3, W - 1, top + 3, "tan")
    shade_bottom(cv)


def shade_bottom(cv):
    cv.dither(0, 276, W - 1, 279, "tan" if False else "plum", 4)
    cv.rect(0, 280, W - 1, H - 1, "plum")
    cv.dither(0, 280, W - 1, H - 1, "ink", 3)


def grass_floor(cv, top=BASE, a="grass", b="grass-light", c="green", seed=3):
    cv.rect(0, top, W - 1, H - 1, a)
    rnd = random.Random(seed)
    for _ in range(500):
        x, y = rnd.randint(0, W - 1), rnd.randint(top, H - 1)
        cv.px(x, y, b)
        if rnd.random() < .4:
            cv.px(x, y - 1, c)
    shade_bottom(cv)


def tile_floor(cv, top=BASE, a="cream", b="sand-light", line="sand", gloss=False):
    cv.rect(0, top, W - 1, H - 1, a)
    for y in range(top, H, 12):
        for x in range(0, W, 12):
            if ((x // 12) + (y - top) // 12) % 2:
                cv.rect(x, y, x + 11, y + 11, b)
    for y in range(top, H, 12):
        cv.rect(0, y, W - 1, y, line)
    for x in range(0, W, 12):
        cv.rect(x, top, x, H - 1, line)
    if gloss:
        for i in range(0, 60, 3):
            cv.rect(30 + i, top + 6 + i // 2, 33 + i, top + 6 + i // 2, "white")
    shade_bottom(cv)


def skirting(cv, y=BASE - 3, c="brown"):
    cv.rect(0, y, W - 1, y + 2, c)
    cv.rect(0, y + 3, W - 1, y + 3, "brown-dark")


def bench(cv, x, y, w=30):
    cv.rect(x, y, x + w, y + 2, "tan")
    cv.rect(x, y + 3, x + w, y + 3, "brown")
    cv.rect(x + 2, y + 4, x + 3, y + 8, "brown-dark")
    cv.rect(x + w - 3, y + 4, x + w - 2, y + 8, "brown-dark")


def flagpole(cv, x, base, top=30):
    cv.rect(x, top, x + 1, base, "grey-light")
    cv.rect(x + 1, top, x + 1, base, "grey")
    cv.rect(x - 1, top - 2, x + 2, top - 1, "yellow")
    fx = x + 2
    for i in range(18):
        wave = int(math.sin(i / 3) * 1)
        cv.rect(fx + i, top + wave, fx + i, top + 3 + wave, "orange")
        cv.rect(fx + i, top + 4 + wave, fx + i, top + 7 + wave, "white")
        cv.rect(fx + i, top + 8 + wave, fx + i, top + 11 + wave, "green")
    cv.px(fx + 9, top + 5, "blue-dark")
    cv.px(fx + 9, top + 6, "blue-dark")
    cv.px(fx + 8, top + 5, "blue-dark")
    cv.px(fx + 10, top + 6, "blue-dark")
    cv.rect(x - 4, base - 3, x + 5, base, "grey")
    cv.rect(x - 4, base - 3, x + 5, base - 3, "grey-light")


def striped_wall(cv, y0, y1, a="orange", b="purple"):
    for y in range(y0, y1 + 1):
        cv.rect(0, y, W - 1, y, a if ((y - y0) // 3) % 2 == 0 else b)
    for x in range(0, W, 11):
        cv.rect(x, y0, x, y1, "plum")


def floodlight(cv, x, base, top):
    cv.rect(x, top, x + 1, base, "grey")
    cv.rect(x - 6, top - 6, x + 7, top, "asphalt-dark")
    for i in range(4):
        cv.rect(x - 5 + i * 3, top - 5, x - 4 + i * 3, top - 1, "yellow")
    for y in range(top + 6, base, 6):
        cv.line([(x - 1, y), (x + 2, y + 3)], "grey-light")


def door(cv, x, y, w=16, h=28, c="brown", frame="cream"):
    cv.rect(x - 2, y - 2, x + w + 1, y + h, frame)
    cv.rect(x, y, x + w - 1, y + h, c)
    cv.rect(x + w // 2, y, x + w // 2, y + h, "brown-dark")
    cv.rect(x + 2, y + 3, x + w // 2 - 2, y + 9, "sky")
    cv.px(x + w // 2 - 2, y + h // 2 + 2, "yellow")
    cv.px(x + w // 2 + 2, y + h // 2 + 2, "yellow")


def posters(cv, x, y, rnd, n=4):
    cols = ["pink-pale", "lime-pale", "yellow", "sky-pale", "coral", "lilac", "mint"]
    for i in range(n):
        c = rnd.choice(cols)
        px_ = x + i * 10 + rnd.randint(0, 2)
        py = y + rnd.randint(0, 4)
        cv.rect(px_, py, px_ + 7, py + 9, c)
        cv.rect(px_ + 1, py + 2, px_ + 6, py + 2, "plum")
        cv.rect(px_ + 1, py + 4, px_ + 4, py + 4, "grey")
        cv.rect(px_ + 1, py + 6, px_ + 5, py + 6, "grey")
        cv.px(px_ + 3, py, "red")


def fan(cv, cx, y):
    cv.rect(cx, 0, cx, y, "grey")
    cv.rect(cx - 3, y, cx + 3, y + 2, "asphalt")
    cv.rect(cx - 20, y + 1, cx - 4, y + 1, "grey-light")
    cv.rect(cx + 4, y + 1, cx + 20, y + 1, "grey-light")
    cv.rect(cx - 20, y + 2, cx - 4, y + 2, "grey")
    cv.rect(cx + 4, y + 2, cx + 20, y + 2, "grey")


def tube(cv, x, y, w=22):
    cv.rect(x, y, x + w, y + 2, "white")
    cv.rect(x, y + 2, x + w, y + 2, "grey-light")


# ---------------------------------------------------------------- scenes

def facade(cv, y0, c="cream", shade="grey-light", x0=0, x1=W - 1):
    cv.rect(x0, y0, x1, BASE, c)
    for y in range(y0 + 34, BASE, 34):
        cv.rect(x0, y, x1, y + 1, shade)


def s_a_block():
    cv = Canvas()
    sky(cv, 0, 60, seed=11)
    facade(cv, 18, "cream")
    cv.rect(0, 14, W - 1, 17, "grey")
    cv.rect(0, 14, W - 1, 14, "grey-light")
    for x in range(8, W, 24):
        window(cv, x, 26, 14, 14)
        window(cv, x, 60, 14, 14)
    # corridor: columns + doors on ground floor
    cv.rect(0, 96, W - 1, BASE, "sand-light")
    cv.rect(0, 96, W - 1, 103, "tan")
    cv.rect(0, 103, W - 1, 104, "brown")
    cv.rect(0, 105, W - 1, BASE, "sand-light")
    cv.dither(0, 105, W - 1, 110, "sand", 3)
    for i, x in enumerate((14, 108)):
        door(cv, x, 150, 20, 46, "blue")
        cv.rect(x + 4, 140, x + 15, 146, "white")
        cv.text(x + 5, 139, f"A{i + 1}0{i + 2}", "blue-dark")
    # notice board
    cv.rect(50, 132, 98, 168, "brown-dark")
    cv.rect(52, 134, 96, 166, "tan")
    cv.dither(52, 134, 96, 166, "sand", 4)
    posters(cv, 54, 137, random.Random(4), 4)
    posters(cv, 56, 152, random.Random(9), 4)
    cv.rect(66, 169, 67, BASE, "brown-dark")
    cv.rect(80, 169, 81, BASE, "brown-dark")
    for x in (0, 44, 100, 144, 186):
        cv.rect(x, 105, x + 5, BASE, "white")
        cv.rect(x + 5, 105, x + 5, BASE, "grey-light")
    sign(cv, "A BLOCK", 96, 108, bg="blue-dark", bold=True, size=16, padx=8)
    bush(cv, 150, 186, 22, 12)
    tile_floor(cv, BASE, "sand-light", "cream", "sand")
    skirting(cv, BASE - 2, "tan")
    return cv


def s_b_block():
    cv = Canvas()
    sky(cv, 0, 110, seed=21)
    facade(cv, 20, "white", "grey-light", 60, W - 1)
    cv.rect(0, 40, 59, BASE, "grey-light")
    for y in range(48, 170, 30):
        for x in (6, 30):
            window(cv, x, y, 16, 16, "white")
        for x in range(70, W, 26):
            window(cv, x, y - 18, 16, 16, "grey-light", "sky", "blue-dark")
    # granite entrance block
    cv.rect(66, 110, 180, BASE, "asphalt-dark")
    cv.rect(66, 110, 180, 113, "ink")
    for x in range(70, 180, 14):
        cv.rect(x, 114, x, 160, "asphalt")
    cv.rect(102, 140, 146, BASE - 14, "ink")
    cv.rect(105, 143, 143, BASE - 14, "blue-dark")
    cv.rect(124, 143, 124, BASE - 14, "ink")
    cv.line([(108, 175), (118, 147)], "sky")
    sign(cv, "PATRONS' BHAVAN", 123, 118, bg="ink", fg="white", trim="grey")
    sign(cv, "B BLOCK", 160, 160, bg="white", fg="blue-dark", trim="sand", border="asphalt-dark", size=8, bold=True)
    # steps
    for i in range(3):
        y = BASE - 12 + i * 4
        cv.rect(92 - i * 6, y, 156 + i * 6, y + 3, "grey-light" if i % 2 else "grey")
        cv.rect(92 - i * 6, y, 156 + i * 6, y, "cream")
    cv.rect(88, 172, 89, BASE, "grey")
    cv.rect(88, 172, 104, 172, "grey")
    flagpole(cv, 30, BASE - 1, 52)
    bush(cv, 0, 186, 24, 12)
    bush(cv, 170, 187, 22, 11)
    paving(cv)
    # rangoli
    cx, cy = 40, 236
    for r, c in ((10, "pink"), (7, "yellow"), (4, "coral"), (1, "white")):
        cv.poly([(cx, cy - r // 2 - 1), (cx + r, cy), (cx, cy + r // 2 + 1), (cx - r, cy)], c)
    return cv


def s_c_block():
    cv = Canvas(bg="lime-pale")
    cv.rect(0, 0, W - 1, BASE, "mint")
    cv.rect(0, 0, W - 1, 10, "white")
    cv.rect(0, 120, W - 1, BASE, "lime-pale")
    cv.rect(0, 119, W - 1, 119, "green")
    fan(cv, 52, 16)
    fan(cv, 140, 16)
    tube(cv, 80, 12)
    # windows left/right
    for x in (6, 162):
        cv.rect(x - 1, 34, x + 24, 96, "white")
        cv.rect(x, 35, x + 23, 95, "sky-pale")
        tree(cv, x + 12, 118, 10, 10)  # seen through window (clipped below)
        cv.rect(x - 1, 96, x + 24, 118, "lime-pale")
        cv.rect(x - 1, 34, x + 24, 35, "white")
        for gx in range(x, x + 24, 6):
            cv.rect(gx, 35, gx, 95, "grey")
        cv.rect(x, 64, x + 23, 64, "grey")
        cv.rect(x - 3, 96, x + 26, 98, "white")
    # blackboard
    cv.rect(36, 40, 156, 108, "brown")
    cv.rect(39, 43, 153, 105, "green-dark")
    cv.dither(39, 43, 153, 105, "green", 5)
    cv.text(46, 48, "HAPPY B'DAY!", "white")
    cv.text(46, 60, "E = MC2  :)", "yellow")
    cv.line([(46, 76), (70, 92), (96, 76)], "pink-pale")
    cv.text(104, 82, "DSA", "sky-pale")
    cv.rect(46, 106, 152, 108, "tan")
    cv.rect(60, 105, 64, 106, "white")
    cv.rect(70, 105, 72, 106, "yellow")
    sign(cv, "C BLOCK", 96, 22, bg="tan", fg="brown-dark", trim="sand-light", border="brown-dark", bold=True)
    cv.text(41, 38, "ROOM C-204", "green-dark")
    # teacher desk
    cv.rect(118, 150, 178, 156, "tan")
    cv.rect(118, 157, 178, 158, "brown")
    cv.rect(120, 159, 176, 190, "brown")
    cv.rect(124, 163, 172, 186, "tan")
    cv.rect(130, 144, 140, 149, "white")
    cv.rect(146, 143, 150, 149, "red")
    # back benches
    for x in (4, 56):
        cv.rect(x, 164, x + 44, 168, "tan")
        cv.rect(x, 169, x + 44, 170, "brown")
        cv.rect(x + 2, 171, x + 42, 190, "brown-dark")
        cv.rect(x + 4, 173, x + 40, 188, "brown")
    tile_floor(cv, BASE, "sand-light", "cream", "sand")
    skirting(cv, BASE - 3, "green")
    return cv


def s_d_block():
    cv = Canvas()
    sky(cv, 0, 100, seed=31)
    cv.rect(10, 34, 182, BASE, "white")
    cv.rect(10, 34, 182, 37, "grey-light")
    # solar panels on roof
    for x in range(14, 180, 22):
        cv.poly([(x, 33), (x + 18, 33), (x + 15, 22), (x + 3, 22)], "blue-dark")
        for gx in range(x + 4, x + 16, 4):
            cv.line([(gx, 32), (gx - 1, 23)], "blue")
        cv.line([(x + 4, 23), (x + 15, 23)], "sky")
        cv.rect(x + 8, 33, x + 9, 34, "grey")
    for y in (48, 84, 120):
        cv.rect(10, y, 182, y + 20, "sky")
        cv.rect(10, y + 10, 182, y + 20, "blue")
        for x in range(10, 183, 12):
            cv.rect(x, y, x, y + 20, "grey-light")
        cv.line([(20, y + 18), (28, y + 2)], "sky-pale")
        cv.line([(100, y + 18), (108, y + 2)], "sky-pale")
        cv.rect(10, y + 21, 182, y + 23, "grey-light")
    # glass entrance
    cv.rect(66, 146, 126, BASE, "grey")
    cv.rect(68, 152, 124, BASE, "sky")
    cv.rect(68, 172, 124, BASE, "blue")
    cv.rect(96, 152, 96, BASE, "grey-light")
    cv.line([(72, 192), (84, 156)], "sky-pale")
    cv.line([(102, 192), (114, 156)], "sky-pale")
    cv.rect(60, 142, 132, 146, "asphalt")
    sign(cv, "D BLOCK", 96, 130, bg="white", fg="blue-dark", trim="sky", border="blue-dark", bold=True)
    for x in (18, 152):
        cv.rect(x, 150, x + 22, 186, "sky-pale")
        cv.rect(x, 168, x + 22, 186, "sky")
    palm(cv, 30, BASE, 44)
    palm(cv, 168, BASE, 38)
    paving(cv, BASE, "cream", "white", "grey-light")
    return cv


def s_e_block():
    cv = Canvas(bg="cream")
    cv.rect(0, 0, W - 1, BASE, "cream")
    cv.rect(0, 0, W - 1, 8, "white")
    tube(cv, 30, 10)
    tube(cv, 130, 10)
    sign(cv, "E BLOCK", 96, 18, bg="purple", fg="white", trim="lilac", bold=True)
    cv.text(70, 34, "- CSE LAB 3 -", "purple")
    # back wall windows
    for x in (6, 66, 126):
        cv.rect(x, 48, x + 58, 92, "white")
        cv.rect(x + 2, 50, x + 56, 90, "sky-pale")
        cv.rect(x + 2, 50, x + 12, 90, "blue")
        cv.rect(x + 46, 50, x + 56, 90, "blue")
        cv.rect(x + 29, 50, x + 29, 90, "white")
    # long desk with computers
    cv.rect(0, 150, W - 1, 155, "grey-light")
    cv.rect(0, 156, W - 1, 158, "grey")
    cv.rect(0, 159, W - 1, BASE - 4, "asphalt")
    for x in range(6, W, 30):
        cv.rect(x + 1, 160, x + 26, BASE - 6, "asphalt-dark")
        cv.rect(x, 116, x + 24, 138, "ink")
        cv.rect(x + 2, 118, x + 22, 136, "blue-dark")
        cv.rect(x + 3, 119, x + 15, 121, "sky")
        cv.rect(x + 3, 124, x + 19, 124, "mint")
        cv.rect(x + 3, 127, x + 12, 127, "lime-pale")
        cv.rect(x + 3, 130, x + 17, 130, "mint")
        cv.rect(x + 10, 139, x + 13, 146, "ink")
        cv.rect(x + 6, 147, x + 18, 149, "ink")
        cv.rect(x + 2, 151, x + 20, 152, "asphalt")
    cv.rect(2, 106, 24, 112, "yellow")
    cv.text(3, 104, "LAB", "brown-dark")
    tile_floor(cv, BASE, "grey-light", "cream", "grey")
    skirting(cv, BASE - 2, "grey")
    return cv


def s_pg_block():
    cv = Canvas()
    sky(cv, 0, 80, seed=41)
    facade(cv, 16, "sand-light", "sand")
    cv.rect(0, 12, W - 1, 15, "tan")
    for y in (24, 58, 92):
        for x in range(6, W, 22):
            window(cv, x, y, 14, 16, "white")
    # dark pillared porch
    cv.rect(40, 118, 152, 124, "asphalt-dark")
    cv.rect(40, 118, 152, 118, "grey")
    sign(cv, "PG BLOCK", 96, 104, bg="ink", fg="yellow", trim="orange", bold=True)
    for x in (44, 74, 110, 140):
        cv.rect(x, 125, x + 7, BASE - 10, "asphalt-dark")
        cv.rect(x, 125, x + 1, BASE - 10, "asphalt")
        cv.rect(x - 1, 125, x + 8, 127, "ink")
    cv.rect(82, 140, 108, BASE - 10, "plum")
    cv.rect(84, 142, 106, BASE - 10, "sky")
    cv.rect(84, 160, 106, BASE - 10, "blue")
    cv.rect(95, 142, 95, BASE - 10, "plum")
    sign(cv, "COMPUTER CENTRE", 96, 130, bg="yellow", fg="ink", trim="orange", border="brown-dark")
    for i in range(3):
        y = BASE - 10 + i * 3
        cv.rect(36 - i * 4, y, 158 + i * 4, y + 2, "grey-light" if i % 2 else "grey")
    tree(cv, 16, BASE - 2, 14, 20)
    tree(cv, 178, BASE - 2, 13, 18)
    paving(cv, BASE, "cream", "white", "grey-light")
    return cv


def s_peb():
    cv = Canvas()
    sky(cv, 0, 120, seed=51)
    tree(cv, 10, 150, 14, 18)
    tree(cv, 182, 150, 14, 18)
    # long pale metal hall: gable front
    cv.rect(8, 70, 184, BASE, "grey-light")
    cv.poly([(2, 72), (96, 26), (190, 72)], "white")
    cv.poly([(96, 26), (190, 72), (184, 74), (96, 32)], "grey-light")
    for x in range(14, 180, 6):
        cv.rect(x, 74, x, BASE, "cream")
    # roof edge trim
    cv.line([(2, 72), (96, 26), (190, 72)], "sky", 2)
    # wide open entrance with truss visible inside
    cv.rect(26, 92, 166, BASE, "asphalt-dark")
    cv.rect(26, 92, 166, 94, "grey")
    cv.line([(28, 112), (96, 96), (164, 112)], "grey")
    for x in range(36, 160, 12):
        y = 112 - int((1 - abs(x - 96) / 68) * 16)
        cv.line([(x, 112), (x + 6, y + 2)], "grey")
        cv.line([(x + 6, y + 2), (x + 12, 112)], "grey")
    cv.rect(28, 112, 164, 113, "grey")
    for x in (40, 96, 152):
        cv.rect(x, 116, x + 9, 122, "yellow")
        cv.rect(x + 1, 123, x + 8, 124, "white")
    # inside: badminton court + net
    cv.rect(28, 160, 164, BASE, "green")
    cv.rect(36, 162, 156, 162, "white")
    cv.rect(36, 162, 36, BASE, "white")
    cv.rect(156, 162, 156, BASE, "white")
    cv.rect(94, 150, 95, BASE, "grey-light")
    cv.rect(60, 152, 132, 158, "plum")
    for x in range(60, 132, 3):
        cv.rect(x, 152, x, 158, "grey")
    cv.rect(60, 151, 132, 151, "white")
    cv.rect(44, 130, 70, 146, "red")
    cv.text(46, 133, "GO!", "white")
    # pillars
    for x in (20, 166):
        cv.rect(x, 74, x + 6, BASE, "grey")
        cv.rect(x, 74, x + 1, BASE, "white")
    sign(cv, "PEB", 96, 50, bg="blue-dark", fg="white", trim="sky", size=16, bold=True, padx=8)
    bush(cv, 0, 186, 22, 12)
    bush(cv, 170, 186, 22, 12)
    paving(cv, BASE, "grey-light", "cream", "grey")
    return cv


def s_siniti():
    cv = Canvas()
    sky(cv, 0, 130, top="sky", seed=61)
    for x, r in ((10, 16), (40, 14), (152, 15), (184, 16)):
        tree(cv, x, 132, r, 14)
    # stage with arch backdrop
    cv.rect(26, 60, 166, 150, "red-dark")
    cv.rect(30, 64, 162, 150, "pink")
    for x in range(30, 163, 8):
        cv.rect(x, 64, x + 3, 150, "pink-pale")
    cv.poly([(22, 64), (96, 36), (170, 64)], "purple")
    cv.poly([(32, 62), (96, 42), (160, 62)], "lilac")
    sign(cv, "SINITI", 96, 70, bg="plum", fg="yellow", trim="pink-pale", size=16, bold=True, padx=8)
    cv.text(66, 94, "OPEN STAGE", "white")
    # string lights
    for i in range(0, 140, 7):
        x = 28 + i
        y = 106 + int(math.sin(i / 22) * 3)
        cv.px(x, y, "plum")
        cv.px(x, y + 1, ["yellow", "coral", "mint", "white"][(i // 7) % 4])
    # stage platform + steps
    cv.rect(20, 150, 172, 166, "brown")
    cv.rect(20, 150, 172, 152, "tan")
    for x in range(24, 172, 16):
        cv.rect(x, 153, x, 166, "brown-dark")
    for i in range(4):
        y = 167 + i * 8
        cv.rect(10 - i * 4, y, 182 + i * 4, y + 7, "grey-light" if i % 2 else "cream")
        cv.rect(10 - i * 4, y + 6, 182 + i * 4, y + 7, "grey")
    cv.rect(150, 154, 156, 166, "asphalt")  # speaker
    cv.rect(151, 156, 155, 160, "ink")
    cv.rect(36, 154, 42, 166, "asphalt")
    cv.rect(37, 156, 41, 160, "ink")
    for px_ in (0, 186):
        cv.rect(px_, 140, px_ + 5, BASE, "orange")
    paving(cv, BASE, "cream", "white", "grey-light", kerb=False)
    return cv


def s_sac():
    cv = Canvas()
    sky(cv, 0, 120, seed=71)
    tree(cv, 14, 150, 16, 20)
    tree(cv, 178, 150, 16, 22)
    # back club room
    cv.rect(28, 90, 164, BASE, "cream")
    cv.rect(28, 90, 164, 93, "grey-light")
    posters(cv, 34, 120, random.Random(3), 5)
    posters(cv, 112, 118, random.Random(5), 5)
    door(cv, 86, 150, 20, 46, "red", "white")
    # tensile canopy peaks
    for cx in (48, 96, 144):
        cv.poly([(cx - 30, 92), (cx, 44), (cx + 30, 92)], "white")
        cv.poly([(cx, 44), (cx + 30, 92), (cx + 8, 92)], "grey-light")
        cv.line([(cx, 44), (cx, 40)], "grey")
        cv.px(cx, 39, "red")
    cv.rect(16, 92, 176, 94, "grey")
    for x in (18, 172):
        cv.rect(x, 94, x + 2, BASE, "grey")
    sign(cv, None, 96, 98, bg="orange", fg="ink", trim="yellow", border="brown-dark",
         lines=["STUDENT ACTIVITY", "CENTRE"])
    cv.text(36, 140, "CLUBS", "purple")
    cv.text(124, 140, "FEST!", "red")
    bench(cv, 34, 182, 34)
    bench(cv, 124, 182, 34)
    paving(cv, BASE, "sand-light", "cream", "sand")
    return cv


def s_sports():
    cv = Canvas()
    sky(cv, 0, 90, seed=81)
    cv.rect(8, 50, 184, 150, "white")
    cv.rect(8, 50, 184, 55, "grey-light")
    for x in range(16, 180, 20):
        window(cv, x, 92, 12, 12, "white")
        window(cv, x, 122, 12, 14, "white")
    sign(cv, None, 96, 60, bg="red-dark", fg="white", trim="yellow",
         lines=["KODE VENKATADRI CHOWDARY", "SPORTS COMPLEX"])
    floodlight(cv, 4, 150, 24)
    floodlight(cv, 186, 150, 24)
    cv.rect(0, 150, W - 1, 152, "grey")
    # court
    cv.rect(0, 153, W - 1, H - 1, "blue")
    cv.dither(0, 153, W - 1, 200, "blue-dark", 6)
    cv.rect(66, 153, 126, 230, "red")
    cv.rect(66, 153, 126, 153, "white")
    cv.rect(66, 153, 66, 230, "white")
    cv.rect(126, 153, 126, 230, "white")
    cv.rect(66, 230, 126, 230, "white")
    cv.ellipse(76, 216, 116, 244, "white")
    cv.ellipse(77, 217, 115, 243, "yellow")
    cv.rect(66, 216, 126, 230, "red")
    cv.rect(66, 230, 126, 230, "white")
    cv.rect(0, 270, W - 1, 270, "white")
    cv.rect(0, 153, W - 1, 154, "white")
    # basketball hoop
    cv.rect(94, 140, 97, 186, "red")
    for y in range(140, 186, 6):
        cv.rect(94, y, 97, y + 2, "yellow")
    cv.rect(82, 122, 110, 140, "white")
    cv.rect(82, 122, 110, 122, "grey")
    cv.rect(90, 130, 102, 138, "red")
    cv.rect(92, 132, 100, 136, "white")
    cv.rect(90, 140, 102, 141, "orange")
    for i in range(5):
        cv.px(91 + i * 3, 142 + i % 2, "white")
        cv.px(92 + i * 2, 145, "white")
    # ball
    cv.ellipse(150, 258, 157, 265, "orange")
    cv.px(153, 258, "brown-dark")
    cv.rect(153, 259, 153, 264, "brown-dark")
    shade_bottom(cv)
    return cv


def s_vjim():
    cv = Canvas()
    sky(cv, 0, 120, seed=91)
    tree(cv, 12, 160, 15, 20)
    tree(cv, 180, 160, 15, 20)
    # round building: drum
    cx = 96
    cv.ellipse(cx - 76, 26, cx + 76, 54, "grey-light")
    cv.rect(cx - 76, 40, cx + 76, 170, "cream")
    cv.ellipse(cx - 76, 156, cx + 76, 184, "cream")
    for x in range(cx - 76, cx + 77):
        t = (x - (cx - 76)) / 152
        if t < .15 or t > .8:
            cv.rect(x, 40, x, 170, "sand-light")
    cv.ellipse(cx - 76, 26, cx + 76, 50, "red")
    cv.ellipse(cx - 70, 28, cx + 70, 46, "coral")
    # curved window bands
    for y in (62, 100):
        for i in range(-5, 6):
            x = cx + int(math.sin(i / 6.5) * 72) - 4
            w = max(3, int(math.cos(i / 6.5) * 10))
            cv.rect(x, y, x + w, y + 16, "sky")
            cv.rect(x, y + 8, x + w, y + 16, "blue")
            cv.rect(x, y + 17, x + w, y + 17, "grey-light")
    # entrance
    cv.rect(76, 140, 116, 178, "asphalt-dark")
    cv.rect(79, 144, 113, 178, "sky")
    cv.rect(79, 160, 113, 178, "blue")
    cv.rect(96, 144, 96, 178, "asphalt-dark")
    cv.rect(70, 136, 122, 140, "grey")
    sign(cv, "VJIM", 96, 116, bg="blue-dark", fg="yellow", trim="sky", size=16, bold=True, padx=8)
    # plaque
    cv.rect(132, 150, 166, 170, "brown-dark")
    cv.rect(134, 152, 164, 168, "ink")
    cv.text(136, 152, "INST.", "yellow")
    cv.text(136, 160, "MGMT", "yellow")
    for x in (2, 150):
        bush(cv, x, 182, 40, 14)
    paving(cv, BASE, "cream", "white", "grey-light")
    return cv


def s_canteen():
    cv = Canvas()
    sky(cv, 0, 90, seed=101)
    tree(cv, 20, 120, 20, 20)
    tree(cv, 170, 116, 20, 18)
    # shed roof
    cv.poly([(0, 66), (W - 1, 66), (W - 1, 82), (0, 82)], "grey")
    for x in range(0, W, 6):
        cv.rect(x, 66, x + 2, 82, "grey-light")
    cv.rect(0, 82, W - 1, 85, "asphalt")
    for x in (4, 94, 184):
        cv.rect(x, 86, x + 3, BASE, "grey")
    # back counter
    cv.rect(10, 86, 182, 170, "cream")
    cv.rect(24, 98, 92, 140, "sky-pale")
    cv.rect(24, 98, 92, 100, "white")
    for x in range(30, 92, 14):
        cv.rect(x, 108, x + 8, 118, "orange")
        cv.rect(x + 1, 109, x + 7, 110, "yellow")
    cv.rect(18, 140, 100, 170, "red")
    cv.rect(18, 140, 100, 143, "red-dark")
    cv.rect(22, 150, 96, 150, "coral")
    # menu board
    cv.rect(108, 96, 176, 144, "brown-dark")
    cv.rect(110, 98, 174, 142, "green-dark")
    for i, t in enumerate(["TEA  10", "SAMOSA15", "MAGGI 30", "DOSA  40"]):
        cv.text(113, 100 + i * 10, t, "white" if i % 2 else "yellow")
    sign(cv, "CANTEEN", 96, 52, bg="red", fg="white", trim="yellow", border="red-dark", size=16, bold=True, padx=8)
    # ice-cream kiosk
    cv.rect(140, 148, 178, BASE - 2, "pink-pale")
    cv.rect(140, 148, 178, 152, "pink")
    cv.rect(144, 156, 174, 170, "white")
    cv.text(145, 158, "ICE", "pink")
    cv.text(160, 160, "", "pink")
    cv.ellipse(166, 156, 172, 162, "mint")
    cv.poly([(167, 162), (171, 162), (169, 168)], "tan")
    # umbrellas + tables
    for ux in (40, 108):
        cv.rect(ux, 162, ux + 1, 190, "white")
        cv.poly([(ux - 22, 166), (ux, 148), (ux + 23, 166)], "red")
        for k in range(-22, 23, 9):
            cv.line([(ux, 148), (ux + k, 166)], "red-dark")
        cv.rect(ux - 22, 166, ux + 23, 167, "white")
        cv.rect(ux - 14, 184, ux + 15, 186, "white")
        cv.rect(ux - 12, 187, ux - 11, BASE, "grey")
        cv.rect(ux + 12, 187, ux + 13, BASE, "grey")
    # red earth with stepping stones
    cv.rect(0, BASE, W - 1, H - 1, "tan")
    rnd = random.Random(12)
    for _ in range(300):
        cv.px(rnd.randint(0, W - 1), rnd.randint(BASE, H - 1), rnd.choice(["sand", "brown"]))
    for i, x in enumerate(range(8, W, 30)):
        y = 214 + (i % 2) * 22
        cv.ellipse(x, y, x + 18, y + 8, "grey")
        cv.ellipse(x, y, x + 18, y + 6, "grey-light")
    shade_bottom(cv)
    return cv


def field_bg(cv, sky_top="sky", sky_mid="sky-pale", far="green-dark", seed=111):
    sky(cv, 0, 160, sky_top, sky_mid, seed=seed)
    rnd = random.Random(seed)
    x = 0
    while x < W:
        r = rnd.randint(9, 15)
        cv.ellipse(x - r, 150 - r - rnd.randint(0, 8), x + r, 160, far)
        x += r
    cv.rect(0, 154, W - 1, 162, far)


def s_ground():
    cv = Canvas()
    field_bg(cv)
    for x in range(0, W, 14):
        cv.ellipse(x, 140, x + 16, 158, "green")
    cv.rect(110, 120, 150, 158, "white")
    for x in range(114, 150, 8):
        cv.rect(x, 126, x + 4, 132, "sky")
    floodlight(cv, 18, 165, 70)
    floodlight(cv, 172, 165, 64)
    cv.rect(0, 160, W - 1, 172, "blue")
    cv.rect(0, 160, W - 1, 161, "sky")
    for x in range(0, W, 16):
        cv.rect(x, 162, x, 172, "blue-dark")
    grass_floor(cv, 173, "lime-pale", "grass-light", "sand", seed=5)
    rnd = random.Random(6)
    for _ in range(140):
        cv.px(rnd.randint(0, W - 1), rnd.randint(173, 270), "sand")
    # goalpost
    gx0, gx1, gt, gb = 60, 132, 150, 190
    cv.rect(gx0 + 6, gt + 4, gx1 - 6, gb - 6, "grey-light")
    for x in range(gx0 + 6, gx1 - 5, 4):
        cv.rect(x, gt + 4, x, gb - 6, "white")
    for y in range(gt + 4, gb - 5, 4):
        cv.rect(gx0 + 6, y, gx1 - 6, y, "white")
    cv.rect(gx0, gt, gx1, gt + 2, "white")
    cv.rect(gx0, gt, gx0 + 2, gb, "white")
    cv.rect(gx1 - 2, gt, gx1, gb, "white")
    cv.rect(0, 196, W - 1, 196, "white")
    cv.ellipse(150, 230, 157, 237, "white")
    cv.px(153, 233, "ink")
    cv.px(152, 232, "ink")
    sign(cv, "COLLEGE GROUND", 96, 18, bg="green-dark", fg="white", trim="lime-pale", posts=0)
    shade_bottom(cv)
    return cv


def s_main_gate():
    cv = Canvas()
    sky(cv, 0, 130, seed=121)
    tree(cv, 14, 150, 18, 22)
    tree(cv, 180, 150, 18, 22)
    striped_wall(cv, 140, 172)
    # arch
    for x in (30, 150):
        cv.rect(x, 50, x + 13, BASE, "sand-light")
        cv.rect(x + 10, 50, x + 13, BASE, "sand")
        for y in range(60, BASE, 12):
            cv.rect(x, y, x + 13, y, "tan")
    cv.rect(24, 34, 168, 62, "red-dark")
    cv.rect(26, 36, 166, 60, "cream")
    cv.rect(24, 30, 168, 34, "orange")
    cv.poly([(80, 30), (96, 18), (112, 30)], "orange")
    tw = cv.tsize("VNR VJIET", 16, True)
    cv.text(96 - tw[0] // 2 - tw[2], 40 - tw[3], "VNR VJIET", "blue-dark", 16, True)
    cv.rect(44, 62, 149, BASE, "sky-pale")
    tree(cv, 70, 150, 10, 10)
    tree(cv, 124, 146, 12, 12)
    cv.rect(44, 150, 149, BASE, "grass")
    # road
    cv.poly([(80, 150), (112, 150), (149, BASE), (44, BASE)], "asphalt")
    for y in range(156, BASE, 12):
        cv.rect(95, y, 97, y + 5, "white")
    # gate boom + booth
    cv.rect(44, 172, 120, 174, "red")
    for x in range(48, 120, 12):
        cv.rect(x, 172, x + 5, 174, "white")
    cv.rect(158, 150, 186, BASE, "white")
    cv.poly([(154, 150), (172, 140), (190, 150)], "blue")
    cv.rect(162, 158, 182, 172, "sky")
    cv.rect(162, 166, 182, 172, "blue")
    cv.text(161, 176, "SECURITY", "red-dark")  # wide; trimmed below
    cv.rect(158, 175, 186, 184, "white")
    sign(cv, "SECURITY", 172, 176, bg="blue-dark", fg="white", trim="sky", padx=2, pady=2)
    sign(cv, "MAIN GATE", 96, 70, bg="green-dark", fg="white", trim="lime-pale")
    paving(cv, BASE, "grey-light", "cream", "grey")
    return cv


# ---------------------------------------------------------------- finale

def s_finale():
    cv = Canvas()
    sky(cv, 0, 160, "coral", "orange", seed=131)
    cv.rect(0, 0, W - 1, 30, "pink")
    cv.dither(0, 31, W - 1, 38, "pink")
    cv.dither(0, 90, W - 1, 100, "yellow", 2)
    cv.rect(0, 100, W - 1, 160, "yellow")
    cv.ellipse(76, 104, 116, 144, "sand-light")
    cv.ellipse(80, 108, 112, 140, "white")
    # clouds tinted
    for x, y in ((14, 50), (130, 40)):
        cv.ellipse(x, y + 3, x + 30, y + 10, "pink-pale")
        cv.ellipse(x + 8, y, x + 20, y + 8, "pink-pale")
    rnd = random.Random(141)
    x = 0
    while x < W:
        r = rnd.randint(9, 15)
        cv.ellipse(x - r, 140 - r - rnd.randint(0, 8), x + r, 160, "plum")
        x += r
    cv.rect(0, 150, W - 1, 172, "plum")
    floodlight(cv, 10, 172, 76)
    floodlight(cv, 180, 172, 70)
    cv.rect(0, 160, W - 1, 172, "purple")
    cv.rect(0, 160, W - 1, 160, "lilac")
    grass_floor(cv, 173, "sand", "sand-light", "tan", seed=8)
    cv.dither(0, 173, W - 1, 176, "orange", 2)
    # bunting
    cols = ["red", "yellow", "mint", "pink", "sky", "lilac"]
    for row, (y0, sag) in enumerate(((44, 12), (70, 10))):
        pts = []
        for x in range(0, W + 1, 2):
            y = y0 + int(sag * math.sin(math.pi * x / W))
            pts.append((x, y))
        cv.line(pts, "plum")
        for i, x in enumerate(range(4 + row * 5, W - 4, 12)):
            y = y0 + int(sag * math.sin(math.pi * x / W))
            cv.poly([(x - 3, y + 1), (x + 3, y + 1), (x, y + 7)], cols[(i + row) % len(cols)])
    # fairy lights
    for x in range(2, W, 6):
        y = 92 + int(6 * math.sin(math.pi * x / W))
        cv.px(x, y - 1, "plum")
        cv.px(x, y, ["yellow", "white", "pink-pale"][(x // 6) % 3])
    # balloons
    for bx, by, c in ((14, 108, "red"), (26, 98, "yellow"), (36, 112, "pink"),
                      (158, 104, "sky"), (170, 96, "mint"), (180, 112, "lilac")):
        cv.ellipse(bx - 5, by - 7, bx + 5, by + 6, c)
        cv.px(bx - 2, by - 4, "white")
        cv.px(bx - 3, by - 3, "white")
        cv.px(bx, by + 7, c)
        cv.line([(bx, by + 8), (bx + 1, 170)], "white")
    tw, th, ox, oy = cv.tsize("HAPPY BIRTHDAY", 16, True)
    sign(cv, "HAPPY BIRTHDAY", 96, 4, bg="plum", fg="yellow", trim="pink-pale", border="ink", bold=True)
    sign(cv, "VAISHALI", 96, 19, bg="pink", fg="white", trim="yellow", border="plum", size=16, bold=True, padx=8)
    # scattered confetti on ground
    for _ in range(60):
        cv.px(rnd.randint(0, W - 1), rnd.randint(178, 270), rnd.choice(cols))
    shade_bottom(cv)
    return cv


def jar(cv, x, y, c):
    cv.rect(x, y + 2, x + 6, y + 10, "sky-pale")
    cv.rect(x + 1, y + 4, x + 5, y + 9, c)
    cv.px(x + 2, y + 5, "white")
    cv.rect(x + 1, y, x + 5, y + 1, "red")


def s_thatibellam():
    cv = Canvas()
    sky(cv, 0, 110, seed=141)
    tree(cv, 14, 168, 18, 24)
    tree(cv, 178, 166, 16, 22)
    # back wall of shop
    cv.rect(22, 70, 170, BASE, "sand-light")
    cv.rect(22, 70, 170, 72, "tan")
    sign(cv, "THATI BELLAM", 96, 52, bg="green-dark", fg="yellow", trim="orange", border="ink", bold=True)
    # striped awning
    for i, x in enumerate(range(16, 176, 10)):
        cv.poly([(x, 76), (x + 10, 76), (x + 12, 96), (x - 2, 96)], "orange" if i % 2 else "white")
    for x in range(16, 176, 10):
        cv.ellipse(x - 2, 93, x + 8, 100, "orange" if (x // 10) % 2 else "white")
    cv.rect(14, 76, 178, 77, "red-dark")
    # shelves inside
    cv.rect(28, 100, 164, 150, "brown")
    for y in (112, 128):
        cv.rect(30, y, 162, y + 1, "brown-dark")
    rnd = random.Random(3)
    for x in range(32, 160, 9):
        jar(cv, x, 101, rnd.choice(["yellow", "orange", "coral", "pink-pale", "lime-pale"]))
        jar(cv, x + 2, 117, rnd.choice(["tan", "brown", "yellow", "red", "mint"]))
    # hanging packets
    for i, x in enumerate(range(26, 170, 8)):
        cv.rect(x, 100, x, 102, "grey")
        cv.rect(x - 2, 102, x + 3, 108, ["red", "yellow", "sky", "pink", "lime-pale", "orange"][i % 6])
        cv.px(x, 104, "white")
    # counter
    cv.rect(24, 150, 140, 154, "tan")
    cv.rect(24, 155, 140, BASE - 2, "blue")
    for x in range(30, 140, 18):
        cv.rect(x, 158, x + 12, 186, "sky")
        cv.rect(x + 2, 162, x + 10, 170, "yellow")
    for x in (34, 54, 74, 96):
        jar(cv, x, 140, rnd.choice(["orange", "coral", "yellow"]))
    # tea kettle on stove
    cv.rect(112, 146, 132, 149, "asphalt")
    cv.ellipse(114, 134, 128, 146, "grey-light")
    cv.rect(118, 131, 124, 134, "grey")
    cv.line([(128, 140), (133, 135)], "grey-light", 2)
    for i, (x, y) in enumerate(((120, 126), (122, 122), (119, 118))):
        cv.px(x, y, "white")
    # menu board on stand
    cv.rect(146, 126, 182, 172, "brown-dark")
    cv.rect(148, 128, 180, 170, "green-dark")
    for i, t in enumerate(["CHAI", "BUN", "VADA", "LADDU"]):
        cv.text(150, 128 + i * 10, t, "white" if i % 2 else "yellow")
    cv.rect(156, 173, 157, BASE, "brown-dark")
    cv.rect(170, 173, 171, BASE, "brown-dark")
    # stool
    cv.ellipse(4, 178, 20, 183, "red")
    cv.rect(6, 183, 7, BASE, "brown-dark")
    cv.rect(17, 183, 18, BASE, "brown-dark")
    # little marigold string
    for x in range(18, 176, 4):
        cv.px(x, 79 + (x // 4) % 2, "yellow")
    paving(cv, BASE, "sand-light", "cream", "sand")
    return cv


CAKE_W, CAKE_H = 40, 32
CANDLE_X = [11, 14, 18, 21, 25, 28]
FW, FH, FN = 3, 5, 4
SW, SH, SN = 5, 7, 4


def cake():
    cv = Canvas(CAKE_W, CAKE_H, alpha=True)
    # table
    cv.rect(1, 25, 38, 27, "pink-pale")
    cv.rect(1, 28, 38, 28, "pink")
    for x in (4, 34):
        cv.rect(x, 29, x + 1, 31, "brown")
    # bottom tier
    cv.rect(5, 17, 34, 25, "pink")
    cv.rect(5, 17, 34, 18, "white")
    for x in range(6, 34, 4):
        cv.rect(x, 19, x + 1, 19 + (x // 4) % 2, "white")
    cv.rect(5, 22, 34, 22, "red")
    cv.rect(33, 19, 34, 25, "red-dark")
    # top tier
    cv.rect(9, 10, 30, 16, "cream")
    cv.rect(9, 10, 30, 11, "pink-pale")
    for x in range(10, 30, 3):
        cv.px(x, 12, "pink-pale")
    cv.rect(29, 12, 30, 16, "sand-light")
    for i, x in enumerate(range(11, 30, 5)):
        cv.px(x, 14, ["red", "yellow", "mint", "lilac"][i % 4])
    # candles
    for i, x in enumerate(CANDLE_X):
        cv.rect(x, 6, x, 9, ["sky", "yellow", "pink", "mint", "lilac", "coral"][i])
        cv.px(x, 5, "ink")
    return cv


def flames():
    cv = Canvas(FW * FN, FH, alpha=True)
    shapes = [
        [".y.", "yoy", "yoy", ".o.", "..."],
        [".y.", ".y.", "yoy", "yoy", ".o."],
        ["..y", ".yy", "yoy", "yoy", ".o."],
        ["y..", "yy.", "yoy", "yoy", ".o."],
    ]
    m = {"y": "yellow", "o": "orange", "w": "white"}
    for f, rows in enumerate(shapes):
        for y, row in enumerate(rows):
            for x, ch in enumerate(row):
                if ch in m:
                    cv.px(f * FW + x, y, m[ch])
        cv.px(f * FW + 1, 3, "white")
    return cv


def smoke():
    cv = Canvas(SW * SN, SH, alpha=True)
    frames = [
        [(2, 6), (2, 5), (2, 4)],
        [(2, 5), (1, 4), (2, 3), (3, 2)],
        [(1, 3), (2, 2), (3, 2), (2, 1), (3, 3)],
        [(1, 1), (3, 0), (2, 1), (4, 1)],
    ]
    cols = ["grey-light", "grey-light", "grey", "grey-light"]
    for f, pts in enumerate(frames):
        for x, y in pts:
            cv.px(f * SW + x, y, cols[f] if (x + y) % 2 else "white")
    return cv


# ---------------------------------------------------------------- output

SCENES = [
    ("a-block", s_a_block, "left"), ("b-block", s_b_block, "right"),
    ("c-block", s_c_block, "left"), ("d-block", s_d_block, "right"),
    ("e-block", s_e_block, "left"), ("pg-block", s_pg_block, "right"),
    ("peb", s_peb, "left"), ("siniti", s_siniti, "right"),
    ("sac", s_sac, "left"), ("sports-complex", s_sports, "right"),
    ("vjim", s_vjim, "left"), ("canteen", s_canteen, "right"),
    ("ground", s_ground, "left"), ("main-gate", s_main_gate, "left"),
    ("thatibellam", s_thatibellam, "right"),
]

PAL_SET = set(PAL.values())


def check(im, name):
    rgba = im.convert("RGBA")
    bad = set()
    for r, g, b, a in rgba.get_flattened_data():
        if a not in (0, 255):
            bad.add(("alpha", a))
        elif a == 255 and (r, g, b) not in PAL_SET:
            bad.add((r, g, b))
    if bad:
        raise SystemExit(f"{name}: off-palette {sorted(bad)[:8]}")


def save(im, path):
    check(im, path.name)
    if im.mode == "RGBA":
        q = im.convert("RGBA")
        cols = list(PAL.values())
        p = Image.new("P", im.size, 0)
        pal = [0, 0, 0] + [c for col in cols for c in col]
        p.putpalette(pal + [0] * (768 - len(pal)))
        idx = {c: i + 1 for i, c in enumerate(cols)}
        p.putdata([idx[(r, g, b)] if a else 0 for r, g, b, a in q.get_flattened_data()])
        p.save(path, optimize=True, transparency=0)
    else:
        cols = sorted(set(im.get_flattened_data()))
        p = Image.new("P", im.size)
        pal = [c for col in cols for c in col]
        p.putpalette(pal + [0] * (768 - len(pal)))
        idx = {c: i for i, c in enumerate(cols)}
        p.putdata([idx[c] for c in im.get_flattened_data()])
        p.save(path, optimize=True)


def main():
    OUT.mkdir(parents=True, exist_ok=True)
    REVIEW.parent.mkdir(parents=True, exist_ok=True)
    meta = {"stage": {"w": W, "h": H}, "scenes": {}}
    ims = []
    for sid, fn, enter in SCENES:
        im = fn().im
        save(im, OUT / f"{sid}.png")
        meta["scenes"][sid] = {"file": f"{sid}.png", "floorTop": FLOOR_TOP,
                               "floorBottom": FLOOR_BOTTOM, "enterFrom": enter}
        ims.append(im)
    fin = s_finale().im
    save(fin, OUT / "finale.png")
    ims.append(fin)
    save(cake().im, OUT / "cake.png")
    save(flames().im, OUT / "flames.png")
    save(smoke().im, OUT / "smoke.png")
    meta["finale"] = {
        "file": "finale.png", "floorTop": FLOOR_TOP, "floorBottom": FLOOR_BOTTOM,
        "cake": {"file": "cake.png", "w": CAKE_W, "h": CAKE_H,
                 "flames": "flames.png", "frameW": FW, "frameH": FH, "frames": FN,
                 "smoke": "smoke.png", "smokeFrameW": SW, "smokeFrameH": SH, "smokeFrames": SN,
                 "_candles": "top-left of a flame frame relative to cake top-left",
                 "candles": [[x - 1, 1] for x in CANDLE_X]},
    }
    (OUT / "locations.json").write_text(json.dumps(meta, indent=2) + "\n")
    cols, gap = 6, 4
    rows = math.ceil(len(ims) / cols)
    sheet = Image.new("RGB", (cols * (W * 2 + gap) + gap, rows * (H * 2 + gap) + gap), C("ink"))
    for i, im in enumerate(ims):
        sheet.paste(im.resize((W * 2, H * 2), Image.NEAREST),
                    (gap + (i % cols) * (W * 2 + gap), gap + (i // cols) * (H * 2 + gap)))
    sheet.save(REVIEW, optimize=True)
    print("ok", len(ims), "backgrounds")


if __name__ == "__main__":
    main()
