"""Atomic combat commands over owned chassis and physical equipment copies."""
from dataclasses import dataclass, replace
import random
from decimal import Decimal

from .attacks import calculate_attack
from .catalog import Catalog
from .characters import Character, FixedWeaponCondition, fixed_weapon_identity, validate_character
from .combat import (RuleError, WeaponCondition, WeaponState, repair_health,
                     repair_weapon, use_weapon)
from .stats import calculate_stats


def rolls_damage(weapon):
    return isinstance(weapon["base_damage"], (int, float, Decimal)) and not isinstance(weapon["base_damage"], bool)


@dataclass(frozen=True)
class CombatResult:
    character: Character
    message: str
    cost: int = 0


def _weapon_target(character, weapon, catalog):
    if not weapon["name"]:
        raise RuleError("This slot has no weapon or equipment")
    owned = next(o for o in character.owned_zoids if o.id == character.active_zoid_id)
    slot = weapon["slot"]
    if slot.startswith("fixed_"):
        index = int(slot[-1]) - 1
        key = fixed_weapon_identity(catalog.find("zoids", character.build.zoid), index)
        condition = next((w.condition for w in owned.weapon_conditions if w.weapon_id == key), WeaponCondition())
        return ("fixed", owned.id, key), condition
    index = ("back", "left", "right", "chest").index(slot)
    form = next(f for f in owned.forms if f.zoid == character.build.zoid)
    copy_id = form.equipment_ids[index]
    item = next(i for i in character.inventory if i.id == copy_id)
    return ("equipment", copy_id), item.condition


def combat_snapshot(character, catalog=None):
    """Read-only calculated stats and current loadout conditions for the UI."""
    catalog = catalog or Catalog()
    character = validate_character(character, catalog)
    if not character.owned_zoids:
        raise RuleError("Select an owned Zoid for combat")
    stats = calculate_stats(character.build, catalog)
    weapons = {}
    for weapon in stats["weapons"]:
        if weapon["name"]:
            key, condition = _weapon_target(character, weapon, catalog)
            weapons[weapon["slot"]] = {"identity": key, "condition": condition, "weapon": weapon}
    return stats, weapons


def _set_condition(character, identity, condition):
    if identity[0] == "equipment":
        return replace(character, inventory=tuple(replace(i, condition=condition) if i.id == identity[1] else i
                                                  for i in character.inventory))
    roster = []
    for owned in character.owned_zoids:
        if owned.id == identity[1]:
            conditions = {w.weapon_id: w for w in owned.weapon_conditions}
            conditions[identity[2]] = FixedWeaponCondition(identity[2], condition)
            owned = replace(owned, weapon_conditions=tuple(conditions.values()))
        roster.append(owned)
    return replace(character, owned_zoids=tuple(roster))


def weapon_action(character, slot, action, *, confirmed=False, catalog=None):
    """Use or repair one current slot; return a new character on success."""
    catalog = catalog or Catalog()
    character = validate_character(character, catalog)
    stats, weapons = combat_snapshot(character, catalog)
    if slot not in weapons:
        raise RuleError("Choose an occupied weapon/equipment slot")
    target = weapons[slot]
    weapon, condition = target["weapon"], target["condition"]
    state = WeaponState(condition.broken)
    cost = 0
    if action == "use":
        result = use_weapon(state, current_energy=character.current_energy, energy_cost=weapon["energy_cost"])
        roll = random.randint(1, 20) if rolls_damage(weapon) else condition.last_roll
        condition = WeaponCondition(result.weapon.broken, roll)
        character = replace(character, current_energy=result.energy)
        message = (f"d20: {roll}. " if rolls_damage(weapon) else "Equipment use recorded. ") + f"Spent {weapon['energy_cost']} energy. Resolve the effect at the table."
        if weapon.get("energy_restore"):
            energy = min(stats["energy"], result.energy + weapon["energy_restore"])
            character = replace(character, current_energy=energy)
            message = f"Activated {weapon['name']}. Restored {energy - result.energy} Energy."
    elif action == "repair":
        result = repair_weapon(state, character.gold, current_health=character.current_health,
                               maximum_health=stats["pilot"]["health"], confirmed=confirmed)
        if result.cost:
            condition = replace(condition, broken=result.weapon.broken)
        character, cost = replace(character, gold=result.gold), result.cost
        message = f"Weapon repaired for {cost:,}g." if cost else "Weapon is intact; no gold spent."
    else:
        raise RuleError(f"Unknown weapon action: {action}")
    character = _set_condition(character, target["identity"], condition)
    return CombatResult(validate_character(character, catalog), message, cost)


def start_turn(character, catalog=None):
    """Apply one turn's recharge to the active chassis, capped at total energy."""
    catalog = catalog or Catalog()
    character = validate_character(character, catalog)
    stats, _ = combat_snapshot(character, catalog)
    energy = min(stats["energy"], character.current_energy + stats["energy_recharge"])
    restored = energy - character.current_energy
    character = replace(character, current_energy=energy)
    return CombatResult(validate_character(character, catalog), f"Turn started. Restored {restored} energy.")


def rest(character, catalog=None):
    """Set the active chassis to half its equipped maximum, rounded down."""
    catalog = catalog or Catalog()
    character = validate_character(character, catalog)
    stats, _ = combat_snapshot(character, catalog)
    energy = stats["energy"] // 2
    character = replace(character, current_energy=energy)
    return CombatResult(validate_character(character, catalog), f"Rested. Energy set to {energy} / {stats['energy']}.")


def repair_character_health(character, points=None, catalog=None):
    catalog = catalog or Catalog()
    character = validate_character(character, catalog)
    stats, _ = combat_snapshot(character, catalog)
    result = repair_health(character.current_health, stats["pilot"]["health"], character.gold, points)
    character = validate_character(replace(character, current_health=result.health, gold=result.gold), catalog)
    return CombatResult(character, f"Restored {result.restored} health for {result.cost:,}g.", result.cost)


def attack_preview(character, slot, *, range_band=None, distance=None, catalog=None):
    """Preview only: never roll, spend gold or energy, or modify resources."""
    catalog = catalog or Catalog()
    character = validate_character(character, catalog)
    _, weapons = combat_snapshot(character, catalog)
    if slot not in weapons:
        raise RuleError("Choose an occupied weapon slot")
    return calculate_attack(character.build, slot, current_health=character.current_health,
                            range_band=range_band, distance=distance, catalog=catalog)
