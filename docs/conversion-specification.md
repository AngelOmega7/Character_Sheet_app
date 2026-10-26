# Offline character app: initial conversion specification

**Current status:** the supplied five-page workflow, purchasing, Transport rules, expanded CAUs, schema-v8 migrations, and single-character JSON export/import are implemented. See `workflow.md` and `HANDOFF.md` for authoritative current behavior and verification. Packaging remains a separate next stage after owner review; scheduled/full-database backups remain deferred.

Status: reference catalogs, stat/combat rules, pilot/feat tracking, Flet character/combat editor, versioned SQLite save/load, and single-character JSON export/import implemented. Scheduled/full-database backups are deferred by owner. Purchasing/building awaits the owner's costs/parts table; Transport awaits owner-defined rules and is required before Step 7 completion. See [Roadmap](roadmap.md) for the current seven-step rollout and [Rules review](rules-review.md) for the completed type/tag/weapon review.

Owner-supplied scripts have now been reviewed. See [Apps Script migration](apps-script-migration.md) for source behavior and owner-confirmed extensions: over-capacity use works once then breaks the weapon, health repair costs 10g per point restored, and weapon repair costs 10,000g per broken weapon. Initial combat and repair rules are implemented and independently testable. GIF display is an optional visual feature deferred from the first playable version.

## Architecture

The installed app has no Google Sheets connection. Development tooling reads a local XLSX snapshot. Curated reference tables become versioned JSON, rules are Python functions, Flet presents the interface, and SQLite stores character state in the platform app-data directory. Images are bundled locally. JSON character transfer/backups are deferred for now.

The generated workbook_inventory.json is an audit artifact, not yet a normalized game database. It preserves cell addresses, raw values, cached formula results, formula metadata, exported validations, named ranges, and table definitions.

## Source mapping

| Source | Destination | Conversion work |
|---|---|---|
| Zoid | Zoid screen, combat state, rules | Base/pilot/current stats, four fixed weapons, four equipment slots, shields, heat, Organoid, cargo |
| Pilot | Pilot screen and character model | Attributes, six active abilities, seven feat selections, inventory and inactive abilities |
| Zoid Upgrades | Per-Zoid/CAS upgrade records | Eight source configuration columns; frame and fixed-weapon upgrades |
| Dashboard (DO NOT TOUCH) | Archived migration reference; translated logic lives in Python | Owner deferred remaining Dashboard discrepancies. Preserve original workbook and formula inventory; no Dashboard UI or runtime worksheet needed |
| Stats | Pilot progression data | TANK, FIGHTER, SCOUT, ALMIGHTY tables; retain formula-derived entries as rules or validated constants |
| Zoid List | Zoid definitions | Zoid_DB table A1:CK163; inspect one character-dependent formula before extracting |
| Armaments | Equipment definitions and rules | Armaments table A1:P159; 21 formulas mean this is not wholly static |
| Organoid | Organoid definitions | Normalize the source layout and identify level/color lookup semantics |
| Zoid Abilities | Ability definitions and effects | Skills table A1:O184; separate descriptions from dynamic formula behavior |
| Zoid_Gifs | Local visual assets and manifest | Preserve asset mapping; inspect embedded workbook media and external URLs |
| Feats | Feat definitions | Feats table A1:B9; distinguish descriptive effects from automated effects |

## Input and action map

These are initial mappings, not a claim that all blank editable cells have been discovered.

| Source cells | Model/UI mapping |
|---|---|
| Zoid!C3, C4, C7, C9, C11 | Pilot name, Zoid selection, Zoid color, pilot level, pilot style |
| Zoid!E14, G14 | Current health and shield damage; preserve as state |
| Zoid!G17:G19 | Organoid enabled, level, color |
| Zoid!C47, C54, C61, C68 | Back, left, right, chest equipment selections |
| Zoid!I3:I9 | Conditional Gustav/transport/cargo module selections |
| Zoid!A4, A6 | Rest/repair controls; establish precise effects before implementing commands |
| Zoid!A25, A30, A35, A40 | Four fixed-weapon roll triggers |
| Zoid!A47, A54, A61, A68 | Four removable-equipment roll triggers |
| Zoid!F29, F34, F39, F44 | Fixed-weapon heat state |
| Zoid!G29, G34, G39, G44 | Fixed-weapon vent controls |
| Pilot!C4:C6 | Physical, mental, social attributes |
| Pilot!B14, B18, B22, B26, B30, B34 | Six selected abilities |
| Pilot!B41:B47 | Seven feat slots |
| Zoid Upgrades!E1:L1 | Owned Zoid/CAS configuration labels |

