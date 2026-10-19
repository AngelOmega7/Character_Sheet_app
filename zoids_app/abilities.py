"""Owned ability ranks and active/inactive selections, independent of the UI."""
from dataclasses import dataclass, replace

from .catalog import Catalog
from .combat import RuleError


@dataclass(frozen=True)
class AbilityLoadout:
    active: tuple[str | None, ...] = ()
    inactive: tuple[str, ...] = ()


def validate_loadout(loadout: AbilityLoadout, catalog: Catalog) -> AbilityLoadout:
    """Canonicalize IDs and reject impossible ownership or active selections.

    Only one rank of a family can be owned across BOTH lists. Older ranks must
    not be retained in the inactive list when an ability is upgraded.
    """
    if len(loadout.active) > 6:
        raise RuleError("At most six active ability slots are supported")
    families = set()
    size_count = 0
    lists = []
    for is_active, selection in ((True, loadout.active), (False, loadout.inactive)):
        normalized = []
        for entry in selection:
            if entry is None and is_active:
                normalized.append(None)
                continue
            record = catalog.find("abilities", entry)
            if record["kind"] == "placeholder" and is_active:
                normalized.append(None)
                continue
            if record["kind"] != "record":
                raise RuleError("Only actual abilities can be owned")
            if record["family"] in families:
                raise RuleError(f"Only one owned rank of {record['name']} is allowed")
            families.add(record["family"])
            if is_active and record["eligible_sizes"]:
                size_count += 1
            normalized.append(record["id"])
        lists.append(tuple(normalized))
    if size_count > 1:
        raise RuleError("Only one size bonus ability may be active at a time")
    return AbilityLoadout(*lists)


def learn_ability(loadout: AbilityLoadout, ability: str, catalog: Catalog) -> AbilityLoadout:
    """Learn into inactive storage, or upgrade an existing rank in its slot.

    Lower ranks are removed, not stored. Acquiring a lower rank is rejected.
    Learning an already-owned rank is an idempotent no-op.
    """
    loadout = validate_loadout(loadout, catalog)
    learned = catalog.find("abilities", ability)
    if learned["kind"] != "record":
        raise RuleError("Only actual abilities can be learned")
    for attribute in ("active", "inactive"):
        entries = list(getattr(loadout, attribute))
        for index, entry in enumerate(entries):
            if entry is None:
                continue
            owned = catalog.find("abilities", entry)
            if owned["family"] != learned["family"]:
                continue
            if learned["rank"] < owned["rank"]:
                raise RuleError("An upgraded ability cannot be downgraded")
            entries[index] = learned["id"]
            return validate_loadout(replace(loadout, **{attribute: tuple(entries)}), catalog)
    return validate_loadout(replace(loadout, inactive=(*loadout.inactive, learned["id"])), catalog)


def deactivate_ability(loadout: AbilityLoadout, slot: int, catalog: Catalog) -> AbilityLoadout:
    loadout = validate_loadout(loadout, catalog)
    if type(slot) is not int or not 0 <= slot < len(loadout.active):
        raise RuleError("Invalid active ability slot")
    entries = list(loadout.active)
    entry = entries[slot]
    if entry is None:
        return loadout
    entries[slot] = None
    return validate_loadout(AbilityLoadout(tuple(entries), (*loadout.inactive, entry)), catalog)


def activate_ability(loadout: AbilityLoadout, ability: str, slot: int, catalog: Catalog) -> AbilityLoadout:
    """Move an owned inactive ability into a slot; store its replacement inactive.

    Replacing the active size ability in its slot is allowed. Placing a second
    size ability in another slot is rejected without changing either list.
    """
    loadout = validate_loadout(loadout, catalog)
    if type(slot) is not int or not 0 <= slot < 6:
        raise RuleError("Invalid active ability slot")
    record = catalog.find("abilities", ability)
    if record["id"] not in loadout.inactive:
        raise RuleError("Ability must be owned and inactive before activation")
    entries = list(loadout.active) + [None] * (max(0, slot + 1 - len(loadout.active)))
    inactive = [entry for entry in loadout.inactive if entry != record["id"]]
    if entries[slot] is not None:
        inactive.append(entries[slot])
    entries[slot] = record["id"]
    return validate_loadout(AbilityLoadout(tuple(entries), tuple(inactive)), catalog)
