"""Step 5: review renders in output/:
  osm_only.png        vector render with scale bar + north arrow
  overlay.png         OSM building outlines on the satellite image
  labeling_sheet.png  satellite + numbered building outlines (2x, for phone zoom)
  missing_check.png   rooftop-like regions not covered by OSM buildings (M01, ...)
Also writes data/processed/missing_candidates.geojson (meters) used by step 6.
"""
import cv2
import numpy as np
from PIL import Image, ImageDraw
from shapely.geometry import Polygon, mapping
from shapely.ops import unary_union

from common import OUTPUT, PROCESSED, TO_UTM, ensure_dirs, save_json
from render_common import (PlainMapper, SatelliteMapper, attribution, draw_geom, font, label_box, load_layer,
                           scale_bar_and_north)

MIN_ROOF_M2 = 120


def osm_only():
    ppm = 2.0
    m = PlainMapper(ppm)
    img = m.image()
    d = ImageDraw.Draw(img, "RGBA")
    for g, _ in load_layer("boundary"):
        draw_geom(d, m, g, fill=(235, 232, 222, 255), outline=(120, 60, 60, 255), width=3)
    for g, p in load_layer("green"):
        draw_geom(d, m, g, fill=(170, 210, 150, 255), outline=(120, 170, 100, 255))
    for g, p in load_layer("open_areas"):
        if p.get("amenity") == "parking":
            draw_geom(d, m, g, fill=(215, 215, 215, 255), outline=(150, 150, 150, 255))
        else:
            draw_geom(d, m, g, fill=(200, 225, 180, 255), outline=(80, 140, 60, 255), width=2)
    for g, _ in load_layer("water"):
        draw_geom(d, m, g, fill=(150, 190, 240, 255), outline=(70, 110, 190, 255))
    for g, p in load_layer("roads"):
        w = 6 if p.get("highway") in ("primary", "secondary", "tertiary", "residential", "unclassified") else 4
        draw_geom(d, m, g, outline=(80, 80, 80, 255), width=int(w * ppm / 2))
    for g, _ in load_layer("paths"):
        draw_geom(d, m, g, outline=(130, 110, 90, 255), width=2, dash=(8, 6))
    for g, p in load_layer("barriers"):
        draw_geom(d, m, g, outline=(140, 40, 40, 255), width=2, fill=(140, 40, 40, 255))
    for g, p in load_layer("buildings"):
        draw_geom(d, m, g, fill=(175, 175, 175, 255), outline=(50, 50, 50, 255), width=2)
    for g, _ in load_layer("trees"):
        draw_geom(d, m, g, fill=(40, 120, 40, 255), width=3)
    f = font(13)
    for g, p in load_layer("buildings"):
        c = g.centroid
        label_box(d, m.xy(c.x, c.y), p["id"], f, bg=(0, 0, 0, 150))
    for g, p in load_layer("pois"):
        if g.geom_type == "Point":
            x, y = m.xy(g.x, g.y)
            d.ellipse((x - 4, y - 4, x + 4, y + 4), fill=(200, 60, 160, 255))
            d.text((x + 6, y - 7), p.get("name") or p.get("amenity", ""), font=f, fill=(90, 20, 70, 255))
    scale_bar_and_north(d, m, ppm)
    img.convert("RGB").save(OUTPUT / "osm_only.png")
    print("wrote output/osm_only.png")


def overlay():
    m = SatelliteMapper()
    img = m.image()
    ov = Image.new("RGBA", img.size, (0, 0, 0, 0))
    d = ImageDraw.Draw(ov, "RGBA")
    for g, _ in load_layer("boundary"):
        draw_geom(d, m, g, outline=(255, 80, 80, 220), width=3)
    for g, _ in load_layer("roads"):
        draw_geom(d, m, g, outline=(255, 255, 255, 120), width=2)
    for g, p in load_layer("buildings"):
        draw_geom(d, m, g, fill=(255, 255, 0, 60), outline=(255, 255, 0, 230), width=2)
    img = Image.alpha_composite(img, ov)
    attribution(ImageDraw.Draw(img, "RGBA"), m)
    img.convert("RGB").save(OUTPUT / "overlay.png")
    print("wrote output/overlay.png")


def labeling_sheet(missing):
    m = SatelliteMapper(scale=2.0)
    img = m.image()
    ov = Image.new("RGBA", img.size, (0, 0, 0, 0))
    d = ImageDraw.Draw(ov, "RGBA")
    big = font(34)
    for g, p in load_layer("buildings"):
        draw_geom(d, m, g, fill=(255, 255, 0, 40), outline=(255, 255, 0, 255), width=3)
    for g, p in missing:
        draw_geom(d, m, g, outline=(0, 230, 255, 255), width=3)
    img = Image.alpha_composite(img, ov)
    d = ImageDraw.Draw(img, "RGBA")
    for g, p in load_layer("buildings"):
        c = g.centroid
        label_box(d, m.xy(c.x, c.y), p["id"], big, fg=(0, 0, 0, 255), bg=(255, 255, 0, 230), pad=6)
    for g, p in missing:
        c = g.centroid
        label_box(d, m.xy(c.x, c.y), p["id"], big, fg=(0, 0, 0, 255), bg=(0, 230, 255, 230), pad=6)
    attribution(d, m, font(22))
    img.convert("RGB").save(OUTPUT / "labeling_sheet.png")
    print(f"wrote output/labeling_sheet.png ({img.size[0]}x{img.size[1]})")


