"""Shared frame-upgrade limits and marginal purchase/refund prices."""
from .combat import RuleError

UPGRADE_LIMITS = {
    "speed": 5, "reaction": 5, "defense": None, "capacity": 5,
    "accuracy": None, "armor": 5, "ept": None,
}


def upgrade_price(field, rank):
    """Price of one point at the given resulting rank (also its refund)."""
    if field not in UPGRADE_LIMITS or type(rank) is not int or rank < 1:
        raise RuleError("Choose a valid frame upgrade and positive rank")
    if field == "ept":
        return 10_000 * 2 ** (rank - 1)
    return 5000 * rank + (20000 if field == "armor" else 0)
