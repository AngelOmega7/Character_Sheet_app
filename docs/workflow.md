# Current application workflow

Implemented from `assets/Polish_Workflow.txt`, `assets/CAU_expand.txt`, `assets/zoid_cost.csv`, and the owner's follow-up decisions. This supersedes earlier purchasing/Transport deferrals and the one-instance-per-model restriction.

## Pages and editing

- **Overview:** Pilot, Organoid, owned-Zoid hangar, required level, starter/build purchase, CAU detachment.
- **Combat:** health/shield damage, repairs, Rest, and occupied fixed/removable weapon cards. Only numerical-damage equipment rolls and displays a d20; non-damaging utilities keep activation controls. Empty cards are hidden.
- **Upgrades:** paid 0–5 counters, equipment-copy inventory, removable equipment assignments.
- **Pilot:** abilities, feats, notes, gold, structured General Inventory quantities, and known-design Zi Database. Existing free-text notes are retained.
- **Transport:** transport type/stats, all owned chassis instances, loaded cargo, and notes. Calculated Stats appears on every other page.

Page changes retain valid draft edits. Closing the Windows window or switching/newing characters with unsaved changes offers Keep editing, Discard changes, or Save. A failed save cancels the transition.

## Purchases and refunds

New pilots have **10,000g**, no automatically granted Zoid, and Organoid **None**. Starter choices must be non-CAU designs costing at most 10,000g with **no Base Zoid requirement in the CSV**. Core, Parts, and Zi Database requirements are waived. Both the picker and transaction validation enforce this restriction.

Later purchases check funds, General Inventory quantities, the required Base Zoid/CAU, and the target's known-design entry. Confirmed normal purchases deduct the CSV price, consume one of each required Core/Parts item, and consume the selected eligible base instance. Consumed chassis must own no CAUs. Replacements start without inherited upgrades; removable equipment remains in pilot inventory. With multiple eligible bases, select the specific instance.

When recipe checks fail, a separate **GM Override** confirmation grants the build without spending gold or consuming materials/external base chassis. A CAU still requires a particular owned host and cannot be duplicated on that host. Upgraded CAUs supersede their predecessor form, including on override; the host remains.

