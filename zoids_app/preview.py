"""Print an offline character calculation without a UI or save file."""
import argparse
from decimal import Decimal
import json

from .combat import RuleError
from .stats import CharacterBuild, Upgrades, calculate_stats


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--zoid", default="Saberlion")
    parser.add_argument("--style", default="FIGHTER", choices=("TANK", "FIGHTER", "SCOUT", "ALMIGHTY"))
    parser.add_argument("--level", type=int, default=1)
    parser.add_argument("--mental", type=int, default=3)
    parser.add_argument("--ability", action="append", default=[])
    parser.add_argument("--snapshot", action="store_true", help="Use the workbook's saved Saberlion example")
    args = parser.parse_args()
    build = CharacterBuild(
        zoid=args.zoid, pilot_style=args.style, pilot_level=args.level,
        mental=args.mental, abilities=tuple(args.ability),
    )
    if args.snapshot:
        build = CharacterBuild("Saberlion", mental=3, abilities=("Lion Type 1",), upgrades=Upgrades(damage=(1, 0, 0, 0)))
    try:
        result = calculate_stats(build)
    except RuleError as exc:
        parser.error(str(exc))

    def encode(value):
        if isinstance(value, Decimal):
            return int(value) if value == value.to_integral_value() else float(value)
        raise TypeError(type(value).__name__)

    print(json.dumps(result, indent=2, default=encode))


if __name__ == "__main__":
    main()
