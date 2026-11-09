# Development handoff

## Goal and current state

Build a fully offline Python/Flet RPG character manager for Android and Windows, migrated from a multi-sheet Google workbook. The workbook is initial source/reference only: the installed app must never connect to or modify Google Sheets.

Implemented: the five-page Flet workflow, CSV-backed purchasing/selling, structured inventory/design knowledge, upgrade costs/refunds, expanded CAUs and detachment, duplicate chassis ownership, Transport cargo rules, NPC/None options, character/combat tracking, icons, SQLite saves, saved-character JSON export/import, confirmed saved-character deletion, equipment-copy deletion, Zoid-specific equipment discovery, restored BLOX/FUZOR building, pre-fusion component recovery, optional retention of sold FUZOR identities/upgrades for rebuilding, and energy-based combat with Health/Energy bars and EPT upgrades. Current baseline: **273 tests passing** with Flet installed. Python 3.10+ is required; rules/storage use the standard library and the UI uses pinned Flet 1.0.4. Packaging is a separate next stage.

New pilots start with 10,000g, no automatically granted Zoid, and Organoid None. Starters must be non-CAU, cost at most 10,000g, and have no CSV Base Zoid or BLOX component requirement; only Core/Parts/Zi Database requirements are waived. Sales refund 75% of the chassis plus its currently owned CAUs, remove that instance/forms/upgrades, and retain removable inventory copies. FUZOR sales also recover component Zoids and can optionally retain the sold FUZOR's identity/upgrades for a later rebuild. Saved-character deletion requires explicit warning/confirmation. Current save schema is v14. See `docs/workflow.md` and `docs/energy-rules.md` for authoritative rules. Saves use the platform application-support directory, with an optional `ZOIDS_SAVE_DIR` override.

## Where to start

- **`docs/workflow.md`: current five-page workflow, purchasing, Transport, expanded CAUs, source corrections, and migration details. This supersedes earlier deferrals/restrictions below.**
- `zoids_app/commerce.py`, `transport.py`, `workflow_migration.py`: new transaction, cargo, and migration logic.
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