- CAU purchases retain their host. Cannonry Molga retains Molga; Killer Spiner retains Dark Spiner and normally consumes a separate Killer Dome.
- Shield Liger DCS-J replaces DCS; Zaber Fang TS replaces AT. Neither predecessor stays as an acquired form.
- Detaching a CAU refunds **half its current CSV price**, including GM-granted forms. Returned Parts include predecessor-CAU Parts. Form-specific upgrades/conditions are removed; host/shared upgrades remain. Assigned removable copies remain owned.
- Chassis upgrade tier N costs **5,000g × N**; fixed-weapon tier N costs **10,000g × N**. Each track is independent. Decreasing a counter refunds the full removed tier cost. Existing recorded points are retained without retroactive charges.
- Removable equipment acquisition remains GM-managed; no equipment purchasing cost is applied. Zoid-specific removable equipment appears under its resolved name whenever the matching Zoid/form is owned (for example, Command Wolf's **Double Beam Cannon**). Generic templates display as equipment slots 5–8 after fixed weapons 1–4. It resolves against the Zoid it is equipped to.

## Selling and deleting

**Sell selected Zoid + CAUs** in Overview quotes 75% of the combined CSV prices of that specific chassis and all its currently owned CAU forms. Confirmation removes the instance and its forms/upgrades, unloads it from Transport, and credits the quoted gold. Removable equipment stays in inventory with its condition intact. Other instances and known designs remain unchanged. Parts and upgrades do not receive additional refunds. Only currently owned forms count, not previously consumed predecessor CAUs. The combined refund is rounded down to whole gold if needed. Selling the last Zoid leaves an empty roster without granting another starter purchase. Save character to retain the sale.

**Delete equipment copy** on the Upgrades inventory list permanently removes one unattached copy after confirmation. Equipped copies must be returned to inventory from all forms first. Deleting a copy does not alter gold, Zoids, upgrades, or other equipment copies.

**Delete saved character** targets the selected entry in the saved-character picker. A warning names the character and requires explicit confirmation before deleting its database record. Deleting the open character also discards its unsaved edits and opens a fresh draft. Deleting another saved character preserves the current draft and its pending edits. Cancel performs no deletion.

## Export and import

**Export selected** writes the selected saved character to a portable `.json` file using the native file picker. It exports the last saved state, not unsaved edits. **Import character** reads a `.json` export, validates it through the normal save decoder/migrations, and adds it to local saves. If the exported save ID already exists, the imported character receives a new ID so existing saves are never overwritten. Import does not replace the open draft; choose **Open** afterward. Files remain local, and no network access is used.

## Transport

Selection is GM-managed and uses unmodified catalog stats. Changing type (including None) unloads all cargo without deleting any owned Zoid. Notes are retained.

| Type | Capacity | Maximum hangar size |
|---|---:|---|
| Gustav | 2 | Medium |
| Hover Cargo | 6 | Large |
| Dragoon Nest | 12 | Large Large |
| Whale King | 24 | Extra Large |

Size order is Small < Medium < Large < Large Large < Extra Large. Ultra Saurus's source typo `Extra Lare` is normalized. Each owned chassis occupies one bay; its CAUs stay with it. Eligibility uses its selected form. Oversized/over-capacity loading is rejected; a loaded chassis must be unloaded before switching to a form that would not fit.

## Reference changes

Dragon Nest is now **Dragoon Nest** in Transport. Catalog Lion terminology is now **Liger**, while the name Saberlion is retained. Legacy reference IDs/aliases remain readable for save compatibility.

- Lightning Saix and BS: Pulse Laser Gun is fixed slot 2; Killer Fang moves to slot 3.
- Shadow Fox: Laser Vulcan Gun is fixed slot 3; Strike Laser Claw moves to slot 4.
- Command Wolf IS: Long Range Rifle is fixed slot 3.
- These newly fixed weapons are upgradeable and removed from their old unique-removable reference fields.
- All CAU families in `CAU_expand.txt` and `CAU_expand_2.txt` are incorporated. Snipe Master AS and FB are separate forms. Approved display-name aliases are normalized during conversion.
- Buster Fury (CAU) belongs to Berserk Fury and costs 50,000g plus an owned Buster Eagle. Zero Falcon (CAU) and Zero Phoenix (CAU) belong to Liger Zero and each cost 20,000g plus an owned Jet Falcon or Fire Phoenix, respectively. The component is consumed; the host remains.
- **NPC** contributes no pilot-style progression bonuses; other explicitly configured modifiers retain their existing rules. **None** prevents Organoid activation and is the new-pilot default.

## Saves and source data

Reference update `workflow-v15`: all 14 remaining BLOX designs and BLOX Type ability ranks 1–5 are restored. These designs retain **BLOX** type, including the six FUZORs. Buster Eagle, Fire Phoenix, and Jet Falcon remain **Flying**; Zero Falcon and Zero Phoenix remain **Liger**. Original corrected workbook types are retained in metadata. BLOX Type grants 5/10/15/20/25 bonus pilot levels only while piloting a BLOX-type Zoid. The source spelling `BLOXType 1` remains a readable alias.

### FUZOR building

The numbered `BLOX 1`, `BLOX 2`, etc. CSV columns specify component designs. Each populated column requires a distinct owned chassis, including repeated names. Select specific copies when duplicates are owned. Components with acquired CAUs cannot be consumed.

| FUZOR | Component Zoids |
|---|---|
| Fuzor Dragon | Leo Blaze, Unenlagia, Mosasledge, Nightwise |
| Chimera Dragon | Diplo Gun, Shell Karn, Demon's Head, Flyscissors |
| Gojulox | Diplo Gun, Shell Karn, Demon's Head, Leo Blaze, Unenlagia, Nightwise |
| 2-Arm Lizard | Leo Blaze, Unenlagia |
| Griffin | Leo Blaze, Unenlagia, Buster Eagle |
| Lord Gale | Diplo Gun, Shell Karn, Demon's Head, Flyscissors |

FUZOR recipes cost **0g**, require their Zi Database design, and consume every selected component atomically. Component identities, upgrades, health, shield/defense adjustments, fixed activation flags, and fixed-weapon conditions are preserved inside the FUZOR. Inventory copies remain owned and become unassigned; consumed chassis are unloaded from Transport. The result is a new independent chassis with no inherited upgrades. Purchase confirmation identifies every consumed instance. GM Override retains its existing explicit-confirmation behavior and consumes no gold, materials, or component Zoids. FUZORs cannot be starters; the eight base BLOX designs can be starters at their CSV prices of 8,000g or 9,000g. Blank CSV cost is accepted as zero only for the six FUZOR recipes.

Selling a FUZOR restores its saved component chassis in their pre-fusion state. FUZOR-specific upgrades are discarded by default, and no component purchase price is refunded as gold. Removable equipment stays in inventory rather than being automatically re-equipped; recovered Zoids remain unloaded from Transport. Confirmation lists the returned instances. New GM-override builds record an empty history and return no components. Older/untracked FUZORs have no recoverable history and return fresh, unupgraded copies from the current recipe; the confirmation explicitly identifies this fallback. Recovery survives save/reload and JSON export/import. A FUZOR can only be sold once, and different FUZORs keep independent histories.

The sale dialog offers **Keep FUZOR identity and upgrades for rebuilding** (off by default). This stores that instance ID, frame upgrades, and fixed-weapon upgrade identities/points separately from the playable roster. It also returns the component Zoids as usual. Stored FUZORs cannot be selected for combat or loaded into Transport.

When purchasing the matching FUZOR design, **Rebuild stored FUZOR** lets the player select a specific stored copy, or leave **New FUZOR** selected for a fresh instance. Rebuilding restores that copy's original ID and upgrades, consumes the selected stored entry exactly once, and still requires the normal design knowledge and component recipe (unless using explicit GM Override). Multiple stored copies retain independent upgrades. Quotes include the stored upgrade snapshot and reject stale/reused selections. Only identity and upgrade points are retained for the rebuilt FUZOR; its health, activation, equipment, and weapon conditions follow normal new-build initialization. Its newly consumed components receive their own pre-fusion recovery history.

Existing archived retirement records remain preserved; catalog restoration does not automatically grant archived Zoids or abilities. Save schema **v9** adds nullable component history: missing/null means legacy fallback, an empty list means no components consumed, and populated history stores the original chassis states.

Current save schema **v10** additionally stores retained FUZOR identities/upgrades. Earlier saves migrate with an empty stored list, preserving component history. Both histories survive JSON export/import.

Schema **v8** migrates earlier saves transactionally. Each former standalone CAU variant becomes a separate instance of its new host plus that form; independently upgraded instances are not merged. Weapon upgrades/conditions follow migrated identities and moved slots. Previously mounted unique-removable copies are unassigned, their condition is carried onto the new fixed weapon, and the inventory copies remain preserved. Dragon Nest ownership is archived and becomes a Transport selection. Existing gold, notes, and recorded upgrades are preserved.

Existing schema-v8 standalone Zero Falcon/Zero Phoenix saves also migrate to their new host family, preserving upgrades and weapon conditions. Current migrations preserve these earlier migration rules.

General inventory quantities/design knowledge are not guessed from old prose. Enter structured records on Pilot; the old notes remain available.

The CSV is imported into `zoids_app/data/purchases.json`. Approved corrections are applied during import: Jagged Stinger consumes Death Stinger; `Zoids Core DS` becomes `Zoid Core DS`; Saberlion's core is placed in the Core field. Original CSV rows are retained in generated metadata. The source CSV was locked during implementation and was not overwritten.

After changing the workbook, refresh its inventory first. Then regenerate references after workbook, CSV, or CAU-list changes and restart the app:

```powershell
.\.venv\Scripts\python tools/inspect_workbook.py source/character_sheet.xlsx docs/generated
.\.venv\Scripts\python tools/convert_reference_data.py
.\.venv\Scripts\python tools/export_zoid_names.py
```

Current references: **154 playable designs (54 CAUs, 6 FUZORs), 165 abilities, 4 Transports, 154 price records**. `assets/ZoidNames.txt` contains all 158 current display names. Reference version: `workflow-v15`; calculation ruleset: `owner-corrected-v14`.

## Verification and next step

**240 tests pass**, including BLOX ability matching, FUZOR component consumption, duplicate selection, pre-fusion recovery, retained FUZOR identity/upgrades and rebuild selection, legacy fallback, starter eligibility, purchasing/override/refund and sale transactions, the second CAU expansion and saved standalone-form migration, saved-character deletion, equipment-copy deletion, saved-character export/import, Zoid-specific equipment names, cargo constraints, workflow migration, page navigation, and save/discard/cancel handling. Scheduled backups remain deferred. Packaging is the next separate stage after owner review; Android execution and distributable packages have not been verified yet.
