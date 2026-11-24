"""Step 10: build data/processed/campus_final.geojson, the single list of
structures the pixel map renders, with game location ids and labels.

Footprints come only from the processed OSM data:
  - most buildings are used as-is (B01..B21)
  - B10 (Patrons Bhavan, one OSM polygon with three courtyards) is cut into
    three wings across its long axis -> A / B / C Block. The B-Block entrance
    sign photographed on Street View sits at the middle wing, so the middle is
    B Block; A (north) / C (south) is a PLACEHOLDER guess.
  - E Block = the large white building east of the main road whose roof is
    only mapped in OSM as four old workshop strips (B09, B11, B12, B14) plus
    rooftop candidates M05-M07. Its footprint is the minimum rotated rectangle
    of those strips. Needs confirmation.
Locations without a building (ground, canteen, main gate) are points/areas.

Anything marked "placeholder": true is a guess the user should confirm in
data/labels.json / LOCATION_RULES below.
"""
import math

from shapely.affinity import rotate
from shapely.geometry import LineString, Point, Polygon, box, mapping, shape
from shapely.ops import split, unary_union

from common import DATA, PROCESSED, load_json, save_json

# location id -> how to get its footprint. Edit here to move a label.
LOCATION_RULES = {
    # Confirmed by the user (2026-11-14): from SAC southwards the wings are C, B, A.
    "c-block": {"name": "C Block", "from": "B10", "wing": 0, "levels": 4, "placeholder": False},
    "b-block": {"name": "B Block", "from": "B10", "wing": 1, "levels": 4, "placeholder": False},
    "a-block": {"name": "A Block", "from": "B10", "wing": 2, "levels": 4, "placeholder": False},
    "d-block": {"name": "D Block", "from": "B16", "levels": 5, "placeholder": False},
    "e-block": {"name": "E Block", "from": ["B09", "B11", "B12", "B14"], "levels": 4, "placeholder": False},
    "pg-block": {"name": "PG Block", "from": "B13", "levels": 4, "placeholder": False},
    "siniti": {"name": "Siniti", "from": "B19", "levels": 3, "placeholder": True},
    "sac": {"name": "SAC", "from": "B08", "levels": 1, "placeholder": False},
    "sports-complex": {"name": "Sports Complex", "from": "B04", "levels": 2, "placeholder": False},
    "vjim": {"name": "VJIM", "from": "B01", "levels": 3, "placeholder": False},
}
# Locations whose footprint is not an OSM building.
#  - PEB: the big shed OSM mislabels as "VNR Tennis Court" (user-confirmed).
#  - Thati Bellam shop: across Medak Road from the main gate (user-described;
#    not in OSM). Box fitted between the road buffers.
EXTRA_BUILDINGS = {
    "peb": {"name": "PEB", "pitch_name": "VNR Tennis Court", "levels": 2, "style": "shed", "placeholder": False},
    "thatibellam": {"name": "Thati Bellam", "box": [352, 676, 372, 688], "levels": 1, "style": "shop", "placeholder": False,
                    "note": "small roadside shop opposite the main gate"},
}
# Point / area locations (meters, processed frame).
AREA_LOCATIONS = {
    "ground": {"name": "College Ground", "pitch_name": "VNR Football cum Cricket Ground", "placeholder": False},
    "canteen": {"name": "Canteen", "point": [169.0, 287.0], "placeholder": False,
                "note": "OSM fast_food POIs (Amul, Hungry Jacks) + Street View food shed at ~(169, 275)"},
    "main-gate": {"name": "Main Gate", "point": [367.0, 638.0], "placeholder": False, "note": "OSM barrier=gate"},
}
DEFAULT_LEVELS = {"roof": 0}  # canopies


def wings(poly, n=3):
    """Cut a polygon into n pieces of equal length along its long axis."""
    mrr = poly.minimum_rotated_rectangle
    xs, ys = mrr.exterior.coords.xy
    e = [(xs[i], ys[i], xs[i + 1], ys[i + 1]) for i in range(4)]
    long = max(e, key=lambda s: math.hypot(s[2] - s[0], s[3] - s[1]))
    ang = math.degrees(math.atan2(long[3] - long[1], long[2] - long[0]))
    c = poly.centroid
    r = rotate(poly, -ang, origin=c)  # long axis now along x
    minx, miny, maxx, maxy = r.bounds
    step = (maxx - minx) / n
    pieces = []
    for i in range(n):
        cut = box(minx + i * step, miny - 1, minx + (i + 1) * step, maxy + 1)
        pieces.append(rotate(r.intersection(cut), ang, origin=c))
    # order north -> south
    pieces.sort(key=lambda g: -g.centroid.y)
    return pieces


