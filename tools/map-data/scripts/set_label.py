"""Record one labeling answer in data/labels.json immediately.

Usage:
  set_label.py <id> "<name>"          label it, include=true
  set_label.py <id> skip              include=false
  set_label.py <id> unknown           include=true, label ""
  set_label.py landmark <name> <ref>  e.g. landmark "Main Gate" B06  (or a POI name)
Ids may be "M01+M02" to apply the same answer to both.
"""
import sys

from common import DATA, load_json, save_json

F = DATA / "labels.json"


def main(argv):
    labels = load_json(F)
    if argv[0] == "landmark":
        name, ref = argv[1], argv[2]
        labels.setdefault("_landmarks", {})[name] = ref
        save_json(F, labels)
        print(f"landmark {name} -> {ref}")
        return
    ids, answer = argv[0].split("+"), argv[1]
    for i in ids:
        e = labels.setdefault(i, {"label": "", "osm_name": "", "include": True, "notes": ""})
        if answer == "skip":
            e["include"], e["label"] = False, ""
        elif answer == "unknown":
            e["include"], e["label"] = True, ""
        else:
            e["include"], e["label"] = True, answer
        if len(ids) > 1:
            e["notes"] = f"part of {'+'.join(ids)}"
        print(f"{i}: label={e['label']!r} include={e['include']}")
    save_json(F, labels)


if __name__ == "__main__":
    main(sys.argv[1:])
