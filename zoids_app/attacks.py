"""Per-attack contextual bonuses; preview only, without rolls or resource edits."""
from .catalog import Catalog
from .combat import RuleError
from .stats import CharacterBuild, calculate_stats, number, sheet_round
from .tags import weapon_tags

RANGE_BANDS = ("close", "normal", "long")


def range_band_for_distance(distance, maximum_range):
    """Close takes priority through 60m; Normal extends to half maximum range."""
    distance, maximum_range = number(distance), number(maximum_range)
    if distance < 0 or maximum_range <= 0:
        raise RuleError("Distance must be nonnegative and maximum range positive")
    half = maximum_range / 2
    if distance <= 60:
        return "close"
    return "normal" if distance <= half else "long"


def calculate_attack(
    build: CharacterBuild,
    slot: str,
    *,
    current_health: int,
    range_band: str | None = None,
    distance: int | float | None = None,
    catalog: Catalog | None = None,
):
    """Preview one weapon's to-hit and damage with Sniper/Comeback applied.

    Range bands are mutually exclusive per attack, not global activation flags.
    Ranged attacks require a band; melee attacks ignore the range selection.
    This does not fire a weapon or change heat, health, gold, or broken status.
    """
    if type(current_health) is not int or current_health < 0:
        raise RuleError("Current health must be a nonnegative integer")
    catalog = catalog or Catalog()
    stats = calculate_stats(build, catalog)
    weapon = next((w for w in stats["weapons"] if w["slot"] == slot), None)
    if weapon is None:
        raise RuleError(f"Unknown weapon slot: {slot}")
    if not weapon["name"] or weapon["base_damage"] is None:
        raise RuleError("Selected slot has no damaging attack")
    tags = weapon_tags(weapon["damage_type"])
    is_ranged = "ranged" in tags and "melee" not in tags
    if is_ranged and distance is not None:
        computed_band = range_band_for_distance(distance, stats["current"]["range"])
        if range_band is not None and range_band != computed_band:
            raise RuleError("Selected range band does not match attack distance")
        range_band = computed_band
    if is_ranged and range_band not in RANGE_BANDS:
        raise RuleError("Choose close, normal, or long range for a ranged attack")
    skills = [catalog.find("abilities", a) for a in build.abilities if a]
    sniper_bonus = sum(a.get("long_range_to_hit_bonus", 0) for a in skills) if is_ranged and range_band == "long" else 0
    comeback_percent = sum(
        (number(a["fields"]["damage_bonus"]) for a in skills if a.get("family") == "comeback"),
        number(0),
    ) if stats["pilot"]["health"] > 0 and current_health * 5 <= stats["pilot"]["health"] else number(0)
    upgraded_damage = number(weapon["base_damage"]) + weapon["damage_upgrade"]
    # Percentage bonuses add to the same upgraded base, with one final rounding.
    percent = number(weapon["damage_percent"]) + comeback_percent
    total_damage = number(weapon["base_damage"]) + sheet_round(weapon["damage_upgrade"] + upgraded_damage * percent)
    return {
        "slot": slot, "name": weapon["name"], "ranged": is_ranged,
        "range_band": range_band if is_ranged else None,
        "maximum_range": stats["current"]["range"],
        "long_range_threshold": stats["current"]["range"] / 2,
        "maximum_health": stats["pilot"]["health"],
        "sniper_bonus": sniper_bonus, "comeback_percent": comeback_percent,
        "to_hit": weapon["to_hit"] + sniper_bonus, "damage": total_damage,
    }
