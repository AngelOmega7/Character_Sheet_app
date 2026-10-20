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
- Removable equipment acquisition remains GM-managed; no equipment purchasing cost is applied.

## Selling and deleting

**Sell selected Zoid + CAUs** in Overview quotes 75% of the combined CSV prices of that specific chassis and all its currently owned CAU forms. Confirmation removes the instance and its forms/upgrades, unloads it from Transport, and credits the quoted gold. Removable equipment stays in inventory with its condition intact. Other instances and known designs remain unchanged. Parts and upgrades do not receive additional refunds. Only currently owned forms count, not previously consumed predecessor CAUs. The combined refund is rounded down to whole gold if needed. Selling the last Zoid leaves an empty roster without granting another starter purchase. Save character to retain the sale.

**Delete saved character** targets the selected entry in the saved-character picker. A warning names the character and requires explicit confirmation before deleting its database record. Deleting the open character also discards its unsaved edits and opens a fresh draft. Deleting another saved character preserves the current draft and its pending edits. Cancel performs no deletion.

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
- All CAU families in `CAU_expand.txt` are incorporated. Snipe Master AS and FB are separate forms. Approved display-name aliases are normalized during conversion.
- **NPC** contributes no pilot-style progression bonuses; other explicitly configured modifiers retain their existing rules. **None** prevents Organoid activation and is the new-pilot default.

## Saves and source data

Schema **v8** migrates earlier saves transactionally. Each former standalone CAU variant becomes a separate instance of its new host plus that form; independently upgraded instances are not merged. Weapon upgrades/conditions follow migrated identities and moved slots. Previously mounted unique-removable copies are unassigned, their condition is carried onto the new fixed weapon, and the inventory copies remain preserved. Dragon Nest ownership is archived and becomes a Transport selection. Existing gold, notes, and recorded upgrades are preserved.

General inventory quantities/design knowledge are not guessed from old prose. Enter structured records on Pilot; the old notes remain available.

The CSV is imported into `zoids_app/data/purchases.json`. Approved corrections are applied during import: Jagged Stinger consumes Death Stinger; `Zoids Core DS` becomes `Zoid Core DS`; Saberlion's core is placed in the Core field. Original CSV rows are retained in generated metadata. The source CSV was locked during implementation and was not overwritten.

After changing the source CSV or CAU list, regenerate references and restart the app:

```powershell
.\.venv\Scripts\python tools/convert_reference_data.py
.\.venv\Scripts\python tools/export_zoid_names.py
```

Current references: **134 playable designs (51 CAUs), 4 Transports, 134 price records**. `assets/ZoidNames.txt` contains all 138 current display names. Reference version: `workflow-v12`; calculation ruleset: `owner-corrected-v14`.

## Verification and next step

**205 tests pass**, including starter eligibility, purchasing/override/refund and sale transactions, saved-character deletion, cargo constraints, workflow migration, page navigation, and save/discard/cancel handling. Export/import/backups remain deferred. Packaging is the next separate stage after owner review; Android execution and distributable packages have not been verified yet.