Inspect remaining blank cells, equipment heat/vent controls, personality, inventory, currency, and inactive-ability areas against the original layout. An exported blank or constant is not enough to establish intended editability.

## Rules migration requirements

1. Preserve lookup behavior and identify missing-key fallbacks explicitly. Convert placeholders to a deliberate empty selection, not a fake equipment record.
2. Translate Dashboard modifiers and all dependents into an ordered calculation pipeline. Audit cycles and source calculation settings before selecting an evaluation order.
3. Preserve ROUND and ROUNDUP semantics. Python's default round uses different tie handling; use explicit spreadsheet-compatible helpers.
4. Preserve first-match behavior in IFS and ability checks; do not assume all matching bonuses stack.
5. Separate base stats, derived totals, and mutable combat resources. A UI refresh must not reset damage or heat.
6. Fixed-weapon attack formulas include a carry-load check and a 0.6 multiplier when overloaded. Match each formula's rounding order and modifiers; do not generalize equipment formulas without checking them.
7. There are eight RANDBETWEEN(1,20) attack formulas. Owner-confirmed replacement: each successful Use rolls exactly one d20 and displays the raw result in its weapon card, retained until that weapon is used again. Refreshing, previewing, and saving never reroll.
8. Source upgrade notes specify five points per slot, +30 speed, +1 reaction, +5 defense, +10 weapon weight, +20 fixed-weapon damage, and +1 fixed-weapon to-hit per point. Verify stored point-versus-bonus semantics: the snapshot contains 20 in E12. Do not interpret it as 20 upgrade points.
9. Upgrade notes exclude non-weapons such as smoke units and shields, and describe sharing upgrades across CAS forms. Implemented in owned-Zoid management: share frame upgrades within an owned base/CAU family and weapon points by matching base-weapon identity across slots; keep other form weapons separate. CAU forms are obtained individually, and each base can be owned once per pilot. BLOX Zoids and BLOX Type abilities are retired. Hover Cargo/Gustav/Whale King have a separate Transport reference section; their transport/storage mechanics are deferred.
10. Preserve source descriptions even when a rule is manually adjudicated. Distinguish automated effects from descriptive-only rules in the final feature checklist.

## Items requiring verification

- Seven formula cells use __xludf.DUMMYFUNCTION export wrappers; they include Google-specific percentage/display behavior. Review source formula text and cached results before translation.
- Named range Assist exports as #REF!. Resolved: Assist slots use equipment below the Armaments ASSIST heading; Weapon and Assist slots accept equipment from the whole sheet. The UI and save validator use the validated equipment API.
- Shared formula followers have no formula text of their own. Expand using relative-reference rules before building a complete dependency graph.
- Owner supplied Heat Script.txt and Gifs Script.txt. Resource actions and overheating rules are documented in apps-script-migration.md. Weapon repair costs 10,000g and resets heat; Rest active loadout resets current-slot heat without healing or repairing. Owner confirmed that each successful Use rolls a d20, displayed in that weapon card. The last raw result is retained independently of read-only attack previews and recalculation.
- Some dropdowns contain headings or joke/placeholder options. Confirm intended choices rather than copying them into valid game records.
- Formula-derived descriptions and character-dependent reference-table cells need explicit treatment.
- Embedded media and linked images still require asset extraction and mapping.

## Persistence design

Use stable IDs for reference entities, a save schema version, and a rules-data version. Save pilot selections, owned configurations, upgrades, equipment, attributes, inventory, currency, damage/resources, and any retained roll history. Calculate totals from state rather than treating cached spreadsheet totals as authoritative.

Use transactional writes. Character export/import must validate schema versions and references. First-run defaults should create a new character; the source's example Saberlion character should be a separate optional fixture.

## Implementation milestones and acceptance

1. **Normalize data:** extract complete tables with provenance; validate identifiers, types, missing values, and references. Preserve all source rows until exclusions are explained.
2. **Rules core:** implement one verified Saberlion/pilot calculation path, then modifiers, load, Organoid, equipment, and upgrades.
3. **Parity fixtures:** compare source results for each pilot style, relevant level boundaries, abilities, equipment activation, overloaded state, and CAS upgrades. The single cached snapshot is not sufficient proof of parity.
4. **Flet UI:** pilot, Zoid/combat, equipment, upgrades, and character selection screens, with responsive phone/desktop layouts.
5. **Persistence:** save/reopen, multiple characters, and versioned migrations; manual transfer/backups are currently deferred by owner.
6. **Offline builds:** build and exercise Android and Windows packages; test without connectivity, including assets, save paths, and restart persistence.

Completion means verified feature parity for agreed behavior, working local saves, and tested platform builds—not merely loading workbook values into a screen.
