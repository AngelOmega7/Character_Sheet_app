"""One-time migration of pre-workflow ownership and moved weapon identities."""
from dataclasses import asdict, replace

from .characters import (FixedWeaponCondition, FormLoadout, WeaponUpgrade,
                         fixed_weapon_identity, restore_roster_selection)
from .combat import WeaponCondition


def prepare_legacy_build(build, catalog):
    record = catalog.find("zoids", build.zoid)
    move = record.get("workflow_weapon_move")
    if not move:
        return build
    damage, hit, active = list(build.upgrades.damage), list(build.upgrades.to_hit), list(build.fixed_active)
    for old, new in move["old_fixed_moves"].items():
        old, new = int(old) - 1, new - 1
        damage[new], hit[new], active[new] = damage[old], hit[old], active[old]
    index = move["destination"] - 1
    damage[index], hit[index], active[index] = 0, 0, False
    equipment, flags = list(build.equipment), list(build.equipment_active)
    for i, item in enumerate(equipment):
        if item and catalog.find("armaments", item)["id"] == move["removable_template"]:
            equipment[i], flags[i] = None, False
    return replace(build, upgrades=replace(build.upgrades, damage=tuple(damage), to_hit=tuple(hit)),
                   fixed_active=tuple(active), equipment=tuple(equipment), equipment_active=tuple(flags))


def migrate_workflow(character, catalog):
    roster, archive = [], list(character.archived_content)
    transport = character.transport
    transports = {r["legacy_zoid_id"]: r for r in catalog.tables["transports"]["records"]}
    inventory = {i.id: i for i in character.inventory}
    for owner in character.owned_zoids:
        if owner.base_zoid in transports:
            archive.append({"kind": "transport_conversion", "record": asdict(owner)})
            transport = transport or transports[owner.base_zoid]["id"]
            continue
        base = catalog.find("zoids", owner.base_zoid)["ownership_base_id"]
        mapping, forms, transferred = {}, [], {}
        for form in owner.forms:
            record = catalog.find("zoids", form.zoid)
            move = record.get("workflow_weapon_move", {})
            old_moves = move.get("old_fixed_moves", {})
            for index, old_id in enumerate(record.get("legacy_fixed_weapon_ids", record["fixed_weapon_ids"])):
                new_index = old_moves.get(str(index + 1), index + 1) - 1
                old_id = old_id or f"{record['id']}:fixed_{index + 1}"
                mapping[old_id] = fixed_weapon_identity(record, new_index)
            flags = list(form.fixed_active)
            for old, new in old_moves.items():
                flags[new - 1] = form.fixed_active[int(old) - 1]
            equipment, ids, enabled = list(form.equipment), list(form.equipment_ids), list(form.equipment_active)
            if move:
                destination = move["destination"] - 1
                flags[destination] = False
                target = fixed_weapon_identity(record, destination)
                for index, item in enumerate(equipment):
                    if item == move["removable_template"]:
                        copy = inventory.get(ids[index])
                        if copy:
                            before = transferred.get(target, WeaponCondition())
                            state = copy.condition
                            transferred[target] = WeaponCondition(max(before.heat, state.heat), before.broken or state.broken,
                                                                  state.last_roll if state.last_roll is not None else before.last_roll)
                        equipment[index], ids[index], enabled[index] = None, None, False
            forms.append(replace(form, fixed_active=tuple(flags), equipment=tuple(equipment), equipment_ids=tuple(ids), equipment_active=tuple(enabled)))
        if not any(f.zoid == base for f in forms):
            forms.insert(0, FormLoadout(base))
        weapons = {}
        for weapon in owner.weapons:
            key = mapping.get(weapon.weapon_id, weapon.weapon_id)
            previous = weapons.get(key, WeaponUpgrade(key))
            weapons[key] = WeaponUpgrade(key, max(previous.damage, weapon.damage), max(previous.to_hit, weapon.to_hit))
        conditions = {}
        for weapon in owner.weapon_conditions:
            key = mapping.get(weapon.weapon_id, weapon.weapon_id)
            conditions[key] = FixedWeaponCondition(key, weapon.condition)
        conditions.update({key: FixedWeaponCondition(key, state) for key, state in transferred.items()})
        roster.append(replace(owner, base_zoid=base, forms=tuple(forms), weapons=tuple(weapons.values()),
                              weapon_conditions=tuple(conditions.values())))
    result = replace(character, owned_zoids=tuple(roster), archived_content=tuple(archive), transport=transport,
                     loaded_zoids=(), starter_pending=False)
    return restore_roster_selection(result, catalog)
