#!/usr/bin/env python3
"""Build character sprites, name tags and FX icons from ~/Downloads/<Name>.jpeg.

Pipeline per character: flood-fill background removal at source res (tolerance vs
border colour) -> crop -> block-mode downsample straight onto the shared pixel
grid (figure height LARGE_H) -> halo cleanup -> per-sprite k-means palette ->
1px dark outline for the map size. Re-runnable.
"""
import json
from collections import deque
from pathlib import Path

import cv2
import numpy as np
from PIL import Image, ImageDraw, ImageFont

ROOT = Path(__file__).resolve().parents[3]
SRC = Path.home() / "Downloads"
OUT = ROOT / "public/assets/sprites"
REVIEW = ROOT / "tools/map-data/output/characters_review.png"
FONT = ROOT / "tools/map-data/fonts/silkscreen_Silkscreen-Regular.ttf"
PAL = json.loads((ROOT / "tools/map-data/palette.json").read_text())["colors"]

def hexrgb(h):
    return tuple(int(h[i:i + 2], 16) for i in (1, 3, 5))

INK, CREAM = hexrgb(PAL["ink"]), hexrgb(PAL["cream"])
NAMES = ["vaishali", "jathin", "anudeep", "laasya", "asritha", "joel", "bhavana", "prabhu"]
LARGE_H, SMALL_H = 96, 32
LARGE_W, SMALL_W = 64, 28
# chibi map sprite: head rows / body rows (inside the 1px outline)
SMALL_HEAD, SMALL_BODY = 11, 19
# fraction of the figure height (from the top) that is the head, per source
HEAD_FRAC = {"vaishali": 0.20, "jathin": 0.19, "anudeep": 0.17, "laasya": 0.17,
             "asritha": 0.17, "joel": 0.20, "bhavana": 0.21, "prabhu": 0.16}
# fraction of the full figure visible in the source (cropped sources)
VISIBLE = {"bhavana": 0.86}
K = 32
BODY_WIDEN = 1.6
DARK_DELTA, DARK_SHARE = 55, 0.28
CLOSE = 21
MAXHOLE = 900


def bg_mask(rgb):
    """True where background: flood from all edges through pixels close to the local border colour."""
    h, w, _ = rgb.shape
    lab = cv2.cvtColor(rgb, cv2.COLOR_RGB2LAB).astype(np.float32)
    border = np.concatenate([lab[0], lab[-1], lab[:, 0], lab[:, -1]])
    border = border[border[:, 0] > 170]  # ignore figure parts cut by the frame
    # background may be a two-tone/gradient panel: compare against several border colours
    crit = (cv2.TERM_CRITERIA_EPS + cv2.TERM_CRITERIA_MAX_ITER, 30, 0.5)
    cv2.setRNGSeed(1)
    _, _, refs = cv2.kmeans(border.astype(np.float32), 4, None, crit, 3, cv2.KMEANS_PP_CENTERS)
    d = np.min([np.linalg.norm(lab - r, axis=2) for r in refs], axis=0)
    light = (lab[..., 0] > 200) & (np.abs(lab[..., 1] - 128) < 14) & (np.abs(lab[..., 2] - 128) < 18)
    cand = ((d < 9) | (light & (d < 13))).astype(np.uint8)
    n, lbl = cv2.connectedComponents(cand, connectivity=4)
    edge = set(np.unique(np.concatenate([lbl[0], lbl[-1], lbl[:, 0], lbl[:, -1]]))) - {0}
    mask = np.isin(lbl, list(edge)) & (cand > 0)
    # drop tiny watermark-ish islands of foreground
    fg = (~mask).astype(np.uint8)
    n, lbl, st, _ = cv2.connectedComponentsWithStats(fg, connectivity=8)
    big = np.argmax(st[1:, cv2.CC_STAT_AREA]) + 1
    keep = st[:, cv2.CC_STAT_AREA] > st[big, cv2.CC_STAT_AREA] * 0.01
    keep[0] = False
    fgm = keep[lbl].astype(np.uint8)
    # close small gaps (white shirts/shoes touching a white background) and fill enclosed holes
    k = cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (CLOSE, CLOSE))
    closed = cv2.morphologyEx(fgm, cv2.MORPH_CLOSE, k)
    ff = closed.copy()
    pad = np.zeros((h + 2, w + 2), np.uint8)
    cv2.floodFill(ff, pad, (0, 0), 1)
    holes = (ff == 0)
    n2, l2, st2, _ = cv2.connectedComponentsWithStats(holes.astype(np.uint8), connectivity=4)
    small_h = st2[:, cv2.CC_STAT_AREA] < MAXHOLE
    small_h[0] = False
    holes = small_h[l2]
    return ~((closed > 0) | holes)


