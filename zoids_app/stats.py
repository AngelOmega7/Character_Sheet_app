"""Deterministic Python translation of the workbook's stat calculation paths.

This follows the source rules plus documented owner-confirmed corrections.
No spreadsheet engine, cached character totals, network, or dice rolls are used.
"""
from dataclasses import dataclass, field
from decimal import Decimal, ROUND_HALF_UP, ROUND_UP
import re

from .catalog import Catalog
from .combat import RuleError
from .abilities import AbilityLoadout, validate_loadout
from .tags import weapon_tags


def number(value):
    if value is None or value == "":
        return Decimal(0)
    if isinstance(value, bool):
        raise RuleError("A Boolean cannot be used as a numeric stat")
    try:
        result = Decimal(str(value))
    except Exception as exc:
        raise RuleError(f"Not a numeric stat: {value!r}") from exc
    if not result.is_finite():
        raise RuleError("Stats must be finite")
    return result


def sheet_round(value):
    return int(number(value).quantize(Decimal(1), rounding=ROUND_HALF_UP))


def sheet_roundup(value):
    return int(number(value).quantize(Decimal(1), rounding=ROUND_UP))


@dataclass(frozen=True)
class Upgrades:
    speed: int = 0
    reaction: int = 0
    defense: int = 0
    capacity: int = 0
    damage: tuple[int, ...] = (0, 0, 0, 0)
    to_hit: tuple[int, ...] = (0, 0, 0, 0)

    def __post_init__(self):
        if len(self.damage) != 4 or len(self.to_hit) != 4:
            raise RuleError("Four fixed-weapon upgrade slots are required")
        for points in (self.speed, self.reaction, self.defense, self.capacity, *self.damage, *self.to_hit):
            if type(points) is not int or not 0 <= points <= 5:
                raise RuleError("Upgrade points must be integers from 0 through 5")


@dataclass(frozen=True)
class CharacterBuild:
    zoid: str
    pilot_style: str = "FIGHTER"
    pilot_level: int = 1
    mental: int = 0
    abilities: tuple[str | None, ...] = ()
    equipment: tuple[str | None, ...] = (None, None, None, None)
    equipment_active: tuple[bool, ...] = (False, False, False, False)
    fixed_active: tuple[bool, ...] = (False, False, False, False)
    upgrades: Upgrades = field(default_factory=Upgrades)
    organoid_enabled: bool = False
    organoid_color: str = "Black"
    organoid_level: int = 1
    defense_up: int = 0
    defense_down: int = 0
    shield_adjustment: int = 0
    inactive_abilities: tuple[str, ...] = ()

    def __post_init__(self):
        if len(self.abilities) > 6:
            raise RuleError("At most six active abilities are supported")
        if any(len(v) != 4 for v in (self.equipment, self.equipment_active, self.fixed_active)):
            raise RuleError("Exactly four fixed and removable equipment slots are required")
        for value in (*self.equipment_active, *self.fixed_active, self.organoid_enabled):
            if type(value) is not bool:
                raise RuleError("Activation flags must be Booleans")
        for name in ("pilot_level", "mental", "organoid_level", "defense_up", "defense_down", "shield_adjustment"):
            value = getattr(self, name)
            if type(value) is not int or value < 0:
                raise RuleError(f"{name} must be a nonnegative integer")


