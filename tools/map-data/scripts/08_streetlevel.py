"""Street-level imagery coverage check (metadata only, no image downloads).

Samples a point every 15 m along campus roads + paths, then asks:
  - Google Street View Static API *metadata* endpoint (free) per point,
    needs env GOOGLE_MAPS_API_KEY
  - Mapillary Graph API for images in the campus bbox, needs env MAPILLARY_TOKEN
Writes data/streetlevel/{samples,streetview,mapillary}.json (cached; delete to
re-query) and output/streetlevel_coverage.png, and prints coverage percentages.
"""
import os
import time

from PIL import Image, ImageDraw
from shapely.geometry import Point, shape

from common import DATA, OUTPUT, PROCESSED, RAW, TO_WGS, get_with_retry, load_json, save_json
from render_common import SatelliteMapper, attribution, draw_geom, font, label_box, load_layer

SL = DATA / "streetlevel"
STEP_M = 15
SV_NEAR_M = 20   # a pano this close counts as covering the sample point
MLY_NEAR_M = 20
SV_META = "https://maps.googleapis.com/maps/api/streetview/metadata"
MLY_TILES = "https://tiles.mapillary.com/maps/vtp/mly1_public/2/{z}/{x}/{y}"


def sample_points():
    meta = load_json(PROCESSED / "meta.json")
    ox, oy = meta["origin_utm"]["x"], meta["origin_utm"]["y"]
    pts = []
    for layer in ("roads", "paths"):
        for g, p in load_layer(layer):
            lines = [g] if g.geom_type == "LineString" else list(getattr(g, "geoms", []))
            for ln in lines:
                if ln.geom_type != "LineString":
                    continue
                d = 0.0
                while d <= ln.length:
                    q = ln.interpolate(d)
                    lon, lat = TO_WGS.transform(q.x + ox, q.y + oy)
                    pts.append({"i": len(pts), "layer": layer, "osm_id": p["osm_id"], "x": round(q.x, 1), "y": round(q.y, 1),
                                "lon": round(lon, 7), "lat": round(lat, 7)})
                    d += STEP_M
    return pts


def streetview(pts, key):
    cache = SL / "streetview.json"
    done = load_json(cache) if cache.exists() else {}
    for p in pts:
        k = str(p["i"])
        if k in done:
            continue
        r = get_with_retry(SV_META, params={"location": f"{p['lat']},{p['lon']}", "radius": SV_NEAR_M, "source": "outdoor", "key": key},
                           min_interval=0.05, timeout=30)
        j = r.json()
        rec = {"status": j.get("status")}
        if j.get("status") == "OK":
            loc = j.get("location", {})
            plat, plon = loc.get("lat"), loc.get("lng")
            from common import TO_UTM
            px, py = TO_UTM.transform(plon, plat)
            meta = load_json(PROCESSED / "meta.json")
            dist = Point(px - meta["origin_utm"]["x"], py - meta["origin_utm"]["y"]).distance(Point(p["x"], p["y"]))
            rec.update({"pano_id": j.get("pano_id"), "date": j.get("date"), "lat": plat, "lon": plon, "distance_m": round(dist, 1)})
        done[k] = rec
        if len(done) % 25 == 0:
            save_json(cache, done)
    save_json(cache, done)
    return done


def mapillary(bbox, token):
    """Image points from Mapillary's public vector tiles (z14). The Graph API's
    images?bbox= search returned nothing even for well-covered cities with this
    token, while the tiles the web map uses work fine."""
    import math
    import mapbox_vector_tile as mvt

    cache = SL / "mapillary.json"
    if cache.exists():
        return load_json(cache)
    z, n = 14, 2 ** 14

    def tile(lon, lat):
        return (int((lon + 180) / 360 * n),
                int((1 - math.log(math.tan(math.radians(lat)) + 1 / math.cos(math.radians(lat))) / math.pi) / 2 * n))

    x0, y1 = tile(bbox["min_lon"], bbox["min_lat"])
    x1, y0 = tile(bbox["max_lon"], bbox["max_lat"])
    out = []
    for tx in range(x0, x1 + 1):
        for ty in range(y0, y1 + 1):
            r = get_with_retry(MLY_TILES.format(z=z, x=tx, y=ty), params={"access_token": token}, timeout=60)
            layers = mvt.decode(r.content)
            img = layers.get("image")
            if not img:
                continue
            ext = img["extent"]
            for f in img["features"]:
                px, py = f["geometry"]["coordinates"]  # y grows upward (decoder default)
                lon = (tx + px / ext) / n * 360 - 180
                lat = math.degrees(math.atan(math.sinh(math.pi * (1 - 2 * (ty + (ext - py) / ext) / n))))
                if not (bbox["min_lon"] <= lon <= bbox["max_lon"] and bbox["min_lat"] <= lat <= bbox["max_lat"]):
                    continue
                p = f["properties"]
                out.append({"id": p.get("id"), "lon": round(lon, 7), "lat": round(lat, 7), "captured_at": p.get("captured_at"),
                            "compass_angle": p.get("compass_angle"), "is_pano": p.get("is_pano"), "sequence": p.get("sequence_id")})
    save_json(cache, out)
    return out