def skin_of(px):
    px = px.astype(int)
    r, g, b = px[..., 0], px[..., 1], px[..., 2]
    return (r > 100) & (g > 0.5 * r) & (g < 0.9 * r) & (b > 0.15 * r) & (b < 0.8 * r) & (r < 250)


def block_mode(rgb, fg, out_h, out_w=None, dark_bias=True, skin_pri=False):
    """Downsample by taking the dominant colour (quantised mode, then median) of each block."""
    h, w = fg.shape
    s = h / out_h
    out_w = out_w or max(1, round(w / s))
    sx = w / out_w
    res = np.zeros((out_h, out_w, 4), np.uint8)
    for y in range(out_h):
        y0, y1 = int(round(y * s)), max(int(round((y + 1) * s)), int(round(y * s)) + 1)
        for x in range(out_w):
            x0, x1 = int(round(x * sx)), max(int(round((x + 1) * sx)), int(round(x * sx)) + 1)
            m = fg[y0:y1, x0:x1]
            if m.size == 0 or m.mean() < 0.5:
                continue
            px = rgb[y0:y1, x0:x1][m].astype(int)
            q = px // 24
            keys = q[:, 0] * 10000 + q[:, 1] * 100 + q[:, 2]
            vals, cnt = np.unique(keys, return_counts=True)
            top = cnt.max() / cnt.sum()
            # crisp pixel art: dominant colour; smooth shading: plain median
            sel = px[keys == vals[np.argmax(cnt)]] if top > 0.45 else px
            # keep thin dark detail (eyes, glasses, brows, outlines) that a median would erase
            lum = px.sum(1) / 3
            dark = lum < np.median(lum) - DARK_DELTA
            if dark_bias and dark.mean() > DARK_SHARE:
                sel = px[dark]
            if skin_pri:
                sk = skin_of(px)
                if sk.mean() > 0.4:
                    sel = px[sk]
            res[y, x, :3] = np.median(sel, axis=0)
            res[y, x, 3] = 255
    return res


def kmeans_palette(img, k=K):
    a = img[..., 3] > 0
    px = img[a][:, :3].astype(np.float32)
    k = min(k, len(np.unique(px, axis=0)))
    crit = (cv2.TERM_CRITERIA_EPS + cv2.TERM_CRITERIA_MAX_ITER, 50, 0.5)
    cv2.setRNGSeed(1)
    _, lbl, cen = cv2.kmeans(px, k, None, crit, 4, cv2.KMEANS_PP_CENTERS)
    cen = np.clip(cen, 0, 255).astype(np.uint8)
    # merge near-duplicates
    for i in range(len(cen)):
        for j in range(i):
            if np.linalg.norm(cen[i].astype(int) - cen[j].astype(int)) < 10:
                cen[i] = cen[j]
    out = img.copy()
    out[a, :3] = cen[lbl.ravel()]
    return out


def dehalo(img):
    """Remove light low-contrast pixels touching transparency (repeat twice)."""
    for _ in range(2):
        a = img[..., 3] > 0
        pad = np.pad(a, 1)
        touch = ~(pad[:-2, 1:-1] & pad[2:, 1:-1] & pad[1:-1, :-2] & pad[1:-1, 2:])
        lum = img[..., :3].astype(int).sum(2) / 3
        sat = img[..., :3].max(2).astype(int) - img[..., :3].min(2)
        lp = np.pad(a & (lum > 190) & (sat < 40), 1).astype(int)
        lightnb = lp[:-2, 1:-1] + lp[2:, 1:-1] + lp[1:-1, :-2] + lp[1:-1, 2:]
        kill = a & touch & (((lum > 235) & (sat < 20)) | ((lum > 190) & (sat < 40) & (lightnb <= 1)))
        img[kill, 3] = 0
        # isolated pixels
        a = img[..., 3] > 0
        pad = np.pad(a, 1).astype(int)
        nb = pad[:-2, 1:-1] + pad[2:, 1:-1] + pad[1:-1, :-2] + pad[1:-1, 2:]
        img[a & (nb == 0), 3] = 0
    return img


