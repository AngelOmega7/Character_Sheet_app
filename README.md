# Zoids offline character app

## Continue on another device

Clone this repository, install **Python 3.10 or newer**, and open a terminal in the cloned directory. The rules/tools use the standard library; the desktop interface uses Flet:

Repository: https://github.com/AngelOmega7/zoids-character-app (private; sign in with an account that has access).

```sh
git clone https://github.com/AngelOmega7/zoids-character-app.git
cd zoids-character-app
```

```sh
python -m unittest discover -s tests -v
python -m zoids_app.preview --snapshot
```

Use `python3` on Linux or `py -3` on Windows if needed. Start a new coding session with `docs/HANDOFF.md` for project status and confirmed rules. Platform packaging will be added in a later milestone.

## Run the character editor (Windows)

From the repository root:

```powershell
python -m venv .venv
.\.venv\Scripts\python -m pip install -r requirements.txt
.\.venv\Scripts\python -m zoids_app
```

Dependency installation and the first Flet desktop-runtime setup may require internet. Once installed, character editing and SQLite saves run locally, without Google Sheets or an account. Android/Windows distributable packages are not built yet.

1. Enter a pilot name, pilot style, level, and Mental; click **Apply pilot details**. Physical and Social, Personality, general inventory/cargo notes, and Zi Database/campaign notes are saved tracking fields. New drafts start with an owned Saberlion.
2. Use **Obtain & select** to record a Zoid acquired in play. The **Owned Zoid** selector only offers this pilot's roster; each base Zoid can be owned once. Obtain CAU forms separately after their base, then switch using **Obtained form**.
3. In **Pilot equipment inventory**, choose equipment and a quantity, then **Acquire equipment**. Multiples are separate owned copies. Attach available copies using the removable-slot dropdowns; slot restrictions still apply. Record upgrade points and toggle activation as needed. Passive bonuses apply automatically.
4. In **Abilities**, choose an ability to read its description, then **Learn / upgrade**. New families enter inactive ownership. Assign them to one of six active slots; choose **Empty / deactivate** to return one to inactive ownership. Higher ranks replace lower ranks in place; only one size ability can be active.
5. In **Organoid**, select White/Red/Blue/Black and level 0–40, then toggle activation. Changes refresh stats immediately; only activated White generates shields. Current health is preserved.
6. In **Combat resources**, record current health, shield damage, and gold, then **Apply resources**. Weapon cards show heat, condition, and attack previews. Ranged cards offer Close/Normal/Long; melee ignores range. Each successful **Use** rolls one d20 and displays its unmodified result in that weapon's **Last d20** box, while applying the normal heat rules. Apply the previewed attack modifier and resolve effects at the table. **Vent** removes one heat; **Rest active loadout** clears heat in the current eight-slot loadout.
7. Click **Save character**. Use **New character** for another pilot, or select a saved pilot and click **Open**. Abilities and Organoid settings are pilot-wide; combat conditions persist through Zoid/form switches, equipment transfers, and reloads.

**Pilot feats** provides seven selections with reference descriptions. Feats and the new pilot tracking fields are handled by players at the table; they do not automate advantage, vent extra weapons, or alter calculated stats. Mental retains its existing calculation rule. Personality is editable text independent of Organoid color.

Health repairs cost **10g per point actually restored**; enter a point amount or leave it blank for full repair. A broken weapon costs **10,000g** to repair and has its heat cleared. If more than 25% of maximum health is missing, the app asks for **Cancel / Repair anyway** before spending gold. An outdated quote cannot be accepted after state changes; click Repair again to review it. Unaffordable actions leave resources unchanged.

Using a weapon at/above its heat capacity rolls and resolves that final use, then breaks it; further uses are blocked and do not roll. Unrated weapons also roll when used. **Last d20** starts empty and retains the most recent result until the next successful Use, including through Vent, Rest, repairs, save/reload, and switching. Fixed-weapon conditions/results follow shared weapon identities across CAU forms; removable conditions/results follow each physical inventory copy. Rest affects only the current loadout, not unrelated stored weapons. Changing range or refreshing a preview adds no heat and never rerolls.

