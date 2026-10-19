"""Inventory current tags on explicitly melee-classified weapon fields."""
from collections import defaultdict
import json
from pathlib import Path
import re

ROOT = Path(__file__).resolve().parents[1]


def audit():
    tags = defaultdict(list)
    records = []
    for dataset, pairs in (("zoids", ((13, 16), (19, 22), (30, 33), (41, 44), (47, 50), (54, 58))), ("armaments", ((1, 3),))):
        table = json.loads((ROOT / f"zoids_app/data/{dataset}.json").read_text())
        for record in table["records"]:
            for name_column, tag_column in pairs:
                raw = record["fields"][table["columns"][tag_column - 1]]
                if not isinstance(raw, str) or not re.search(r"\bMelee\b", raw, re.I):
                    continue
                entry = {
                    "id": record["id"], "zoid_or_item": record["name"],
                    "weapon": record["fields"][table["columns"][name_column - 1]],
                    "tags": raw, "source": {**record["source"], "column": tag_column},
                }
                records.append(entry)
                for tag in {t.strip() for t in raw.split(",")}:
                    tags[tag].append(entry)
    output = ROOT / "docs/generated"
    (output / "melee-tags.json").write_text(json.dumps({"weapon_entries": len(records), "literal_tags": dict(sorted(tags.items())), "weapons": records}, indent=2) + "\n")
    lines = ["# Melee weapon tag inventory", "", f"{len(records)} explicitly melee-tagged weapon entries (shared weapons on different Zoids count separately).", "", "Current tags after owner-approved conversion. Original spellings are retained in catalog correction metadata and the source inventory. Untagged weapons are not inferred to be melee.", "", "| Tag | Entries | Example |", "|---|---:|---|"]
    for tag, entries in sorted(tags.items()):
        e = entries[0]
        lines.append(f"| {tag} | {len(entries)} | {e['zoid_or_item']} — {e['weapon']} |")
    (output / "melee-tags.md").write_text("\n".join(lines) + "\n")
    print("\n".join(lines))


if __name__ == "__main__":
    audit()
