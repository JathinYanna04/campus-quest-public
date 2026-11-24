"""Drawing helpers shared by 05_render.py and apply_labels.py."""
import math

from PIL import Image, ImageDraw, ImageFont
from shapely.geometry import shape

from common import ATTRIBUTION, PROCESSED, SATELLITE, TO_WGS, load_json

FONT_PATHS = [
    "/usr/share/fonts/TTF/DejaVuSans-Bold.ttf",
    "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf",
    "/usr/share/fonts/noto/NotoSans-Bold.ttf",
    "/usr/share/fonts/liberation/LiberationSans-Bold.ttf",
]


def font(size):
    for p in FONT_PATHS:
        try:
            return ImageFont.truetype(p, size)
        except OSError:
            continue
    return ImageFont.load_default()


def load_layer(name):
    p = PROCESSED / f"{name}.geojson"
    if not p.exists():
        return []
    return [(shape(f["geometry"]), f["properties"]) for f in load_json(p)["features"]]


class SatelliteMapper:
    """Maps processed (meter, origin-relative) coords to satellite image pixels."""

    def __init__(self, scale=1.0):
        self.meta = load_json(SATELLITE / "campus_satellite.json")
        self.proc = load_json(PROCESSED / "meta.json")
        self.scale = scale
        b = self.meta["bounds_wgs84"]
        z = self.meta["zoom"]
        self.z = z
        self.px0, self.py0 = self._merc(b["min_lon"], b["max_lat"])
        self.w = self.meta["width_px"] * scale
        self.h = self.meta["height_px"] * scale

    def _merc(self, lon, lat):
        n = 2 ** self.z * 256
        x = (lon + 180) / 360 * n
        y = (1 - math.log(math.tan(math.radians(lat)) + 1 / math.cos(math.radians(lat))) / math.pi) / 2 * n
        return x, y

    def xy(self, mx, my):
        ox, oy = self.proc["origin_utm"]["x"], self.proc["origin_utm"]["y"]
        lon, lat = TO_WGS.transform(mx + ox, my + oy)
        px, py = self._merc(lon, lat)
        return ((px - self.px0) * self.scale, (py - self.py0) * self.scale)

    def image(self):
        img = Image.open(SATELLITE / "campus_satellite.png").convert("RGBA")
        if self.scale != 1:
            img = img.resize((int(self.w), int(self.h)), Image.LANCZOS)
        return img


class PlainMapper:
    """Maps meter coords to a blank canvas at `ppm` pixels per meter."""

    def __init__(self, ppm=2.0, margin=40):
        self.proc = load_json(PROCESSED / "meta.json")
        self.ppm = ppm
        self.margin = margin
        s = self.proc["bbox_size_m"]
        self.w = int(s["width"] * ppm + 2 * margin)
        self.h = int(s["height"] * ppm + 2 * margin)

    def xy(self, mx, my):
        return (self.margin + mx * self.ppm, self.h - self.margin - my * self.ppm)

    def image(self, bg=(245, 242, 235, 255)):
        return Image.new("RGBA", (self.w, self.h), bg)


def ring_px(mapper, coords):
    return [mapper.xy(x, y) for x, y in coords]


def draw_geom(draw, mapper, geom, fill=None, outline=None, width=1, dash=None):
    t = geom.geom_type
    if t == "Polygon":
        pts = ring_px(mapper, geom.exterior.coords)
        if fill:
            draw.polygon(pts, fill=fill)
            for hole in geom.interiors:
                draw.polygon(ring_px(mapper, hole.coords), fill=0 if isinstance(fill, int) else (0, 0, 0, 0))
        if outline:
            draw.line(pts, fill=outline, width=width)
            for hole in geom.interiors:
                draw.line(ring_px(mapper, hole.coords), fill=outline, width=width)
    elif t in ("MultiPolygon", "GeometryCollection", "MultiLineString"):
        for g in geom.geoms:
            draw_geom(draw, mapper, g, fill, outline, width, dash)
    elif t == "LineString":
        pts = ring_px(mapper, geom.coords)
        if dash:
            draw_dashed(draw, pts, outline, width, dash)
        else:
            draw.line(pts, fill=outline, width=width)
    elif t == "Point":
        x, y = mapper.xy(geom.x, geom.y)
        r = width
        draw.ellipse((x - r, y - r, x + r, y + r), fill=fill or outline)


def draw_dashed(draw, pts, color, width, dash):
    on, off = dash
    for (x0, y0), (x1, y1) in zip(pts, pts[1:]):
        seg = math.hypot(x1 - x0, y1 - y0)
        if seg == 0:
            continue
        d = 0.0
        while d < seg:
            e = min(d + on, seg)
            draw.line([(x0 + (x1 - x0) * d / seg, y0 + (y1 - y0) * d / seg),
                       (x0 + (x1 - x0) * e / seg, y0 + (y1 - y0) * e / seg)], fill=color, width=width)
            d += on + off


def label_box(draw, xy, text, fnt, fg=(255, 255, 255, 255), bg=(0, 0, 0, 190), pad=4):
    x, y = xy
    l, t, r, b = draw.textbbox((0, 0), text, font=fnt)
    w, h = r - l, b - t
    draw.rectangle((x - w / 2 - pad, y - h / 2 - pad, x + w / 2 + pad, y + h / 2 + pad), fill=bg)
    draw.text((x - w / 2 - l, y - h / 2 - t), text, font=fnt, fill=fg)


def scale_bar_and_north(draw, mapper, ppm, where=(30, 30), fnt=None):
    """Scale bar (100 m) and a north arrow at the bottom-left pixel offset."""
    fnt = fnt or font(16)
    x, y = where[0], mapper.h - where[1]
    length = 100 * ppm
    draw.rectangle((x, y - 6, x + length, y), fill=(20, 20, 20, 255))
    draw.rectangle((x, y - 6, x + length / 2, y), fill=(255, 255, 255, 255), outline=(20, 20, 20, 255))
    draw.text((x, y - 28), "0", font=fnt, fill=(20, 20, 20, 255))
    draw.text((x + length - 30, y - 28), "100 m", font=fnt, fill=(20, 20, 20, 255))
    ax, ay = x + length + 60, y - 10
    draw.polygon([(ax, ay - 40), (ax - 10, ay), (ax, ay - 10), (ax + 10, ay)], fill=(20, 20, 20, 255))
    draw.text((ax - 6, ay - 62), "N", font=fnt, fill=(20, 20, 20, 255))


def attribution(draw, mapper, fnt=None):
    fnt = fnt or font(14)
    l, t, r, b = draw.textbbox((0, 0), ATTRIBUTION, font=fnt)
    draw.rectangle((mapper.w - (r - l) - 14, mapper.h - (b - t) - 12, mapper.w, mapper.h), fill=(0, 0, 0, 160))
    draw.text((mapper.w - (r - l) - 8, mapper.h - (b - t) - 8), ATTRIBUTION, font=fnt, fill=(255, 255, 255, 255))
