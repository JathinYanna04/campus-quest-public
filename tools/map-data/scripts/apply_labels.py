"""Step 6b: after data/labels.json is filled in, merge labels into
data/processed/campus_final.geojson and render output/labeled_map.png.

- B.. entries with include=false are dropped.
- M.. entries with include=true are added as buildings using the polygon traced
  from the satellite detection (data/processed/missing_candidates.geojson).
"""
from PIL import Image, ImageDraw
from shapely.geometry import mapping, shape

from common import DATA, OUTPUT, PROCESSED, load_json, save_json
from render_common import SatelliteMapper, attribution, draw_geom, font, label_box, load_layer


def main():
    labels = load_json(DATA / "labels.json")
    feats = []
    for f in load_json(PROCESSED / "buildings.geojson")["features"]:
        p = f["properties"]
        lb = labels.get(p["id"], {})
        if not lb.get("include", True):
            continue
        p = {**p, "label": lb.get("label", ""), "notes": lb.get("notes", ""), "source": "osm"}
        feats.append({"type": "Feature", "properties": p, "geometry": f["geometry"]})
    mc = PROCESSED / "missing_candidates.geojson"
    if mc.exists():
        for f in load_json(mc)["features"]:
            p = f["properties"]
            lb = labels.get(p["id"], {})
            if not lb.get("include"):
                continue
            g = shape(f["geometry"])
            # Simplify to a cleaner footprint: the minimum rotated rectangle is a
            # decent stand-in for most rooftops; keep the traced polygon too.
            c = g.centroid
            p = {**p, "label": lb.get("label", ""), "notes": lb.get("notes", ""), "source": "satellite",
                 "centroid_x": round(c.x, 1), "centroid_y": round(c.y, 1)}
            feats.append({"type": "Feature", "properties": p, "geometry": mapping(g.minimum_rotated_rectangle)})
    save_json(PROCESSED / "campus_final.geojson", {"type": "FeatureCollection", "features": feats}, indent=None)
    labelled = sum(1 for f in feats if f["properties"]["label"])
    print(f"{len(feats)} buildings in campus_final.geojson, {labelled} labelled")

    m = SatelliteMapper(scale=2.0)
    img = m.image()
    ov = Image.new("RGBA", img.size, (0, 0, 0, 0))
    d = ImageDraw.Draw(ov, "RGBA")
    for f in feats:
        g = shape(f["geometry"])
        col = (255, 255, 0) if f["properties"]["source"] == "osm" else (0, 230, 255)
        draw_geom(d, m, g, fill=col + (50,), outline=col + (255,), width=3)
    img = Image.alpha_composite(img, ov)
    d = ImageDraw.Draw(img, "RGBA")
    big, small = font(30), font(20)
    for f in feats:
        g = shape(f["geometry"])
        c = g.centroid
        p = f["properties"]
        text = p["label"] or p["id"]
        label_box(d, m.xy(c.x, c.y), text, big if p["label"] else small, fg=(0, 0, 0, 255),
                  bg=(255, 255, 255, 235) if p["label"] else (255, 120, 120, 220), pad=6)
    attribution(d, m, font(22))
    img.convert("RGB").save(OUTPUT / "labeled_map.png")
    print("wrote output/labeled_map.png")


if __name__ == "__main__":
    main()
