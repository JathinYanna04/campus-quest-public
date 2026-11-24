"""Step 2: fetch every OSM feature inside the padded bbox via Overpass and split it
into cleaned, boundary-clipped GeoJSON layers in data/osm/.

Re-running uses data/raw/osm_raw.json if it exists (delete it to re-fetch).
"""
import re

from shapely.geometry import LineString, Point, Polygon, mapping, shape
from shapely.ops import polygonize, unary_union

from common import OSM, RAW, ensure_dirs, get_with_retry, load_json, save_json

OVERPASS = "https://overpass-api.de/api/interpreter"
RAW_FILE = RAW / "osm_raw.json"
BUILDING_TAGS = ("name", "building", "building:levels", "height", "roof:shape")
NAME_RE = re.compile(r"block|bhavan|lab|hall|canteen", re.I)


def fetch(bbox):
    if RAW_FILE.exists():
        print("using cached data/raw/osm_raw.json")
        return load_json(RAW_FILE)
    b = f"{bbox['min_lat']},{bbox['min_lon']},{bbox['max_lat']},{bbox['max_lon']}"
    q = f"""
[out:json][timeout:120][bbox:{b}];
(
  nwr["building"];
  nwr["highway"];
  nwr["amenity"="parking"];
  nwr["leisure"];
  nwr["landuse"];
  nwr["natural"];
  nwr["barrier"];
  nwr["entrance"];
  nwr["amenity"];
  nwr["name"~"block|bhavan|lab|hall|canteen",i];
);
out geom;
"""
    print("overpass: fetching features")
    r = get_with_retry(OVERPASS, data={"data": q}, tries=6, timeout=240)
    j = r.json()
    save_json(RAW_FILE, j, indent=None)
    return j


def geom_of(el):
    """Shapely geometry for an Overpass element with `out geom`."""
    t = el["type"]
    if t == "node":
        return Point(el["lon"], el["lat"])
    if t == "way":
        pts = [(p["lon"], p["lat"]) for p in el.get("geometry", [])]
        if len(pts) < 2:
            return None
        tags = el.get("tags", {})
        closed = pts[0] == pts[-1] and len(pts) >= 4
        is_area = closed and tags.get("area") != "no" and not (
            tags.get("highway") and tags.get("area") != "yes" and tags.get("highway") != "pedestrian"
        ) and not tags.get("barrier")
        return Polygon(pts) if is_area else LineString(pts)
    if t == "relation":
        outers, inners = [], []
        for m in el.get("members", []):
            g = m.get("geometry")
            if not g:
                continue
            line = LineString([(p["lon"], p["lat"]) for p in g])
            (inners if m.get("role") == "inner" else outers).append(line)
        polys = list(polygonize(unary_union(outers))) if outers else []
        if not polys:
            return None
        geom = unary_union(polys)
        if inners:
            holes = list(polygonize(unary_union(inners)))
            if holes:
                geom = geom.difference(unary_union(holes))
        return geom
    return None


def classify(tags, geom):
    """Return the layer name for a feature, or None to drop it."""
    gt = geom.geom_type
    if "building" in tags and gt in ("Polygon", "MultiPolygon"):
        return "buildings"
    hw = tags.get("highway")
    if hw:
        if hw in ("footway", "path", "steps", "pedestrian", "cycleway", "corridor"):
            return "paths"
        return "roads"
    if tags.get("natural") == "tree":
        return "trees"
    if tags.get("natural") == "water" or tags.get("water") or tags.get("landuse") in ("reservoir", "basin") or tags.get("leisure") == "swimming_pool":
        return "water"
    if tags.get("amenity") == "parking" or tags.get("leisure") in ("pitch", "track", "sports_centre", "playground", "stadium"):
        return "open_areas"
    if tags.get("landuse") in ("grass", "forest", "orchard", "meadow", "village_green", "recreation_ground") or tags.get("natural") in ("wood", "scrub", "grassland", "heath") or tags.get("leisure") in ("park", "garden"):
        return "green"
    if tags.get("barrier") or tags.get("entrance"):
        return "barriers"
    if gt == "Point" and (tags.get("amenity") or tags.get("name")):
        return "pois"
    if tags.get("name") and NAME_RE.search(tags["name"]):
        return "pois"
    if tags.get("amenity") in ("university", "college", "school"):
        return None  # neighbouring institutions' grounds, not campus features
    if tags.get("landuse") or tags.get("leisure"):
        return "open_areas"
    return None


def feature(el, geom, tags):
    props = {"osm_type": el["type"], "osm_id": el["id"]}
    props.update(tags)
    return {"type": "Feature", "properties": props, "geometry": mapping(geom)}


def main():
    ensure_dirs()
    bbox = load_json(RAW / "bbox.json")
    boundary = shape(load_json(RAW / "boundary.geojson")["features"][0]["geometry"])
    j = fetch(bbox)

    layers = {k: [] for k in ("buildings", "roads", "paths", "open_areas", "green", "water", "trees", "barriers", "pois")}
    roads_unclipped = []
    skipped = 0
    for el in j["elements"]:
        tags = el.get("tags")
        if not tags:
            continue
        geom = geom_of(el)
        if geom is None or geom.is_empty or not geom.is_valid:
            geom = geom.buffer(0) if geom is not None and not geom.is_valid else geom
            if geom is None or geom.is_empty:
                skipped += 1
                continue
        layer = classify(tags, geom)
        if layer is None:
            skipped += 1
            continue
        if layer == "buildings":
            tags = {k: v for k, v in tags.items() if k in BUILDING_TAGS or k.startswith("addr:")}
        if layer == "roads":
            roads_unclipped.append(feature(el, geom, tags))
        clipped = geom.intersection(boundary)
        if clipped.is_empty:
            continue
        # Keep buildings whole if they touch the boundary; clipping half a building is useless.
        if layer == "buildings":
            clipped = geom
        layers[layer].append(feature(el, clipped, tags))

    for name, feats in layers.items():
        save_json(OSM / f"{name}.geojson", {"type": "FeatureCollection", "features": feats}, indent=None)
        print(f"  {name}: {len(feats)}")
    save_json(OSM / "roads_unclipped.geojson", {"type": "FeatureCollection", "features": roads_unclipped}, indent=None)
    print(f"  roads_unclipped: {len(roads_unclipped)}   (skipped {skipped} untagged/unclassified elements)")


if __name__ == "__main__":
    main()
