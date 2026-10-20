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

1. **Overview:** create a pilot with 10,000g and purchase a non-CAU starter costing at most 10,000g. Other starter prerequisites are waived. Select pilot style (including NPC), Organoid (None by default), owned chassis, and CAU form. Multiple instances of a model are allowed; required level is displayed.
2. **Pilot:** edit gold/notes, learn and assign abilities, track feats, record General Inventory item quantities, and add known designs to Zi Database. Existing notes remain available separately from these structured records.
3. **Overview purchasing:** select a design, host/base instance if needed, and review the quote. Normal purchases consume CSV costs and prerequisites; failed recipe checks offer a separate GM Override. CAUs can be detached with a quoted refund. See `docs/workflow.md` for replacement and refund rules.
4. **Upgrades:** use paid +/− counters (0–5); chassis tiers cost 5,000g × tier and weapon tiers 10,000g × tier. Minus refunds the full removed tier cost. Acquire and attach equipment copies here; removable equipment still has no purchasing costs.
5. **Combat:** record health/shield damage, use/vent/repair weapons, and rest the active loadout. Only occupied slots are shown. Numerical-damage weapons roll one d20 on Use; non-damaging utilities keep activation controls without a die roller.
6. **Transport:** choose None/Gustav/Hover Cargo/Dragoon Nest/Whale King, inspect base stats, and load/unload owned chassis within size/capacity limits. Changing transport unloads cargo without deleting Zoids. Calculated Stats appears on every other page.
7. **Save character** retains edits and combat state. Closing or switching characters with unsaved changes offers Keep editing, Discard changes, or Save; unsuccessful saves cancel the transition.

**Pilot feats** provides seven selections with reference descriptions. Feats and the new pilot tracking fields are handled by players at the table; they do not automate advantage, vent extra weapons, or alter calculated stats. Mental retains its existing calculation rule. Personality is editable text independent of Organoid color.

Health repairs cost **10g per point actually restored**; enter a point amount or leave it blank for full repair. A broken weapon costs **10,000g** to repair and has its heat cleared. If more than 25% of maximum health is missing, the app asks for **Cancel / Repair anyway** before spending gold. An outdated quote cannot be accepted after state changes; click Repair again to review it. Unaffordable actions leave resources unchanged.

Using a weapon at/above its heat capacity resolves that final use, then breaks it; further uses are blocked. Numerical-damage weapons roll even if unrated; utilities without numerical damage do not roll. **Last d20** retains the latest weapon result through Vent, Rest, repairs, reloads, and switching. Fixed conditions/results follow shared identities across CAU forms; removable conditions/results follow physical copies. Rest affects the current loadout only. Changing range or refreshing never rerolls.

Switching preserves chassis upgrades/health and each form's loadout. Frame upgrades are shared across CAUs; fixed upgrades follow matching base-weapon identity across slots. Consuming a Base Zoid in a purchase does not transfer upgrades; equipped copies return to inventory. Upgraded CAUs replace their predecessor while retaining the host. Detachment refunds half the CSV price plus current/predecessor Parts, losing form-specific upgrades.

Zoid-acquisition, ability-learning, equipment-acquisition, and removable-equipment dropdowns support **typing to filter** (case-insensitive) as well as scrolling. Clear the search to browse the full list, and select an entry to commit it; typing alone does not acquire or equip anything.

Equipment remains owned when unequipped. One copy can be reused in different CAU forms of the **same owned Zoid**, but not on different Zoids or in multiple slots of one form. A copy referenced by any saved form stays assigned to that Zoid. **Empty / unequip** clears just the selected form's slot; **Return to inventory (all forms)** frees that copy from every saved form so it can be attached elsewhere. The inventory shows each copy's assignments and the number currently unattached.

BLOX content is retired. Dragon Nest is renamed Dragoon Nest and joins the four Transport choices. Size order is Small, Medium, Large, Large Large, Extra Large. Capacity/maximum size: Gustav 2/Medium; Hover Cargo 6/Large; Dragoon Nest 12/Large Large; Whale King 24/Extra Large. Each owned chassis uses one bay, including its CAUs.

Invalid fields show an error and cannot overwrite a save. New/Open asks before discarding unsaved changes. The app opens a fresh draft on startup; saved pilots remain available in the selector.

Saves use `characters.sqlite3` in the platform application-support directory, with an optional `ZOIDS_SAVE_DIR` override. Schema v8 migrates older saves transactionally. Former standalone variants become separate host-plus-CAU instances rather than being merged. Existing gold, upgrades, notes, inventory identities, and conditions are retained through the new ownership and weapon mappings. See `docs/workflow.md` for details.

Export/import/backups remain deferred. The supplied purchasing, Transport, and expanded-CAU workflow is implemented. `assets/ZoidNames.txt` lists all 138 current names. NPC contributes zero style progression bonuses; Organoid None cannot activate. Catalog Lion terminology is now Liger, except the name Saberlion. Packaging is the next separate stage after owner review.

Prices and CAU families are compiled from the source assets. After editing `zoid_cost.csv` or `CAU_expand.txt`, run `python tools/convert_reference_data.py` and restart the app. Refresh the names worksheet explicitly with `python tools/export_zoid_names.py`. The importer applies the approved CSV typo corrections without overwriting the source CSV.

The Step 5 review now uses exact listed Type categories, restores explicit Ranged classifications, renames ranged Energy to Laser, and makes Laser Expert match Laser only. Zaber Fang's restored Laser Machine Gun occupies fixed slot 3, Killer Saber occupies slot 4, and 20mm is Particle. See `docs/rules-review.md` for decisions and remaining deferrals.

The supplied `assets/icon.png` is used in the app header, and `assets/icon.ico` is used for the Windows window icon. The launcher resolves the assets directory from the project path. Distributable platform builds are still a later milestone.

Run all rules, persistence, and headless UI interaction tests:

```powershell
.\.venv\Scripts\python -m unittest discover -s tests -v
```

Current baseline: **200 tests passing**. Without Flet installed, 28 UI interaction tests are skipped; core and persistence tests still run.

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
