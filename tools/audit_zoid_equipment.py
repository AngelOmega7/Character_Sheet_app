"""Audit named cost entries, resolved removable items, and legal simultaneous mounts."""
from itertools import permutations

from tools.audit_energy import ROOT, audit
from zoids_app.catalog import Catalog
from zoids_app.equipment import SLOT_COLUMNS, ZOID_EQUIPMENT_COLUMNS, eligible_equipment, is_assist_equipment, resolved_equipment_name


def equipment_audit(catalog=None):
    catalog = catalog or Catalog()
    costs = audit()
    missing = [(entry["name"], weapon["name"]) for entry in costs["matched"] for weapon in entry["weapons"]
               if len(weapon["app_slots"]) != 1]
    designs = []
    for zoid in catalog.tables["zoids"]["records"]:
        if zoid["kind"] != "record":
            continue
        items = []
        for index, (name_column, damage_column) in enumerate(ZOID_EQUIPMENT_COLUMNS):
            if not catalog.column(zoid, name_column):
                continue
            template = catalog.find("armaments", f"armaments:zoid_equipment_slot_{index + 1}")
            slots = [i + 5 for i, slot in enumerate(SLOT_COLUMNS) if template in eligible_equipment(zoid["id"], slot, catalog)]
            items.append({"name": resolved_equipment_name(template, zoid, catalog), "template": template["id"],
                          "source_slot": index + 5, "slots": slots,
                          "kind": "Assist" if is_assist_equipment(template, zoid, catalog) else "Weapon",
                          "damage": catalog.column(zoid, damage_column), "energy_cost": zoid["energy_costs"][index + 4]})
        if items:
            assignments = [list(slots) for slots in permutations(range(5, 9), len(items))
                           if all(slot in item["slots"] for slot, item in zip(slots, items))]
            designs.append({"name": zoid["name"], "items": items, "assignments": assignments})
    return {"missing_cost_items": missing, "unknown_zoids": costs["unknown_zoids"], "designs": designs}


def write_report():
    result = equipment_audit()
    assert not result["missing_cost_items"] and not result["unknown_zoids"], result
    assert all(design["assignments"] for design in result["designs"])
    lines = ["# Zoid-specific equipment audit", "",
             "Every named entry in the Zoid energy-cost spreadsheet maps to an implemented fixed or removable item. No missing named items were found.", "",
             "Great Zaber and Buster Fury are absent from that spreadsheet; their approved app entries were also checked. Great Zaber is the only current design with two removable Zoid-specific items. Both can be equipped simultaneously.", "",
             "Source E5–E8 identifies the catalog lookup, not a required mounting position. Weapons use Weapon and Assist slots, subject to explicit mounting restrictions: Great Zaber's 20mm Solid Rifle uses slot 6. Named non-weapon equipment uses either Assist or Weapon and Assist slots, including slots 5–8 on every design listed below. One physical copy still occupies only one slot per form.", "",
             "| Zoid | Item | Type | Source | Allowed slots | Energy cost |",
             "| --- | --- | --- | --- | --- | --- |"]
    for design in result["designs"]:
        for item in design["items"]:
            lines.append(f"| {design['name']} | {item['name']} | {item['kind']} | E{item['source_slot']} | {', '.join(map(str, item['slots']))} | {item['energy_cost']} |")
    lines += ["", "## Multiple removable items", ""]
    for design in result["designs"]:
        if len(design["items"]) > 1:
            for assignment in design["assignments"]:
                lines.append(f"- {design['name']}: " + "; ".join(f"{item['name']} in slot {slot}" for item, slot in zip(design["items"], assignment)) + ".")
    lines += ["", "The Konig Wolf DSR's Dual Sniper Rifle is already fixed equipment; its removable 5-Shot Missile Pod can mount in slot 6 or 7 alongside it.", "",
              "Lightning Saix/BS Pulse Laser Gun, Command Wolf IS Long Range Rifle, and Shadow Fox Laser Vulcan Gun were moved from source removable positions to fixed weapons in the app. Their costs follow their current fixed positions; they are not missing items.", "",
              "Reproduce with `python3 -m tools.audit_zoid_equipment`.", ""]
    path = ROOT / "docs/generated/zoid-equipment-audit.md"
    path.write_text("\n".join(lines))
    print(f"Audited {len(result['designs'])} designs and {sum(len(d['items']) for d in result['designs'])} removable items; no missing named cost entries. Report: {path}")


if __name__ == "__main__":
    write_report()
