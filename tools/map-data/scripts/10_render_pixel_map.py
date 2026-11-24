"""Step 10 (render): pixel-art campus map for the game.

Reads data/processed/*.geojson (+ palette, Silkscreen font) and writes
  public/assets/map/campus_ground.png     flat ground layer (full map)
  public/assets/map/campus_buildings.png  building sprites (roof + south wall)
  public/assets/map/campus_props.png      trees, benches, lamps, vehicles, signs, gate, kiosk
  public/assets/map/campus.json           positions, hit polygons, doors, walk graph
  output/pixel_map_{debug,preview,sat_check}.png

Map pixel space: 0.5 m/px, px = x*2, py = (H_m - y)*2 (y down).
Run: cd tools/map-data && .venv/bin/python scripts/10_render_pixel_map.py
"""
import heapq
import json
import math
import sys
import zlib
from pathlib import Path

import cv2
import numpy as np
from PIL import Image, ImageDraw
from shapely.geometry import LineString, MultiLineString, Point, Polygon, box, shape
from shapely.affinity import translate
from shapely.ops import nearest_points, transform, unary_union

sys.path.insert(0, str(Path(__file__).resolve().parent))
from pixelmap import sprites as SP  # noqa: E402
from pixelmap.pix import (T, text_mask, bayer, c, dilate, edge4, erode, hashnoise, paste, raster,  # noqa: E402
                          raster_lines, save_indexed, shade, shift, to_rgba, value_noise)

TOOLS = Path(__file__).resolve().parents[1]
PROC = TOOLS / "data" / "processed"
OUT_PUBLIC = TOOLS.parents[1] / "public" / "assets" / "map"
OUT_DBG = TOOLS / "output"
META = json.loads((PROC / "meta.json").read_text())
HM_DATA = META["bbox_size_m"]["height"]
NORTH_MARGIN_M = 30.0  # extra map above the data bbox (neighbourhood north of Medak Road)
HM = HM_DATA + NORTH_MARGIN_M
W = math.ceil(META["bbox_size_m"]["width"] * 2)
H = math.ceil(HM * 2)
LEVEL_PX = 6
IGNORE_AREAS = {"Potti Sreeramulu Telugu University", "VJPS Play Ground"}
GATE_M = (367.0, 638.0)
CANTEEN_M = (169.0, 287.0)

LOG = []


def log(*a):
    s = " ".join(str(x) for x in a)
    LOG.append(s)
    print(s)


def to_px(g):
    return transform(lambda x, y, z=None: (np.asarray(x) * 2.0, (HM - np.asarray(y)) * 2.0), g)


def ptpx(x, y):
    return (x * 2.0, (HM - y) * 2.0)


def layer(name):
    p = PROC / f"{name}.geojson"
    return [(to_px(shape(f["geometry"])), f["properties"]) for f in json.loads(p.read_text())["features"]]


def lines_of(g):
    if g.is_empty:
        return []
    if g.geom_type == "LineString":
        return [g]
    if hasattr(g, "geoms"):
        out = []
        for s in g.geoms:
            out += lines_of(s)
        return out
    return []


# --------------------------------------------------------------------------- data
FINAL = layer("campus_final")
ROADS_U = [(g, p) for g, p in layer("roads_unclipped") if "Line" in g.geom_type]
PATHS = [(g, p) for g, p in layer("paths") if "Line" in g.geom_type]
OPEN = [(g, p) for g, p in layer("open_areas") if p.get("name") not in IGNORE_AREAS]
GREEN = layer("green")
TREES = [g for g, p in layer("trees")]
BARRIERS = layer("barriers")
BOUNDARY = layer("boundary")[0][0]
BBOX = box(0, 0, W, H)

GATE = Point(ptpx(*GATE_M))
CANTEEN = Point(ptpx(*CANTEEN_M))
CAMPUS_MASK = raster(BOUNDARY, W, H)


def road_width_px(p, inside):
    hw = p.get("highway")
    if p.get("name") == "Hanuman Marg":
        return 13
    if hw == "primary":
        return 14
    if hw == "tertiary":
        return 16
    if hw == "residential":
        return 11
    if hw == "road":
        return 12
    return 12 if inside else 9


ROADS = []  # (line px, width px, inside campus, props)
for g, p in ROADS_U:
    g = g.intersection(BBOX)
    for ln in lines_of(g):
        inside = ln.intersection(BOUNDARY.buffer(6)).length > 0.5 * ln.length
        cs = list(ln.coords)
        top = int(NORTH_MARGIN_M * 2)
        if p.get("highway") in ("residential", "service", "tertiary") and not inside:
            if abs(cs[0][1] - top) < 1.5:
                cs = [(cs[0][0], 0.0)] + cs
            if abs(cs[-1][1] - top) < 1.5:
                cs = cs + [(cs[-1][0], 0.0)]
            ln = LineString(cs)
        ROADS.append((ln, road_width_px(p, inside), inside, p))

# --------------------------------------------------------------------------- buildings
STYLES = {
    # wall, wall_dark, roof, roof_light, roof_dark, accent, roof type
    "a-block": ("cream", "grey-light", "grey-light", "white", "grey", "blue", "flat"),
    "b-block": ("grey-light", "grey", "cream", "white", "grey-light", "plum", "flat"),
    "c-block": ("white", "cream", "grey-light", "white", "grey", "red-dark", "flat"),
    "d-block": ("white", "cream", "grey-light", "white", "grey", "blue-dark", "flat"),
    "e-block": ("white", "grey-light", "cream", "white", "grey-light", "sky", "flat"),
    "pg-block": ("sand-light", "sand", "cream", "white", "grey-light", "brown-dark", "flat"),
    "peb": ("cream", "grey-light", "cream", "white", "grey-light", "grey", "metal"),
    "B18": ("cream", "grey-light", "sky-pale", "white", "sky", "blue", "metal"),
    "thatibellam": ("sky-pale", "sky", "cream", "white", "grey-light", "red", "flat"),
    "siniti": ("cream", "sand-light", "grey-light", "white", "grey", "purple", "flat"),
    "sac": ("sky-pale", "sky", "red", "coral", "red-dark", "blue", "tile"),
    "sports-complex": ("white", "cream", "cream", "white", "grey-light", "red", "metal"),
    "vjim": ("sand-light", "sand", "cream", "white", "grey-light", "orange", "flat"),
    "B03": ("cream", "grey-light", "grey-light", "white", "grey", "mint", "flat"),
    "B17": ("cream", "grey-light", "coral", "pink-pale", "red", "red-dark", "tile"),
    "B20": ("white", "cream", "grey-light", "white", "grey", "mint", "flat"),
    "B21": ("grey-light", "grey", "red", "coral", "red-dark", "grey", "tile"),
    "B15": ("grey-light", "grey", "grey", "grey-light", "asphalt", "yellow", "flat"),
    "B02": ("cream", "grey-light", "red", "coral", "red-dark", "grey", "tile"),
}
CANOPY_STYLE = ("grey", "grey", "white", "white", "grey-light", "grey", "metal")
SOLAR = {"d-block": 0.45, "e-block": 0.22, "a-block": 0.25, "b-block": 0.2, "c-block": 0.3,
         "pg-block": 0.2, "siniti": 0.3, "B20": 0.25, "vjim": 0.0}


class Bld:
    pass


BLDS = []
for g, p in FINAL:
    if p["kind"] not in ("building", "canopy"):
        continue
    b = Bld()
    b.id, b.p, b.kind = p["id"], p, p["kind"]
    b.poly = g.buffer(0)
    b.levels = max(1, int(p.get("levels") or 1)) if b.kind == "building" else 0
    b.h = b.levels * LEVEL_PX if b.kind == "building" else 4
    b.style = CANOPY_STYLE if b.kind == "canopy" else STYLES.get(b.id, ("cream", "grey-light", "grey-light", "white", "grey", "grey", "flat"))
    b.location = p.get("location")
    b.label = p.get("label")
    BLDS.append(b)
# E Block's footprint is a synthetic rectangle that spills onto Hanuman Marg: clip it
_hm = unary_union([ln.buffer(w / 2 + 2) for ln, w, inside, p in ROADS if p.get("name") == "Hanuman Marg"])
for b in BLDS:
    if b.p.get("style") in ("house", "shop"):
        _md = unary_union([ln.buffer(w / 2 + 3) for ln, w, inside, p in ROADS if p.get("highway") == "primary"])
        cl = b.poly.difference(_md)
        if cl.geom_type != "Polygon":
            cl = max(cl.geoms, key=lambda q: q.area)
        b.poly = cl.buffer(0)
        if b.p.get("style") == "shop":
            b.h = 10
    if b.id == "e-block":
        cl = b.poly.difference(_hm)
        if cl.geom_type != "Polygon":
            cl = max(cl.geoms, key=lambda q: q.area)
        b.poly = cl.buffer(0)
# generic neighbourhood north of Medak Road (unlabelled, not tappable)
def _neighbourhood():
    rng = np.random.default_rng(99)
    prim = [ln for ln, w, i, p in ROADS if p.get("highway") == "primary"]
    roadbuf = unary_union([ln.buffer(w / 2 + 5) for ln, w, i, p in ROADS])
    taken = unary_union([b.poly.buffer(26 if b.p.get("style") in ("house", "shop") else 8) for b in BLDS])
    styles = [("cream", "sand-light", "red", "coral", "red-dark", "brown", "tile"),
              ("sky-pale", "sky", "grey-light", "white", "grey", "blue", "flat"),
              ("lime-pale", "grass-light", "coral", "pink-pale", "red", "green", "flat"),
              ("lilac", "purple", "cream", "white", "grey-light", "plum", "flat"),
              ("sand-light", "sand", "orange", "yellow", "tan", "brown-dark", "tile"),
              ("white", "cream", "red-dark", "red", "brown-dark", "sky", "tile")]
    out = []
    for gy in range(4, 200, 26):
        for gx in range(6, W - 20, 30):
            x = gx + rng.integers(-4, 5)
            y = gy + rng.integers(-3, 4)
            w_, h_ = int(rng.integers(14, 24)), int(rng.integers(10, 15))
            r = box(x, y, x + w_, y + h_)
            # only north of Medak Road
            vl = LineString([(x + w_ / 2, 0), (x + w_ / 2, H)])
            ys = [min(q[1] for q in ln.intersection(vl).coords) for ln in prim if not ln.intersection(vl).is_empty]
            if not ys or y + h_ + 16 > min(ys):
                continue
            if r.intersects(roadbuf) or r.intersects(taken) or r.intersects(BOUNDARY.buffer(12)):
                continue
            if rng.random() < 0.25:
                continue
            b = Bld()
            b.id = f"N{len(out) + 1:02d}"
            b.p = {"id": b.id, "kind": "building", "style": "nhouse", "placeholder": False}
            b.kind = "building"
            b.poly = r
            b.levels = int(rng.integers(1, 3))
            b.h = b.levels * LEVEL_PX
            b.style = styles[int(rng.integers(len(styles)))]
            b.location, b.label = None, None
            out.append(b)
            taken = taken.union(r.buffer(8))
    return out


NEIGH = _neighbourhood()
BLDS += NEIGH
FOOT_UNION = unary_union([b.poly for b in BLDS])

# --------------------------------------------------------------------------- walk graph


