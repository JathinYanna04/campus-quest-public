"""Step 3: reproject data/osm/*.geojson to UTM 44N (EPSG:32644, meters) into
data/processed/, and build buildings_table.csv plus meta.json.

Coordinates in processed files are in meters relative to `origin` in meta.json
(origin = south-west corner of the padded bbox), so x grows east and y grows north.
"""
import csv
import math

from shapely.geometry import mapping, shape
from shapely.affinity import translate

from common import OSM, PROCESSED, RAW, TO_UTM, UTM_EPSG, ensure_dirs, load_json, reproject, save_json

LAYERS = ("buildings", "roads", "roads_unclipped", "paths", "open_areas", "green", "water", "trees", "barriers", "pois")


def mrr_dims(poly):
    mrr = poly.minimum_rotated_rectangle
    xs, ys = mrr.exterior.coords.xy
    e1 = math.dist((xs[0], ys[0]), (xs[1], ys[1]))
    e2 = math.dist((xs[1], ys[1]), (xs[2], ys[2]))
    # Orientation of the long edge, degrees counter-clockwise from east, in [0, 180).
    if e1 >= e2:
        ang = math.degrees(math.atan2(ys[1] - ys[0], xs[1] - xs[0]))
    else:
        ang = math.degrees(math.atan2(ys[2] - ys[1], xs[2] - xs[1]))
    return max(e1, e2), min(e1, e2), ang % 180


def main():
    ensure_dirs()
    bbox = load_json(RAW / "bbox.json")
    ox, oy = TO_UTM.transform(bbox["min_lon"], bbox["min_lat"])
    ex, ey = TO_UTM.transform(bbox["max_lon"], bbox["max_lat"])
    boundary = shape(load_json(RAW / "boundary.geojson")["features"][0]["geometry"])
    boundary_m = translate(reproject(TO_UTM, boundary), -ox, -oy)
    save_json(PROCESSED / "boundary.geojson", {"type": "FeatureCollection", "features": [
        {"type": "Feature", "properties": {}, "geometry": mapping(boundary_m)}]}, indent=None)

    buildings = []
    for layer in LAYERS:
        src = OSM / f"{layer}.geojson"
        if not src.exists():
            continue
        fc = load_json(src)
        out = []
        for f in fc["features"]:
            g = translate(reproject(TO_UTM, shape(f["geometry"])), -ox, -oy)
            f2 = {"type": "Feature", "properties": dict(f["properties"]), "geometry": mapping(g)}
            out.append(f2)
            if layer == "buildings":
                buildings.append((f2, g))
        if layer != "buildings":
            save_json(PROCESSED / f"{layer}.geojson", {"type": "FeatureCollection", "features": out}, indent=None)

    # Ids: sort north -> south (descending y), then west -> east. Rows are binned
    # every 40 m so buildings on roughly the same latitude go left to right.
    def key(item):
        c = item[1].centroid
        return (-round(c.y / 40), c.x)

    buildings.sort(key=key)
    # Keep ids stable across runs: reuse the id a building had last time
    # (matched by OSM id) and number new ones after the highest existing id.
    prev_file = PROCESSED / "buildings.geojson"
    prev = {}
    if prev_file.exists():
        for f in load_json(prev_file)["features"]:
            prev[(f["properties"]["osm_type"], f["properties"]["osm_id"])] = f["properties"]["id"]
    next_id = max([int(v[1:]) for v in prev.values()] + [0]) + 1
    rows, feats = [], []
    for f, g in buildings:
        k = (f["properties"]["osm_type"], f["properties"]["osm_id"])
        if k in prev:
            bid = prev[k]
        else:
            bid = f"B{next_id:02d}"
            next_id += 1
        c = g.centroid
        long_m, short_m, ang = mrr_dims(g)
        p = f["properties"]
        p.update({"id": bid, "centroid_x": round(c.x, 1), "centroid_y": round(c.y, 1), "area_m2": round(g.area, 1),
                  "mrr_long_m": round(long_m, 1), "mrr_short_m": round(short_m, 1), "orientation_deg": round(ang, 1)})
        feats.append(f)
        rows.append({
            "id": bid, "osm_type": p["osm_type"], "osm_id": p["osm_id"], "osm_name": p.get("name", ""),
            "building": p.get("building", ""), "levels": p.get("building:levels", ""), "height": p.get("height", ""),
            "centroid_x": p["centroid_x"], "centroid_y": p["centroid_y"], "area_m2": p["area_m2"],
            "mrr_long_m": p["mrr_long_m"], "mrr_short_m": p["mrr_short_m"], "orientation_deg": p["orientation_deg"],
        })
    feats.sort(key=lambda f: f["properties"]["id"])
    rows.sort(key=lambda r: r["id"])
    save_json(PROCESSED / "buildings.geojson", {"type": "FeatureCollection", "features": feats}, indent=None)
    with open(PROCESSED / "buildings_table.csv", "w", newline="") as fh:
        w = csv.DictWriter(fh, fieldnames=list(rows[0].keys()) if rows else ["id"])
        w.writeheader()
        w.writerows(rows)
    print(f"wrote data/processed/buildings_table.csv ({len(rows)} buildings)")

    bx = boundary_m.bounds
    save_json(PROCESSED / "meta.json", {
        "crs": UTM_EPSG, "units": "meters",
        "origin_utm": {"x": ox, "y": oy}, "origin_wgs84": {"lon": bbox["min_lon"], "lat": bbox["min_lat"]},
        "bbox_size_m": {"width": round(ex - ox, 1), "height": round(ey - oy, 1)},
        "campus_bounds_m": {"min_x": round(bx[0], 1), "min_y": round(bx[1], 1), "max_x": round(bx[2], 1), "max_y": round(bx[3], 1)},
        "campus_size_m": {"width": round(bx[2] - bx[0], 1), "height": round(bx[3] - bx[1], 1)},
        "campus_area_m2": round(boundary_m.area, 1),
        "building_count": len(rows),
    })
    for r in rows:
        print(f"  {r['id']}  {r['area_m2']:>7} m²  {r['mrr_long_m']:>5}x{r['mrr_short_m']:<5} m  lv={r['levels'] or '-':<3} {r['osm_name']}")


if __name__ == "__main__":
    main()
