"""Shared paths, HTTP helpers and projection utilities for the map-data scripts."""
import json
import time
from pathlib import Path

import numpy as np
import requests
import shapely
from pyproj import Transformer

ROOT = Path(__file__).resolve().parent.parent
DATA = ROOT / "data"
RAW = DATA / "raw"
OSM = DATA / "osm"
PROCESSED = DATA / "processed"
TILES = DATA / "tiles"
SATELLITE = DATA / "satellite"
OUTPUT = ROOT / "output"

USER_AGENT = "campus-quest-personal-project"
UTM_EPSG = "EPSG:32644"  # UTM zone 44N (Hyderabad)

TO_UTM = Transformer.from_crs("EPSG:4326", UTM_EPSG, always_xy=True)
TO_WGS = Transformer.from_crs(UTM_EPSG, "EPSG:4326", always_xy=True)

ATTRIBUTION = "Imagery: Esri, Maxar, Earthstar Geographics"


def ensure_dirs():
    for d in (RAW, OSM, PROCESSED, TILES, SATELLITE, OUTPUT):
        d.mkdir(parents=True, exist_ok=True)


def load_json(path):
    with open(path) as f:
        return json.load(f)


def save_json(path, obj, indent=2):
    Path(path).parent.mkdir(parents=True, exist_ok=True)
    with open(path, "w") as f:
        json.dump(obj, f, indent=indent, ensure_ascii=False)
    print(f"wrote {Path(path).relative_to(ROOT)}")


def get_with_retry(url, params=None, data=None, tries=5, timeout=180, min_interval=1.0, headers=None):
    """GET (or POST when data is given) with exponential backoff. Respects a minimum interval."""
    hdrs = {"User-Agent": USER_AGENT}
    if headers:
        hdrs.update(headers)
    delay = 2.0
    last = None
    for attempt in range(tries):
        t0 = time.time()
        try:
            if data is not None:
                r = requests.post(url, data=data, headers=hdrs, timeout=timeout)
            else:
                r = requests.get(url, params=params, headers=hdrs, timeout=timeout)
            if r.status_code == 200:
                elapsed = time.time() - t0
                if elapsed < min_interval:
                    time.sleep(min_interval - elapsed)
                return r
            last = f"HTTP {r.status_code}: {r.text[:200]}"
            if r.status_code in (400, 404):
                break
        except requests.RequestException as e:
            last = repr(e)
        print(f"  attempt {attempt + 1} failed ({last}); retrying in {delay:.0f}s")
        time.sleep(delay)
        delay *= 2
    raise RuntimeError(f"request failed after {tries} tries: {last}")


def project_geom(geom, transformer):
    """Reproject a GeoJSON geometry dict coordinate-by-coordinate."""
    def rec(coords):
        if isinstance(coords[0], (int, float)):
            x, y = transformer.transform(coords[0], coords[1])
            return [round(x, 3), round(y, 3)]
        return [rec(c) for c in coords]

    return {"type": geom["type"], "coordinates": rec(geom["coordinates"])}


def reproject(transformer, geom):
    """Reproject a shapely geometry with a pyproj Transformer."""
    return shapely.transform(geom, lambda a: np.column_stack(transformer.transform(a[:, 0], a[:, 1])))
