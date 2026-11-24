"""Prop sprites (index arrays) with their base anchor (ax, ay) = feet point."""
import numpy as np

from .pix import T, art, c, text_mask

K = {
    "k": "ink", "p": "plum", "w": "white", "W": "cream", "g": "grey", "G": "grey-light",
    "b": "tan", "B": "brown", "d": "brown-dark", "r": "red", "R": "red-dark", "o": "orange",
    "y": "yellow", "Y": "sand-light", "s": "sky", "S": "sky-pale", "u": "blue", "U": "blue-dark",
    "e": "grass", "E": "green", "f": "green-dark", "l": "grass-light", "c": "coral", "a": "asphalt",
    "A": "asphalt-dark", "n": "sand", "q": "pink-pale", "m": "mint", "v": "purple",
}


class Sprite:
    def __init__(self, img, ax, ay, kind, foot=None):
        self.img, self.ax, self.ay, self.kind = img, ax, ay, kind
        # foot = (x0,y0,x1,y1) rectangle relative to anchor that touches the ground
        self.foot = foot or (-1, -1, 1, 0)

    @property
    def w(self):
        return self.img.shape[1]

    @property
    def h(self):
        return self.img.shape[0]


def _tree(circles, trunk_h, seed, palm=False):
    """circles: list of (cx, cy, r) in a local canopy frame."""
    rng = np.random.default_rng(seed)
    R = max(cx + r for cx, cy, r in circles) + 2
    Hc = max(cy + r for cx, cy, r in circles) + 2
    W = int(R) + 1
    H = int(Hc) + trunk_h + 1
    img = np.full((H, W), T, np.uint8)
    yy, xx = np.mgrid[0:H, 0:W]
    light = np.full((H, W), -9.0)
    inside = np.zeros((H, W), bool)
    for cx, cy, r in circles:
        dx, dy = (xx - cx) / r, (yy - cy) / r
        d2 = dx * dx + dy * dy
        m = d2 <= 1.0
        # sphere-ish shading, light from upper-left
        nz = np.sqrt(np.clip(1 - d2, 0, 1))
        L = -0.55 * dx - 0.65 * dy + 0.5 * nz
        light = np.where(m & (L > light), L, light)
        inside |= m
    # trunk
    tx = int(round(sum(cx for cx, _, _ in circles) / len(circles)))
    base = H - 1
    cbot = int(max(cy + r * 0.7 for cx, cy, r in circles))
    trunk = np.zeros((H, W), bool)
    for y in range(cbot, base + 1):
        trunk[y, tx - 1:tx + 1] = True
    img[trunk] = c("brown")
    img[trunk & (xx == tx)] = c("brown-dark")
    # whitewash the lowest 2 rows
    ww = trunk & (yy >= base - 1)
    img[ww] = c("white")
    img[ww & (xx == tx)] = c("cream")
    # canopy
    d = np.random.default_rng(seed).random((H, W))
    col = np.full((H, W), c("green"), np.uint8)
    col[light > 0.05] = c("grass")
    col[(light > 0.05) & (light < 0.2) & (d < 0.35)] = c("green")
    col[light > 0.45] = c("grass-light")
    col[(light > 0.45) & (light < 0.6) & (d < 0.4)] = c("grass")
    col[light < -0.25] = c("green-dark")
    col[(light < -0.25) & (light > -0.4) & ((xx + yy) % 2 == 0)] = c("green")
    img[inside] = col[inside]
    # sparkles
    sp = inside & (light > 0.62) & (d > 0.86)
    img[sp] = c("lime-pale")
    # outline
    o = np.zeros_like(inside)
    for ddx, ddy in ((1, 0), (-1, 0), (0, 1), (0, -1)):
        o |= np.roll(np.roll(inside, ddy, 0), ddx, 1)
    o &= ~inside
    img[o & ~trunk] = c("green-dark")
    # leaf clumps: a few darker crescent pixels inside
    for _ in range(len(circles) * 3):
        cx, cy, r = circles[rng.integers(len(circles))]
        a = rng.random() * 6.28
        px, py = int(cx + np.cos(a) * r * 0.5), int(cy + np.sin(a) * r * 0.5)
        if 0 <= py + 1 < H and 0 <= px + 1 < W and inside[py, px] and inside[py + 1, px + 1]:
            if light[py, px] < 0.45:
                img[py + 1, px] = c("green-dark") if light[py, px] < 0.1 else c("green")
                img[py + 1, px + 1] = c("green-dark") if light[py, px] < 0.1 else c("green")
    rows = np.nonzero((img != T).any(1))[0]
    cols = np.nonzero((img != T).any(0))[0]
    img = img[rows[0]:rows[-1] + 1, cols[0]:cols[-1] + 1]
    ax = tx - cols[0]
    ay = base - rows[0]
    return img, ax, ay