Switching owned Zoids preserves each chassis's upgrades and health. Each obtained form retains its own equipment and activation. Frame upgrades are shared across a base and its CAU forms; fixed-weapon upgrades follow shared base-weapon identity even across different slots. Other form weapons keep separate upgrades. The three legacy claw spellings now display as **Strike Laser Claw**. Acquisition and upgrade controls record decisions from play; they do not deduct gold or enforce purchase costs.

Zoid-acquisition, ability-learning, equipment-acquisition, and removable-equipment dropdowns support **typing to filter** (case-insensitive) as well as scrolling. Clear the search to browse the full list, and select an entry to commit it; typing alone does not acquire or equip anything.

Equipment remains owned when unequipped. One copy can be reused in different CAU forms of the **same owned Zoid**, but not on different Zoids or in multiple slots of one form. A copy referenced by any saved form stays assigned to that Zoid. **Empty / unequip** clears just the selected form's slot; **Return to inventory (all forms)** frees that copy from every saved form so it can be attached elsewhere. The inventory shows each copy's assignments and the number currently unattached.

BLOX Zoids and BLOX Type ranks 1–5 are retired. **Transport** is a separate reference section containing Hover Cargo, Gustav, and Whale King. These are excluded from normal Zoid acquisition and selection. Carrying other Zoids and storing unused collected Zoids will be implemented later.

Invalid fields show an error and cannot overwrite a save. New/Open asks before discarding unsaved changes. The app opens a fresh draft on startup; saved pilots remain available in the selector.

Saves use `characters.sqlite3` under the platform application-support directory, in a `zoids-character-app` subfolder. The full location is shown at the bottom of the editor. To choose a different local save directory, set `ZOIDS_SAVE_DIR` before launch. Schema v7 migrates v1–v6 transactionally, preserving roster, resources, inventory IDs, conditions, last rolls, and archives. It defaults new pilot tracking fields and moves existing Zaber Fang Killer Saber upgrades/activation/conditions to fixed slot 4. Migration never rolls dice or grants replacement Zoids.

Export/import and backups are deferred for now. Purchasing/building rules await the owner's costs/required-parts table; `assets/ZoidNames.txt` lists all 138 current Zoid/CAU/Transport names for that work. Transport rules await the owner's design and **must be implemented before Step 7 is complete**. See `docs/roadmap.md` for the seven-step rollout.

The Step 5 review now uses exact listed Type categories, restores explicit Ranged classifications, renames ranged Energy to Laser, and makes Laser Expert match Laser only. Zaber Fang's restored Laser Machine Gun occupies fixed slot 3, Killer Saber occupies slot 4, and 20mm is Particle. See `docs/rules-review.md` for decisions and remaining deferrals.

The supplied `assets/icon.png` is used in the app header, and `assets/icon.ico` is used for the Windows window icon. The launcher resolves the assets directory from the project path. Distributable platform builds are still a later milestone.

Run all rules, persistence, and headless UI interaction tests:

```powershell
.\.venv\Scripts\python -m unittest discover -s tests -v
```

Without Flet installed, the twenty-three UI interaction tests are skipped; core and persistence tests still run.

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

The inspector does not access the internet or calculate formulas. The XLSX is a development source, not the runtime database. The first Flet character editor and SQLite saves are implemented; platform packages remain pending.

## Initial combat rules

`zoids_app/combat.py` implements heat capacities, overheating breakage, venting, rest, health repairs at 10g per point, and weapon repairs at 10,000g per broken weapon. `combat_controller.py` applies these rules atomically to owned weapon identities and equipment copies, integrated with the editor and saves.

Weapon repair requires explicit confirmation when more than 25% of health is missing. The Flet dialog displays the warning and cost breakdown and rejects stale confirmations.

Run the rule tests with Python 3 (no third-party dependencies):

```sh
python3 -m unittest discover -s tests -v
```
