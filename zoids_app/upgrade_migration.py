"""Convert pre-v11 weapon investments into chassis-wide Accuracy once."""
from .combat import RuleError


def _points(value):
    if type(value) is not int or not 0 <= value <= 5:
        raise RuleError("Legacy weapon upgrade points must be integers from 0 through 5")
    return value


def _convert_frame(frame, weapons=None):
    legacy = 0
    for key in ("damage", "to_hit"):
        values = frame.get(key, [0] * 4)
        if len(values) != 4:
            raise RuleError("Four legacy weapon upgrade slots are required")
        legacy += sum(_points(value) for value in values)
        frame[key] = [0] * 4
    if weapons:
        # Shared weapons occur once per physical chassis, not once per form.
        unique = {}
        for weapon in weapons:
            key = weapon["weapon_id"]
            damage, hit = _points(weapon["damage"]), _points(weapon["to_hit"])
            previous = unique.get(key, (0, 0))
            unique[key] = (max(previous[0], damage), max(previous[1], hit))
        legacy = sum(damage + hit for damage, hit in unique.values())
    frame["accuracy"] = frame.get("accuracy", 0) + legacy
    frame.setdefault("armor", 0)


def migrate_upgrade_payload(values, version):
    """Mutate decoded JSON before construction of current dataclasses.

    Owned frames are authoritative; the active build is only their projection.
    FUZOR components and stored/sold FUZORs retain their own investments.
    """
    if version >= 11:
        return

    def owner(record):
        _convert_frame(record["frame"], record.get("weapons"))
        record["weapons"] = [dict(weapon, damage=0, to_hit=0)
                             for weapon in record.get("weapons", [])]
        for component in record.get("fusion_components") or []:
            owner(component)

    for record in values.get("owned_zoids", []):
        owner(record)
    for record in values.get("stored_fuzors", []):
        owner(record)
    if version == 1:
        _convert_frame(values["build"]["upgrades"])
    else:
        active = next((r for r in values.get("owned_zoids", [])
                       if r["id"] == values.get("active_zoid_id")), None)
        if active:
            values["build"]["upgrades"] = dict(active["frame"])
        else:
            _convert_frame(values["build"]["upgrades"])