def tree_variants():
    out = []
    img, ax, ay = _tree([(8, 7, 7.2)], 4, 1)
    out.append(Sprite(img, ax, ay, "tree", (-2, -2, 2, 0)))
    img, ax, ay = _tree([(6, 6, 5.2)], 3, 2)
    out.append(Sprite(img, ax, ay, "tree", (-2, -2, 2, 0)))
    img, ax, ay = _tree([(6, 9, 5.5), (12, 8, 5.5), (9, 4.5, 5.5)], 4, 3)
    out.append(Sprite(img, ax, ay, "tree", (-2, -2, 2, 0)))
    img, ax, ay = _tree([(5, 8, 4.6), (10, 7, 4.8), (7.5, 4, 4.2)], 3, 4)
    out.append(Sprite(img, ax, ay, "tree", (-2, -2, 2, 0)))
    return out


def palm():
    a = art([
        "...E....E...",
        "..EeE..EeE..",
        ".Ee.eElE.eE.",
        "Ee...lel..eE",
        "E...EfefE..E",
        "...E.fBf.E..",
        "..E...B...E.",
        "......B.....",
        "......B.....",
        "......d.....",
        "......B.....",
        "......d.....",
        "......w.....",
        "......w.....",
    ], K)
    return Sprite(a, 6, 13, "tree", (-1, -1, 1, 0))


def bush():
    a = art([
        ".fEEf.",
        "fElleE",
        "EeeeEf",
        ".fEEf.",
    ], K)
    return Sprite(a, 3, 3, "bush", (-3, -2, 2, 0))


def bench():
    a = art([
        ".BBBBBBB.",
        "BbbbbbbbB",
        "dBBBBBBBd",
        "d.......d",
    ], K)
    return Sprite(a, 4, 3, "bench", (-4, -2, 4, 0))


def lamp():
    a = art([
        ".kkk.",
        "kyYyk",
        ".kyk.",
        "..k..",
        "..p..",
        "..k..",
        "..p..",
        "..k..",
        "..p..",
        "..k..",
        ".kpk.",
        ".kkk.",
    ], {**K, "Y": "white"})
    return Sprite(a, 2, 11, "lamp", (-1, -1, 1, 0))


def car(body, dark, seed=0):
    a = art([
        "...kkkkkk...",
        "..kSSkSSSk..",
        ".kbsskssskk.",
        "kbbbbbbbbbbk",
        "kBbbbbbbbbBk",
        "kkkBBBBBBkkk",
        ".kk......kk.",
    ], {**K, "b": body, "B": dark})
    return Sprite(a, 6, 6, "car", (-6, -3, 6, 0))


def bus():
    a = art([
        ".kkkkkkkkkkkkkkkkkkkkkk.",
        "kyyyyyyyyyyyyyyyyyyyyyyk",
        "kyykssksskssksskssksskyk",
        "kyykuukuukuukuukuukuukyk",
        "kyyyyyyyyyyyyyyyyyyyyyyk",
        "kooooooooooooooooooooook",
        "kyyyyyyyyyyyyyyyyyyyyyyk",
        "koooooooooooooooooooooWk",
        ".kkAAkkkkkkkkkkkkkAAkkk.",
        "...kk.............kk....",
    ], K)
    return Sprite(a, 12, 9, "bus", (-12, -4, 11, 0))


def scooter(col):
    a = art([
        ".k.",
        "krk",
        ".r.",
        ".r.",
        "kkk",
        ".k.",
    ], {**K, "r": col})
    return Sprite(a, 1, 5, "bike", (-1, -2, 1, 0))


def kiosk():
    a = art([
        ".kkkkkkkkkkkkkkkk.",
        "krrwwrrwwrrwwrrwwk",
        "krrwwrrwwrrwwrrwwk",
        "kRRccRRccRRccRRcck",
        ".kRkRkRkRkRkRkRkk.",
        ".kWWWWWWWWWWWWWWk.",
        ".kWkkkkkkkkkkkWWk.",
        ".kWkyyyyyyyyykWWk.",
        ".kWkyYyyYyyyykWWk.",
        ".kbbbbbbbbbbbbbbk.",
        ".kBBBBBBBBBBBBBBk.",
        ".kWWWWWWWWWWWWWWk.",
        ".kGGGGGGGGGGGGGGk.",
        ".kkkkkkkkkkkkkkkk.",
    ], {**K, "Y": "white"})
    return Sprite(a, 9, 13, "kiosk", (-8, -4, 8, 0))


