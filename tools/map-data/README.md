# map-data

Fetches and prepares the geographic reference for the pixel-art campus map:
OpenStreetMap vectors, Esri satellite imagery, and a labeling workflow.
Nothing here is shipped in the build.

## Setup

```sh
cd tools/map-data
python3 -m venv .venv
.venv/bin/pip install -r requirements.txt
```

## Scripts (run in order; each is re-runnable and uses its cache)

| Script | Does | Reads | Writes |
|---|---|---|---|
| `scripts/01_boundary.py` | Geocode the campus (Nominatim) and fetch its boundary polygon (Overpass). Falls back to a 600 m box if none. | network | `data/raw/nominatim.json`, `boundary_overpass.json`, `boundary.geojson`, `bbox.json` |
| `scripts/02_fetch_osm.py` | One Overpass query for buildings, roads, paths, parking, leisure, landuse, natural, barriers, POIs inside the padded bbox; splits into layers clipped to the boundary. | `bbox.json`, `boundary.geojson` | `data/raw/osm_raw.json`, `data/osm/*.geojson` (+ `roads_unclipped`) |
| `scripts/03_project.py` | Reproject to UTM 44N meters relative to the bbox's SW corner; assign `B01..` ids (north→south, then west→east); building stats. | `data/osm/` | `data/processed/*.geojson`, `buildings_table.csv`, `meta.json` |
| `scripts/04_satellite.py` | Download Esri World Imagery tiles at zoom 19 (falls back to 18), stitch, write bounds + world file. | `bbox.json` | `data/tiles/z/x/y.jpg`, `data/satellite/campus_satellite.{png,json,pgw}` |
| `scripts/05_render.py` | Review images + satellite-based missing-building detection. | processed + satellite | `output/osm_only.png`, `overlay.png`, `labeling_sheet.png`, `missing_check.png`, `data/processed/missing_candidates.geojson` |
| `scripts/06_labels_template.py` | Create/refresh `data/labels.json` (keeps labels you already filled). | processed | `data/labels.json` |
| `scripts/07_boundary_check.py` | Wider satellite render with VNR boundary, VJ Public School polygon and outside buildings as `X..`. | raw | `output/boundary_check.png`, `data/raw/outside_buildings.geojson` |
| `scripts/08_streetlevel.py` | Street View (metadata) + Mapillary coverage along campus roads/paths; needs `GOOGLE_MAPS_API_KEY` / `MAPILLARY_TOKEN`. | processed | `data/streetlevel/*.json`, `output/streetlevel_coverage.png` |
| `scripts/apply_labels.py` | After you fill `labels.json`: merge labels, add included `M..` candidates, render the final named map. | `labels.json` | `data/processed/campus_final.geojson`, `output/labeled_map.png` |

Run one with `.venv/bin/python scripts/<name>.py` from this folder.
`common.py` and `render_common.py` are shared helpers, not steps.

To force a re-fetch, delete the cached file: `data/raw/nominatim.json` /
`boundary_overpass.json` (step 1), `data/raw/osm_raw.json` (step 2), or the
tiles under `data/tiles/` (step 4).

## Labeling workflow

1. Open `output/labeling_sheet.png` (big; zoom in). Yellow = OSM buildings
   `B01..`, cyan = satellite-detected candidates `M01..`.
2. Edit `data/labels.json`: set `label` to the real name ("A Block", "Siniti",
   "Canteen" …), set `include: false` for things that shouldn't be on the game
   map, and `include: true` for `M..` entries that are real buildings.
3. Run `scripts/apply_labels.py` and check `output/labeled_map.png`.

## Coordinates

Processed files are in meters: x east, y north, origin = SW corner of the
padded bbox (`data/processed/meta.json` has the origin in UTM and WGS84).
`data/satellite/campus_satellite.json` gives the image's exact bounds and
m/px; `render_common.SatelliteMapper` converts meters → image pixels.

## Imagery terms

Satellite tiles are Esri World Imagery (Esri, Maxar, Earthstar Geographics),
used only as a private drawing reference. `data/tiles/` and `data/satellite/`
are git-ignored and must never be copied into `public/`.
