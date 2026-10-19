"""Extract independent expected values from the workbook's saved character."""
import json
from pathlib import Path
import re

ROOT = Path(__file__).resolve().parents[1]


def extract():
    raw = json.loads((ROOT / "docs/generated/workbook_inventory.json").read_text())
    sheets = {s["name"]: {c["address"]: c["value"] for c in s["cells"]} for s in raw["sheets"]}
    z, p = sheets["Zoid"], sheets["Pilot"]
    expected = {}
    for group, letter in (("base", "C"), ("pilot", "D"), ("current", "E")):
        expected[group] = {stat: float(z[f"{letter}{row}"]) for row, stat in enumerate(("health", "armor", "defense", "speed", "reaction", "range"), 14) if not (group == "current" and stat == "health")}
    expected.update({key: float(z[cell]) for key, cell in {"bonus_levels": "C10", "carry_capacity": "C20", "carry_load": "C21", "standard_weapon_range": "E21", "shields": "F14"}.items()})
    expected["weapon_to_hit"] = [int(re.search(r"(-?\d+)\s*$", z[f"E{row}"])[1]) for row in (25, 30, 35, 40, 47, 54, 61, 68)]
    fixture = {
        "source": "Original workbook cached results, not Python-generated expectations",
        "build": {"zoid": z["C4"], "pilot_style": z["C11"], "pilot_level": int(float(z["C9"])), "mental": int(float(p["C5"])), "abilities": [p[f"B{row}"] for row in (14, 18, 22, 26, 30, 34) if not re.fullmatch(r"[-\s]+", p[f"B{row}"]) ]},
        "upgrades": {"damage": [1, 0, 0, 0]},
        "upgrade_provenance": "Zoid Upgrades!E12 contains +20 damage (one +20 point); other snapshot upgrade cells are empty.",
        "expected": expected,
    }
    path = ROOT / "tests/fixtures/saberlion_snapshot.json"
    path.parent.mkdir(exist_ok=True)
    path.write_text(json.dumps(fixture, indent=2) + "\n")
    print(path)


if __name__ == "__main__":
    extract()