def calculate_stats(build: CharacterBuild, catalog: Catalog | None = None):
    """Calculate base, pilot, current stats and all eight weapon displays.

    Combat resources (current health, heat, broken status, gold) are deliberately
    not modified or recomputed here. Activation is separate from firing.
    """
    catalog = catalog or Catalog()
    zoid = catalog.find("zoids", build.zoid)
    loadout = validate_loadout(AbilityLoadout(build.abilities, build.inactive_abilities), catalog)
    abilities = [catalog.find("abilities", a) if a else None for a in loadout.active]
    abilities += [None] * (6 - len(abilities))
    equipment = [catalog.find("armaments", e) if e else None for e in build.equipment]
    if any(e and e["kind"] == "heading" for e in equipment):
        raise RuleError("An equipment heading cannot be equipped")
    warnings = []
    pilot_speed = None

    def col(record, index):
        if record is None:
            return None
        dataset = record["id"].split(":")[0]
        key = catalog.tables[dataset]["columns"][index - 1]
        expression = record["dynamic_fields"].get(key)
        if not expression:
            return record["fields"][key]
        if expression == "Zoid!D17" and pilot_speed is not None:
            return pilot_speed
        match = re.fullmatch(r"vlookup\(Zoid!C4,Zoid_DB\[\],(\d+),FALSE(?:\(\))?\)", expression, re.I)
        if match:
            return col(zoid, int(match[1]))
        raise RuleError(f"Unresolved dynamic reference: {record['id']}.{key}: {expression}")

    def n(record, index):
        return number(col(record, index))

    def damage_note(record, index):
        if record is None:
            return None
        dataset = record["id"].split(":")[0]
        key = catalog.tables[dataset]["columns"][index - 1]
        expression = record["dynamic_fields"].get(key, "")
        match = re.fullmatch(r"vlookup\(Zoid!C4,Zoid_DB\[\],(\d+),FALSE(?:\(\))?\)", expression, re.I)
        if match:
            return damage_note(zoid, int(match[1]))
        return record.get("damage_notes", {}).get(key)

    def contains(needle, haystack):
        # Source SEARCH is case-insensitive. Blank numeric lookup cells behave
        # as zero; do not accidentally make a blank ability match every string.
        return str(needle if needle is not None else 0).casefold() in str(haystack if haystack is not None else 0).casefold()

    def total(index):
        return sum((n(a, index) for a in abilities), Decimal(0))

    zoid_type, size = col(zoid, 3), col(zoid, 4)
    bonus_levels = max((n(a, 3) for a in abilities if a and str(zoid_type).strip().casefold()
                        in {t.strip().casefold() for t in a.get("eligible_types", [])}), default=Decimal(0))
    effective_level = number(build.pilot_level) + bonus_levels
    if effective_level != int(effective_level):
        raise RuleError("Effective pilot level must be an integer")
    style = build.pilot_style.lower()
    if style not in ("tank", "fighter", "scout", "almighty"):
        raise RuleError(f"Unknown pilot style: {build.pilot_style}")
    progression = catalog.find(style, str(int(effective_level)))
    matching_size = next((a for a in abilities if a and str(size).strip().casefold() in {s.casefold() for s in a["eligible_sizes"]}), None)
    all_stats = n(matching_size, 5)

    org = {key: Decimal(0) for key in ("health", "armor", "speed", "range", "to_hit", "damage", "shield")}
    if build.organoid_enabled:
        colors = {"White": 2, "Red": 7, "Blue": 12, "Black": 17}
        if build.organoid_color not in colors:
            raise RuleError(f"Unknown Organoid color: {build.organoid_color}")
        record = catalog.find("organoids", str(build.organoid_level))
        start = colors[build.organoid_color]
        for offset, stat in enumerate(("health", "armor", "speed", "range", "to_hit")):
            org[stat] = n(record, start + offset)
        org["damage"] = org["to_hit"]  # Dashboard H23 reads F rather than H.
        if build.organoid_color == "White":
            org["shield"] = n(record, 22)

    u = build.upgrades
    capacity = n(zoid, 12) + u.capacity * 10
    load = sum((n(e, 12) for e in equipment), Decimal(0))
    overloaded = load > capacity
    underleveled = effective_level < n(zoid, 5)
    penalty = Decimal("0.6") if overloaded or underleveled else Decimal(1)
    base = {
        "health": n(zoid, 6), "armor": n(zoid, 7),
        "defense": n(zoid, 8) + u.defense * 5,
        "speed": sheet_roundup(n(zoid, 9) * penalty) + u.speed * 30,
        "reaction": sheet_roundup(n(zoid, 10) * penalty) + u.reaction,
        "range": n(zoid, 11),
    }
    pilot = {
        "health": sheet_round(base["health"] * (1 + n(progression, 2) + all_stats + org["health"])),
        "armor": sheet_round(base["armor"] * (1 + n(progression, 3) + all_stats + (total(6) if matching_size else 0) + org["armor"])),
        "defense": base["defense"],
        "speed": sheet_round(base["speed"] * (1 + org["speed"])),
        "reaction": sheet_round(number(base["reaction"]) * (1 + n(progression, 4) + all_stats)) + build.mental,
        "range": base["range"] * (1 + n(progression, 5) + all_stats + org["range"]),
    }
    pilot_speed = pilot["speed"]

    equipment_enabled = [
        bool(e and e["kind"] != "placeholder" and (active or contains("Passive", col(e, 13))))
        for e, active in zip(equipment, build.equipment_active)
    ]
    # Only fixed slots 2 and 3 have these stat-modifier fields in the source.
    fixed_modifiers_enabled = [
        active or contains("Passive", col(zoid, activation_column))
        for active, activation_column in zip(build.fixed_active[1:3], (29, 40))
    ]

    def equipment_bonus(index):
        return sum((n(e, index) for e, enabled in zip(equipment, equipment_enabled) if enabled), Decimal(0))

    def active_bonus(equipment_column, fixed_columns):
        return equipment_bonus(equipment_column) + sum((n(zoid, c) for c, enabled in zip(fixed_columns, fixed_modifiers_enabled) if enabled), Decimal(0))

    defensive_items = sum(enabled and n(e, 6) > 0 for e, enabled in zip(equipment, equipment_enabled))
    reaction_items = sum(enabled and n(e, 10) > 0 for e, enabled in zip(equipment, equipment_enabled))
    reaction_items += sum(enabled and n(zoid, column) > 0 for column, enabled in zip((27, 38), fixed_modifiers_enabled))
    evasion_rank = sum(a.get("armor_per_reaction_item", 0) for a in abilities if a)
    heat_capacity_bonus = sum(a.get("heat_capacity_bonus", 0) for a in abilities if a)

    current = {
        "armor": sheet_round(pilot["armor"] + equipment_bonus(7) + reaction_items * evasion_rank),
        "defense": sheet_round(pilot["defense"] + equipment_bonus(6) + total(13) * defensive_items + total(15) + build.defense_up - build.defense_down),
        "speed": pilot["speed"] + active_bonus(11, (25, 36)) + total(8),
        "reaction": sheet_round(pilot["reaction"] + active_bonus(10, (27, 38)) + total(10)),
        "range": pilot["range"] + active_bonus(9, (28, 39)),
    }
    # The source only has shield fields for fixed units 2 and 3.
    # Each belongs to its own unit, just like removable units 5–8.
    shields = active_bonus(14, (24, 35)) + org["shield"]
    if shields > 0:
        shields += total(12)
    shields -= build.shield_adjustment
    hit_bonus = active_bonus(8, (26, 37))

    def weapon_skill_bonus(damage_type):
        tags = weapon_tags(damage_type)
        eligible = [a for a in abilities if a and weapon_tags(col(a, 14)) and weapon_tags(col(a, 14)) <= tags]
        # Anti-Air Pro is additive; other Expert families compete for one bonus.
        strongest = max((n(a, 7) for a in eligible if a["family"] != "anti_air_pro"), default=Decimal(0))
        anti_air = sum((n(a, 7) for a in eligible if a["family"] == "anti_air_pro"), Decimal(0))
        return strongest + anti_air

    weapons = []
    for i, (name_col, damage_col, type_col, hit_col, effect_col) in enumerate(((13, 15, 16, 17, 14), (19, 21, 22, 23, 20), (30, 32, 33, 34, 31), (41, 43, 44, 45, 42))):
        raw_damage = col(zoid, damage_col)
        base_hit = sheet_roundup(n(zoid, hit_col) * (Decimal("0.6") if overloaded else 1))
        skill_hit = weapon_skill_bonus(col(zoid, type_col))
        if isinstance(raw_damage, str):
            damage_bonus = None
            warnings.append(f"{zoid['name']} fixed_{i + 1}: textual damage {raw_damage!r} requires adjudication; spreadsheet arithmetic is invalid")
        else:
            damage_bonus = sheet_round(u.damage[i] * 20 + (number(raw_damage) + u.damage[i] * 20) * org["damage"])
        weapons.append({
            "slot": f"fixed_{i + 1}", "name": col(zoid, name_col), "effect": col(zoid, effect_col),
            "damage_type": col(zoid, type_col), "base_damage": raw_damage,
            "damage_note": damage_note(zoid, damage_col),
            "damage_bonus": damage_bonus, "base_to_hit": base_hit + u.to_hit[i],
            "damage_upgrade": u.damage[i] * 20, "damage_percent": org["damage"],
            # Owner correction: fixed-slot upgrades add a flat bonus to the
            # final attack modifier; removable slots have no upgrade inputs.
            "to_hit": sheet_round(base_hit * (1 + n(progression, 6) + all_stats + org["to_hit"]) + hit_bonus + skill_hit) + u.to_hit[i],
            "heat_rating": col(zoid, 85 + i),
        })
    for slot, e in zip(("back", "left", "right", "chest"), equipment):
        raw_damage = col(e, 2)
        if isinstance(raw_damage, str):
            damage_bonus = None
            warnings.append(f"{slot}: textual damage {raw_damage!r} requires adjudication; spreadsheet arithmetic is invalid")
        else:
            damage_bonus = sheet_round(number(raw_damage) * org["damage"])
        weapons.append({
            "slot": slot, "name": col(e, 1), "effect": col(e, 4), "damage_type": col(e, 3),
            "base_damage": raw_damage, "damage_bonus": damage_bonus,
            "damage_upgrade": 0, "damage_percent": org["damage"],
            "damage_note": damage_note(e, 2),
            "base_to_hit": n(e, 5), "to_hit": sheet_round(n(e, 5) * (1 + n(progression, 6) + all_stats + org["to_hit"]) + hit_bonus + weapon_skill_bonus(col(e, 3))),
            "heat_rating": col(e, 16),
        })
    for weapon in weapons:
        weapon["heat_capacity_bonus"] = heat_capacity_bonus if weapon["heat_rating"] is not None else 0
        weapon["maximum_heat"] = weapon["heat_rating"] + weapon["heat_capacity_bonus"] if weapon["heat_rating"] is not None else None
    return {
        "ruleset": "owner-corrected-v13", "zoid_id": zoid["id"],
        "size_bonus": all_stats,
        "bonus_levels": bonus_levels, "effective_level": effective_level,
        "base": base, "pilot": pilot, "current": current,
        "carry_capacity": capacity, "carry_load": load, "overloaded": overloaded,
        "underleveled": underleveled, "standard_weapon_range": pilot["range"] / 2,
        "shields": sheet_round(shields), "weapons": weapons, "warnings": warnings,
    }
