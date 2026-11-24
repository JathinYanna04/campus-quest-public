"""Palette-indexed raster helpers. Images are uint8 numpy arrays of palette
indices; T (255) means fully transparent."""
import json
from pathlib import Path

import numpy as np
from PIL import Image, ImageDraw, ImageFont

ROOT = Path(__file__).resolve().parents[2]
PAL = json.loads((ROOT / "palette.json").read_text())["colors"]
NAMES = list(PAL)
IDX = {n: i for i, n in enumerate(NAMES)}
RGB = [tuple(int(PAL[n][i:i + 2], 16) for i in (1, 3, 5)) for n in NAMES]
T = 255
FONT_R = ROOT / "fonts" / "silkscreen_Silkscreen-Regular.ttf"
FONT_B = ROOT / "fonts" / "silkscreen_Silkscreen-Bold.ttf"

BAYER4 = np.array([[0, 8, 2, 10], [12, 4, 14, 6], [3, 11, 1, 9], [15, 7, 13, 5]]) / 16.0


def c(name):
    return IDX[name]


def bayer(h, w, ox=0, oy=0):
    yy, xx = np.mgrid[0:h, 0:w]
    return BAYER4[(yy + oy) % 4, (xx + ox) % 4]


def hashnoise(h, w, seed=0, ox=0, oy=0):
    yy, xx = np.mgrid[0:h, 0:w].astype(np.uint64)
    yy += np.uint64(oy)
    xx += np.uint64(ox)
    v = (xx * np.uint64(73856093)) ^ (yy * np.uint64(19349663)) ^ np.uint64(seed * 83492791 + 12345)
    v = (v * np.uint64(2654435761)) & np.uint64(0xFFFFFFFF)
    v ^= v >> np.uint64(15)
    v = (v * np.uint64(2246822519)) & np.uint64(0xFFFFFFFF)
    v ^= v >> np.uint64(13)
    return (v & np.uint64(0xFFFF)).astype(np.float64) / 65535.0


def value_noise(h, w, cell, seed=0):
    """Smooth-ish blocky noise in [0,1] (bilinear of random grid)."""
    gh, gw = h // cell + 2, w // cell + 2
    rng = np.random.default_rng(seed)
    g = rng.random((gh, gw))
    yy, xx = np.mgrid[0:h, 0:w] / cell
    y0, x0 = yy.astype(int), xx.astype(int)
    fy, fx = yy - y0, xx - x0
    fy = fy * fy * (3 - 2 * fy)
    fx = fx * fx * (3 - 2 * fx)
    a = g[y0, x0] * (1 - fx) + g[y0, x0 + 1] * fx
    b = g[y0 + 1, x0] * (1 - fx) + g[y0 + 1, x0 + 1] * fx
    return a * (1 - fy) + b * fy


def _polys(geom):
    if geom is None or geom.is_empty:
        return []
    t = geom.geom_type
    if t == "Polygon":
        return [geom]
    if t in ("MultiPolygon", "GeometryCollection"):
        out = []
        for g in geom.geoms:
            out += _polys(g)
        return out
    return []


def raster(geom, w, h, ox=0.0, oy=0.0):
    """Bool mask of a (multi)polygon in pixel coords; (ox,oy) = window origin."""
    im = Image.new("1", (w, h), 0)
    d = ImageDraw.Draw(im)
    for p in _polys(geom):
        d.polygon([(x - ox, y - oy) for x, y in p.exterior.coords], fill=1, outline=1)
        for r in p.interiors:
            d.polygon([(x - ox, y - oy) for x, y in r.coords], fill=0, outline=0)
    return np.array(im, dtype=bool)


def raster_lines(lines, w, h, width=1, ox=0.0, oy=0.0):
    im = Image.new("1", (w, h), 0)
    d = ImageDraw.Draw(im)
    for ln in lines:
        d.line([(x - ox, y - oy) for x, y in ln], fill=1, width=width)
    return np.array(im, dtype=bool)


def shift(m, dx, dy):
    out = np.zeros_like(m)
    h, w = m.shape
    ys0, ys1 = max(0, -dy), min(h, h - dy)
    xs0, xs1 = max(0, -dx), min(w, w - dx)
    out[ys0 + dy:ys1 + dy, xs0 + dx:xs1 + dx] = m[ys0:ys1, xs0:xs1]
    return out


