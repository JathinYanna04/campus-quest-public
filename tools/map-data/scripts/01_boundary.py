"""Step 1: geocode the campus with Nominatim and fetch its boundary polygon from Overpass.

Outputs data/raw/boundary.geojson and data/raw/bbox.json (padded ~50 m).
Falls back to a ~600 m box around the geocoded point if no polygon is found.
"""
import math
import sys

from shapely.geometry import shape, mapping, Point, box

from common import RAW, TO_UTM, TO_WGS, ensure_dirs, get_with_retry, load_json, reproject, save_json

NOMINATIM = "https://nominatim.openstreetmap.org/search"
OVERPASS = "https://overpass-api.de/api/interpreter"
GEOCODE_CACHE = RAW / "nominatim.json"
OVERPASS_CACHE = RAW / "boundary_overpass.json"

QUERIES = [
    "VNR Vignana Jyothi Institute of Engineering and Technology Hyderabad",
    "VNR Vignana Jyothi Institute of Engineering and Technology, Bachupally, Hyderabad",
    "VNR Vignana Jyothi, Hyderabad",
    "VNRVJIET Bachupally",
]
PAD_M = 50
FALLBACK_HALF_M = 600


def geocode():
    if GEOCODE_CACHE.exists():
        return load_json(GEOCODE_CACHE)
    for q in QUERIES:
        print(f"nominatim: {q}")
        r = get_with_retry(NOMINATIM, params={"q": q, "format": "json", "limit": 5}, min_interval=1.1)
        results = r.json()
        if results:
            save_json(GEOCODE_CACHE, results)
            return results
    sys.exit("Nominatim returned nothing for any query variant")


def overpass_boundary(lat, lon):
    if OVERPASS_CACHE.exists():
        return load_json(OVERPASS_CACHE)
    q = f"""
[out:json][timeout:60];
(
  wr["amenity"~"university|college"]["name"~"VNR|Vignana Jyothi|VNRVJIET",i](around:1500,{lat},{lon});
  wr["landuse"]["name"~"VNR|Vignana Jyothi|VNRVJIET",i](around:1500,{lat},{lon});
  wr["name"~"VNR|Vignana Jyothi|VNRVJIET",i](around:1500,{lat},{lon});
);
out geom;
"""
    print("overpass: searching for boundary polygon")
    r = get_with_retry(OVERPASS, data={"data": q})
    j = r.json()
    save_json(OVERPASS_CACHE, j)
    return j


def element_to_polygon(el):
    if el["type"] == "way" and el.get("geometry"):
        pts = [(p["lon"], p["lat"]) for p in el["geometry"]]
        if len(pts) >= 4 and pts[0] == pts[-1]:
            from shapely.geometry import Polygon
            return Polygon(pts)
    if el["type"] == "relation":
        from shapely.geometry import Polygon
        from shapely.ops import unary_union, polygonize
        lines = []
        for m in el.get("members", []):
            if m.get("role") == "outer" and m.get("geometry"):
                lines.append([(p["lon"], p["lat"]) for p in m["geometry"]])
        from shapely.geometry import LineString
        polys = list(polygonize(unary_union([LineString(l) for l in lines])))
        if polys:
            return unary_union(polys)
    return None


def main():
    ensure_dirs()
    results = geocode()
    best = results[0]
    lat, lon = float(best["lat"]), float(best["lon"])
    print(f"geocoded: {best['display_name']}\n  {lat}, {lon}  ({best['osm_type']} {best['osm_id']}, {best.get('class')}={best.get('type')})")

    j = overpass_boundary(lat, lon)
    candidates = []
    for el in j.get("elements", []):
        poly = element_to_polygon(el)
        if poly is None or poly.is_empty:
            continue
        tags = el.get("tags", {})
        candidates.append((poly, el, tags))
    # Prefer amenity=university/college, then the largest polygon containing the point.
    pt = Point(lon, lat)
    candidates.sort(key=lambda c: (c[2].get("amenity") not in ("university", "college"), not c[0].contains(pt), -c[0].area))

    fallback = False
    if candidates:
        poly, el, tags = candidates[0]
        print(f"boundary: {el['type']} {el['id']} tags={ {k: v for k, v in tags.items() if k in ('name', 'amenity', 'landuse')} }")
        props = {"osm_type": el["type"], "osm_id": el["id"], **tags}
    else:
        fallback = True
        print("!! no boundary polygon found; using a ~600 m box around the geocoded point. Adjust data/raw/boundary.geojson by hand.")
        cx, cy = TO_UTM.transform(lon, lat)
        poly = reproject(TO_WGS, box(cx - FALLBACK_HALF_M, cy - FALLBACK_HALF_M, cx + FALLBACK_HALF_M, cy + FALLBACK_HALF_M))
        props = {"fallback": True}

    save_json(RAW / "boundary.geojson", {
        "type": "FeatureCollection",
        "features": [{"type": "Feature", "properties": props, "geometry": mapping(poly)}],
    })

    utm = reproject(TO_UTM, poly)
    minx, miny, maxx, maxy = utm.bounds
    padded = reproject(TO_WGS, box(minx - PAD_M, miny - PAD_M, maxx + PAD_M, maxy + PAD_M))
    blon, blat, elon, elat = padded.bounds
    save_json(RAW / "bbox.json", {
        "min_lat": blat, "max_lat": elat, "min_lon": blon, "max_lon": elon,
        "pad_m": PAD_M, "fallback": fallback, "center": {"lat": lat, "lon": lon},
    })
    print(f"area: {utm.area:,.0f} m²  ({utm.area / 10000:.1f} ha)")
    print(f"extent: {maxx - minx:.0f} m east-west x {maxy - miny:.0f} m north-south")
    mrr = utm.minimum_rotated_rectangle
    xs, ys = mrr.exterior.coords.xy
    e1 = math.dist((xs[0], ys[0]), (xs[1], ys[1]))
    e2 = math.dist((xs[1], ys[1]), (xs[2], ys[2]))
    print(f"min rotated rectangle: {max(e1, e2):.0f} m x {min(e1, e2):.0f} m")


if __name__ == "__main__":
    main()