def main():
    SL.mkdir(exist_ok=True)
    bbox = load_json(RAW / "bbox.json")
    pts = sample_points()
    save_json(SL / "samples.json", pts, indent=None)
    print(f"{len(pts)} sample points every {STEP_M} m")

    sv = None
    key = os.environ.get("GOOGLE_MAPS_API_KEY")
    if key:
        sv = streetview(pts, key)
        panos = {r["pano_id"] for r in sv.values() if r.get("pano_id")}
        print(f"street view: {sum(1 for r in sv.values() if r['status'] == 'OK')} points covered, {len(panos)} unique panos")
    else:
        print("!! GOOGLE_MAPS_API_KEY not set: skipping Street View")

    mly = None
    tok = os.environ.get("MAPILLARY_TOKEN")
    if tok:
        mly = mapillary(bbox, tok)
        print(f"mapillary: {len(mly)} images in bbox")
    else:
        print("!! MAPILLARY_TOKEN not set: skipping Mapillary")

    # Coverage per point.
    meta = load_json(PROCESSED / "meta.json")
    ox, oy = meta["origin_utm"]["x"], meta["origin_utm"]["y"]
    from common import TO_UTM
    mly_pts = []
    if mly:
        for m in mly:
            x, y = TO_UTM.transform(m["lon"], m["lat"])
            mly_pts.append(Point(x - ox, y - oy))
    sv_cov = mly_cov = 0
    for p in pts:
        p["sv"] = bool(sv and sv.get(str(p["i"]), {}).get("status") == "OK")
        q = Point(p["x"], p["y"])
        p["mly"] = any(q.distance(m) <= MLY_NEAR_M for m in mly_pts)
        sv_cov += p["sv"]
        mly_cov += p["mly"]
    save_json(SL / "samples.json", pts, indent=None)
    n = len(pts)
    print(f"coverage: street view {100 * sv_cov / n:.0f}%  mapillary {100 * mly_cov / n:.0f}%  either {100 * sum(1 for p in pts if p['sv'] or p['mly']) / n:.0f}%  none {100 * sum(1 for p in pts if not (p['sv'] or p['mly'])) / n:.0f}%")

    # Render.
    m = SatelliteMapper()
    img = m.image()
    d = ImageDraw.Draw(img, "RGBA")
    for g, _ in load_layer("roads") + load_layer("paths"):
        draw_geom(d, m, g, outline=(200, 200, 200, 220), width=4)
    for mp in mly_pts:
        x, y = m.xy(mp.x, mp.y)
        d.ellipse((x - 3, y - 3, x + 3, y + 3), fill=(60, 120, 255, 200))
    for p in pts:
        x, y = m.xy(p["x"], p["y"])
        col = (40, 220, 60, 255) if p["sv"] else (60, 120, 255, 255) if p["mly"] else (255, 50, 50, 255)
        d.ellipse((x - 5, y - 5, x + 5, y + 5), fill=col, outline=(0, 0, 0, 255))
    legend = f"green = Street View ({100 * sv_cov / n:.0f}%)   blue = Mapillary ({100 * mly_cov / n:.0f}%)   red = none"
    if not key:
        legend += "   [Street View skipped: no key]"
    if not tok:
        legend += "   [Mapillary skipped: no token]"
    label_box(d, (img.size[0] / 2, 30), legend, font(18))
    attribution(d, m)
    img.convert("RGB").save(OUTPUT / "streetlevel_coverage.png")
    print("wrote output/streetlevel_coverage.png")


if __name__ == "__main__":
    main()
