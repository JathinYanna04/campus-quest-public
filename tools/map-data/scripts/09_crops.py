"""Crop the satellite image around every building (B..) and missing candidate
(M..) with ~30 m of context, outlined, to output/crops/<id>.png. Also prints
each one's size and position relative to the reference blocks.
"""
import math

from PIL import Image, ImageDraw
from shapely.ops import unary_union

from common import OUTPUT, PROCESSED, load_json
from render_common import SatelliteMapper, draw_geom, font, label_box, load_layer

CONTEXT_M = 30
SCALE = 2.0
REFS = {"B10": "B Block", "B13": "PG Block", "B16": "D Block"}
MERGE = {("M01", "M02"): "M01+M02"}  # treat the two ends of the long shed as one


def rel(c, refs):
    parts = []
    for rid, name in refs.items():
        if rid not in refs_c:
            continue
        rc = refs_c[rid]
        dx, dy = c.x - rc.x, c.y - rc.y
        dist = math.hypot(dx, dy)
        ang = (math.degrees(math.atan2(dx, dy)) + 360) % 360
        comp = ["N", "NE", "E", "SE", "S", "SW", "W", "NW"][int((ang + 22.5) // 45) % 8]
        parts.append(f"{dist:.0f} m {comp} of {name}")
    return "; ".join(parts)


def main():
    (OUTPUT / "crops").mkdir(exist_ok=True)
    m = SatelliteMapper(scale=SCALE)
    base = m.image()
    items = {p["id"]: (g, p) for g, p in load_layer("buildings")}
    missing = {p["id"]: (g, p) for g, p in load_layer("missing_candidates")}
    for pair, name in MERGE.items():
        if all(k in missing for k in pair):
            g = unary_union([missing[k][0] for k in pair])
            missing[name] = (g, {"id": name, "area_m2": round(g.area, 1)})
            for k in pair:
                del missing[k]
    items.update(missing)
    global refs_c
    refs_c = {k: items[k][0].centroid for k in REFS if k in items}

    f = font(28)
    for bid, (g, p) in items.items():
        minx, miny, maxx, maxy = g.bounds
        x0, y0 = m.xy(minx - CONTEXT_M, maxy + CONTEXT_M)
        x1, y1 = m.xy(maxx + CONTEXT_M, miny - CONTEXT_M)
        crop = base.crop((int(x0), int(y0), int(x1), int(y1)))
        ov = Image.new("RGBA", crop.size, (0, 0, 0, 0))
        d = ImageDraw.Draw(ov, "RGBA")

        class Local:
            def xy(self_, mx, my):
                px, py = m.xy(mx, my)
                return (px - int(x0), py - int(y0))

        loc = Local()
        for oid, (og, op) in items.items():
            if oid != bid and og.intersects(g.buffer(CONTEXT_M)):
                draw_geom(d, loc, og, outline=(255, 255, 255, 140), width=2)
        draw_geom(d, loc, g, fill=(255, 0, 200, 40), outline=(255, 0, 200, 255), width=5)
        crop = Image.alpha_composite(crop, ov)
        d = ImageDraw.Draw(crop, "RGBA")
        for oid, (og, op) in items.items():
            if oid != bid and og.intersects(g.buffer(CONTEXT_M)):
                c = og.centroid
                label_box(d, loc.xy(c.x, c.y), oid, font(18), bg=(0, 0, 0, 150))
        label_box(d, (crop.size[0] / 2, 24), bid, f, fg=(0, 0, 0, 255), bg=(255, 0, 200, 230), pad=6)
        # 10 m scale bar
        L = 10 * SCALE / m.meta["m_per_px"]["x"]
        d.rectangle((10, crop.size[1] - 18, 10 + L, crop.size[1] - 10), fill=(255, 255, 255, 255), outline=(0, 0, 0, 255))
        d.text((12, crop.size[1] - 40), "10 m", font=font(16), fill=(255, 255, 255, 255))
        crop.convert("RGB").save(OUTPUT / "crops" / f"{bid}.png")
        c = g.centroid
        size = f"{p.get('mrr_long_m', '?')}x{p.get('mrr_short_m', '?')} m" if "mrr_long_m" in p else f"{p['area_m2']} m²"
        print(f"{bid:8} {size:16} lv={p.get('building:levels', '-'):3} {p.get('name', '')!s:45} {rel(c, REFS)}")


if __name__ == "__main__":
    main()
