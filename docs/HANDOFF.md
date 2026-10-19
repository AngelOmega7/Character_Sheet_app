# Development handoff

## Goal and current state

Build a fully offline Python/Flet RPG character manager for Android and Windows, migrated from a multi-sheet Google workbook. The workbook is initial source/reference only: the installed app must never connect to or modify Google Sheets.

Implemented: local reference catalogs, stat calculation, owned abilities/equipment/Zoids/CAU forms, Flet editor with pilot fields/feat tracking, upgrade/Organoid controls and searchable dropdowns, resource tracking, persistent weapon conditions and last d20 results, combat actions and previews, Transport reference section, supplied app icons, and versioned SQLite saves. Current baseline: **183 tests passing** with Flet installed (twenty-three UI tests skip without it). Python 3.10+ is required; the rules/storage use the standard library and the UI uses pinned Flet 1.0.4. Android/Windows distributable packages are pending.

New drafts start with an owned Saberlion and empty equipment inventory. Each base Zoid can be owned once; equipment types can be acquired multiple times. Switching preserves chassis upgrades/resources and form equipment/activation. Abilities, Organoid settings, inventory, gold, pilot notes, and feats stay pilot-wide. Fixed-weapon conditions/results follow shared weapon IDs; removable conditions/results follow inventory-copy IDs. Save schema v7 migrates v1–v6, defaults new pilot fields, and moves Zaber Fang's existing Killer Saber upgrades/activation/conditions to slot 4 without giving them to the restored slot-3 Laser Machine Gun. Saves use the platform application-support directory (path shown in the editor), with an optional `ZOIDS_SAVE_DIR` override.

## Where to start

- `docs/data-and-rules.md`: current calculation rules, resolved issues, remaining discrepancies.
- `docs/ability-review.md`: ability decisions and remaining work.
- `docs/roadmap.md`: agreed seven-step rollout, owner deferrals, and Transport's Step 7 completion requirement.
- `docs/rules-review.md`: current Step 5 decisions and Zaber Fang correction/migration.
- `docs/apps-script-migration.md`: original scripts and owner-confirmed changes.
- `docs/conversion-specification.md`: overall migration milestones.
- `zoids_app/stats.py`, `abilities.py`, `equipment.py`, `attacks.py`, `combat.py`: implemented rules. `characters.py` handles owned inventory and ability transitions; `combat_controller.py` applies atomic combat commands to persistent identities. The calculator accepts supplied builds directly.
- `zoids_app/ui.py`, `characters.py`, `storage.py`: first editor, character validation, and SQLite persistence. `requirements.txt` pins the UI dependency. See README for setup and launch instructions.
- `tools/convert_reference_data.py`: authoritative repeatable data conversion. Change it when changing reference data so regeneration preserves corrections.
- `source/character_sheet.xlsx`, original Apps Script TXT files, and `docs/generated/`: preserved migration source/audit.

## Latest decisions