def fill_holes(img):
    """Fill transparent pixels fully enclosed by the figure (pinholes) with neighbour colour."""
    a = (img[..., 3] > 0).astype(np.uint8)
    inv = 1 - a
    n, lbl, st, _ = cv2.connectedComponentsWithStats(inv, connectivity=4)
    h, w = a.shape
    for i in range(1, n):
        x, y, bw, bh, area = st[i]
        if x == 0 or y == 0 or x + bw == w or y + bh == h or area > 3:
            continue
        for yy, xx in zip(*np.where(lbl == i)):
            nbs = [img[yy + dy, xx + dx] for dy, dx in ((0, 1), (1, 0), (0, -1), (-1, 0))
                   if 0 <= yy + dy < h and 0 <= xx + dx < w and img[yy + dy, xx + dx, 3]]
            if nbs:
                img[yy, xx] = nbs[0]
    return img


def outline(img, color=INK):
    a = img[..., 3] > 0
    pad = np.pad(a, 1)
    ring = (pad[:-2, 1:-1] | pad[2:, 1:-1] | pad[1:-1, :-2] | pad[1:-1, 2:]) & ~a
    img[ring] = (*color, 255)
    return img


def place(fig, cw, ch, feet):
    h, w = fig.shape[:2]
    if w > cw:  # crop symmetric overflow (raised arms etc.)
        o = (w - cw) // 2
        fig, w = fig[:, o:o + cw], cw
    can = np.zeros((ch, cw, 4), np.uint8)
    x0 = (cw - w) // 2
    can[feet - h:feet, x0:x0 + w] = fig
    return can


def process(name):
    rgb = np.array(Image.open(SRC / f"{name.capitalize()}.jpeg").convert("RGB"))
    bg = bg_mask(rgb)
    ys, xs = np.where(~bg)
    rgb, fg = rgb[ys.min():ys.max() + 1, xs.min():xs.max() + 1], ~bg[ys.min():ys.max() + 1, xs.min():xs.max() + 1]
    vis = VISIBLE.get(name, 1.0)
    period = detect_period(rgb)
    print(f"  {name}: source block ~{period:.1f}px, figure ~{rgb.shape[0] / period:.0f} blocks tall")
    big = block_mode(rgb, fg, max(1, round(LARGE_H * vis)))
    big = fill_holes(dehalo(kmeans_palette(big)))
    # chibi map sprite, built from the clean large sprite: head reduced gently, body hard
    big = trim(big)
    hy = int(round(big.shape[0] / vis * HEAD_FRAC[name]))
    bfg = big[..., 3] > 0
    brgb = big[..., :3]
    head = block_mode(brgb[:hy], bfg[:hy], SMALL_HEAD, dark_bias=False, skin_pri=True)
    body_rows = max(1, round((SMALL_BODY + SMALL_HEAD) * vis) - SMALL_HEAD)
    bh = big.shape[0] - hy
    body = block_mode(brgb[hy:], bfg[hy:], body_rows, max(1, round(big.shape[1] * body_rows / bh * BODY_WIDEN)), dark_bias=False)
    small = stack_center(head, body)
    small = fill_holes(dehalo(kmeans_palette(small, 16)))
    small = outline(trim(np.pad(small, ((1, 1), (1, 1), (0, 0)))))
    return trim(big), trim(small)


def detect_period(rgb):
    g = rgb.mean(2)
    e = np.abs(np.diff(g, axis=0)).sum(1)
    e = e - e.mean()
    n = len(e) * 8
    F = np.abs(np.fft.rfft(e, n))
    fr = np.fft.rfftfreq(n)
    m = (fr > 1 / 24) & (fr < 1 / 6)
    return 1 / fr[np.argmax(F * m)]


