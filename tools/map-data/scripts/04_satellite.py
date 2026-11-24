"""Step 4: download Esri World Imagery tiles over the padded bbox, stitch them
into data/satellite/campus_satellite.png and write its exact bounds.

Tiles are cached in data/tiles/{z}/{x}/{y}.jpg and never re-downloaded.
Falls back from zoom 19 to 18 if too many tiles are blank placeholders.
"""
import io
import math
import sys
import time

import numpy as np
from PIL import Image, ImageDraw

from common import ATTRIBUTION, RAW, SATELLITE, TILES, TO_UTM, ensure_dirs, get_with_retry, load_json, save_json

URL = "https://server.arcgisonline.com/ArcGIS/rest/services/World_Imagery/MapServer/tile/{z}/{y}/{x}"
DELAY = 0.15


def lonlat_to_tile(lon, lat, z):
    n = 2 ** z
    x = (lon + 180) / 360 * n
    y = (1 - math.log(math.tan(math.radians(lat)) + 1 / math.cos(math.radians(lat))) / math.pi) / 2 * n
    return x, y


def tile_to_lonlat(x, y, z):
    n = 2 ** z
    lon = x / n * 360 - 180
    lat = math.degrees(math.atan(math.sinh(math.pi * (1 - 2 * y / n))))
    return lon, lat


def get_tile(z, x, y):
    p = TILES / str(z) / str(x) / f"{y}.jpg"
    if p.exists():
        return Image.open(p).convert("RGB")
    r = get_with_retry(URL.format(z=z, x=x, y=y), min_interval=DELAY, timeout=60)
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_bytes(r.content)
    return Image.open(io.BytesIO(r.content)).convert("RGB")


def is_blank(img):
    a = np.asarray(img)
    return a.std() < 4  # flat grey/white placeholder


def stitch(bbox, z):
    x0, y1 = lonlat_to_tile(bbox["min_lon"], bbox["min_lat"], z)
    x1, y0 = lonlat_to_tile(bbox["max_lon"], bbox["max_lat"], z)
    tx0, tx1, ty0, ty1 = int(x0), int(x1), int(y0), int(y1)
    cols, rows = tx1 - tx0 + 1, ty1 - ty0 + 1
    print(f"zoom {z}: {cols}x{rows} = {cols * rows} tiles")
    canvas = Image.new("RGB", (cols * 256, rows * 256))
    blank = 0
    for ty in range(ty0, ty1 + 1):
        for tx in range(tx0, tx1 + 1):
            img = get_tile(z, tx, ty)
            if is_blank(img):
                blank += 1
            canvas.paste(img, ((tx - tx0) * 256, (ty - ty0) * 256))
    print(f"  blank tiles: {blank}/{cols * rows}")
    # Crop to the bbox exactly.
    left = int((x0 - tx0) * 256)
    top = int((y0 - ty0) * 256)
    right = int((x1 - tx0) * 256)
    bottom = int((y1 - ty0) * 256)
    crop = canvas.crop((left, top, right, bottom))
    # Exact geographic bounds of the crop.
    lon_w, lat_n = tile_to_lonlat(tx0 + left / 256, ty0 + top / 256, z)
    lon_e, lat_s = tile_to_lonlat(tx0 + right / 256, ty0 + bottom / 256, z)
    return crop, blank / (cols * rows), (lon_w, lat_s, lon_e, lat_n)


def main():
    ensure_dirs()
    bbox = load_json(RAW / "bbox.json")
    for z in (19, 18):
        img, blank_frac, bounds = stitch(bbox, z)
        if blank_frac < 0.2:
            break
        print(f"  too many blank tiles at zoom {z}, falling back")
    else:
        sys.exit("imagery unavailable at zoom 19 and 18")

    out = SATELLITE / "campus_satellite.png"
    img.save(out)
    lon_w, lat_s, lon_e, lat_n = bounds
    w, h = img.size
    # Web Mercator is conformal, but pixel size in meters varies slightly with
    # latitude. Over ~700 m it's negligible; record both UTM corners anyway.
    sw = TO_UTM.transform(lon_w, lat_s)
    ne = TO_UTM.transform(lon_e, lat_n)
    meta = {
        "zoom": z, "width_px": w, "height_px": h,
        "bounds_wgs84": {"min_lon": lon_w, "min_lat": lat_s, "max_lon": lon_e, "max_lat": lat_n},
        "bounds_utm": {"min_x": sw[0], "min_y": sw[1], "max_x": ne[0], "max_y": ne[1]},
        "m_per_px": {"x": (ne[0] - sw[0]) / w, "y": (ne[1] - sw[1]) / h},
        "attribution": ATTRIBUTION,
        "note": "Web Mercator tiles; vectors are placed by lon/lat -> pixel using the mercator formula in common.py / 05_render.py.",
    }
    save_json(SATELLITE / "campus_satellite.json", meta)
    # ESRI world file for GIS tools (pixel size in degrees, WGS84).
    (SATELLITE / "campus_satellite.pgw").write_text(
        f"{(lon_e - lon_w) / w:.12f}\n0\n0\n{-(lat_n - lat_s) / h:.12f}\n{lon_w:.10f}\n{lat_n:.10f}\n")
    # Preview with attribution.
    prev = img.copy()
    ImageDraw.Draw(prev).text((6, h - 16), ATTRIBUTION, fill=(255, 255, 255))
    prev.save(SATELLITE / "campus_satellite_attributed.png")
    print(f"wrote {out.relative_to(out.parents[3])}: {w}x{h}px, {meta['m_per_px']['x']:.3f} m/px, zoom {z}")


if __name__ == "__main__":
    main()