class Graph:
    def __init__(self):
        self.nodes = []
        self.key = {}
        self.adj = {}

    def node(self, x, y):
        k = (round(x * 2), round(y * 2))
        if k in self.key:
            return self.key[k]
        i = len(self.nodes)
        self.nodes.append((float(x), float(y)))
        self.key[k] = i
        self.adj[i] = set()
        return i

    def edge(self, a, b):
        if a != b:
            self.adj[a].add(b)
            self.adj[b].add(a)

    def add_line(self, coords, maxlen=20.0):
        prev = self.node(*coords[0])
        for (x0, y0), (x1, y1) in zip(coords[:-1], coords[1:]):
            L = math.hypot(x1 - x0, y1 - y0)
            n = max(1, math.ceil(L / maxlen))
            for k in range(1, n + 1):
                t = k / n
                cur = self.node(x0 + (x1 - x0) * t, y0 + (y1 - y0) * t)
                self.edge(prev, cur)
                prev = cur
        return prev

    def edges(self):
        return sorted({(min(a, b), max(a, b)) for a in self.adj for b in self.adj[a]})

    def nearest_on_edges(self, pt):
        P = np.array(self.nodes)
        E = np.array(self.edges())
        A, B = P[E[:, 0]], P[E[:, 1]]
        d = B - A
        L2 = np.maximum((d * d).sum(1), 1e-9)
        t = np.clip(((np.array(pt) - A) * d).sum(1) / L2, 0, 1)
        Q = A + d * t[:, None]
        dist = np.hypot(*(Q - np.array(pt)).T)
        i = int(np.argmin(dist))
        return E[i], tuple(Q[i]), float(dist[i]), float(t[i])

    def nearest_clear(self, pt, blocker, hidden=None):
        """Nearest graph point whose straight connector from pt avoids blocker."""
        P = np.array(self.nodes)
        E = np.array(self.edges())
        A, B = P[E[:, 0]], P[E[:, 1]]
        d = B - A
        L2 = np.maximum((d * d).sum(1), 1e-9)
        t = np.clip(((np.array(pt) - A) * d).sum(1) / L2, 0, 1)
        Q = A + d * t[:, None]
        dist = np.hypot(*(Q - np.array(pt)).T)
        for i in np.argsort(dist)[:80]:
            q = tuple(Q[i])
            if hidden is not None:
                xi, yi = int(q[0]), int(q[1])
                if 0 <= xi < W and 0 <= yi < H and hidden[yi, xi]:
                    continue
            if dist[i] < 0.5 or not LineString([pt, q]).intersects(blocker):
                return q, float(dist[i])
        return None, None

    def insert(self, pt):
        (a, b), q, _, t = self.nearest_on_edges(pt)
        pa, pb = self.nodes[a], self.nodes[b]
        if math.dist(q, pa) < 2:
            return a
        if math.dist(q, pb) < 2:
            return b
        n = self.node(*q)
        self.adj[a].discard(b)
        self.adj[b].discard(a)
        self.edge(a, n)
        self.edge(n, b)
        return n

    def dist_from(self, s):
        D = {s: 0.0}
        pq = [(0.0, s)]
        while pq:
            d, u = heapq.heappop(pq)
            if d > D.get(u, 1e18):
                continue
            for v in self.adj[u]:
                nd = d + math.dist(self.nodes[u], self.nodes[v])
                if nd < D.get(v, 1e18):
                    D[v] = nd
                    heapq.heappush(pq, (nd, v))
        return D


def build_graph():
    region = BOUNDARY.buffer(4).union(GATE.buffer(40))
    lines = []
    for ln, w, inside, p in ROADS:
        lines += lines_of(ln.intersection(region))
    for g, p in PATHS:
        lines += lines_of(g.intersection(region))
    merged = unary_union(lines)
    segs = lines_of(merged)
    # snap dangling endpoints within ~2 m (4 px) to other lines
    cnt = {}
    for s in segs:
        for q in (s.coords[0], s.coords[-1]):
            k = (round(q[0], 1), round(q[1], 1))
            cnt[k] = cnt.get(k, 0) + 1
    extra = []
    for i, s in enumerate(segs):
        for q in (s.coords[0], s.coords[-1]):
            if cnt[(round(q[0], 1), round(q[1], 1))] != 1:
                continue
            P = Point(q)
            best = None
            for j, o in enumerate(segs):
                if j == i:
                    continue
                d = o.distance(P)
                if 0.01 < d < 4.5 and (best is None or d < best[0]):
                    best = (d, o)
            if best:
                _, np_ = nearest_points(P, best[1])
                extra.append(LineString([q, (np_.x, np_.y)]))
    if extra:
        log(f"graph: snapped {len(extra)} dangling endpoints")
        segs = lines_of(unary_union(segs + extra))
    G = Graph()
    for s in segs:
        G.add_line(list(s.coords))
    return G


# --------------------------------------------------------------------------- doors