- FUZOR sale offers **Keep FUZOR identity and upgrades for rebuilding**, off by default. Schema v10 stores these records in `Character.stored_fuzors`, separate from playable/cargo ownership. Purchasing the matching design offers a specific stored copy or a fresh build. Rebuilding consumes that stored record and the normal component recipe, restores its ID and frame/weapon upgrade points, and records the new components' recovery history. Multiple retained copies are independent. Stored records survive save/reload and export/import; older saves default to none. FUZOR combat state follows normal new-build initialization; component recovery still preserves pre-fusion combat state.
- Reference update `workflow-v15`: all remaining BLOX Zoids and BLOX Type ranks 1–5 are restored. Fuzor Dragon, Chimera Dragon, Gojulox, 2-Arm Lizard, Griffin, and Lord Gale retain BLOX type and cost 0g plus the multiple owned components listed in CSV `BLOX 1`, `BLOX 2`, etc. Each selected component is consumed; its pre-fusion chassis state is preserved, inventory equipment is retained, and cargo assignments are cleared. Selling the FUZOR restores original component IDs/upgrades/health/conditions, without re-equipping inventory or loading cargo. Schema v9 persists this history through saves and export/import. Old untracked FUZORs return fresh recipe copies; new GM-override builds return none. Zi Database knowledge is required; FUZORs cannot be starters. See `workflow.md` for recipes and GM Override behavior. Existing retirement archives remain preserved without automatic reacquisition.
- Buster Eagle, Fire Phoenix, and Jet Falcon remain **Flying** type; Zero Falcon and Zero Phoenix remain **Liger** type. Converter corrections preserve original BLOX source values and apply on regeneration.
- Each weapon receives the strongest matching active bonus among Laser, Missile, Particle, Melee, and Rifle Expert. **Anti-Air Pro is an exception and adds on top** for Anti-Air-tagged weapons. Expert ranks 3/4 grant no advantage.
- Ranged Piercing becomes Ranged + Bullet; Rifle Expert requires both tags. Melee Piercing stays as a player-managed label. Command Wolf IS's Long Range Rifle now has its missing Ranged tag.
- Ranged Energy becomes Laser; Laser Expert matches Laser only, not retained melee Energy. Explicit Ranged class/description tags have been restored, including Zaber Fang RS's Double Beam Cannon as Ranged + Laser.
- Type abilities match exact listed game types. Lion terminology is now Liger (Saberlion retains its name). Mammal does not include Liger/Tiger/Wolf/Gorilla; Dinosaur, Land does not include Raptor/T-Rex.
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
- Removable equipment is owned as individual copies with stable IDs. Duplicates are allowed. One copy can be reused across CAU forms of one owned Zoid, but not across different Zoids or in two slots of one form. Unassigned copies remain in pilot inventory. Clearing a slot affects that form; Return to inventory clears the copy from all forms without deleting it. Acquisition records play decisions without charging gold. Deleting an unattached copy is permanent and confirmed; an equipped copy must be returned from all forms first. Zoid-specific templates appear under their resolved names for owned Zoids (for example, Command Wolf's Double Beam Cannon) and resolve against the Zoid they are equipped to.
- Zoid acquisition, ability learning, equipment acquisition, and equipment attachment menus are editable, case-insensitive searchable dropdowns with scrolling retained. Search text alone never commits an acquisition or loadout change.
- Current rules/data: **energy-v17**, save schema **14**. Heat/Vent/heat-clearing Rest are removed. Energy Rest sets current Energy to half maximum (rounded down), from either above or below. New Zoids also start at half maximum. See `energy-rules.md` and `generated/energy-mapping.md` for authoritative costs, equipment, mapping decisions, and save migration. Current verification: **273 tests passing**.
- EPT upgrades add +1 Energy Per Turn each with no cap. Prices start at 10,000g and double each rank; Minus refunds the removed rank's price. Frame persistence includes EPT; pre-v14 saves default to zero points. Upgrade boxes display the selected form's raw base stat on the right (fixed-weapon base to-hit values for Accuracy).
- Zoid-specific utility equipment is classified against its resolved Zoid data and fits slots 5–8. Konig Wolf DSR missiles fit slots 6/7. Great Zaber's rifle is restricted to slot 6 and can be equipped with its cannon in slot 5/7. Schema 13 migrates earlier rifle placements while preserving owned copies. The 13-item/12-design audit found no missing named cost entries; see `generated/zoid-equipment-audit.md`.
- Weapon/system Use spends energy; insufficient energy rejects without a roll. Start Turn adds recharge capped at total. Each owned chassis saves its current energy, shared across forms. Health and Energy bars display current/total values.
- Multi Attack, Smoke Master, Armor Breaker, Weapon Breaker, Counter Attack are tracked but player-managed.
- Economized Shooting ranks 1–4 reduce Ranged-tagged weapon Energy Costs by 2/4/6/8, minimum 0. Demolitionist is player-tracked: “Once per Rest, you may completely fill your Zoid's Energy.” Inactive pilot abilities can be removed and learned again later.
- Physics Reinforcer Unit grants +100 max Health; Energy Reinforcer Unit grants +20 max Energy. Both are passive, weight 3, with flat bonuses and no automatic refill. Energy Container is active, weight 10; Activate restores 20 Energy capped at the equipped maximum. All three use zero energy.
- Use rolls one inclusive 1–20 d20 only for numerical-damage weapons. Non-damaging utilities spend energy without rolling and retain activation controls. Empty Combat cards are hidden. Results persist across refreshes, Start Turn/repair, transfers, CAU switches, and save/reload.
- Read-only attack previews remain separate: range affects Sniper and current health affects Comeback. Apply the displayed modifier to the raw die at the table. Range changes never use a weapon, spend energy, or reroll.
- Health repair accepts partial points or blank/full, charging 10g per point actually restored. Weapon repair charges 10,000g once and clears broken status. The low-health confirmation dialog supports Cancel/Repair anyway and refuses an outdated quote; click Repair again after state changes.
- `assets/icon.png` is the app-header icon; `assets/icon.ico` is the Windows window icon. The launcher supplies the absolute assets directory. Both were visually checked in the Windows smoke test; packaged installers remain pending.
- GIFs deferred. Remaining Dashboard-origin discrepancies are deferred unless needed for a gameplay requirement; preserve the Dashboard source.
- Obtain CAU forms separately after their base. Liger Zero: Zero Jager/Schneider/Panzer/X/Empire/Falcon/Phoenix; Konig Wolf: Konig Wolf DSR; Berserk Fury: Sturm Fury/Jagd Fury/Berserk Fury Z/Buster Fury. All form names retain `(CAU)`. `CAU_expand_2.txt` adds the latest three forms. Buster Fury costs 50,000g plus Buster Eagle; Zero Falcon/Phoenix cost 20,000g plus Jet Falcon/Fire Phoenix respectively. Components are consumed, hosts retained. Existing standalone expansion-form saves migrate without losing upgrades or weapon conditions.
- Share frame upgrades across an owned base and its forms. Weapon upgrades follow matching base-weapon identity, not slot number; other form weapons remain separate. Sharing is scoped to one owned chassis. Strike Laster Claw / Strike Laser Claw / Strike Laser Claws all display as **Strike Laser Claw**. The converter preserves originals and emits stable ownership/weapon IDs.
- There are 154 playable designs (54 CAUs, 6 FUZORs), 165 abilities, and four Transports. Dragon Nest is now Dragoon Nest and is no longer a playable chassis.
- Transport capacities/sizes: Gustav 2/Medium, Hover Cargo 6/Large, Dragoon Nest 12/Large Large, Whale King 24/Extra Large. Type changes unload cargo; each chassis counts once. Size/capacity checks are enforced.
- Purchasing is implemented from the owner's CSV. Its locked source file was preserved; approved typo corrections are applied in the importer. Upgrade counters charge/refund tiers. CAU detachment refunds half CSV price plus current/predecessor Parts; unique upgrades are lost. Current ruleset/reference versions: `owner-corrected-v14` / `workflow-v15`.
- Export/import of individual saved characters is implemented as versioned JSON through the native file picker. Export writes the last saved state; import validates/migrates through the normal save decoder, adds a new saved entry, and assigns a new ID on collision instead of overwriting. Import never changes the open draft. Scheduled backups and full-database export remain deferred. `assets/ZoidNames.txt` has been refreshed with all 158 current names. Packaging remains pending owner review.

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

Desktop startup and layout have been visually checked on Windows. Headless UI tests cover create/equip/activate/save/reopen, owned-only selectors, shared upgrades, retirement, ability learning/replacement/deactivation, size-slot rejection, all Organoid colors and level boundaries, inventory-copy availability/returns/deletion, Zoid-specific equipment names, saved-character export/import, search submission behavior, and settings through Zoid/form switches. Roster/storage tests cover CAU families, cross-form copy reuse, duplicate-copy rejection, export/import validation and ID collisions, preservation of loose items, and atomic migrations (including v3 equipment to v4 inventory). Platform packages and Android execution are not verified.

On Linux, use `python3` if `python` is unavailable. On Windows, `py -3` also works when the Python launcher is installed.

Private GitHub repository: https://github.com/AngelOmega7/zoids-character-app. Shared branch: `main`. Current implementation is ready for owner playtesting; then proceed to packaging as a separate task. Dashboard findings and scheduled/full-database backups retain their explicit deferrals. Keep follow-up work bounded to reported issues and agreed packaging requirements.

Git tracks project files, not OpenCode conversation history or machine-local configuration. A fresh conversation can resume by reading this handoff and the linked documents.
