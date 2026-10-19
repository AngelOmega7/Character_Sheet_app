# Zoids offline character app

## Continue on another device

Clone this repository, install **Python 3.10 or newer**, and open a terminal in the cloned directory. No third-party packages are needed for the current rules/tools:

Repository: https://github.com/AngelOmega7/zoids-character-app (private; sign in with an account that has access).

```sh
git clone https://github.com/AngelOmega7/zoids-character-app.git
cd zoids-character-app
```

```sh
python -m unittest discover -s tests -v
python -m zoids_app.preview --snapshot
```

Use `python3` on Linux or `py -3` on Windows if needed. Start a new coding session with `docs/HANDOFF.md` for project status and confirmed rules. Flet and platform packaging will be added in a later milestone.

Before switching devices, commit and push your changes. On the other device, pull the latest changes before continuing. The source workbook and generated reference data are included, so cloning does not require access to Google Sheets.

## Project overview

Initial workbook audit and migration specification for a Python/Flet Android and Windows app.

The offline reference catalogs and first stat-calculation engine are now implemented. See `docs/data-and-rules.md` for usage, coverage, and source-rule issues requiring decisions.

Preview the saved character's calculated stats:

```sh
python3 -m zoids_app.preview --snapshot
```

## Start here

- `docs/conversion-specification.md`: proposed data model, source mappings, rules requirements, unresolved semantics, and implementation milestones.
- `docs/apps-script-migration.md`: reviewed heat/resource actions, optional GIF behavior, and remaining combat-rule questions.
- `docs/data-and-rules.md`: extracted data, calculation API, verification, and formula findings.
- `docs/generated/inventory.md`: worksheet and formula summary.
- `docs/generated/workbook_inventory.json`: exported cells, formulas, validation rules, named ranges, and table definitions.
- `docs/generated/formulas.json`: formula-cell audit with source addresses and cached results.
- `source/character_sheet.xlsx`: one-time read-only source snapshot.

## Reproduce the inventory offline

Requires Python 3; no third-party dependencies.

```sh
python3 tools/inspect_workbook.py source/character_sheet.xlsx docs/generated
```

The inspector does not access the internet or calculate formulas. The XLSX is a development source, not the intended runtime database. No playable app or platform package has been implemented yet.

## Initial combat rules

`zoids_app/combat.py` implements heat capacities, overheating breakage, venting, rest, health repairs at 10g per point, and weapon repairs at 10,000g per broken weapon. Successful weapon repairs reset heat and clear broken status; insufficient funds reject the repair. UI and save integration are pending.

Weapon repair also requires explicit confirmation when more than 25% of health is missing. The rules provide the warning and cost breakdown; the Flet confirmation dialog is pending with the rest of the UI.

Run the rule tests with Python 3 (no third-party dependencies):

```sh
python3 -m unittest discover -s tests -v
```
