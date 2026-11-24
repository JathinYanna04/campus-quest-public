"""Step 1b: widen data/raw/boundary.geojson to include chosen outside buildings
(X ids from data/raw/outside_buildings.geojson, written by 07_boundary_check.py).

Usage: 01b_widen_boundary.py X01 X02 ...
The original OSM polygon is kept in data/raw/boundary_osm.geojson. The new
boundary is the convex hull of the OSM polygon plus the chosen buildings,
minus the outside buildings not chosen; bbox.json is recomputed.
"""
import sys

from shapely.geometry import box, mapping, shape
from shapely.ops import unary_union

from common import RAW, TO_UTM, TO_WGS, load_json, reproject, save_json

PAD_M = 50


def main(ids):
    osm_file = RAW / "boundary_osm.geojson"
    if not osm_file.exists():
        (RAW / "boundary.geojson").rename(osm_file)
    base_fc = load_json(osm_file)
    base = reproject(TO_UTM, shape(base_fc["features"][0]["geometry"]))
    outside = {f["properties"]["id"]: f for f in load_json(RAW / "outside_buildings.geojson")["features"]}
    chosen = []
    for i in ids:
        if i not in outside:
            sys.exit(f"unknown id {i}")
        chosen.append(reproject(TO_UTM, shape(outside[i]["geometry"])).buffer(15))
    widened = unary_union([base] + chosen).convex_hull
    # Carve out the outside buildings that were NOT chosen so they stay excluded.
    others = [reproject(TO_UTM, shape(f["geometry"])).buffer(8) for k, f in outside.items() if k not in ids]
    if others:
        widened = widened.difference(unary_union(others))
        if widened.geom_type != "Polygon":
            widened = max(widened.geoms, key=lambda g: g.area)
    wgs = reproject(TO_WGS, widened)
    save_json(RAW / "boundary.geojson", {"type": "FeatureCollection", "features": [
        {"type": "Feature", "properties": {**base_fc["features"][0]["properties"], "widened_with": ids}, "geometry": mapping(wgs)}]})
    save_json(RAW / "added_buildings.geojson", {"type": "FeatureCollection", "features": [outside[i] for i in ids]}, indent=None)
    minx, miny, maxx, maxy = widened.bounds
    padded = reproject(TO_WGS, box(minx - PAD_M, miny - PAD_M, maxx + PAD_M, maxy + PAD_M))
    blon, blat, elon, elat = padded.bounds
    old = load_json(RAW / "bbox.json")
    save_json(RAW / "bbox.json", {**old, "min_lat": blat, "max_lat": elat, "min_lon": blon, "max_lon": elon, "widened_with": ids})
    print(f"boundary: {base.area:,.0f} -> {widened.area:,.0f} m², extent {maxx - minx:.0f} x {maxy - miny:.0f} m")


if __name__ == "__main__":
    main(sys.argv[1:])