def door_candidates(b):
    poly = b.poly
    ext = poly.exterior
    coords = list(ext.coords)
    out = []
    for (x0, y0), (x1, y1) in zip(coords[:-1], coords[1:]):
        L = math.hypot(x1 - x0, y1 - y0)
        if L < 8:
            continue
        ux, uy = (x1 - x0) / L, (y1 - y0) / L
        nx, ny = uy, -ux
        mid = ((x0 + x1) / 2, (y0 + y1) / 2)
        if poly.contains(Point(mid[0] + nx * 1.5, mid[1] + ny * 1.5)):
            nx, ny = -nx, -ny
        side = "S" if ny > 0.6 else ("N" if ny < -0.6 else ("E" if nx > 0 else "W"))
        n = int((L - 8) // 3) + 1
        for k in range(n):
            s = 4 + k * 3 + ((L - 8) - (n - 1) * 3) / 2
            bx, by = x0 + ux * s, y0 + uy * s
            off = 3 if side != "N" else b.h + 4
            out.append(dict(side=side, base=(bx, by), pt=(bx + nx * off, by + ny * off),
                            normal=(nx, ny), center_off=abs(s - L / 2)))
    return out


PENALTY = {"S": 0, "E": 30, "W": 30, "N": 90}


def choose_door(b, G, foot_shrunk, other_sil=None):
    best = None

    def in_sil(x, y):
        xi, yi = int(round(x)), int(round(y))
        return other_sil is not None and 0 <= xi < W and 0 <= yi < H and other_sil[yi, xi]
    for cand in door_candidates(b):
        pt = cand["pt"]
        if not (0 <= pt[0] < W and 0 <= pt[1] < H):
            continue
        if foot_shrunk.contains(Point(pt)) or in_sil(*pt):
            continue
        q, d = G.nearest_clear(pt, foot_shrunk)
        if q is None:
            continue
        hidden = sum(in_sil(pt[0] + (q[0] - pt[0]) * t / 20, pt[1] + (q[1] - pt[1]) * t / 20) for t in range(21))
        conn = LineString([pt, q]) if d > 0.5 else None
        if conn is not None and conn.intersects(foot_shrunk):
            continue
        if cand["side"] == "N":
            # the north walk must also stay clear of the roof band
            pass
        score = d + PENALTY[cand["side"]] + 0.3 * cand["center_off"] + 4 * hidden
        if best is None or score < best[0]:
            best = (score, cand, q, d)
    if best is None and other_sil is not None:
        log(f"  door {b.id}: every side is behind another building; ignoring occlusion")
        return choose_door(b, G, foot_shrunk, None)
    if best is None:
        raise SystemExit(f"FAIL: no valid door for {b.id}")
    return best[1]


# --------------------------------------------------------------------------- building sprites


def render_building(b):
    st = dict(zip(("wall", "wall_dark", "roof", "roof_light", "roof_dark", "accent", "type"), b.style))
    minx, miny, maxx, maxy = b.poly.bounds
    ox, oy = int(math.floor(minx)) - 2, int(math.floor(miny)) - b.h - 3
    w = int(math.ceil(maxx)) + 3 - ox
    hh = int(math.ceil(maxy)) + 5 - oy
    F = raster(b.poly, w, hh, ox, oy)
    outer = raster(Polygon(b.poly.exterior), w, hh, ox, oy)
    R = shift(F, 0, -b.h)
    Bd = F.copy()
    for k in range(1, b.h + 1):
        Bd |= shift(F, 0, -k)
    Wm = Bd & ~R
    # courtyard floor = inside the swept outer outline but not body
    So = outer.copy()
    for k in range(1, b.h + 1):
        So |= shift(outer, 0, -k)
    court = So & ~Bd
    S = Bd | court
    img = np.full((hh, w), T, np.uint8)
    rng = np.random.default_rng(zlib.crc32(b.id.encode()))
    yy, xx = np.mgrid[0:hh, 0:w]

    # --- roof
    img[R] = c(st["roof"])
    if st["type"] in ("metal", "tile"):
        mrr = b.poly.minimum_rotated_rectangle
        cs = list(mrr.exterior.coords)
        e1 = (cs[1][0] - cs[0][0], cs[1][1] - cs[0][1])
        e2 = (cs[2][0] - cs[1][0], cs[2][1] - cs[1][1])
        long_ = e1 if math.hypot(*e1) >= math.hypot(*e2) else e2
        Ll = math.hypot(*long_)
        nx, ny = -long_[1] / Ll, long_[0] / Ll
        if st["type"] == "tile":
            nx, ny = 0.0, 1.0
        v = (xx + ox) * nx + (yy + oy + b.h) * ny
        per = 3 if st["type"] == "metal" else 2
        stripe = (np.floor(v).astype(int) % per) == 0
        img[R & stripe] = c(st["roof_dark"])
        if st["type"] == "metal":
            # ridge highlight along the middle of the long axis
            cen = b.poly.centroid
            vc = cen.x * nx + (cen.y) * ny
            ridge = np.abs(v - vc) < 0.8
            img[R & ridge] = c(st["roof_light"])
    redge = R & ~erode(R, 1, cross=True)
    img[redge] = c(st["roof_light"])
    if st["type"] == "flat" and b.kind == "building":
        inner = R & ~redge
        sh = inner & (shift(redge, 0, 1) | shift(redge, 1, 0))
        img[sh] = c(st["roof_dark"])
    # --- roof details
    if b.kind == "building" and st["type"] == "flat":
        free = erode(R, 3) & ~court
        area = int(free.sum())

        def place(pw, ph, tries=60, zone=None):
            for _ in range(tries):
                ys, xs = np.nonzero(free if zone is None else free & zone)
                if len(xs) == 0:
                    return None
                i = rng.integers(len(xs))
                x0, y0 = xs[i], ys[i]
                if y0 + ph + 1 >= hh or x0 + pw + 1 >= w:
                    continue
                if free[y0:y0 + ph + 1, x0:x0 + pw + 1].all():
                    free[max(0, y0 - 1):y0 + ph + 2, max(0, x0 - 1):x0 + pw + 2] = False
                    return x0, y0
            return None

        # solar panel rows (rows of 3 px with gaps), in the southern part of the roof
        frac = SOLAR.get(b.id, 0)
        if frac:
            rys = np.nonzero(R.any(1))[0]
            ytop = int(rys[0] + (rys[-1] - rys[0]) * (1 - frac))
            for y0 in range(ytop, rys[-1] - 4, 5):
                row = free[y0] & free[y0 + 1] & free[y0 + 2] & free[y0 + 3]
                xs = np.nonzero(row)[0]
                if len(xs) == 0:
                    continue
                runs = np.split(xs, np.nonzero(np.diff(xs) > 1)[0] + 1)
                for r in runs:
                    if len(r) < 8:
                        continue
                    a0, a1 = r[0] + 1, r[-1] - 1
                    a1 = a0 + min(a1 - a0, 34)
                    for x in range(a0, a1 + 1):
                        k = (x - a0) % 6
                        if k == 5:
                            continue
                        img[y0, x] = c("sky") if k != 0 else c("blue")
                        img[y0 + 1, x] = c("blue-dark") if k else c("blue")
                        img[y0 + 2, x] = c("blue-dark")
                        img[y0 + 3, x] = c(st["roof_dark"])
                    free[y0 - 1:y0 + 4, a0 - 1:a1 + 2] = False
        if b.id == "vjim":
            ring = edge4(erode(R, 9)) & free
            img[ring] = c(st["roof_light"])
            img[shift(ring, 0, 1) & free & ~ring] = c(st["roof_dark"])
            free &= ~dilate(ring, 2)
        if b.id == "e-block":
            seam = free & ((((yy + oy) % 14) == 0) | (((xx + ox) % 22) == 0))
            img[seam & ((xx + yy) % 2 == 0)] = c(st["roof_dark"])
        # stair rooms (mumty)

        for _ in range(1 if area < 1500 else 2):
            p = place(8, 7)
            if p:
                x0, y0 = p
                img[y0:y0 + 4, x0:x0 + 8] = c(st["roof_light"])
                img[y0 + 1:y0 + 4, x0 + 1:x0 + 7] = c(st["roof"])
                img[y0 + 4:y0 + 7, x0:x0 + 8] = c(st["wall"])
                img[y0 + 5:y0 + 7, x0 + 3:x0 + 5] = c("brown-dark")
                img[y0 + 4, x0:x0 + 8] = c(st["wall_dark"])
                img[y0 + 7, x0 + 1:x0 + 9] = c(st["roof_dark"])
                img[y0:y0 + 7, x0 + 8] = c(st["roof_dark"])
                # outline
                img[y0 - 1, x0:x0 + 8] = c("ink")
                img[y0:y0 + 7, x0 - 1] = c("ink")
                img[y0:y0 + 7, x0 + 8] = c("ink")
                img[y0 + 7, x0:x0 + 8] = c("ink")
        # water tanks
        nt = 2 + min(4, area // 900)
        for _ in range(nt):
            p = place(4, 5)
            if p:
                x0, y0 = p
                tank = SP.art([".kk.", "kppk", "kgpk", "kppk", ".kk."], SP.K)
                paste(img, tank, x0, y0)
                img[y0 + 5, x0 + 1:x0 + 4] = c(st["roof_dark"])
        # AC units
        for _ in range(2 + min(6, area // 500)):
            p = place(3, 3)
            if p:
                x0, y0 = p
                img[y0, x0:x0 + 3] = c("white")
                img[y0 + 1, x0:x0 + 3] = c("grey-light")
                img[y0 + 1, x0 + 1] = c("grey")
                img[y0 + 2, x0:x0 + 3] = c("grey")
    # --- courtyard
    if court.any():
        img[court] = c("grey-light")
        img[court & ((xx + yy) % 4 == 0)] = c("cream")
        cshadow = court & (shift(Bd, 0, 1) | shift(Bd, 1, 0) | shift(Bd, 0, 2))
        shade_mask = cshadow & ((xx + yy) % 2 == 0)
        img[shade_mask] = c("grey")
    # --- walls
    if b.kind == "canopy":
        # posts only, see-through elsewhere
        posts = np.zeros_like(Wm)
        cols = np.nonzero(Wm.any(0))[0]
        for x in cols:
            col = np.nonzero(Wm[:, x])[0]
            if len(col) and ((x - cols[0]) % 7 == 1 or x == cols[-1] - 1):
                posts[col, x] = True
        img[posts] = c("grey")
        Wm2 = Wm & ~posts
        img[Wm2] = T
        # thin roof thickness: first wall row under roof
        rim = Wm & shift(R, 0, 1)
        img[rim] = c("grey-light")
        S = S & ~(Wm2 & ~rim)
    else:
        img[Wm] = c(st["wall"])
        # height above ground per wall pixel
        D = np.full((hh, w), -1, int)
        for x in range(w):
            e = None
            for y in range(hh - 1, -1, -1):
                if F[y, x] and (y + 1 >= hh or not F[y + 1, x]):
                    e = y
                if Wm[y, x] and e is not None:
                    D[y, x] = e - y
        r = D % LEVEL_PX
        f = D // LEVEL_PX
        wallpx = Wm & (D >= 0)
        img[wallpx & (r == 0) & (f > 0)] = c(st["wall_dark"])
        img[wallpx & (D == 0)] = c(st["accent"])
        colpat = ((xx + ox) % 4)
        band = wallpx & (r >= 2) & (r <= 4) & (f < b.levels)
        # only where the whole 3-row band fits on this wall column
        full = band & (((r == 2) & shift(band, 0, 1) & shift(band, 0, 2)) |
                       ((r == 3) & shift(band, 0, 1) & shift(band, 0, -1)) |
                       ((r == 4) & shift(band, 0, -1) & shift(band, 0, -2)))
        # need a little run horizontally too
        full &= shift(full, 1, 0) | shift(full, -1, 0)
        win = full & (colpat != 0)
        img[win] = c("blue-dark")
        img[win & (r == 4)] = c("sky")
        img[win & (r == 4) & (colpat == 1)] = c("sky-pale")
        img[win & (r == 2)] = c("blue")
        img[full & (colpat == 0)] = c(st["wall"])
        # window sill line
        sill = wallpx & (r == 1) & shift(full, 0, 1)
        img[sill] = c(st["wall_dark"])
        # overhang shadow under the roof edge
        img[Wm & shift(R, 0, 1)] = c(st["wall_dark"])
        style = b.p.get("style")
        if style == "house" or (style == "nhouse" and b.levels >= 2):
            # first-floor balcony: slab, railing with potted plants
            slab = wallpx & (D == LEVEL_PX)
            img[slab] = c("white")
            img[shift(slab, 0, 1) & wallpx] = c("pink")
            rail = wallpx & (D == LEVEL_PX + 2)
            img[rail] = c("white")
            img[rail & (colpat % 2 == 0)] = c("cream")
            img[wallpx & (D == LEVEL_PX + 1) & (colpat == 0)] = c("white")
            plant = wallpx & (D == LEVEL_PX + 3) & (((xx + ox) % 5) == 2)
            img[plant] = c("grass")
            img[shift(plant, 1, 0) & wallpx & (D == LEVEL_PX + 3)] = c("green")
            img[shift(plant, 0, -1) & wallpx] = c("grass-light")
            # arched pastel windows on the ground floor
            img[wallpx & (D >= 2) & (D <= 4) & (colpat != 0) & (((xx + ox) // 4) % 3 == 1)] = c("sky")
            # water tank + parapet details on the roof
            ys_, xs_ = np.nonzero(erode(R, 2))
            if len(xs_):
                tx_, ty_ = int(xs_.mean()) + 6, int(ys_.min())
                paste(img, SP.art([".kk.", "kppk", "kgpk", "kppk", ".kk."], SP.K), tx_, ty_)
        elif style == "shop":
            top = Wm & shift(R, 0, 1)
            aw = wallpx & (D >= b.h - 3)
            img[aw] = np.where(((xx + ox) // 2) % 2 == 0, c("red"), c("white"))[aw]
            img[wallpx & (D == b.h - 4) & ((xx + ox) % 2 == 0)] = c("red-dark")
            img[wallpx & (D == b.h - 4) & ((xx + ox) % 2 == 1)] = T
            opening = wallpx & (D >= 2) & (D <= b.h - 5)
            img[opening] = c("brown-dark")
            snack = opening & (D == 2)
            cols_ = ["yellow", "orange", "red", "lime-pale", "pink-pale"]
            for k_, cn in enumerate(cols_):
                img[snack & (((xx + ox) % 5) == k_)] = c(cn)
            img[wallpx & (D <= 1)] = c("tan")
            img[wallpx & (D == 1)] = c("sand")
        # door / porch on the south wall
        if getattr(b, "door", None) and b.door["side"] == "S":
            bx, by = b.door["base"]
            dx = int(round(bx)) - ox
            col = np.nonzero(Wm[:, dx])[0]
            if len(col):
                base = col.max()
                if b.id == "b-block":
                    # dark granite entrance block, two floors tall
                    for y in range(base - 13, base + 1):
                        for x in range(dx - 5, dx + 6):
                            if 0 <= y and Wm[y, x]:
                                img[y, x] = c("plum") if abs(x - dx) < 5 else c("ink")
                    img[base - 13, dx - 5:dx + 6] = c("ink")
                    img[base - 11:base - 9, dx - 3:dx + 4] = c("grey-light")  # name plate
                elif b.id == "pg-block":
                    for y in range(base - 7, base + 1):
                        for x in (dx - 4, dx + 4):
                            img[y, x] = c("ink")
                    img[base - 8, dx - 5:dx + 6] = c("plum")
                    img[base - 7, dx - 5:dx + 6] = c("ink")
                img[base - 4:base + 1, dx - 1:dx + 2] = c("brown-dark")
                img[base - 4, dx - 1:dx + 2] = c("ink")
                img[base - 5, dx - 2:dx + 3] = c(st["accent"])
                img[base - 3, dx + 1] = c("tan")
                # step / porch on the ground in front
                img[base + 1, dx - 3:dx + 4] = c("grey-light")
                img[base + 2, dx - 3:dx + 4] = c("grey")
                S = S.copy()
                S[base + 1:base + 3, dx - 3:dx + 4] = True
    # --- outline
    out = edge4(S)
    img[out & (img != T)] = c("ink")
    if b.kind == "building":
        # 1px lighter parapet just inside the outline on the roof
        pass
    b.img, b.ox, b.oy, b.S, b.F, b.R = img, ox, oy, S, F, R
    b.Wm = Wm if b.kind == "building" else np.zeros_like(Wm)
    b.depthY = int(np.nonzero(F.any(1))[0].max()) + oy


# --------------------------------------------------------------------------- helpers


def mask_contour(mask, ox=0, oy=0, maxpts=40):
    m = (mask.astype(np.uint8)) * 255
    cs, _ = cv2.findContours(m, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_NONE)
    if not cs:
        return []
    cnt = max(cs, key=cv2.contourArea)
    eps = 0.5
    while True:
        ap = cv2.approxPolyDP(cnt, eps, True)
        if len(ap) <= maxpts:
            break
        eps *= 1.3
    return [[int(p[0][0] + ox), int(p[0][1] + oy)] for p in ap]


def rect_mask(x0, y0, x1, y1):
    m = np.zeros((H, W), bool)
    m[max(0, y0):max(0, y1), max(0, x0):max(0, x1)] = True
    return m


def rect_free(mask, x0, y0, x1, y1):
    if x0 < 0 or y0 < 0 or x1 > W or y1 > H:
        return False
    return not mask[y0:y1, x0:x1].any()


def mrr_frame(poly):
    """centre, long unit axis, short unit axis, half long, half short."""
    cs = list(poly.minimum_rotated_rectangle.exterior.coords)
    e1 = np.subtract(cs[1], cs[0])
    e2 = np.subtract(cs[2], cs[1])
    if np.hypot(*e1) < np.hypot(*e2):
        e1, e2 = e2, e1
    cen = np.mean(cs[:4], axis=0)
    l1, l2 = np.hypot(*e1), np.hypot(*e2)
    return cen, e1 / l1, e2 / l2, l1 / 2, l2 / 2


def frame_pt(fr, u, v):
    cen, a, b, hl, hs = fr
    p = cen + a * u * hl + b * v * hs
    return (float(p[0]), float(p[1]))


def frame_rect(fr, u0, v0, u1, v1):
    return [frame_pt(fr, u0, v0), frame_pt(fr, u1, v0), frame_pt(fr, u1, v1), frame_pt(fr, u0, v1), frame_pt(fr, u0, v0)]


def frame_circle(fr, u, v, r_px, n=28):
    cen = frame_pt(fr, u, v)
    return [(cen[0] + r_px * math.cos(t * 2 * math.pi / n), cen[1] + r_px * math.sin(t * 2 * math.pi / n)) for t in range(n + 1)]


# --------------------------------------------------------------------------- main


def main():
    OUT_PUBLIC.mkdir(parents=True, exist_ok=True)
    OUT_DBG.mkdir(parents=True, exist_ok=True)
    log(f"map {W}x{H} px at 0.5 m/px; {len(BLDS)} buildings/canopies")

    # ---- overlaps of footprints
    n_ov = 0
    for i, a in enumerate(BLDS):
        for b in BLDS[i + 1:]:
            ar = a.poly.intersection(b.poly).area
            if ar > 1.0:
                n_ov += 1
                log(f"  OVERLAP footprint {a.id} x {b.id}: {ar / 4:.1f} m2")
    log(f"footprint overlaps: {n_ov}")

    # ---- graph
    G = build_graph()
    foot_shrunk = FOOT_UNION.buffer(-0.6)
    # outside the gate: zebra crossing over Medak Road + footpath along its north side
    prim = [(ln, w) for ln, w, i, p in ROADS if p.get("highway") == "primary"]
    vline = LineString([(GATE.x, GATE.y), (GATE.x, 0)])
    hits = []
    for ln, w in prim:
        x_ = ln.intersection(vline)
        if not x_.is_empty:
            hits.append((min(q[1] for q in x_.coords), ln, w))
    _, nln, nw = min(hits)
    side = None
    for off in (nw / 2 + 5, -(nw / 2 + 5)):
        oc = nln.offset_curve(off)
        xx_ = oc.intersection(vline)
        if not xx_.is_empty and min(q[1] for q in xx_.coords) < _:
            side = oc
            break
    outs = [b for b in BLDS if b.p.get("style") in ("house", "shop")]
    xs_ = [GATE.x] + [b.poly.bounds[0] for b in outs] + [b.poly.bounds[2] for b in outs]
    walk = side.intersection(box(min(xs_) - 6, 0, max(xs_) + 6, GATE.y))
    walk = max(lines_of(walk), key=lambda l: l.length)
    cp = walk.intersection(vline)
    cp = (cp.x, cp.y) if cp.geom_type == "Point" else list(cp.coords)[0]
    OUT_Y = cp[1]
    from shapely.ops import substring
    t = walk.project(Point(cp))
    g_top = G.insert((GATE.x, GATE.y))
    G.add_line([G.nodes[g_top], cp])
    for part in (substring(walk, 0, t), substring(walk, t, walk.length)):
        if part.length > 1:
            G.add_line(list(part.coords))
    extra_paths = [walk]
    CROSSING = LineString([(GATE.x, GATE.y - 4), (GATE.x, OUT_Y)])
    # spawn: just inside the gate
    gate_node = G.insert((GATE.x, GATE.y + 6))
    spawn = G.insert((GATE.x, GATE.y + 26))
    D = G.dist_from(spawn)
    keep = set(D)
    dropped = len(G.nodes) - len(keep)
    log(f"graph: dropped {dropped} nodes in fragments not connected to the gate")

    def compact():
        nonlocal spawn, gate_node
        idx = {}
        nodes = []
        for i, p in enumerate(G.nodes):
            if i in keep:
                idx[i] = len(nodes)
                nodes.append(p)
        adj = {idx[i]: {idx[j] for j in G.adj[i] if j in keep} for i in G.adj if i in keep}
        G.nodes, G.adj = nodes, adj
        G.key = {(round(x * 2), round(y * 2)): i for i, (x, y) in enumerate(nodes)}
        spawn, gate_node = idx[spawn], idx[gate_node]

    compact()
    connectors = list(extra_paths)  # LineStrings drawn as footpaths

    def connect(pt, hidden=None):
        q, d = G.nearest_clear(pt, foot_shrunk, hidden)
        n_on = G.insert(q)
        dn = G.node(*pt)
        if dn != n_on:
            G.add_line([pt, G.nodes[n_on]])
            connectors.append(LineString([pt, G.nodes[n_on]]))
        return dn

    # doors (pre-render sprites without doors to know every roof/wall silhouette)
    sil = {}
    for b in BLDS:
        b.door = None
        render_building(b)
        m_ = np.zeros((H, W), bool)
        h_, w_ = b.S.shape
        x0, y0 = b.ox, b.oy
        gx0, gy0, gx1, gy1 = max(0, x0), max(0, y0), min(W, x0 + w_), min(H, y0 + h_)
        m_[gy0:gy1, gx0:gx1] = b.S[gy0 - y0:gy1 - y0, gx0 - x0:gx1 - x0]
        sil[b.id] = m_
    for b in BLDS:
        if not b.location:
            continue
        other = np.zeros((H, W), bool)
        for o in BLDS:
            if o is not b:
                other |= sil[o.id]
        cand = choose_door(b, G, foot_shrunk, dilate(other, 2))
        b.door = cand
        b.door_node = connect(cand["pt"])
        log(f"door {b.id:15s} side {cand['side']} at ({cand['pt'][0]:.0f},{cand['pt'][1]:.0f})")

    # ---- building sprites, front to back, cropping occluded pixels
    for b in BLDS:
        render_building(b)
    occ = np.zeros((H, W), bool)
    owner = np.full((H, W), -1, int)
    for k, b in sorted(enumerate(BLDS), key=lambda kb: -kb[1].depthY):
        h_, w_ = b.S.shape
        x0, y0 = b.ox, b.oy
        gx0, gy0, gx1, gy1 = max(0, x0), max(0, y0), min(W, x0 + w_), min(H, y0 + h_)
        sub = occ[gy0:gy1, gx0:gx1]
        loc = b.S[gy0 - y0:gy1 - y0, gx0 - x0:gx1 - x0]
        hidden = loc & sub
        if hidden.any():
            L = b.img[gy0 - y0:gy1 - y0, gx0 - x0:gx1 - x0]
            L[hidden] = T
            loc &= ~hidden
            # re-outline the newly cut edge
        vis = np.zeros_like(b.S)
        vis[gy0 - y0:gy1 - y0, gx0 - x0:gx1 - x0] = loc
        b.vis_full = np.zeros((H, W), bool)
        b.vis_full[gy0:gy1, gx0:gx1] = loc
        vis &= b.img != T
        b.vis = vis
        occ[gy0:gy1, gx0:gx1] |= loc
        owner[gy0:gy1, gx0:gx1][loc] = k
    BUILD_SIL = occ

    # ---- geometry masks for ground and validation
    road_inside = [r for r in ROADS]
    road_polys = unary_union([ln.buffer(w / 2, cap_style=2 if not inside else 1) for ln, w, inside, p in road_inside])
    ROAD = raster(road_polys, W, H)
    KERB = dilate(ROAD, 1, cross=True) & ~ROAD
    side_ln = [ln.buffer(w / 2 + 5) for ln, w, inside, p in ROADS if p.get("sidewalk") == "both"]
    SIDEWALK = raster(unary_union(side_ln).difference(FOOT_UNION.buffer(10)), W, H) & ~ROAD & ~KERB if side_ln else np.zeros((H, W), bool)
    path_geom = unary_union([g.buffer(2.6) for g, p in PATHS] + [cn.buffer(2.2) for cn in connectors])
    PATH = raster(path_geom, W, H) & ~ROAD & ~KERB
    STEPS = raster(unary_union([g.buffer(2.6) for g, p in PATHS if p.get("highway") == "steps"]), W, H) & PATH
    courts = []
    pitch = None
    parking = []
    for g, p in OPEN:
        if g.geom_type != "Polygon":
            continue
        if p.get("leisure") == "pitch":
            if "Football" in (p.get("name") or ""):
                pitch = (g, p)
            else:
                courts.append((g, p))
        elif p.get("amenity") == "parking":
            parking.append((g, p))
    courts = [(g_, p_) for g_, p_ in courts if g_.intersection(FOOT_UNION).area <= 0.3 * g_.area]
    COURT = raster(unary_union([g for g, p in courts]), W, H)
    PITCH = raster(pitch[0], W, H)
    PARK = raster(unary_union([g for g, p in parking]), W, H) if parking else np.zeros((H, W), bool)
    walls = []
    for g, p in BARRIERS:
        if p.get("barrier") == "wall":
            walls += lines_of(g)
    WALL = raster_lines([list(l.coords) for l in walls], W, H, width=4) & ~dilate(ROAD, 2)

    # ---- fixed props: gate arch, canteen
    props = []  # dict(sprite, x(anchor), y(anchor), kind)
    PROP_FOOT = np.zeros((H, W), bool)
    PROP_BOX = np.zeros((H, W), bool)

    def add_prop(spr, ax, ay, kind=None, extra=None):
        d = dict(spr=spr, x=int(ax), y=int(ay), kind=kind or spr.kind)
        if extra:
            d.update(extra)
        props.append(d)
        x0, y0 = int(ax) - spr.ax, int(ay) - spr.ay
        PROP_BOX[max(0, y0):y0 + spr.h, max(0, x0):x0 + spr.w] |= True
        fx0, fy0, fx1, fy1 = spr.foot
        PROP_FOOT[max(0, int(ay) + fy0):int(ay) + fy1 + 1, max(0, int(ax) + fx0):int(ax) + fx1 + 1] = True
        return d

    # road direction at gate
    gate_road = min((ln for ln, w, i, p in ROADS), key=lambda l: l.distance(GATE))
    gw = [w for ln, w, i, p in ROADS if ln is gate_road][0]
    span = gw + 10
    arch, (pl, pr) = SP.gate_arch(span)
    gq = nearest_points(gate_road, GATE)[0]
    ax_, ay_ = int(round(gq.x)), int(round(gq.y)) + 4
    gate_prop = add_prop(arch, ax_, ay_, "gate")
    # pillar feet only
    PROP_FOOT[ay_ - 3:ay_ + 1, ax_ + pl - 3:ax_ + pl + 4] = True
    PROP_FOOT[ay_ - 3:ay_ + 1, ax_ + pr - 3:ax_ + pr + 4] = True
    gate_hit = [[ax_ - arch.ax, ay_ - arch.ay], [ax_ - arch.ax + arch.w, ay_ - arch.ay],
                [ax_ - arch.ax + arch.w, ay_ + 1], [ax_ - arch.ax, ay_ + 1]]

    # canteen kiosk: nearest free spot to the canteen point
    BLOCK = BUILD_SIL | ROAD | KERB | PATH | COURT | PITCH | WALL
    kio = SP.kiosk()
    umb = SP.umbrella()
    best = None
    for r in range(0, 60, 2):
        for t in range(0, 360, 15):
            x = int(CANTEEN.x + r * math.cos(math.radians(t)))
            y = int(CANTEEN.y + r * math.sin(math.radians(t)))
            # kiosk box + umbrellas to its right/below
            if rect_free(dilate(BLOCK, 1) if best is None and False else BLOCK, x - kio.ax - 2, y - kio.ay - 2, x - kio.ax + kio.w + 26, y + 16):
                best = (x, y)
                break
        if best:
            break
    if not best:
        raise SystemExit("FAIL: no canteen spot")
    kx, ky = best
    add_prop(kio, kx, ky, "kiosk")
    umbs = [(kx + 16, ky - 2), (kx + 6, ky + 13), (kx + 19, ky + 12)]
    for ux, uy in umbs:
        add_prop(umb, ux, uy, "umbrella")
    canteen_hit = [[kx - 12, ky - 16], [kx + 26, ky - 16], [kx + 26, ky + 16], [kx - 12, ky + 16]]
    best_c = None
    for cpt in ((kx + 30, ky + 6), (kx - 2, ky + 4), (kx - 14, ky), (kx + 8, ky - 18)):
        q, d = G.nearest_clear(cpt, foot_shrunk, BUILD_SIL)
        if q is not None and (best_c is None or d < best_c[0]):
            best_c = (d, cpt)
    canteen_door = connect(best_c[1], BUILD_SIL)

    # ground area entry
    pg = pitch[0]
    gl = MultiLineString([[G.nodes[a], G.nodes[b]] for a, b in G.edges()])
    pe, ge = nearest_points(pg.exterior, gl)
    ground_door = connect((pe.x, pe.y)) if pe.distance(ge) > 1 else G.insert((pe.x, pe.y))
    gate_door = gate_node

    # ---- reachability
    D = G.dist_from(spawn)
    targets = {b.location: b.door_node for b in BLDS if b.location}
    targets.update({"ground": ground_door, "canteen": canteen_door, "main-gate": gate_door})
    bad = []
    for loc, n in sorted(targets.items()):
        ok = n in D
        log(f"reach {loc:15s} node {n:4d} {'OK' if ok else 'UNREACHABLE'} {D.get(n, float('nan')) / 2:.0f} m")
        if not ok:
            bad.append(loc)
    if bad:
        raise SystemExit(f"FAIL: unreachable {bad}")

    # ---------------------------------------------------------------- ground
    rngG = np.random.default_rng(7)
    g = np.zeros((H, W), np.uint8)
    by = bayer(H, W)
    hn = hashnoise(H, W, 3)
    vn = value_noise(H, W, 24, 5)
    vn2 = value_noise(H, W, 9, 11)
    # outside: muted dry sand + scrub
    g[:] = c("sand-light")
    g[(by < 0.06 + 0.22 * vn)] = c("sand")
    g[(vn > 0.66) & (by < (vn - 0.62) * 2.0)] = c("lime-pale")
    g[(vn2 > 0.7) & (hn > 0.9)] = c("sand")
    g[(hn > 0.993)] = c("tan")
    # campus grass
    camp = CAMPUS_MASK
    grass = np.full((H, W), c("grass"), np.uint8)
    grass[by < 0.18 + 0.30 * vn] = c("grass-light")
    grass[(vn2 < 0.3) & (by < 0.35)] = c("green")
    tuft = (hn > 0.965)
    grass[tuft] = c("green")
    grass[(hn > 0.995)] = c("lime-pale")
    g[camp] = grass[camp]
    # bare earth zones (hand-placed from the satellite reading, map px)
    MY = int(NORTH_MARGIN_M * 2)  # hand-placed px polygons were drawn before the margin existed
    bare_polys = [
        translate(Polygon([(424, 765), (505, 752), (640, 785), (650, 905), (630, 1000), (560, 1000), (470, 930), (424, 905)]), 0, MY),
        translate(Polygon([(742, 330), (838, 318), (848, 560), (808, 785), (742, 785)]), 0, MY),
        translate(Polygon([(640, 778), (840, 790), (845, 1030), (650, 1030)]), 0, MY),
        translate(Polygon([(800, 1150), (880, 1150), (880, 1300), (800, 1300)]), 0, MY),
    ]
    BARE0 = raster(unary_union(bare_polys).intersection(BOUNDARY.buffer(-3)), W, H)
    din = cv2.distanceTransform(BARE0.astype(np.uint8), cv2.DIST_L2, 3)
    dout = cv2.distanceTransform((~BARE0).astype(np.uint8), cv2.DIST_L2, 3)
    sd = din - dout + (vn2 - 0.5) * 22 + (hn - 0.5) * 2.5
    BARE = (sd > 0) & CAMPUS_MASK & ~raster(BOUNDARY.buffer(-3).exterior.buffer(3), W, H)
    bare_col = np.full((H, W), c("sand"), np.uint8)
    bare_col[by < 0.22 + 0.25 * vn2] = c("sand-light")
    bare_col[(vn < 0.3) & (by < 0.18)] = c("tan")
    bare_col[hn > 0.98] = c("tan")
    # ragged edge between grass and earth
    BARE &= ~((~dilate(~BARE, 2)) & False)
    edge_rag = dilate(BARE, 2) & ~BARE & (hn > 0.5)
    g[BARE | (edge_rag & camp)] = bare_col[BARE | (edge_rag & camp)]
    # wood + parks
    for gg, p in GREEN:
        m = raster(gg, W, H) & camp
        if p.get("natural") == "wood":
            col = np.full((H, W), c("green"), np.uint8)
            col[by < 0.35 + 0.2 * vn2] = c("grass")
            col[hn > 0.97] = c("green-dark")
            g[m] = col[m]
        else:
            col = np.full((H, W), c("grass"), np.uint8)
            col[by < 0.55] = c("grass-light")
            col[(hn > 0.985)] = c("lime-pale")
            g[m] = col[m]
            # tidy hedge edge
            e = edge4(m) & ~ROAD
            g[e] = c("green")
    # parking surfaces: gravel with stall marks
    for gg, p in parking:
        m = raster(gg, W, H)
        col = np.full((H, W), c("grey-light"), np.uint8)
        col[by < 0.3] = c("cream")
        col[hn > 0.97] = c("grey")
        g[m] = col[m]
        fr = mrr_frame(gg)
        hl = fr[3]
        n = int(2 * hl / 6)
        lines = []
        for k in range(1, n):
            u = -1 + 2 * k / n
            lines.append(frame_rect(fr, u, -1, u, -0.78)[:2])
            lines.append(frame_rect(fr, u, 0.78, u, 1)[:2])
        lm = raster_lines(lines, W, H) & m
        g[lm] = c("white")
        g[edge4(m)] = c("grey")
    # football / cricket ground
    pm = PITCH
    col = np.full((H, W), c("tan"), np.uint8)
    col[by < 0.2 + 0.25 * vn2] = c("sand")
    col[(vn < 0.3) & (by < 0.12)] = c("grass-light")
    col[hn > 0.99] = c("brown")
    g[pm] = col[pm]
    fr = mrr_frame(pg)
    cen, a_, b_, hl, hs = fr
    fu, fv = 0.78, 0.72
    lines = [frame_rect(fr, -fu, -fv, fu, fv), frame_rect(fr, 0, -fv, 0, fv)[:2],
             frame_circle(fr, 0, 0, 16)]
    for s in (-1, 1):
        lines.append([frame_pt(fr, s * fu, -0.36), frame_pt(fr, s * (fu - 0.16), -0.36),
                      frame_pt(fr, s * (fu - 0.16), 0.36), frame_pt(fr, s * fu, 0.36)])
        lines.append([frame_pt(fr, s * fu, -0.16), frame_pt(fr, s * (fu - 0.06), -0.16),
                      frame_pt(fr, s * (fu - 0.06), 0.16), frame_pt(fr, s * fu, 0.16)])
    lm = raster_lines(lines, W, H) & pm
    g[lm] = c("white")
    # cricket pitch strip in the middle
    strip = raster(Polygon(frame_rect(fr, -0.12, -0.03, 0.12, 0.03)), W, H)
    g[strip] = c("sand-light")
    g[strip & edge4(strip)] = c("cream")
    # goal posts
    for s in (-1, 1):
        gp = raster_lines([[frame_pt(fr, s * fu, -0.06), frame_pt(fr, s * fu, 0.06)]], W, H, width=2)
        g[gp & pm] = c("white")
    g[edge4(pm)] = c("brown")
    # courts
    for gg, p in courts:
        if gg.intersection(FOOT_UNION).area > 0.3 * gg.area:
            continue
        m = raster(gg, W, H)
        sport = p.get("sport") or ("throwball" if "Throwball" in (p.get("name") or "") else "")
        fr = mrr_frame(gg)
        if sport == "basketball":
            base, line = "blue", "white"
        elif sport == "tennis":
            base, line = "green", "white"
        elif sport == "cricket":
            base, line = "grass-light", "white"
        elif sport == "volleyball":
            base, line = "coral", "white"
        else:
            base, line = "sand-light", "red"
        col = np.full((H, W), c(base), np.uint8)
        if base == "tan":
            col[by < 0.3] = c("sand")
        g[m] = col[m]
        g[edge4(m)] = c("mint" if base == "green" else ("blue-dark" if base == "blue" else "brown"))
        L = [frame_rect(fr, -0.88, -0.8, 0.88, 0.8)]
        if sport == "basketball":
            L.append(frame_rect(fr, 0, -0.8, 0, 0.8)[:2])
            L.append(frame_circle(fr, 0, 0, 3.5, 12))
            for s in (-1, 1):
                key = Polygon(frame_rect(fr, s * 0.88, -0.25, s * 0.6, 0.25))
                km = raster(key, W, H) & m
                g[km] = c("red")
                L.append(frame_rect(fr, s * 0.88, -0.25, s * 0.6, 0.25))
        elif sport == "tennis":
            cen_, a_u, a_v, hl_, hs_ = fr
            nu = max(1, int(round(hl_ * 2 / 38)))
            nv = max(1, int(round(hs_ * 2 / 34)))
            L = []
            for iu in range(nu):
                for iv in range(nv):
                    uc = -1 + (2 * iu + 1) / nu
                    vc = -1 + (2 * iv + 1) / nv
                    sub = (np.array(frame_pt(fr, uc, vc)), a_u, a_v, hl_ / nu, hs_ / nv)
                    L.append(frame_rect(sub, -0.8, -0.7, 0.8, 0.7))
                    L.append(frame_rect(sub, -0.8, -0.5, 0.8, -0.5)[:2])
                    L.append(frame_rect(sub, -0.8, 0.5, 0.8, 0.5)[:2])
                    L.append(frame_rect(sub, -0.42, 0, 0.42, 0)[:2])
                    for s_ in (-0.42, 0.42):
                        L.append(frame_rect(sub, s_, -0.5, s_, 0.5)[:2])
                    net = raster_lines([frame_rect(sub, 0, -0.85, 0, 0.85)[:2]], W, H) & m
                    g[net] = c("white")
                    g[net & (by < 0.5)] = c("ink")
                    if iu:
                        sep = raster_lines([frame_rect(sub, -1, -1, -1, 1)[:2]], W, H) & m
                        g[sep] = c("mint")
        elif sport == "cricket":
            g[m] = c("sand-light")
            L = [frame_rect(fr, -0.75, -0.4, -0.75, 0.4)[:2], frame_rect(fr, 0.75, -0.4, 0.75, 0.4)[:2]]
        else:
            L.append(frame_rect(fr, 0, -0.95, 0, 0.95)[:2])
        lm = raster_lines(L, W, H) & m
        g[lm] = c(line)
        if sport in ("volleyball", ""):
            net = raster_lines([frame_rect(fr, 0, -0.95, 0, 0.95)[:2]], W, H) & m
            g[net & (by < 0.5)] = c("ink")
    # off-campus house / shop: compound wall, garden, forecourt
    HOUSE_YARD = []
    for b in outs:
        x0_, y0_, x1_, y1_ = [int(round(v)) for v in b.poly.bounds]
        dx_ = int(round(b.door["base"][0]))
        if b.p.get("style") == "house":
            blockr = dilate(ROAD | KERB, 1)
            yb = y1_ + 3
            while yb < H - 1 and not blockr[yb + 1, x0_ - 10:x1_ + 11].any() and yb < y1_ + 22:
                yb += 1
            m = rect_mask(x0_ - 10, max(0, y0_ - 16), x1_ + 11, yb + 1)
            HOUSE_YARD.append((x0_ - 10, max(0, y0_ - 16), x1_ + 11, yb + 1, dx_))
            gcol = np.full((H, W), c("grass"), np.uint8)
            gcol[by < 0.4] = c("grass-light")
            gcol[(hn > 0.93)] = c("pink-pale")
            gcol[(hn > 0.97)] = c("yellow")
            g[m] = gcol[m]
            yy, xx = np.mgrid[0:H, 0:W]
            e = edge4(m)
            g[e] = c("cream")
            g[e & ((xx + yy) % 6 == 0)] = c("pink")
            # gate gap with two pillars and a little iron gate
            # inner row of the compound wall: cap shading
            g[edge4(m & ~e) & ((xx + yy) % 2 == 0)] = c("grey-light")
            # paved walk from the door to the gate
            g[y1_ + 1:yb, dx_ - 2:dx_ + 3] = c("cream")
            g[y1_ + 1:yb, dx_ - 2] = c("grey-light")
            g[y1_ + 1:yb, dx_ + 2] = c("grey-light")
        else:
            yy, xx = np.mgrid[0:H, 0:W]
            m = rect_mask(x0_ - 3, y1_, x1_ + 4, y1_ + 4)
            g[m] = c("cream")
            g[m & ((xx + yy) % 4 == 0)] = c("grey-light")
    # footpaths (paved, tiled)
    pcol = np.full((H, W), c("cream"), np.uint8)
    pcol[(by < 0.12)] = c("grey-light")
    g[PATH] = pcol[PATH]
    g[edge4(PATH) & ~ROAD] = c("grey-light")
    yy, xx = np.mgrid[0:H, 0:W]
    g[STEPS & ((yy + xx) % 3 == 0)] = c("grey")
    # sidewalks along Hanuman Marg
    scol = np.full((H, W), c("cream"), np.uint8)
    scol[((xx % 4) == 0) | ((yy % 4) == 0)] = c("grey-light")
    g[SIDEWALK] = scol[SIDEWALK]
    # roads
    out_road = raster(unary_union([ln.buffer(w / 2) for ln, w, inside, p in ROADS if not inside and p.get("highway") != "primary"]), W, H) & ~camp
    rcol = np.full((H, W), c("asphalt"), np.uint8)
    rcol[(hn > 0.93) | ((by < 0.1) & (vn2 > 0.5))] = c("asphalt-dark")
    rcol[hn < 0.02] = c("grey")
    g[ROAD] = rcol[ROAD]
    ocol = np.full((H, W), c("grey-light"), np.uint8)
    ocol[by < 0.25] = c("grey")
    g[out_road] = ocol[out_road]
    kc = np.where(((xx // 2 + yy // 2) % 2) == 0, c("yellow"), c("white")).astype(np.uint8)
    KIN = KERB & ~dilate(out_road, 1)
    g[KIN] = kc[KIN]
    g[KERB & ~KIN] = c("grey-light")
    # centre dashes on campus roads
    junctions = [Point(G.nodes[i]) for i in G.adj if len(G.adj[i]) >= 3]
    jun = unary_union([j.buffer(14) for j in junctions]) if junctions else None
    dash = np.zeros((H, W), bool)
    for ln, w, inside, p in ROADS:
        if w < 12:
            continue
        L = ln.length
        s = 0.0
        while s < L:
            if (s % 10) < 5:
                q = ln.interpolate(s)
                if jun is None or not jun.contains(q):
                    xi, yi = int(q.x), int(q.y)
                    if 0 <= xi < W and 0 <= yi < H:
                        dash[yi, xi] = True
            s += 0.5
    dash &= ROAD
    g[dash & dilate(camp, 4)] = c("white")
    g[dash & out_road] = c("grey-light")
    g[dash & ~out_road] = c("white")
    # zebra crossing straight out from the main gate
    zb = raster(CROSSING.buffer(6, cap_style=2), W, H) & ROAD
    g[zb] = c("asphalt")
    g[zb & ((xx // 2) % 2 == 0)] = c("white")
    # boundary wall: orange/purple striped stone, 3px
    wc = np.where(((xx + yy) // 3) % 2 == 0, c("orange"), c("purple")).astype(np.uint8)
    g[WALL] = wc[WALL]
    we = edge4(WALL)
    g[we] = np.where(g[we] == c("orange"), c("brown"), c("plum"))
    # coping highlight on the stones
    cap = WALL & ~we & shift(we, 0, 1)
    g[cap] = np.where(g[cap] == c("orange"), c("yellow"), c("lilac"))
    # building ground shadows (to the east and south, dithered)
    shadow = np.zeros((H, W), bool)
    for b in BLDS:
        fm = np.zeros((H, W), bool)
        h_, w_ = b.F.shape
        x0, y0 = b.ox, b.oy
        gx0, gy0, gx1, gy1 = max(0, x0), max(0, y0), min(W, x0 + w_), min(H, y0 + h_)
        fm[gy0:gy1, gx0:gx1] = b.F[gy0 - y0:gy1 - y0, gx0 - x0:gx1 - x0]
        s = fm.copy()
        reach = max(3, b.h // 2) if b.kind == "building" else 3
        for k in range(1, reach + 1):
            s |= shift(fm, k, 0)
        s |= shift(s, 0, 2)
        shadow |= s & ~fm
    shadow &= ~BUILD_SIL
    shade(g, shadow, 0.5)

    # ---------------------------------------------------------------- signs
    SIGN_OK = CAMPUS_MASK.copy()
    for b in outs:
        x0_, y0_, x1_, y1_ = b.poly.bounds
        SIGN_OK[0:int(y1_) + 40, max(0, int(x0_) - 100):int(x1_) + 100] = True
    signs = {}
    SIGN_BLOCK = np.zeros((H, W), bool)
    PROTECT = dilate(BUILD_SIL, 1) | ROAD | dilate(KERB, 1) | PATH | COURT | WALL | PROP_BOX | PITCH | PARK

    def nameplate(b):
        """Bake a name board onto the building's own visible front wall, near the door."""
        tm = text_mask(b.label.upper())
        th, tw = tm.shape
        pw, ph = tw + 4, th + 4
        plate = np.full((ph, pw), c("cream"), np.uint8)
        plate[0, :] = plate[-1, :] = c("ink")
        plate[:, 0] = plate[:, -1] = c("ink")
        plate[2:2 + th, 2:2 + tw][tm] = c("ink")
        # usable wall pixels in global coords: own wall, still visible
        h_, w_ = b.S.shape
        wall = np.zeros((H, W), bool)
        x0, y0 = b.ox, b.oy
        gx0, gy0, gx1, gy1 = max(0, x0), max(0, y0), min(W, x0 + w_), min(H, y0 + h_)
        wall[gy0:gy1, gx0:gx1] = b.Wm[gy0 - y0:gy1 - y0, gx0 - x0:gx1 - x0]
        wall &= b.vis_full
        own_vis = b.vis_full & ~edge4(b.vis_full)
        ii = cv2.integral((~own_vis).astype(np.uint8))
        sums = ii[ph:, pw:] - ii[:-ph, pw:] - ii[ph:, :-pw] + ii[:-ph, :-pw]
        iw = cv2.integral((~wall).astype(np.uint8))
        nonwall = iw[ph:, pw:] - iw[:-ph, pw:] - iw[ph:, :-pw] + iw[:-ph, :-pw]
        ys, xs = np.nonzero(sums == 0)
        nonwall = nonwall[ys, xs]
        dbx, dby = b.door["base"]
        if not len(xs):
            log(f"  NAMEPLATE FAILED {b.id}; falling back to nearest ground spot")
            place_sign(b.location, b.label, *b.door["pt"], (0, 8), b)
            return
        cx = xs + pw / 2
        by_ = ys + ph
        # prefer centred above the door, low on the wall (but above the door: 6 px over the base)
        cost = np.abs(cx - dbx) * 1.0 + np.abs(by_ - (dby - 6)) * 0.6 + 6 * nonwall
        i = int(np.argmin(cost))
        px0, py0 = int(xs[i]), int(ys[i])
        paste(b.img, plate, px0 - b.ox, py0 - b.oy)
        anchor = (px0 + pw // 2, py0 + ph - 1)
        signs[b.location] = anchor
        b.plate = True
        log(f"  nameplate {b.id}: on wall at {anchor}, {math.dist(anchor, b.door['pt']):.0f}px from door")

    def place_sign(key, label, ax, ay, prefer, own=None, max_dist=1e9):
        spr = SP.signboard(label)
        blk = (PROTECT | SIGN_BLOCK | ~SIGN_OK).astype(np.uint8)
        ii = cv2.integral(blk)
        bw, bh = spr.w + 2, spr.h + 2
        sums = ii[bh:, bw:] - ii[:-bh, bw:] - ii[bh:, :-bw] + ii[:-bh, :-bw]
        ys, xs = np.nonzero(sums == 0)
        if not len(xs):
            log(f"  SIGN FAILED {key}")
            return None
        axs = xs + 1 + spr.ax
        ays = ys + 1 + spr.ay
        cxs = np.clip(axs, 0, W - 1)
        cys = np.clip(ays - spr.h // 2, 0, H - 1)
        d_door = np.hypot(axs - ax, ays - ay)
        if own is not None:
            om = (~own.vis_full).astype(np.uint8)
            d_own = cv2.distanceTransform(om, cv2.DIST_L2, 3)[cys, cxs]
            oth = np.zeros((H, W), bool)
            for o in BLDS:
                if o is not own:
                    oth |= o.vis_full
            d_oth = cv2.distanceTransform((~oth).astype(np.uint8), cv2.DIST_L2, 3)[cys, cxs]
            # the sign must read as belonging to its own building
            ok = d_own + 4 < d_oth
            cost = d_door + 1.5 * d_own + 0.3 * np.hypot(axs - (ax + prefer[0]), ays - (ay + prefer[1]))
            cost = np.where(ok, cost, cost + 400)
        else:
            cost = d_door + 0.05 * np.hypot(axs - (ax + prefer[0]), ays - (ay + prefer[1]))
        i = int(np.argmin(cost))
        x, y = int(axs[i]), int(ays[i])
        if own is not None and d_door[i] > max_dist:
            return None
        if d_door[i] > 60:
            log(f"  sign {key}: {d_door[i]:.0f}px from its door")
        x0, y0 = x - spr.ax, y - spr.ay
        SIGN_BLOCK[max(0, y0 - 2):y0 + spr.h + 2, max(0, x0 - 2):x0 + spr.w + 2] = True
        add_prop(spr, x, y, "sign", {"location": key})
        signs[key] = (x, y)
        return (x, y)

    place_sign("ground", "College Ground", *G.nodes[ground_door], (0, 8))
    place_sign("canteen", "Canteen", *G.nodes[canteen_door], (0, 8))
    # the arch itself is the Main Gate sign (its beam reads VNR VJIET)
    signs["main-gate"] = (int(ax_), int(ay_) - arch.ay)
    for b in BLDS:
        if not b.location:
            continue
        px_, py_ = b.door["pt"]
        nx, ny = b.door["normal"]
        if b.id == "peb" or place_sign(b.location, b.label, px_, py_, (nx * 10 + 14, ny * 10 + 8), b, max_dist=30) is None:
            nameplate(b)

    entry = {b.location: b.door["pt"] for b in BLDS if b.location}
    entry.update({"ground": G.nodes[ground_door], "canteen": G.nodes[canteen_door], "main-gate": G.nodes[gate_door]})
    for k_, v_ in signs.items():
        log(f"sign-to-door {k_:15s} {math.dist(v_, entry[k_]):5.1f}px")
    # ---------------------------------------------------------------- scatter props
    rng = np.random.default_rng(42)
    trees = SP.tree_variants()
    palm = SP.palm()
    SOFT = ROAD | KERB | PATH | COURT | PITCH | WALL | SIDEWALK | PARK
    HARD = BUILD_SIL | SIGN_BLOCK | PROP_BOX
    trunks = []
    rejects = {"tree": 0, "bench": 0, "lamp": 0, "vehicle": 0, "bush": 0}
    canopy_occ = np.zeros((H, W), bool)

    def try_tree(x, y, spr=None, kind_soft=SOFT):
        spr = spr or trees[rng.integers(len(trees))]
        x, y = int(x), int(y)
        x0, y0 = x - spr.ax, y - spr.ay
        if x0 < 0 or y0 < 0 or x0 + spr.w > W or y0 + spr.h > H:
            return False
        if not CAMPUS_MASK[y, x]:
            return False
        box_ = (spr.img != T)
        reg = slice(y0, y0 + spr.h), slice(x0, x0 + spr.w)
        if (HARD[reg] & box_).any() or (kind_soft[reg] & box_).any():
            rejects["tree"] += 1
            return False
        # foot buffer 2px off anything soft/hard
        if (dilate_cache[y - 3:y + 3, x - 4:x + 5]).any():
            rejects["tree"] += 1
            return False
        if (canopy_occ[reg] & box_).sum() > 0.25 * box_.sum():
            return False
        canopy_occ[reg] |= box_
        add_prop(spr, x, y, "tree")
        PROP_BOX[reg] &= True
        trunks.append((x, y, spr))
        return True

    dilate_cache = dilate(SOFT | HARD, 2)
    # OSM tree points
    for t in TREES:
        if not try_tree(t.x, t.y):
            log(f"  osm tree at ({t.x:.0f},{t.y:.0f}) rejected")
    # wood: dense
    for gg, p in GREEN:
        m = raster(gg, W, H) & CAMPUS_MASK
        dense = p.get("natural") == "wood"
        step = 9 if dense else 16
        ys, xs = np.nonzero(m)
        if not len(xs):
            continue
        for y in range(ys.min(), ys.max() + 1, step):
            for x in range(xs.min() + (y // step % 2) * step // 2, xs.max() + 1, step):
                jx, jy = x + rng.integers(-3, 4), y + rng.integers(-3, 4)
                if 0 <= jy < H and 0 <= jx < W and m[jy, jx] and rng.random() < (0.95 if dense else 0.55):
                    try_tree(jx, jy)
    # along campus roads: both sides
    for ln, w, inside, p in ROADS:
        if not inside:
            continue
        L = ln.length
        for side in (-1, 1):
            s = rng.uniform(4, 14)
            while s < L - 2:
                q = ln.interpolate(s)
                q2 = ln.interpolate(min(L, s + 1))
                dx, dy = q2.x - q.x, q2.y - q.y
                n = math.hypot(dx, dy) or 1
                off = w / 2 + 11 + rng.uniform(0, 4) + (5 if p.get("sidewalk") else 0)
                x = q.x - dy / n * off * side
                y = q.y + dx / n * off * side
                spr = palm if rng.random() < 0.12 else None
                try_tree(x, y, spr)
                s += rng.uniform(18, 30)
    # sprinkle on campus grass
    ys, xs = np.nonzero(CAMPUS_MASK & ~BARE)
    for _ in range(420):
        i = rng.integers(len(xs))
        try_tree(xs[i], ys[i])
    # a few hardy trees on bare earth
    ys, xs = np.nonzero(BARE)
    for _ in range(40):
        i = rng.integers(len(xs))
        try_tree(xs[i], ys[i], trees[1])
    # outside scrub bushes (ground texture only, cheap): darker blobs
    ntree = sum(1 for p in props if p["kind"] == "tree")
    log(f"trees placed: {ntree}")

    FOOTFORBID = ROAD | PATH | COURT | BUILD_SIL | PITCH
    def try_prop(spr, x, y, kind, soft=None, extra_ok=None):
        x, y = int(x), int(y)
        x0, y0 = x - spr.ax, y - spr.ay
        if x0 < 0 or y0 < 0 or x0 + spr.w > W or y0 + spr.h > H:
            return False
        box_ = spr.img != T
        reg = slice(y0, y0 + spr.h), slice(x0, x0 + spr.w)
        S_ = SOFT if soft is None else soft
        if (HARD[reg] & box_).any() or (S_[reg] & box_).any() or (canopy_occ[reg] & box_).any():
            rejects[kind] = rejects.get(kind, 0) + 1
            return False
        fx0, fy0, fx1, fy1 = spr.foot
        fr_ = slice(max(0, y + fy0), y + fy1 + 1), slice(max(0, x + fx0), x + fx1 + 1)
        if (FOOTFORBID[fr_]).any():
            rejects[kind] = rejects.get(kind, 0) + 1
            return False
        canopy_occ[reg] |= box_
        add_prop(spr, x, y, spr.kind)
        HARD[reg] |= box_
        return True

    # lamps along campus roads
    lampspr = SP.lamp()
    for ln, w, inside, p in ROADS:
        if not inside or w < 12:
            continue
        L = ln.length
        s, side = 10.0, 1
        while s < L:
            q = ln.interpolate(s)
            q2 = ln.interpolate(min(L, s + 1))
            dx, dy = q2.x - q.x, q2.y - q.y
            n = math.hypot(dx, dy) or 1
            for off in (w / 2 + 3 + (5 if p.get("sidewalk") else 0), w / 2 + 6 + (5 if p.get("sidewalk") else 0)):
                x = q.x - dy / n * off * side
                y = q.y + dx / n * off * side
                if try_prop(lampspr, x, y, "lamp"):
                    break
            side = -side
            s += 36
    # benches along footpaths and in parks
    benchspr = SP.bench()
    for gg, p in PATHS:
        L = gg.length
        s = 8.0
        while s < L:
            q = gg.interpolate(s)
            for off in (7, -7, 9, -9):
                if try_prop(benchspr, q.x, q.y + off, "bench"):
                    break
            s += 40
    for gg, p in GREEN:
        if p.get("natural") == "wood":
            continue
        cpt = gg.representative_point()
        for dx, dy in ((0, 0), (8, 6), (-10, 4), (6, -8)):
            try_prop(benchspr, cpt.x + dx, cpt.y + dy, "bench")
        fb = SP.flowerbed()
        for k in range(10):
            pt = (cpt.x + rng.integers(-25, 26), cpt.y + rng.integers(-25, 26))
            if gg.contains(Point(pt)):
                try_prop(fb, pt[0], pt[1], "flowers")
    # benches near the canteen umbrellas
    for dx, dy in ((-16, 14), (30, 4), (-18, -2)):
        try_prop(benchspr, kx + dx, ky + dy, "bench")

    # vehicles: buses in the big gravel lot, cars/bikes near parking points
    busspr = SP.bus()
    cars = [SP.car("red", "red-dark"), SP.car("sky", "blue"), SP.car("white", "grey-light"), SP.car("yellow", "orange")]
    VSOFT = ROAD | KERB | PATH | COURT | PITCH | WALL | SIDEWALK
    for gg, p in parking:
        fr = mrr_frame(gg)
        placed = 0
        for v in (-0.62, -0.35, -0.08):
            for u in np.linspace(-0.8, 0.8, 10):
                x, y = frame_pt(fr, u, v)
                if placed < 11 and gg.contains(Point(x, y)) and rng.random() < 0.75 and try_prop(busspr, x, y, "vehicle", VSOFT):
                    placed += 1
        for v in (0.3, 0.62):
            for u in np.linspace(-0.85, 0.85, 22):
                x, y = frame_pt(fr, u, v)
                if gg.contains(Point(x, y)) and rng.random() < 0.55:
                    try_prop(cars[rng.integers(len(cars))], x, y, "vehicle", VSOFT)
    ppts = [(g_, p) for g_, p in layer("open_areas") if g_.geom_type == "Point" and p.get("amenity") == "parking"]
    for pt, p in ppts:
        nm = p.get("name", "")
        n_ok = 0
        for r in range(0, 50, 3):
            for t in range(0, 360, 30):
                x = pt.x + r * math.cos(math.radians(t))
                y = pt.y + r * math.sin(math.radians(t))
                if "Car" in nm or "Staff" in nm:
                    if n_ok < 3 and try_prop(cars[(n_ok + int(x)) % 4], x, y, "vehicle", VSOFT):
                        n_ok += 1
                else:
                    if n_ok < 10:
                        sc = SP.scooter(["red", "blue", "ink", "purple"][n_ok % 4])
                        if try_prop(sc, x, y, "vehicle", VSOFT):
                            n_ok += 1
        log(f"parking '{nm}': {n_ok} vehicles")
    # bikes next to the parking canopies
    for b in BLDS:
        if b.kind != "canopy":
            continue
        minx, miny, maxx, maxy = b.poly.bounds
        k = 0
        for x in range(int(minx) + 2, int(maxx) - 1, 3):
            sc = SP.scooter(["red", "blue", "ink", "purple", "orange"][k % 5])
            if try_prop(sc, x, maxy + 7, "vehicle", VSOFT):
                k += 1
    # boulders on bare earth and lawns, bushes on campus grass
    rocks = [SP.rock(0), SP.rock(1)]
    ys, xs = np.nonzero(BARE)
    for _ in range(70):
        i = rng.integers(len(xs))
        try_prop(rocks[rng.integers(2)], xs[i], ys[i], "rock")
    ys, xs = np.nonzero(CAMPUS_MASK & ~BARE)
    bsh_in = SP.bush()
    for _ in range(260):
        i = rng.integers(len(xs))
        try_prop(bsh_in, xs[i], ys[i], "bush")
    for _ in range(40):
        i = rng.integers(len(xs))
        try_prop(rocks[rng.integers(2)], xs[i], ys[i], "rock")
    # neighbourhood north of Medak Road: trees, bushes, lamps
    PRIM = raster(unary_union([ln.buffer(w / 2) for ln, w, i, p in ROADS if p.get("highway") == "primary"]), W, H)
    first = np.where(PRIM.any(0), PRIM.argmax(0), 0)
    yy_, xx_ = np.mgrid[0:H, 0:W]
    NORTH = (yy_ < first[None, :] - 6) & ~dilate(CAMPUS_MASK, 6)
    NSOFT = VSOFT | out_road | dilate(ROAD | KERB, 2) | ~NORTH
    ys, xs = np.nonzero(NORTH)
    nt = 0
    for _ in range(500):
        i = rng.integers(len(xs))
        if try_prop(trees[rng.integers(len(trees))], xs[i], ys[i], "tree", NSOFT):
            nt += 1
            trunks.append((int(xs[i]), int(ys[i]), props[-1]["spr"]))
    for _ in range(120):
        i = rng.integers(len(xs))
        try_prop(SP.bush(), xs[i], ys[i], "bush", NSOFT)
    nl = 0
    for x in range(40, W - 20, 70):
        y = int(first[x]) - 4
        if first[x] and nl < 12:
            for dy in range(0, 6):
                if try_prop(lampspr, x, y - dy, "lamp", NSOFT & ~(~NORTH & (yy_ >= first[None, :] - 10) & (yy_ < first[None, :]))):
                    nl += 1
                    break
    log(f"neighbourhood: {len(NEIGH)} houses, {nt} trees, {nl} lamps")
    # outside the campus: a few dry bushes
    bsh = SP.bush()
    for _ in range(160):
        x, y = rng.integers(4, W - 4), rng.integers(4, H - 4)
        if not CAMPUS_MASK[max(0, y - 10):y + 10, max(0, x - 10):x + 10].any():
            try_prop(bsh, x, y, "bush", VSOFT | out_road | dilate(out_road, 3))

    # off-campus houses (style "house"): front gate, garden tree, flowers, potted plants
    for (yx0, yy0, yx1, yy1, gdx) in HOUSE_YARD:
        gate = SP.art([
            "kk.......kk",
            "oo.......oo",
            "ookyykyykoo",
            "oo.k..k..oo",
            "ookyykyykoo",
            "pp.......pp",
        ], SP.K)
        gspr = SP.Sprite(gate, 5, 5, "gate", (-5, -1, 5, 0))
        add_prop(gspr, gdx, yy1 - 1, "house-gate")
        HARD[yy1 - 7:yy1 + 1, gdx - 6:gdx + 7] = True
        pot = SP.Sprite(SP.art([".e.", "elE", "rrr", ".R."], SP.K), 1, 3, "pot", (-1, -1, 1, 0))
        yard_ok = np.zeros((H, W), bool)
        yard_ok[yy0 + 2:yy1 - 1, yx0 + 2:yx1 - 2] = True
        ysoft = SOFT | ~yard_ok | dilate(PATH, 1)
        ys_, xs_ = np.nonzero(yard_ok & ~ysoft)
        n_t = n_p = n_f = 0
        for i_ in rng.permutation(len(xs_)):
            x_, y_ = xs_[i_], ys_[i_]
            if abs(x_ - gdx) < 5:
                continue
            if n_t < 2 and try_prop([palm, trees[1], SP.bush()][n_t % 3], x_, y_, "tree", ysoft):
                n_t += 1
            elif n_f < 3 and try_prop(SP.flowerbed(), x_, y_, "flowers", ysoft):
                n_f += 1
            elif n_p < 6 and try_prop(pot, x_, y_, "pot", ysoft):
                n_p += 1
        # garden trees just inside / beside the compound corners
        for tx_, ty_ in ((yx1 + 7, yy0 + 14), (yx1 + 7, yy1 - 1), (yx1 + 18, yy0 + 12), (yx0 - 7, yy0 + 10)):
            if n_t < 2 and (try_prop(trees[1], tx_, ty_, "tree", VSOFT) or try_prop(palm, tx_, ty_, "tree", VSOFT)):
                n_t += 1
        log(f"home garden: {n_t} trees, {n_f} flowerbeds, {n_p} pots")
    # tree ground shadows
    tsh = np.zeros((H, W), bool)
    for x, y, spr in trunks:
        r = spr.w // 2
        cv2.ellipse(tsh.view(np.uint8), (x + 2, y - 1), (max(2, r - 1), max(1, r // 3)), 0, 0, 360, 1, -1)
    tsh = tsh.astype(bool) & ~BUILD_SIL & ~ROAD
    shade(g, tsh, 0.5)
    for d_ in props:
        if d_["kind"] in ("car", "bus", "kiosk", "bench", "bike"):
            spr = d_["spr"]
            x0 = d_["x"] - spr.ax + 2
            y0 = d_["y"] - 1
            m = rect_mask(x0, y0, x0 + spr.w - 2, y0 + 2) & ~BUILD_SIL
            shade(g, m, 0.5)

    # ---------------------------------------------------------------- validate props
    n_bad = 0
    FORBID = ROAD | PATH | COURT | BUILD_SIL | PITCH
    for d_ in props:
        if d_["kind"] in ("gate", "house-gate"):
            continue
        spr = d_["spr"]
        fx0, fy0, fx1, fy1 = spr.foot
        x, y = d_["x"], d_["y"]
        foot = FORBID[max(0, y + fy0):y + fy1 + 1, max(0, x + fx0):x + fx1 + 1]
        x0, y0 = x - spr.ax, y - spr.ay
        boxm = spr.img != T
        over = BUILD_SIL[y0:y0 + spr.h, x0:x0 + spr.w] & boxm[:BUILD_SIL[y0:y0 + spr.h, x0:x0 + spr.w].shape[0], :BUILD_SIL[y0:y0 + spr.h, x0:x0 + spr.w].shape[1]]
        if d_["kind"] == "sign":
            sb = (ROAD | KERB | BUILD_SIL)[max(0, y0):y0 + spr.h, max(0, x0):x0 + spr.w]
            if sb.any():
                foot = sb
        if foot.any() or over.any():
            n_bad += 1
            log(f"  INVALID prop {d_['kind']} at ({x},{y})")
    log(f"props: {len(props)} placed, rejected attempts {rejects}, invalid {n_bad}")
    if n_bad:
        raise SystemExit("FAIL: invalid prop placement")

    # ---------------------------------------------------------------- sheets
    def pack(items, maxw=1024):
        """items: list of index images; returns sheet and rects. Dedupes identical frames."""
        uniq = {}
        order = []
        for i, im in enumerate(items):
            k = (im.shape, im.tobytes())
            if k not in uniq:
                uniq[k] = len(order)
                order.append(im)
        idxs = sorted(range(len(order)), key=lambda i: -order[i].shape[0])
        x = y = rowh = 0
        rects = [None] * len(order)
        for i in idxs:
            h_, w_ = order[i].shape
            if x + w_ > maxw:
                x, y, rowh = 0, y + rowh + 1, 0
            rects[i] = (x, y, w_, h_)
            x += w_ + 1
            rowh = max(rowh, h_)
        sh = np.full((y + rowh, maxw), T, np.uint8)
        for i, (x0, y0, w_, h_) in enumerate(rects):
            sh[y0:y0 + h_, x0:x0 + w_] = order[i]
        used = max(r[0] + r[2] for r in rects)
        sh = sh[:, :used]
        out = [rects[uniq[(im.shape, im.tobytes())]] for im in items]
        return sh, out

    # crop building images to their visible pixels
    for b in BLDS:
        ys, xs = np.nonzero(b.img != T)
        y0, y1, x0, x1 = ys.min(), ys.max() + 1, xs.min(), xs.max() + 1
        b.img = b.img[y0:y1, x0:x1]
        b.vis = b.vis[y0:y1, x0:x1]
        b.ox += x0
        b.oy += y0
    bsheet, brects = pack([b.img for b in BLDS], 1024)
    psheet, prects = pack([d_["spr"].img for d_ in props], 512)
    save_indexed(g, OUT_PUBLIC / "campus_ground.png")
    save_indexed(bsheet, OUT_PUBLIC / "campus_buildings.png")
    save_indexed(psheet, OUT_PUBLIC / "campus_props.png")

    # ---------------------------------------------------------------- json
    def fp(poly):
        return [[round(x, 1), round(y, 1)] for x, y in list(poly.exterior.coords)[:-1]]

    out_b = []
    for b, r in zip(BLDS, brects):
        e = {"id": b.id, "location": b.location, "label": b.label, "placeholder": bool(b.p.get("placeholder")),
             "kind": b.kind,
             "frame": {"x": r[0], "y": r[1], "w": r[2], "h": r[3]}, "pos": {"x": int(b.ox), "y": int(b.oy)},
             "depthY": int(b.depthY), "footprint": fp(b.poly)}
        if b.location:
            hit = mask_contour(b.vis, b.ox, b.oy)
            e["hit"] = hit
            dx_, dy_ = G.nodes[b.door_node]
            e["door"] = {"x": round(dx_, 1), "y": round(dy_, 1), "node": b.door_node, "side": b.door["side"]}
            s = signs.get(b.location)
            e["sign"] = {"x": s[0], "y": s[1]} if s else None
        else:
            e["hit"] = None
            e["door"] = None
            e["sign"] = None
        out_b.append(e)
    pts = list(pg.simplify(1.0).exterior.coords)[:-1]
    while len(pts) > 40:
        pts = list(Polygon(pts).simplify(len(pts) / 20).exterior.coords)[:-1]
    areas = [
        {"id": "ground", "location": "ground", "label": "College Ground", "placeholder": False,
         "hit": [[round(x), round(y)] for x, y in pts], "door": {"x": round(G.nodes[ground_door][0], 1), "y": round(G.nodes[ground_door][1], 1), "node": ground_door}},
        {"id": "canteen", "location": "canteen", "label": "Canteen", "placeholder": False,
         "hit": canteen_hit, "door": {"x": round(G.nodes[canteen_door][0], 1), "y": round(G.nodes[canteen_door][1], 1), "node": canteen_door}},
        {"id": "main-gate", "location": "main-gate", "label": "Main Gate", "placeholder": False,
         "hit": gate_hit, "door": {"x": round(G.nodes[gate_door][0], 1), "y": round(G.nodes[gate_door][1], 1), "node": gate_door}},
    ]
    for a in areas:
        s = signs.get(a["location"])
        a["sign"] = {"x": s[0], "y": s[1]} if s else None
    out_p = []
    for d_, r in zip(props, prects):
        spr = d_["spr"]
        e = {"kind": d_["kind"], "frame": {"x": r[0], "y": r[1], "w": r[2], "h": r[3]},
             "x": d_["x"] - spr.ax, "y": d_["y"] - spr.ay, "depthY": d_["y"]}
        if "location" in d_:
            e["location"] = d_["location"]
        out_p.append(e)
    edges = G.edges()
    data = {
        "version": 1, "mpp": 0.5, "width": W, "height": H,
        "ground": "campus_ground.png",
        "sheets": {"buildings": "campus_buildings.png", "props": "campus_props.png"},
        "spawn": {"x": round(G.nodes[spawn][0], 1), "y": round(G.nodes[spawn][1], 1), "node": spawn},
        "buildings": out_b, "areas": areas, "props": out_p,
        "graph": {"nodes": [[round(x, 1), round(y, 1)] for x, y in G.nodes], "edges": [list(e) for e in edges]},
        "credits": "Map data © OpenStreetMap contributors",
    }
    (OUT_PUBLIC / "campus.json").write_text(json.dumps(data, separators=(",", ":"), default=lambda o: o.item()))

    # ---------------------------------------------------------------- composites
    comp = g.copy()
    draw = []
    for b in BLDS:
        draw.append((b.depthY, 0, b.img, b.ox, b.oy))
    for d_ in props:
        spr = d_["spr"]
        draw.append((d_["y"], 1, spr.img, d_["x"] - spr.ax, d_["y"] - spr.ay))
    for _, _, im, x, y in sorted(draw, key=lambda t: (t[0], t[1])):
        paste(comp, im, x, y)
    rgb = Image.fromarray(to_rgba(comp)[:, :, :3])
    rgb.resize((W * 2, H * 2), Image.NEAREST).save(OUT_DBG / "pixel_map_preview.png", optimize=True)
    dbg = rgb.resize((W * 2, H * 2), Image.NEAREST)
    dd = ImageDraw.Draw(dbg)
    S2 = lambda pts_: [(x * 2, y * 2) for x, y in pts_]
    for a, b_ in edges:
        dd.line(S2([G.nodes[a], G.nodes[b_]]), fill=(255, 255, 255), width=1)
    for x, y in G.nodes:
        dd.rectangle([x * 2 - 1, y * 2 - 1, x * 2 + 1, y * 2 + 1], fill=(255, 255, 255))
    for b in BLDS:
        dd.line(S2(list(b.poly.exterior.coords)), fill=(0, 255, 255))
    for e in out_b + areas:
        if e.get("hit"):
            dd.line(S2(e["hit"] + [e["hit"][0]]), fill=(255, 0, 255), width=2)
        if e.get("door"):
            x, y = e["door"]["x"] * 2, e["door"]["y"] * 2
            dd.ellipse([x - 4, y - 4, x + 4, y + 4], fill=(255, 0, 0))
    for d_ in props:
        if d_["kind"] == "sign":
            spr = d_["spr"]
            x0, y0 = (d_["x"] - spr.ax) * 2, (d_["y"] - spr.ay) * 2
            dd.rectangle([x0, y0, x0 + spr.w * 2, y0 + spr.h * 2], outline=(255, 255, 0), width=2)
    sx, sy = G.nodes[spawn]
    dd.ellipse([sx * 2 - 10, sy * 2 - 10, sx * 2 + 10, sy * 2 + 10], fill=(0, 230, 0), outline=(0, 0, 0))
    dbg.save(OUT_DBG / "pixel_map_debug.png", optimize=True)
    # satellite alignment check (private)
    try:
        from render_common import SatelliteMapper
        m = SatelliteMapper()
        src, dst = [], []
        for x in (0, 267, 535):
            for y in (0, 356, 713):
                src.append(m.xy(x, y))
                dst.append((x * 2, (HM - y) * 2))
        A, _ = cv2.estimateAffine2D(np.float32(src), np.float32(dst))
        sat = cv2.warpAffine(np.array(m.image().convert("RGB")), A, (W, H))
        si = Image.fromarray(sat).resize((W * 2, H * 2), Image.NEAREST)
        sd = ImageDraw.Draw(si)
        for b in BLDS:
            sd.line(S2(list(b.poly.exterior.coords)), fill=(0, 255, 255), width=2)
        for ln, w, inside, p in ROADS:
            sd.line(S2(list(ln.coords)), fill=(255, 80, 80), width=1)
        si.save(OUT_DBG / "pixel_map_sat_check.png", optimize=True)
    except Exception as ex:  # noqa: BLE001
        log(f"sat check skipped: {ex}")

    # ---------------------------------------------------------------- report
    log(f"graph: {len(G.nodes)} nodes, {len(edges)} edges; max edge "
        f"{max(math.dist(G.nodes[a], G.nodes[b_]) for a, b_ in edges):.1f}px; spawn node {spawn}")
    log(f"signs placed: {len(signs)} / {sum(1 for b in BLDS if b.location) + 3}")
    tot = 0
    for f in ("campus_ground.png", "campus_buildings.png", "campus_props.png", "campus.json"):
        sz = (OUT_PUBLIC / f).stat().st_size
        tot += sz
        log(f"  {f}: {sz / 1024:.0f} KB")
    log(f"  total: {tot / 1024:.0f} KB; buildings sheet {bsheet.shape[1]}x{bsheet.shape[0]}, props sheet {psheet.shape[1]}x{psheet.shape[0]}")


if __name__ == "__main__":
    main()