def dilate(m, r=1, cross=False):
    out = m.copy()
    for dy in range(-r, r + 1):
        for dx in range(-r, r + 1):
            if (dx or dy) and (not cross or abs(dx) + abs(dy) <= r) and dx * dx + dy * dy <= r * r + r:
                out |= shift(m, dx, dy)
    return out


def erode(m, r=1, cross=False):
    return ~dilate(~m, r, cross)


def edge4(m):
    """Pixels of m with a 4-neighbour outside m."""
    inner = m & shift(m, 1, 0) & shift(m, -1, 0) & shift(m, 0, 1) & shift(m, 0, -1)
    return m & ~inner


def art(rows, cmap):
    """ASCII art -> index array. '.' or ' ' = transparent."""
    w = max(len(r) for r in rows)
    a = np.full((len(rows), w), T, np.uint8)
    for y, r in enumerate(rows):
        for x, ch in enumerate(r):
            if ch not in ". ":
                a[y, x] = c(cmap[ch])
    return a


def paste(dst, src, x, y):
    """Alpha-paste index image src onto dst at (x,y) (clipped)."""
    h, w = src.shape
    H, W = dst.shape
    x0, y0 = max(0, x), max(0, y)
    x1, y1 = min(W, x + w), min(H, y + h)
    if x1 <= x0 or y1 <= y0:
        return
    s = src[y0 - y:y1 - y, x0 - x:x1 - x]
    d = dst[y0:y1, x0:x1]
    m = s != T
    d[m] = s[m]


def text_mask(text, bold=False, size=8):
    f = ImageFont.truetype(str(FONT_B if bold else FONT_R), size)
    l, t, r, b = f.getbbox(text)
    im = Image.new("L", (r - l + 2, b - t + 2), 0)
    d = ImageDraw.Draw(im)
    d.fontmode = "1"
    d.text((-l, -t), text, font=f, fill=255)
    m = np.array(im) > 127
    ys, xs = np.nonzero(m)
    return m[: ys.max() + 1, : xs.max() + 1]


def to_rgba(a):
    pal = np.zeros((256, 4), np.uint8)
    for i, rgb in enumerate(RGB):
        pal[i, :3] = rgb
        pal[i, 3] = 255
    return pal[a]


def save_indexed(a, path):
    """Save as palette PNG; index len(NAMES) is transparent."""
    n = len(NAMES)
    b = a.copy()
    b[a == T] = n
    im = Image.fromarray(b, "P")
    flat = []
    for rgb in RGB:
        flat += list(rgb)
    flat += [0, 0, 0]
    im.putpalette(flat)
    if (a == T).any():
        im.save(path, optimize=True, transparency=n)
    else:
        im.save(path, optimize=True)


# darker shade of each colour (for dithered shadows)
DARKER = {
    "grass": "green", "grass-light": "grass", "lime-pale": "grass-light", "green": "green-dark",
    "green-dark": "ink", "sand": "tan", "sand-light": "sand", "tan": "brown", "brown": "brown-dark",
    "asphalt": "asphalt-dark", "asphalt-dark": "ink", "grey": "asphalt", "grey-light": "grey",
    "cream": "grey-light", "white": "cream", "blue": "blue-dark", "sky": "blue", "sky-pale": "sky",
    "red": "red-dark", "coral": "red", "orange": "tan", "yellow": "orange", "mint": "green",
    "purple": "plum", "pink": "purple", "pink-pale": "pink", "lilac": "purple", "red-dark": "brown-dark",
    "brown-dark": "plum", "plum": "ink", "blue-dark": "ink", "ink": "ink",
}
DARK_LUT = np.arange(256, dtype=np.uint8)
for _k, _v in DARKER.items():
    DARK_LUT[IDX[_k]] = IDX[_v]


def shade(img, mask, density=0.5):
    """Dithered darkening of img where mask."""
    h, w = img.shape
    m = mask & (bayer(h, w) < density)
    img[m] = DARK_LUT[img[m]]
