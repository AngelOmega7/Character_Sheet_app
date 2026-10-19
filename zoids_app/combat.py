"""Combat resource rules, independent of Flet, spreadsheet cells, and storage.

These functions return new immutable state. Callers persist successful results
and leave existing state untouched when an action raises RuleError.
"""

from dataclasses import dataclass, replace

HEALTH_REPAIR_GOLD_PER_POINT = 10
WEAPON_REPAIR_GOLD_COST = 10_000


class RuleError(ValueError):
    """An action cannot be completed with the supplied state."""


class RepairConfirmationRequired(RuleError):
    """The UI must ask the user before retrying this repair as confirmed."""

    def __init__(self, current_health: int, maximum_health: int, gold: int):
        self.health_repair_cost = (maximum_health - current_health) * HEALTH_REPAIR_GOLD_PER_POINT
        self.weapon_repair_cost = WEAPON_REPAIR_GOLD_COST
        self.gold_after_repair = gold - self.weapon_repair_cost
        message = (
            f"Your health is {current_health}/{maximum_health}; more than 25% is missing. "
            f"Repairing this weapon costs {self.weapon_repair_cost:,}g and leaves "
            f"{self.gold_after_repair:,}g. Restoring all missing health costs "
            f"{self.health_repair_cost:,}g. "
        )
        if self.gold_after_repair < self.health_repair_cost:
            message += "You will not have enough gold left to fully repair health. "
        super().__init__(message + "Repair weapon anyway?")


def _nonnegative_integer(value: int, name: str) -> None:
    if type(value) is not int or value < 0:
        raise RuleError(f"{name} must be a nonnegative integer")


@dataclass(frozen=True)
class WeaponState:
    heat_rating: int | None = None
    heat: int = 0
    broken: bool = False

    def __post_init__(self):
        if self.heat_rating is not None and (
            type(self.heat_rating) is not int or self.heat_rating not in (1, 2, 3)
        ):
            raise RuleError("Heat rating must be 1, 2, 3, or None")
        _nonnegative_integer(self.heat, "Heat")
        if type(self.broken) is not bool:
            raise RuleError("Broken state must be a Boolean")
        if self.heat_rating is None and self.heat != 0:
            raise RuleError("A weapon without a heat rating cannot accumulate heat")


@dataclass(frozen=True)
class WeaponUse:
    weapon: WeaponState
    broke_after_use: bool


def use_weapon(weapon: WeaponState, *, heat_capacity_bonus: int = 0) -> WeaponUse:
    """A successful use at/above capacity works, then breaks the weapon.

    Raising RuleError means no shot/use occurs. Otherwise the caller resolves
    the shot even when broke_after_use is true. This does not imply a hit.
    """
    if type(heat_capacity_bonus) is not int or heat_capacity_bonus not in (0, 1):
        raise RuleError("Heat capacity bonus must be 0 or 1")
    if weapon.broken:
        raise RuleError("Weapon is broken and must be repaired before use")
    if weapon.heat_rating is None:
        return WeaponUse(weapon, False)
    breaks = weapon.heat >= weapon.heat_rating + heat_capacity_bonus
    return WeaponUse(replace(weapon, heat=weapon.heat + 1, broken=breaks), breaks)


def vent_weapon(weapon: WeaponState) -> WeaponState:
    """Venting removes one heat; it never repairs a broken weapon."""
    return replace(weapon, heat=max(0, weapon.heat - 1))


def rest_weapons(weapons: tuple[WeaponState, ...]) -> tuple[WeaponState, ...]:
    """Reset heat across slots without repairing weapons."""
    return tuple(replace(weapon, heat=0) for weapon in weapons)


def restore_repaired_weapon(weapon: WeaponState) -> WeaponState:
    """Apply a completed repair: clear broken status and reset heat to zero.

    This is only the state transition, not a purchase. Use repair_weapon for
    the paid transaction, including balance validation and deduction.
    """
    return replace(weapon, heat=0, broken=False)


@dataclass(frozen=True)
class WeaponRepair:
    weapon: WeaponState
    gold: int
    cost: int


def repair_weapon(
    weapon: WeaponState,
    gold: int,
    *,
    current_health: int,
    maximum_health: int,
    confirmed: bool = False,
) -> WeaponRepair:
    """Repair one broken weapon for 10,000g, resetting its heat.

    Reject unaffordable repairs without changing state. An intact weapon is
    unchanged and incurs no charge; this action is not a cooling shortcut.

    More than 25% missing health requires explicit confirmation. The UI should
    catch RepairConfirmationRequired and offer Cancel / Repair anyway. Only
    retry with confirmed=True for that action after acceptance; never persist
    confirmation as a character setting. Use current state for the retry and
    request confirmation again if the quoted health, balance, or weapon changed.
    """
    _nonnegative_integer(gold, "Gold")
    _nonnegative_integer(current_health, "Current health")
    _nonnegative_integer(maximum_health, "Maximum health")
    if maximum_health == 0:
        raise RuleError("Maximum health must be greater than zero")
    if type(confirmed) is not bool:
        raise RuleError("Confirmation must be a Boolean")
    if not weapon.broken:
        return WeaponRepair(weapon, gold, 0)
    if gold < WEAPON_REPAIR_GOLD_COST:
        raise RuleError(
            f"Weapon repair costs {WEAPON_REPAIR_GOLD_COST}g, but only {gold}g is available"
        )
    if (maximum_health - current_health) * 4 > maximum_health and not confirmed:
        raise RepairConfirmationRequired(current_health, maximum_health, gold)
    return WeaponRepair(
        restore_repaired_weapon(weapon),
        gold - WEAPON_REPAIR_GOLD_COST,
        WEAPON_REPAIR_GOLD_COST,
    )


@dataclass(frozen=True)
class HealthRepair:
    health: int
    gold: int
    restored: int
    cost: int


def repair_health(
    current_health: int,
    maximum_health: int,
    gold: int,
    points: int | None = None,
) -> HealthRepair:
    """Restore selected points, or all missing health, for 10g per point.

    An unaffordable request is rejected atomically; callers can request fewer
    points explicitly. No overheal is granted and already-full health is free.
    Maximum health must be the character's latest derived value.
    """
    for name, value in (("Current health", current_health), ("Maximum health", maximum_health), ("Gold", gold)):
        _nonnegative_integer(value, name)
    missing = max(0, maximum_health - current_health)
    if points is not None:
        _nonnegative_integer(points, "Repair points")
    restored = missing if points is None else min(points, missing)
    cost = restored * HEALTH_REPAIR_GOLD_PER_POINT
    if cost > gold:
        raise RuleError(f"Repair costs {cost}g, but only {gold}g is available")
    return HealthRepair(current_health + restored, gold - cost, restored, cost)
