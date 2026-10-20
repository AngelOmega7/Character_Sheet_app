"""Owner workflow data corrections and CSV conversion; no network access."""
import csv
import json
import re

RENAMES = {"Dragon Nest": "Dragoon Nest", "Command Wolf Town": "Command Wolf UC",
           "Molga Cannonry": "Cannonry Molga", "Redler BoostC": "Redler BC",
           "Rev Raptor Pile Bunker": "Rev Raptor Pilebunker", "Gun sniper LS": "Gun Sniper LS"}
TRANSPORTS = {"Gustav": (2, "Medium"), "Hover Cargo": (6, "Large"),
              "Dragoon Nest": (12, "Large Large"), "Whale King": (24, "Extra Large")}


def apply_workflow(records, keys, root, existing_families):
    families = dict(existing_families)
    base = None
    for line in (root / "assets/CAU_expand.txt").read_text(encoding="utf-8-sig").splitlines()[5:]:
        line = line.strip()
        if not line:
            continue
        if line.startswith("/"):
            name = line[1:].split(" (")[0].strip().replace("Sniper Master", "Snipe Master")
            families[name + " (CAU)"] = base
        else:
            base = line
    stems = {name.removesuffix(" (CAU)") for name in families}
    for r in records:
        fields = r["fields"]
        old_name = r["name"]
        r["legacy_fixed_weapon_ids"] = r.get("fixed_weapon_ids", [None] * 4)
        r["legacy_ownership_base_id"] = r.get("ownership_base_id", r["id"])
        name = RENAMES.get(old_name, old_name)
        if name in stems:
            name += " (CAU)"
        r["legacy_names"] = list(dict.fromkeys([old_name, name.removesuffix(" (CAU)")]))
        r["name"] = fields["name"] = name
        for key, value in fields.items():
            if isinstance(value, str):
                fields[key] = re.sub(r"\bLion\b", "Liger", value)
        if fields["size"] == "Extra Lare":
            fields["size"] = "Extra Large"
        if old_name not in ("Lightning Saix", "Lightning Saix BS", "Shadow Fox", "Command Wolf IS"):
            continue
        original = dict(fields)
        destination = 2 if old_name.startswith("Lightning Saix") else 3
        moved_to = 3 if destination == 2 else 4
        groups = {2: (19, 20, 21, 22, 23), 3: (30, 31, 32, 33, 34), 4: (41, 42, 43, 44, 45)}
        def put(column, value, source=None):
            key = keys[column - 1]
            r.setdefault("corrections", {})[key] = {"original": original[key], "corrected": value,
                "reason": "Owner moved unique removable weapon into fixed loadout", "copied_from_column": source}
            fields[key] = value
        slot_moves = {}
        if original[keys[groups[destination][0] - 1]]:
            for target, source in zip(groups[moved_to], groups[destination]):
                put(target, original[keys[source - 1]], source)
            put(84 + moved_to, original[keys[84 + destination - 1]], 84 + destination)
            slot_moves[str(destination)] = moved_to
        for target, source in zip(groups[destination], (47, 48, 49, 50, 51)):
            put(target, original[keys[source - 1]], source)
        if old_name == "Shadow Fox":
            put(groups[destination][0], "Laser Vulcan Gun")
        elif old_name == "Command Wolf IS":
            put(groups[destination][0], "Long Range Rifle")
        put(84 + destination, None)
        note = r.setdefault("damage_notes", {}).pop(keys[48], None)
        if note is not None:
            r["damage_notes"][keys[groups[destination][2] - 1]] = note
        for col in range(47, 53):
            put(col, None)
        r["workflow_weapon_move"] = {"destination": destination, "old_fixed_moves": slot_moves,
                                     "removable_template": "armaments:zoid_equipment_slot_1"}
    return families


def write_purchases(output, records, root):
    lookup = {}
    for r in records:
        for name in [r["name"], r["name"].removesuffix(" (CAU)"), *r.get("legacy_names", [])]:
            lookup[name.casefold()] = r
    converted = []
    with (root / "assets/zoid_cost.csv").open(encoding="utf-8-sig", newline="") as stream:
        for row_number, row in enumerate(csv.DictReader(stream), 2):
            original = dict(row)
            if row["Name"] == "Jagged Stinger":
                row["Base Zoid"] = "Death Stinger"
            if row["Zoid Core"] == "Zoids Core DS":
                row["Zoid Core"] = "Zoid Core DS"
            if row["Name"] == "Saberlion" and row["Parts"] == "Zoid Core SS":
                row["Zoid Core"], row["Parts"] = "Zoid Core SS", ""
            r = lookup[row["Name"].strip().casefold()]
            base_name = row["Base Zoid"].strip()
            cost = int(row["Cost"].replace(",", ""))
            if cost < 0:
                raise ValueError(f"Negative price for {r['name']}")
            converted.append({"id": "purchases:" + r["id"].split(":")[1], "name": r["name"], "kind": "record",
                "zoid_id": r["id"], "source": {"sheet": "zoid_cost.csv", "row": row_number}, "original": original,
                "fields": {"name": r["name"], "cost": cost,
                    "core": row["Zoid Core"].strip() or None, "parts": row["Parts"].strip() or None,
                    "base_zoid": lookup[base_name.casefold()]["id"] if base_name else None}, "dynamic_fields": {}})
    if {r["zoid_id"] for r in converted} != {r["id"] for r in records} or len(converted) != len(records):
        raise ValueError("Every playable Zoid/form must have exactly one cost row")
    data = {"schema_version": 1, "columns": ["name", "cost", "core", "parts", "base_zoid"],
            "source_headers": ["Name", "Cost", "Zoid Core", "Parts", "Base Zoid"], "records": converted, "excluded_rows": []}
    (output / "purchases.json").write_text(json.dumps(data, indent=2) + "\n", encoding="utf-8", newline="\n")
    return len(converted)
