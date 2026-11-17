"""Restore the four formerly fixed unique weapons to removable Slot 5."""
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def restore_weapons(records, columns):
    for record in records:
        move = record.get("workflow_weapon_move")
        if not move or record.get("removable_weapon_restore"):
            continue
        index = move["destination"] - 1
        start = (13, 19, 30, 41)[index]
        fields = record["fields"]
        former_id = record["fixed_weapon_ids"][index]
        for source, target in zip(range(start, start + 5), (47, 48, 49, 50, 51)):
            fields[columns[target - 1]] = fields[columns[source - 1]]
            fields[columns[source - 1]] = None
        original = record["corrections"][columns[46]]["original"]
        if not fields[columns[47]] and ":" in original:
            fields[columns[47]] = original.split(":", 1)[1].strip() or None
        fields[columns[51]] = record["corrections"][columns[51]]["original"]
        fields[columns[45]] = "Weapon and Assist"
        record["fixed_weapon_ids"][index] = None
        if "energy_costs" in record:
            record["energy_costs"][4] = record["energy_costs"][index]
            record["energy_costs"][index] = None
        notes = record.get("damage_notes", {})
        if columns[start + 1] in notes:
            notes[columns[48]] = notes.pop(columns[start + 1])
        record.setdefault("zoid_equipment_mounts", {})[move["removable_template"]] = ["back"]
        record["removable_weapon_restore"] = {
            "fixed_slot": index + 1, "fixed_weapon_id": former_id,
            "template": move["removable_template"], "slot": "back",
        }
    for record in records:
        if record["id"] == "zoids:shadow_fox":
            record["fields"][columns[47]] = "Back-mounted gun. AoE attack targeting a 30m by 90m area. (Shadow Fox Only)"
            record["fields"][columns[48]] = 90
            record["fields"][columns[49]] = "Ranged, Laser, Close Range"
            record.get("damage_notes", {}).pop(columns[48], None)
            if "energy_costs" in record:
                record["energy_costs"][4] = 8


def main():
    path = ROOT / "zoids_app/data/zoids.json"
    table = json.loads(path.read_text())
    restore_weapons(table["records"], table["columns"])
    path.write_text(json.dumps(table, indent=2, ensure_ascii=False) + "\n")


if __name__ == "__main__":
    main()
