"""Step 6a: write data/labels.json with one entry per building (B..) and missing
candidate (M..). Pre-fills `label` only when the OSM name is an unambiguous match.
Existing labels are preserved on re-run; new ids are added.
"""
import re

from common import DATA, PROCESSED, load_json, save_json

LABELS_FILE = DATA / "labels.json"

# (regex on OSM name, label). Only clear-cut patterns; anything else stays blank.
RULES = [
    (r"^\s*([A-E])[\s-]*block\b", lambda m: f"{m.group(1).upper()} Block"),
    (r"\b([A-E])[\s-]*block\b", lambda m: f"{m.group(1).upper()} Block"),
    (r"\bblock[\s-]*([A-E])\b", lambda m: f"{m.group(1).upper()} Block"),
    (r"\bsiniti\b", lambda m: "Siniti"),
    (r"\bP\.?G\.?[\s-]*block\b", lambda m: "PG Block"),
    (r"\bPEB\b", lambda m: "PEB"),
    (r"\bcanteen\b", lambda m: "Canteen"),
    (r"\blibrary\b", lambda m: "Library"),
    (r"\bmain\s*gate\b", lambda m: "Main Gate"),
    (r"\b(ground|playground|cricket ground|football ground)\b", lambda m: "Ground"),
    (r"\bparking\b", lambda m: "Parking"),
]


def guess(name):
    if not name:
        return ""
    for pat, fn in RULES:
        m = re.search(pat, name, re.I)
        if m:
            return fn(m)
    return ""


def main():
    existing = load_json(LABELS_FILE) if LABELS_FILE.exists() else {}
    out = {}
    for f in load_json(PROCESSED / "buildings.geojson")["features"]:
        p = f["properties"]
        prev = existing.get(p["id"], {})
        if prev.get("osm_name", "") != p.get("name", ""):
            prev = {}  # ids shifted since the last run; don't carry a stale label over
        out[p["id"]] = {
            "label": prev.get("label") or guess(p.get("name")),
            "osm_name": p.get("name", ""),
            "area_m2": p["area_m2"],
            "include": prev.get("include", True),
            "notes": prev.get("notes", ""),
        }
    mc = PROCESSED / "missing_candidates.geojson"
    if mc.exists():
        for f in load_json(mc)["features"]:
            p = f["properties"]
            prev = existing.get(p["id"], {})
            out[p["id"]] = {
                "label": prev.get("label", ""),
                "osm_name": "",
                "area_m2": p["area_m2"],
                "include": prev.get("include", False),
                "notes": prev.get("notes", "satellite-detected candidate; set include=true if it is a real building"),
            }
    save_json(LABELS_FILE, out)
    auto = {k: v["label"] for k, v in out.items() if v["label"]}
    print(f"{len(out)} entries, {len(auto)} pre-filled: {auto}")


if __name__ == "__main__":
    main()