def detect_missing():
    """Find flat, bright, large regions on the satellite image not covered by OSM buildings."""
    m = SatelliteMapper()
    sat = cv2.imread(str(m.image().convert("RGB").save(OUTPUT / "_tmp.png") or OUTPUT / "_tmp.png"))
    (OUTPUT / "_tmp.png").unlink()
    h, w = sat.shape[:2]
    mpp = m.meta["m_per_px"]["x"]

    hsv = cv2.cvtColor(sat, cv2.COLOR_BGR2HSV)
    gray = cv2.cvtColor(sat, cv2.COLOR_BGR2GRAY)
    # Rooftops: not green (low saturation or non-green hue), fairly bright, locally smooth.
    sat_ch = hsv[:, :, 1]
    hue = hsv[:, :, 0]
    green = (hue > 30) & (hue < 95) & (sat_ch > 60)
    blur = cv2.GaussianBlur(gray, (5, 5), 0)
    lap = cv2.Laplacian(blur, cv2.CV_32F, ksize=3)
    smooth = cv2.blur(np.abs(lap), (9, 9)) < 14
    # Measured on this imagery: metal/concrete roofs are very bright (~200) or
    # grey (sat < 45); bare soil and clay courts are ~150-175 with sat > 60.
    roofish = ((blur > 185) & (sat_ch < 70)) | ((blur > 105) & (sat_ch < 45))
    mask = (roofish & smooth & ~green).astype(np.uint8) * 255
    k = cv2.getStructuringElement(cv2.MORPH_RECT, (7, 7))
    mask = cv2.morphologyEx(mask, cv2.MORPH_OPEN, k, iterations=2)
    mask = cv2.morphologyEx(mask, cv2.MORPH_CLOSE, k, iterations=2)

    # Remove everything OSM already has as a building (dilated slightly) and outside campus.
    osm_mask = np.zeros((h, w), np.uint8)
    pil = Image.fromarray(osm_mask)
    d = ImageDraw.Draw(pil)
    for g, _ in load_layer("buildings"):
        draw_geom(d, m, g.buffer(4), fill=255)
    osm_mask = np.array(pil)
    campus = Image.fromarray(np.zeros((h, w), np.uint8))
    d = ImageDraw.Draw(campus)
    for g, _ in load_layer("boundary"):
        draw_geom(d, m, g, fill=255)
    campus = np.array(campus)
    # Roads/paths are also bright and smooth; mask them out with a buffer.
    road = Image.fromarray(np.zeros((h, w), np.uint8))
    d = ImageDraw.Draw(road)
    for g, _ in load_layer("roads") + load_layer("paths"):
        draw_geom(d, m, g.buffer(5), fill=255)
    for g, p in load_layer("open_areas"):
        draw_geom(d, m, g, fill=255)
    road = np.array(road)
    mask[(osm_mask > 0) | (campus == 0) | (road > 0)] = 0

    contours, _ = cv2.findContours(mask, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
    cands = []
    ox, oy = m.proc["origin_utm"]["x"], m.proc["origin_utm"]["y"]
    for c in contours:
        area_m2 = cv2.contourArea(c) * mpp * mpp
        if area_m2 < MIN_ROOF_M2:
            continue
        rect = cv2.minAreaRect(c)
        if min(rect[1]) * mpp < 6:
            continue
        approx = cv2.approxPolyDP(c, 2.0, True).reshape(-1, 2)
        if len(approx) < 3:
            continue
        # pixel -> lon/lat -> meters
        pts = []
        for px, py in approx:
            lon, lat = m.meta["bounds_wgs84"]["min_lon"], 0
            n = 2 ** m.z * 256
            gx = (m.px0 + px) / n * 360 - 180
            gy = np.degrees(np.arctan(np.sinh(np.pi * (1 - 2 * (m.py0 + py) / n))))
            ux, uy = TO_UTM.transform(gx, gy)
            pts.append((ux - ox, uy - oy))
        poly = Polygon(pts).buffer(0)
        if poly.is_empty:
            continue
        cands.append(poly)
    cands.sort(key=lambda g: (-round(g.centroid.y / 40), g.centroid.x))
    missing = [(g, {"id": f"M{i:02d}", "area_m2": round(g.area, 1)}) for i, g in enumerate(cands, 1)]
    save_json(PROCESSED / "missing_candidates.geojson", {"type": "FeatureCollection", "features": [
        {"type": "Feature", "properties": p, "geometry": mapping(g)} for g, p in missing]}, indent=None)

    img = m.image()
    ov = Image.new("RGBA", img.size, (0, 0, 0, 0))
    d = ImageDraw.Draw(ov, "RGBA")
    for g, _ in load_layer("buildings"):
        draw_geom(d, m, g, outline=(255, 255, 0, 200), width=2)
    for g, p in missing:
        draw_geom(d, m, g, fill=(255, 60, 200, 50), outline=(255, 60, 200, 255), width=3)
    img = Image.alpha_composite(img, ov)
    d = ImageDraw.Draw(img, "RGBA")
    f = font(20)
    for g, p in missing:
        c = g.centroid
        label_box(d, m.xy(c.x, c.y), p["id"], f, bg=(255, 60, 200, 230))
    attribution(d, m)
    img.convert("RGB").save(OUTPUT / "missing_check.png")
    print(f"wrote output/missing_check.png ({len(missing)} candidates)")
    return missing


def main():
    ensure_dirs()
    osm_only()
    overlay()
    missing = detect_missing()
    labeling_sheet(missing)


if __name__ == "__main__":
    main()