def stack_center(a, b):
    w = max(a.shape[1], b.shape[1])
    out = np.zeros((a.shape[0] + b.shape[0], w, 4), np.uint8)
    out[:a.shape[0], (w - a.shape[1]) // 2:(w - a.shape[1]) // 2 + a.shape[1]] = a
    out[a.shape[0]:, (w - b.shape[1]) // 2:(w - b.shape[1]) // 2 + b.shape[1]] = b
    return out


# Hand-tuned chibi faces on the final small canvas (x = face centre column, y = eye row).
# The block-mode reduction alone leaves faces as 3-4 muddy pixels, so a clean
# 6x6 face (skin from the large sprite, two ink eyes, mouth, optional glasses) is stamped on.
FACE = {
    "vaishali": {"cx": 14, "ey": 11, "glasses": (196, 48, 40)},
    "jathin": {"cx": 15, "ey": 10, "glasses": (30, 26, 30)},
    "anudeep": {"cx": 14, "ey": 11},
    "laasya": {"cx": 14, "ey": 10},
    "asritha": {"cx": 14, "ey": 10, "glasses": (70, 52, 46)},
    "joel": {"cx": 14, "ey": 11, "glasses": (30, 26, 30)},
    "bhavana": {"cx": 16, "ey": 10},
    "prabhu": {"cx": 14, "ey": 10},
}
FACE_MASK = [
    ".SSSS.",
    "SSSSSS",
    "SESSES",
    "SSSSSS",
    ".SMMS.",
    "..SS..",
]


def skin_colour(big):
    head = big[: big.shape[0] // 4]
    sk = skin_of(head[..., :3]) & (head[..., 3] > 0)
    px = head[sk][:, :3].astype(int)
    lum = px.sum(1)
    px = px[lum >= np.median(lum)]  # lit side of the face
    return tuple(int(v) for v in np.median(px, axis=0))


def stamp_face(can, name, skin):
    f = FACE[name]
    x0, y0 = f["cx"] - 3, f["ey"] - 2
    shade = tuple(int(v * 0.8) for v in skin)
    mouth = tuple(int(v * 0.72) for v in skin)
    g = f.get("glasses")
    for dy, row in enumerate(FACE_MASK):
        for dx, ch in enumerate(row):
            if ch == ".":
                continue
            y, x = y0 + dy, x0 + dx
            col = {"S": skin, "E": EYE_INK, "M": mouth}[ch]
            if ch == "S" and dx == 5 and dy >= 1:
                col = shade
            if g and dy == 2 and ch == "S":
                col = g
            can[y, x] = (*col, 255)
    if g:  # bridge/top of frames
        for dx in (1, 4):
            can[y0 + 1, x0 + dx] = (*g, 255)
    return can


# per-character eye placement on the small sprite: (row, dx from face centre, gap, colour key)
EYES = {}
EYE_INK = (40, 30, 36)


def find_eyes(big, hy):
    """Eye row and face span (in large-sprite coords) from the head region."""
    head = big[:hy]
    sk = skin_of(head[..., :3]) & (head[..., 3] > 0)
    ys, xs = np.where(sk)
    if len(ys) < 6:
        return None
    fy0, fy1 = ys.min(), ys.max()
    best, by = -1, None
    for y in range(fy0, fy0 + int((fy1 - fy0) * 0.7) + 1):
        cols = np.where(sk[y])[0]
        if len(cols) < 2:
            continue
        seg = head[y, cols.min():cols.max() + 1]
        lum = seg[..., :3].astype(int).sum(-1) / 3
        dark = int(((lum < 90) & (seg[..., 3] > 0)).sum())
        if dark > best:
            best, by = dark, y
    cols = np.where(sk[by])[0] if by is not None else xs
    return {"y": by, "x0": int(np.percentile(xs, 10)), "x1": int(np.percentile(xs, 90)), "w": big.shape[1]}


def paint_eyes(img, name, eye, hy):
    """Stamp two ink eye pixels on the chibi head at the row found in the large sprite."""
    if eye is None or eye["y"] is None:
        return img
    spec = EYES.get(name, {})
    sy = SMALL_HEAD / hy
    row = min(SMALL_HEAD - 2, int(round(eye["y"] * sy))) + spec.get("dy", 0)
    # head was centred in the stacked image; map x through the head's own scale
    hw = int(round(eye["w"] * sy)) if False else None
    cols = np.where(skin_of(img[row, :, :3]) & (img[row, :, 3] > 0))[0]
    if len(cols) < 2:
        cols = np.where(img[row, :, 3] > 0)[0]
    cx = (cols.min() + cols.max()) / 2 + spec.get("dx", 0)
    half = max(1, int(round((cols.max() - cols.min()) / 4))) if len(cols) >= 5 else 1
    half = spec.get("half", half)
    for ex in (int(np.floor(cx - half)), int(np.ceil(cx + half))):
        if 0 <= ex < img.shape[1] and img[row, ex, 3]:
            img[row, ex] = (*spec.get("color", EYE_INK), 255)
    return img
    spec = EYES.get(name, {})
    cy = spec.get("row", int(np.percentile(ys, 35)))
    row = xs[ys == cy]
    cx = int(round((row.min() + row.max()) / 2)) if len(row) else int(np.median(xs))
    cx += spec.get("dx", 0)
    gap = spec.get("gap", 2)
    col = spec.get("color", EYE_INK)
    for ex in (cx - gap + (gap // 2) - (0 if gap % 2 else 0), cx + (gap - gap // 2)):
        pass
    left, right = cx - (gap + 1) // 2, cx + gap // 2 + (1 if gap % 2 == 0 else 0)
    for ex in (left, right):
        if 0 <= ex < img.shape[1] and img[cy, ex, 3]:
            img[cy, ex] = (*col, 255)
    return img


def trim(img):
    ys, xs = np.where(img[..., 3] > 0)
    return img[ys.min():ys.max() + 1, xs.min():xs.max() + 1]


def save(arr, path):
    path.parent.mkdir(parents=True, exist_ok=True)
    Image.fromarray(arr, "RGBA").save(path, optimize=True)


def make_tag(text):
    font = ImageFont.truetype(str(FONT), 8)
    tmp = Image.new("1", (200, 20))
    d = ImageDraw.Draw(tmp)
    d.fontmode = "1"
    l, t, r, b = d.textbbox((0, 0), text, font=font)
    tw = r - l
    W, H = tw + 6, 11
    im = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    d = ImageDraw.Draw(im)
    d.fontmode = "1"
    d.rectangle([0, 0, W - 1, H - 1], fill=CREAM + (255,), outline=INK + (255,))
    for c in ((0, 0), (W - 1, 0), (0, H - 1), (W - 1, H - 1)):
        im.putpixel(c, (0, 0, 0, 0))
    d.text((3 - l, (H - (b - t)) // 2 - t), text, font=font, fill=INK + (255,))
    return im


def grid_img(rows, color):
    """rows: list of strings; '#'=color '.'=transparent, 'o'=ink, 'w'=white"""
    h, w = len(rows), len(rows[0])
    im = Image.new("RGBA", (w, h), (0, 0, 0, 0))
    cm = {"o": INK, "w": hexrgb(PAL["white"]), "#": color, "r": hexrgb(PAL["red"]),
          "y": hexrgb(PAL["yellow"]), "p": hexrgb(PAL["pink-pale"])}
    for y, row in enumerate(rows):
        for x, c in enumerate(row):
            if c in cm:
                im.putpixel((x, y), cm[c] + (255,))
    return im


def make_fx():
    fx = OUT / "fx"
    bang = grid_img([
        ".ooooooo.",
        "owwwrwwwo",
        "owwwrwwwo",
        "owwwrwwwo",
        "owwwrwwwo",
        "owwwwwwwo",
        "owwwrwwwo",
        "owwwwwwwo",
        ".ooowooo.",
        "...owo...",
        "....o....",
    ], INK)
    bang.save(fx / "bang.png")
    heart = grid_img([
        ".oo...oo.",
        "orro.orro",
        "orpr#rrro",
        "orrrrrrro",
        ".orrrrro.",
        "..orrro..",
        "...oro...",
        "....o....",
    ], hexrgb(PAL["red"]))
    heart.save(fx / "heart.png")
    frames = [
        [".......", ".......", ".......", "...y...", ".......", ".......", "......."],
        [".......", ".......", "...y...", "..ywy..", "...y...", ".......", "......."],
        [".......", "...y...", "...y...", ".yywyy.", "...y...", "...y...", "......."],
        ["...y...", ".y.y.y.", "..yyy..", "yyywyyy", "..yyy..", ".y.y.y.", "...y..."],
    ]
    strip = Image.new("RGBA", (28, 7), (0, 0, 0, 0))
    for i, f in enumerate(frames):
        strip.paste(grid_img(f, INK), (i * 7, 0))
    strip.save(fx / "sparkle.png")
    for fname, (w, h) in (("shadow.png", (17, 5)), ("shadow_small.png", (14, 4))):
        im = Image.new("RGBA", (w, h), (0, 0, 0, 0))
        yy, xx = np.mgrid[0:h, 0:w]
        m = ((xx + 0.5 - w / 2) / (w / 2)) ** 2 + ((yy + 0.5 - h / 2) / (h / 2)) ** 2 <= 1.0
        a = np.zeros((h, w, 4), np.uint8)
        a[m] = (*INK, 255)
        Image.fromarray(a, "RGBA").save(fx / fname)


def review(large, small):
    cw = LARGE_W + 4
    W, H = cw * len(NAMES), LARGE_H + 4 + SMALL_H + 4
    panels = []
    for bgkind in ("check", "green"):
        p = np.zeros((H, W, 3), np.uint8)
        if bgkind == "check":
            yy, xx = np.mgrid[0:H, 0:W]
            p[:] = np.where((((yy // 4) + (xx // 4)) % 2)[..., None] == 0, 200, 150)
        else:
            p[:] = hexrgb(PAL["grass"])
        for i, n in enumerate(NAMES):
            for arr, oy, ox in ((large[n], 2, i * cw + 2), (small[n], LARGE_H + 6, i * cw + 2 + (LARGE_W - SMALL_W) // 2)):
                h, w = arr.shape[:2]
                reg = p[oy:oy + h, ox:ox + w]
                a = arr[..., 3:] > 0
                reg[:] = np.where(a, arr[..., :3], reg)
        panels.append(p)
    out = np.concatenate(panels, 0)
    REVIEW.parent.mkdir(parents=True, exist_ok=True)
    Image.fromarray(out).resize((out.shape[1] * 4, out.shape[0] * 4), Image.NEAREST).save(REVIEW)


def main():
    large, small, chars = {}, {}, {}
    for n in NAMES:
        b, s = process(n)
        large[n] = place(b, LARGE_W, LARGE_H, LARGE_H)
        small[n] = stamp_face(place(s, SMALL_W, SMALL_H, SMALL_H), n, skin_colour(b))
        save(large[n], OUT / f"{n}.png")
        save(small[n], OUT / f"{n}_map.png")
        tag = make_tag(n.capitalize())
        tag.save(OUT / "tags" / f"{n}.png")
        ncol = len(np.unique(large[n][large[n][..., 3] > 0][:, :3], axis=0))
        print(f"{n}: fig {b.shape[1]}x{b.shape[0]} small {s.shape[1]}x{s.shape[0]} colours {ncol}")
        chars[n] = {
            "name": n.capitalize(),
            "large": {"file": f"{n}.png", "w": LARGE_W, "h": LARGE_H, "feetY": LARGE_H},
            "small": {"file": f"{n}_map.png", "w": SMALL_W, "h": SMALL_H, "feetY": SMALL_H},
            "tag": {"file": f"tags/{n}.png", "w": tag.width, "h": tag.height},
            "walk": None,
        }
    make_fx()
    data = {
        "player": "vaishali",
        "order": [n for n in NAMES if n != "vaishali"],
        "characters": chars,
        "fx": {"bang": "fx/bang.png", "heart": "fx/heart.png", "sparkle": "fx/sparkle.png",
               "sparkleFrame": {"w": 7, "h": 7, "frames": 4},
               "largeFxScale": 2,
               "shadow": "fx/shadow.png", "shadowSmall": "fx/shadow_small.png"},
    }
    (OUT / "characters.json").write_text(json.dumps(data, indent=2) + "\n")
    review(large, small)


if __name__ == "__main__":
    main()