- Each weapon receives the strongest matching active bonus among Laser, Missile, Particle, Melee, and Rifle Expert. **Anti-Air Pro is an exception and adds on top** for Anti-Air-tagged weapons. Expert ranks 3/4 grant no advantage.
- Ranged Piercing becomes Ranged + Bullet; Rifle Expert requires both tags. Melee Piercing stays as a player-managed label. Command Wolf IS's Long Range Rifle now has its missing Ranged tag.
- Ranged Energy becomes Laser; Laser Expert matches Laser only, not retained melee Energy. Explicit Ranged class/description tags have been restored, including Zaber Fang RS's Double Beam Cannon as Ranged + Laser.
- Type abilities match exact listed game types, case-insensitively with surrounding whitespace trimmed. Mammal does not include Lion/Tiger/Wolf/Gorilla; Dinosaur, Land does not include Raptor/T-Rex.
- Zaber Fang: fixed 2 remains 20mm but uses Ranged + Particle; fixed 3 is Laser Machine Gun (45 damage, 17 base to-hit, Ranged/Laser/Close Range); Killer Saber moves to fixed 4 with its existing values and persistent identity.
- Physical, Social, Personality, general inventory/cargo notes, Zi Database/campaign notes, and seven feat slots are tracking-only. No automatic feat advantage, extra Vent, or stat effects. Mental retains its pre-existing calculation role.
- Anti-Ait becomes Anti-Air. Slashing/Bludgeon removed. Freeze/Electric/Electrical/Lighting combined into Electrical. Tags have no automatic damage/status effects; they still support ability matching.
- Legacy NdM damage becomes N × M, including descriptions. Burst counts remain separate.
- One active size ability; exact size matching, explicit multi-size lists. Higher ability ranks permanently replace lower ranks within ownership. Other owned abilities remain inactive.
- Size and activated Organoid percentages affect all eight weapons' to-hit. Fixed weapon upgrades apply only to slots 1–4, with flat to-hit upgrades after percentage rounding.
- Equipment bonuses apply independently: passive while equipped, active only while activated.
- Fleet Footed applies while active. Sniper applies only to Long Range ranged attacks. Close is <=60m and takes priority; Normal is >60m and <=half maximum range; Long is >60m and >half maximum range. Melee ignores range controls.
- Comeback ranks grant 20/30/40/50% damage at current health <=20% of current derived maximum health.
- Wimp, Cross Eyed, Slowpoke, Bad Armor and all ranks retired.
- True Tank applies per defensive item; Evasion Master adds Armor per reaction-boosting item; Shield Master adds once to combined positive Shield HP from any source.
- Shield-producing units use their own activation/passive state; fixed shield fields belong to units 2 and 3. Only activated White Organoids generate shields, once, using Organoid level. Red/Blue/Black generate none.
- Assist slots accept equipment below the Armaments ASSIST heading; Weapon and Assist slots accept equipment from the whole sheet. `equipment.py` provides catalog compatibility rules. UI/save changes use `characters.py`'s owned-copy APIs, not the raw build-level `equip_item()` helper.
- Removable equipment is owned as individual copies with stable IDs. Duplicates are allowed. One copy can be reused across CAU forms of one owned Zoid, but not across different Zoids or in two slots of one form. Unassigned copies remain in pilot inventory. Clearing a slot affects that form; Return to inventory clears the copy from all forms without deleting it. Acquisition records play decisions without charging gold.
- Zoid acquisition, ability learning, equipment acquisition, and equipment attachment menus are editable, case-insensitive searchable dropdowns with scrolling retained. Search text alone never commits an acquisition or loadout change.
- Economized Shooting adds 1 maximum heat while active. Heat counters persist independently; firing at/above capacity works once then breaks the weapon.
- Rest clears heat without healing or repairing broken weapons. Weapon repair costs 10,000g and clears heat/broken status. Health repair costs 10g per point. Weapon repair requires confirmation if more than 25% of health is missing.
- Multi Attack, Smoke Master, Armor Breaker, Weapon Breaker, Counter Attack are tracked but player-managed.
- Demolitionist is tracked but player-managed: manually Vent each applicable weapon.
- Every successful Use rolls one inclusive 1–20 d20, including unrated equipment and the final use that causes overheating breakage. Each occupied weapon/equipment card has a Last d20 box displaying the raw result (no modifier added). Failed uses do not roll. The latest result persists until the next successful use, across refreshes, Vent/Rest/repair, transfers, CAU switches, and save/reload.
- Read-only attack previews remain separate: range affects Sniper and current health affects Comeback. Apply the displayed modifier to the raw die at the table. Range changes never use a weapon, add heat, or reroll.
- Rest active loadout clears the current eight-slot weapons/equipment only, preserving health, shield damage, gold, and broken flags. Other stored/form-specific weapons retain heat; shared identities naturally retain the same condition across forms.
- Health repair accepts partial points or blank/full, charging 10g per point actually restored. Weapon repair charges 10,000g once and clears heat/broken. The low-health confirmation dialog supports Cancel/Repair anyway and refuses an outdated quote; click Repair again after state changes.
- `assets/icon.png` is the app-header icon; `assets/icon.ico` is the Windows window icon. The launcher supplies the absolute assets directory. Both were visually checked in the Windows smoke test; packaged installers remain pending.
- GIFs deferred. Remaining Dashboard-origin discrepancies are deferred unless needed for a gameplay requirement; preserve the Dashboard source.
- Obtain CAU forms separately after their base. Liger Zero: Zero Jager/Schneider/Panzer/X/Empire; Konig Wolf: Konig Wolf DSR; Berserk Fury: Sturm Fury/Jagd Fury/Berserk Fury Z. All form names retain `(CAU)`.
- Share frame upgrades across an owned base and its forms. Weapon upgrades follow matching base-weapon identity, not slot number; other form weapons remain separate. Sharing is scoped to one owned chassis. Strike Laster Claw / Strike Laser Claw / Strike Laser Claws all display as **Strike Laser Claw**. The converter preserves originals and emits stable ownership/weapon IDs.
- Retire all 19 BLOX-type Zoids (trim source types) and BLOX Type ranks 1–5, including the `BLOXType 1` spelling. There are now 135 playable Zoids and 160 playable abilities.
- Hover Cargo, Gustav, and Whale King belong to `transports.json` and the Transport reference section. Owner is designing Transport rules; implementation is still required before Step 7 is complete. Current ruleset/reference versions: `owner-corrected-v13` / `laser-and-types-v11`.
- Export/import/backups are deferred. Purchasing/building is deferred while the owner creates costs/required-parts data. `assets/ZoidNames.txt` contains 138 sorted current names (nine CAU forms and three Transports included).

## Resume

From the repository root:

```sh
python -m unittest discover -s tests -v
python -m zoids_app.preview --snapshot
```

Launch the editor on Windows after installing `requirements.txt` into `.venv`:

```powershell
.\.venv\Scripts\python -m zoids_app
```

Desktop startup and layout have been visually checked on Windows. Headless UI tests cover create/equip/activate/save/reopen, owned-only selectors, shared upgrades, retirement, ability learning/replacement/deactivation, size-slot rejection, all Organoid colors and level boundaries, inventory-copy availability/returns, search submission behavior, and settings through Zoid/form switches. Roster/storage tests cover CAU families, cross-form copy reuse, duplicate-copy rejection, preservation of loose items, and atomic migrations (including v3 equipment to v4 inventory). Platform packages and Android execution are not verified.

On Linux, use `python3` if `python` is unavailable. On Windows, `py -3` also works when the Python launcher is installed.

Private GitHub repository: https://github.com/AngelOmega7/zoids-character-app. The shared branch is `main`. Next active step: UI polish and playtesting (Step 6). Step 5's current type/tag/weapon corrections are implemented; Dashboard findings retain their earlier deferrals. Follow `docs/roadmap.md`: skip export/import/backups for now; await the owner's purchasing table and Transport rules; do not mark Step 7 complete before Transport implementation.

Git tracks project files, not OpenCode conversation history or machine-local configuration. A fresh conversation can resume by reading this handoff and the linked documents.