def main():
    blds = {f["properties"]["id"]: (shape(f["geometry"]), f["properties"]) for f in load_json(PROCESSED / "buildings.geojson")["features"]}
    labels = load_json(DATA / "labels.json")
    used = set()
    feats = []

    for loc, rule in LOCATION_RULES.items():
        src = rule["from"]
        if isinstance(src, list):
            geom = unary_union([blds[s][0] for s in src]).minimum_rotated_rectangle
            used.update(src)
            osm_ids = [blds[s][1]["osm_id"] for s in src]
        elif "wing" in rule:
            geom = wings(blds[src][0])[rule["wing"]]
            used.add(src)
            osm_ids = [blds[src][1]["osm_id"]]
        else:
            geom = blds[src][0]
            used.add(src)
            osm_ids = [blds[src][1]["osm_id"]]
        if geom.geom_type == "MultiPolygon":
            geom = max(geom.geoms, key=lambda g: g.area)
        feats.append({"type": "Feature", "geometry": mapping(geom), "properties": {
            "id": loc, "kind": "building", "location": loc, "label": rule["name"], "levels": rule["levels"],
            "source": src if isinstance(src, str) else "+".join(src), "osm_ids": osm_ids,
            "placeholder": rule["placeholder"], "area_m2": round(geom.area, 1)}})

    pitches_all = {pp.get("name"): gg for gg, pp in ((shape(f["geometry"]), f["properties"]) for f in load_json(PROCESSED / "open_areas.geojson")["features"])}
    for loc, rule in EXTRA_BUILDINGS.items():
        geom = pitches_all[rule["pitch_name"]] if "pitch_name" in rule else box(*rule["box"])
        feats.append({"type": "Feature", "geometry": mapping(geom), "properties": {
            "id": loc, "kind": "building", "location": loc, "label": rule["name"], "levels": rule["levels"],
            "style": rule["style"], "source": rule.get("pitch_name", "user"), "osm_ids": [],
            "placeholder": rule["placeholder"], "note": rule.get("note", ""), "area_m2": round(geom.area, 1)}})

    for bid, (g, p) in sorted(blds.items()):
        if bid in used or not labels.get(bid, {}).get("include", True):
            continue
        lv = p.get("building:levels")
        levels = int(lv) if lv else DEFAULT_LEVELS.get(p.get("building"), 1 if g.area < 300 else 2)
        feats.append({"type": "Feature", "geometry": mapping(g), "properties": {
            "id": bid, "kind": "canopy" if p.get("building") == "roof" else "building", "location": None,
            "label": labels.get(bid, {}).get("label", ""), "osm_name": p.get("name", ""), "levels": levels,
            "source": bid, "osm_ids": [p["osm_id"]], "placeholder": False, "area_m2": round(g.area, 1)}})

    pitches = {p.get("name"): g for g, p in ((shape(f["geometry"]), f["properties"]) for f in load_json(PROCESSED / "open_areas.geojson")["features"])}
    for loc, rule in AREA_LOCATIONS.items():
        if "pitch_name" in rule:
            g = pitches[rule["pitch_name"]]
            kind = "area"
        else:
            g = Point(rule["point"])
            kind = "point"
        feats.append({"type": "Feature", "geometry": mapping(g), "properties": {
            "id": loc, "kind": kind, "location": loc, "label": rule["name"], "placeholder": rule["placeholder"],
            "note": rule.get("note", "")}})

    # Sanity: no two buildings overlap (beyond slivers).
    bl = [(f["properties"]["id"], shape(f["geometry"])) for f in feats if f["properties"]["kind"] in ("building", "canopy")]
    for i in range(len(bl)):
        for j in range(i + 1, len(bl)):
            ov = bl[i][1].intersection(bl[j][1]).area
            if ov > 5:
                print(f"!! overlap {bl[i][0]} / {bl[j][0]}: {ov:.0f} m²")

    save_json(PROCESSED / "campus_final.geojson", {"type": "FeatureCollection", "features": feats}, indent=None)
    for f in feats:
        p = f["properties"]
        g = shape(f["geometry"])
        print(f"{p['id']:15} {p['kind']:8} {p.get('label', ''):16} lv={p.get('levels', '-')!s:2} src={p.get('source', '-')!s:16} "
              f"c=({g.centroid.x:.0f},{g.centroid.y:.0f}) {'PLACEHOLDER' if p['placeholder'] else ''}")


if __name__ == "__main__":
    main()