def umbrella():
    a = art([
        "....kkk....",
        "..kkrwrkk..",
        ".krrrwrrrk.",
        "krrrrwrrrrk",
        "kRwRwRwRwRk",
        ".k.k.k.k.k.",
        ".....p.....",
        "..kbbpbbk..",
        "..kBBBBBk..",
        "..k.....k..",
    ], K)
    return Sprite(a, 5, 9, "umbrella", (-3, -2, 3, 0))


def flowerbed():
    a = art([
        ".fEqEf.",
        "fqEyEqf",
        ".fEqEf.",
    ], K)
    return Sprite(a, 3, 2, "flowers", (-3, -2, 3, 0))


# 3x5 font for the gate beam
GLYPHS = {
    "V": ["x.x", "x.x", "x.x", "x.x", ".x."], "N": ["x.x", "xxx", "xxx", "x.x", "x.x"],
    "R": ["xx.", "x.x", "xx.", "x.x", "x.x"], "J": ["..x", "..x", "..x", "x.x", ".x."],
    "I": ["xxx", ".x.", ".x.", ".x.", "xxx"], "E": ["xxx", "x..", "xx.", "x..", "xxx"],
    "T": ["xxx", ".x.", ".x.", ".x.", ".x."], " ": ["..", "..", "..", "..", ".."],
}


def gate_arch(span):
    """Arch spanning `span` px between pillar centres. Anchor = bottom centre."""
    txt = "VNR VJIET"
    tw = sum(len(GLYPHS[ch][0]) + 1 for ch in txt) - 1
    beam_w = max(span + 8, tw + 8)
    W = beam_w + 2
    H = 26
    img = np.full((H, W), T, np.uint8)
    cx = W // 2
    pl, pr = cx - span // 2, cx + span // 2
    # pillars (striped stone)
    for px in (pl, pr):
        for y in range(8, H):
            for x in range(px - 2, px + 3):
                col = "orange" if ((y // 2) % 2 == 0) else "purple"
                if x == px + 2:
                    col = "tan" if col == "orange" else "plum"
                img[y, x] = c(col)
            img[y, px - 3] = c("ink")
            img[y, px + 3] = c("ink")
        img[H - 1, px - 3:px + 4] = c("ink")
        img[7, px - 3:px + 4] = c("ink")
    # beam
    bx0 = cx - beam_w // 2
    img[0, bx0 + 1:bx0 + beam_w - 1] = c("ink")
    img[1, bx0:bx0 + beam_w] = c("ink")
    img[2:10, bx0] = c("ink")
    img[2:10, bx0 + beam_w - 1] = c("ink")
    img[10, bx0:bx0 + beam_w] = c("ink")
    img[1, bx0 + 1:bx0 + beam_w - 1] = c("orange")
    img[2:10, bx0 + 1:bx0 + beam_w - 1] = c("red-dark")
    img[2, bx0 + 1:bx0 + beam_w - 1] = c("red")
    img[9, bx0 + 1:bx0 + beam_w - 1] = c("brown-dark")
    x = cx - tw // 2
    for ch in txt:
        g = GLYPHS[ch]
        for gy, row in enumerate(g):
            for gx, v in enumerate(row):
                if v == "x":
                    img[3 + gy + 0, x + gx] = c("cream")
        x += len(g[0]) + 1
    # finials
    for px in (pl, pr):
        img[0, px] = c("yellow")
    return Sprite(img, cx, H - 1, "gate", None), (pl - cx, pr - cx)


def signboard(label):
    m = text_mask(label.upper())
    th, tw = m.shape
    bw, bh = tw + 6, th + 6
    H = bh + 2
    img = np.full((H, bw), T, np.uint8)
    img[0:bh, :] = c("ink")
    img[1:bh - 1, 1:bw - 1] = c("brown")
    img[2:bh - 2, 2:bw - 2] = c("cream")
    img[bh - 3, 2:bw - 2] = c("sand-light")
    sub = img[3:3 + th, 3:3 + tw]
    sub[m] = c("ink")
    for px in (2, bw - 3):
        img[bh:H, px] = c("brown-dark")
    img[0, 0] = img[0, bw - 1] = img[bh - 1, 0] = img[bh - 1, bw - 1] = T
    return Sprite(img, bw // 2, H - 1, "sign", (-bw // 2, -2, bw // 2, 0))


def rock(v=0):
    a = art([
        "..kkk..",
        ".kGGgk.",
        "kGWGggk",
        "kgggggk",
        ".kkkkk.",
    ] if v == 0 else [
        ".kk.kk.",
        "kGgkGgk",
        "kgggggk",
        ".kkkkk.",
    ], K)
    return Sprite(a, 3, a.shape[0] - 1, "rock", (-3, -1, 3, 0))
