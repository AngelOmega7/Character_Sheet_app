"""Validated equipment changes and slot choices for character management."""
from dataclasses import replace

from .catalog import Catalog
from .combat import RuleError


SLOT_COLUMNS = {"back": 46, "left": 53, "right": 60, "chest": 65}


def eligible_equipment(zoid, slot, catalog=None):
    """Return equippable Armaments records for this Zoid's removable slot."""
    catalog = catalog or Catalog()
    if slot not in SLOT_COLUMNS:
        raise RuleError(f"Unknown removable equipment slot: {slot}")
    record = catalog.find("zoids", zoid)
    slot_type = str(catalog.column(record, SLOT_COLUMNS[slot]) or "").strip().casefold()
    items = [r for r in catalog.tables["armaments"]["records"] if r["kind"] in {"record", "dynamic"}]
    if slot_type == "weapon and assist":
        return items
    if slot_type == "assist":
        return [r for r in items if r["assist_eligible"]]
    if not slot_type:
        return []
    raise RuleError(f"Unknown equipment slot type: {slot_type}")


def equip_item(build, slot, item, catalog=None):
    """Equip an eligible item (or clear with None), resetting its activation."""
    catalog = catalog or Catalog()
    choices = eligible_equipment(build.zoid, slot, catalog)
    record = catalog.find("armaments", item) if item is not None else None
    if record is not None and record not in choices:
        raise RuleError(f"{record['name']} cannot be equipped in {slot}")
    index = list(SLOT_COLUMNS).index(slot)
    equipment, active = list(build.equipment), list(build.equipment_active)
    equipment[index] = record["id"] if record else None
    active[index] = False
    return replace(build, equipment=tuple(equipment), equipment_active=tuple(active))
