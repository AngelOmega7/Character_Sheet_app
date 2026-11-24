"""Apply the handbook's owner-confirmed AoE save rule to live effect text."""
import json
from pathlib import Path
import re

DATA = Path(__file__).resolve().parents[1] / "zoids_app/data"
SAVE_TEXT = re.compile(
    r"((?:successful (?:saves|rolls)\s+(?:make )?take)|"
    r"(?:a successful save takes)|(?:On a successful save you take)) no damage",
    re.IGNORECASE,
)
SUCCESS_RULE = "A d20 + Reaction total equal to or greater than the modified attack roll succeeds."


def update():
    count = 0
    for name in ("zoids", "armaments", "transports"):
        path = DATA / f"{name}.json"
        data = json.loads(path.read_text(encoding="utf-8"))
        changed = False
        for record in data["records"]:
            for key, value in record["fields"].items():
                if "effect" not in key or not isinstance(value, str) or "reaction" not in value.lower():
                    continue
                revised = SAVE_TEXT.sub(lambda m: m[1].replace("make take", "take") + " half damage", value)
                revised = revised.replace("On a success they dodge the attack", "On a success they take half damage")
                if revised != value:
                    revised = revised.rstrip()
                    if not revised.endswith("."):
                        revised += "."
                    record["fields"][key] = revised + " " + SUCCESS_RULE
                    count += 1
                    changed = True
        if changed:
            path.write_text(json.dumps(data, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    return count


if __name__ == "__main__":
    print(f"Updated {update()} AoE weapon effects.")
