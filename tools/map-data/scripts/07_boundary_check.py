"""Boundary check: satellite over a wider area (padded bbox + the whole
"Vignana Jyothi Public School" polygon), with the VNR boundary in red, the
school polygon in yellow and every OSM building outlined. Buildings outside
the current boundary get X01.. ids (saved to data/raw/outside_buildings.geojson).
"""
import importlib
import math

from PIL import Image, ImageDraw
from shapely.geometry import LineString, Polygon, box, mapping, shape
from shapely.ops import polygonize, unary_union

from common import ATTRIBUTION, OUTPUT, RAW, TO_UTM, TO_WGS, ensure_dirs, get_with_retry, load_json, reproject, save_json
from render_common import font, label_box

sat = importlib.import_module("04_satellite")
fetch_osm = importlib.import_module("02_fetch_osm")

OVERPASS = "https://overpass-api.de/api/interpreter"
SCHOOL_WAY = 158321649
WIDE_RAW = RAW / "osm_wide_buildings.json"
PAD_M = 40


def main():
    ensure_dirs()
    boundary = shape(load_json(RAW / "boundary.geojson")["features"][0]["geometry"])
    wide = load_json(RAW / "wide_named_buildings.json")
    school_el = next(e for e in wide["elements"] if e["type"] == "way" and e["id"] == SCHOOL_WAY)
    school = Polygon([(p["lon"], p["lat"]) for p in school_el["geometry"]])

    # Wider bbox in meters, padded.
    bm = unary_union([reproject(TO_UTM, boundary), reproject(TO_UTM, school)]).bounds
    wbox = reproject(TO_WGS, box(bm[0] - PAD_M - 50, bm[1] - PAD_M - 50, bm[2] + PAD_M + 50, bm[3] + PAD_M + 50))
    lo, la, hi, ha = wbox.bounds
    bbox = {"min_lon": lo, "min_lat": la, "max_lon": hi, "max_lat": ha}

    if WIDE_RAW.exists():
        j = load_json(WIDE_RAW)
    else:
        q = f'[out:json][timeout:120][bbox:{la},{lo},{ha},{hi}];(nwr["building"];);out geom;'
        print("overpass: buildings in wider bbox")
        j = get_with_retry(OVERPASS, data={"data": q}).json()
        save_json(WIDE_RAW, j, indent=None)

    img, _, bounds = sat.stitch(bbox, 19)
    lon_w, lat_s, lon_e, lat_n = bounds
    z = 19
    n = 2 ** z * 256

    def merc(lon, lat):
        return ((lon + 180) / 360 * n,
                (1 - math.log(math.tan(math.radians(lat)) + 1 / math.cos(math.radians(lat))) / math.pi) / 2 * n)

    px0, py0 = merc(lon_w, lat_n)

    def xy(lon, lat):
        x, y = merc(lon, lat)
        return (x - px0, y - py0)

    def ring(geom):
        return [xy(*c) for c in geom.exterior.coords]

    def draw_poly(d, geom, **kw):
        if geom.geom_type == "Polygon":
            d.polygon(ring(geom), **kw)
        else:
            for g in geom.geoms:
                draw_poly(d, g, **kw)

    img = img.convert("RGBA")
    ov = Image.new("RGBA", img.size, (0, 0, 0, 0))
    d = ImageDraw.Draw(ov, "RGBA")
    draw_poly(d, school, fill=(255, 230, 0, 35), outline=(255, 230, 0, 255), width=4)
    draw_poly(d, boundary, fill=(255, 40, 40, 25), outline=(255, 40, 40, 255), width=5)

    inside, outside = [], []
    for el in j["elements"]:
        if "building" not in el.get("tags", {}):
            continue
        g = fetch_osm.geom_of(el)
        if g is None or g.is_empty or g.geom_type not in ("Polygon", "MultiPolygon"):
            continue
        if g.intersects(boundary):
            inside.append((g, el))
            continue
        # Only plausible campus candidates: inside the school polygon or close to
        # the boundary, and not tagged as housing (the apartment complex to the west).
        if el["tags"].get("building") in ("apartments", "residential", "house"):
            continue
        near = reproject(TO_UTM, g).distance(reproject(TO_UTM, boundary)) < 40
        if g.intersects(school) or near:
            outside.append((g, el))
    outside.sort(key=lambda t: (-round(t[0].centroid.y * 111000 / 40), t[0].centroid.x))
    for g, el in inside:
        draw_poly(d, g, outline=(90, 255, 90, 230), width=3)
    feats = []
    for i, (g, el) in enumerate(outside, 1):
        xid = f"X{i:02d}"
        draw_poly(d, g, fill=(0, 220, 255, 45), outline=(0, 220, 255, 255), width=3)
        feats.append({"type": "Feature", "properties": {"id": xid, "osm_type": el["type"], "osm_id": el["id"], **el.get("tags", {})}, "geometry": mapping(g)})
    save_json(RAW / "outside_buildings.geojson", {"type": "FeatureCollection", "features": feats}, indent=None)

    img = Image.alpha_composite(img, ov)
    d = ImageDraw.Draw(img, "RGBA")
    f = font(26)
    for i, (g, el) in enumerate(outside, 1):
        c = g.centroid
        label_box(d, xy(c.x, c.y), f"X{i:02d}", f, fg=(0, 0, 0, 255), bg=(0, 220, 255, 235), pad=5)
    # Scale bar + north arrow (0.29 m/px at this latitude and zoom).
    mpp = 156543.03 * math.cos(math.radians((lat_s + lat_n) / 2)) / 2 ** z
    L = 100 / mpp
    x, y = 40, img.size[1] - 60
    d.rectangle((x, y - 10, x + L, y), fill=(0, 0, 0, 255))
    d.rectangle((x, y - 10, x + L / 2, y), fill=(255, 255, 255, 255), outline=(0, 0, 0, 255))
    label_box(d, (x + L / 2, y - 32), "100 m", f)
    ax = x + L + 90
    d.polygon([(ax, y - 70), (ax - 16, y), (ax, y - 18), (ax + 16, y)], fill=(255, 255, 255, 255), outline=(0, 0, 0, 255))
    label_box(d, (ax, y - 100), "N", f)
    label_box(d, (img.size[0] / 2, 40), "red = VNR boundary   yellow = VJ Public School   green = OSM bldg inside   cyan X = outside", font(22))
    d.text((8, img.size[1] - 22), ATTRIBUTION, font=font(16), fill=(255, 255, 255, 255))
    out = OUTPUT / "boundary_check.png"
    img.convert("RGB").save(out)
    print(f"wrote {out.relative_to(OUTPUT.parent)} ({img.size[0]}x{img.size[1]}); {len(inside)} inside, {len(outside)} outside")
    for fe in feats:
        p = fe["properties"]
        print(f"  {p['id']}  {p.get('name', '')}")


if __name__ == "__main__":
    main()
