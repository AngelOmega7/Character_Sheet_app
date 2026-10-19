# Apps Script behavior and offline replacements

Sources: owner-provided `Heat Script.txt` and `Gifs Script.txt`.

## Confirmed app rules (supersede missing spreadsheet behavior)

The owner clarified that heat ratings are safe-use capacities. A Heat 3 weapon can be used three times safely. Using it again while its counter is at or above three resolves that use, then breaks it. Subsequent uses are prohibited until Repair fixes it. This is a successful use, not an automatic hit.

- Each heat-generating use adds one to the counter, including the final use that breaks the weapon.
- Vent removes one heat, floored at zero. Vent and Rest do not clear broken status.
- Rest resets all weapon heat to zero and does not restore health points.
- Repairing a weapon clears its broken status and resets its heat to zero.
- Weapons without a heat rating do not accumulate heat.
- Broken status is persistent character state, separate from heat.
- Health repair costs **10 gold per point actually restored**, deducted from Pilot gold.
- Weapon repair costs a flat **10,000g per broken weapon**, deducted from Pilot gold, regardless of heat rating.
- When more than 25% of maximum health is missing, weapon repair requires explicit confirmation. Exactly 25% missing does not trigger the warning. Warn even if remaining gold would cover health repair.

### Weapon repair confirmation

`repair_weapon()` requires current and maximum health. Before spending gold on an affordable broken-weapon repair, it raises `RepairConfirmationRequired` when health is below 75%. The exception carries the weapon price, remaining gold, full health-repair price, and a display message. No resource state changes at this stage.

The future Flet UI must display **Cancel** and **Repair anyway**, default dismissal to cancellation, and retry with `confirmed=True` only after explicit acceptance for this action. Confirmation must not be saved as a preference. If health, gold, or weapon state changes while the dialog is open, refresh the quote and request confirmation again. Insufficient gold still prevents a confirmed repair. Intact weapons incur no charge and do not need confirmation. This gate is implemented in the rules; the visual dialog awaits the UI implementation.

Example: at 50/100 health with 10,100g, warn that weapon repair costs 10,000g, leaves 100g, and restoring health costs 500g. Explicitly state that remaining gold will not cover full health repair.

Implemented in `zoids_app/combat.py`: weapon use, vent, rest, health repair calculations, and paid single-weapon repairs. The UI and persistence integration are pending. The health repair helper supports an explicit point amount and rejects unaffordable requests atomically. Partial repairs and integer-only resource inputs are provisional interface/data choices, not additional owner-confirmed game rules.

`repair_weapon()` checks the supplied Pilot gold balance, deducts 10,000g, and returns the repaired weapon with zero heat and its broken status cleared. Insufficient funds reject the action without modifying state. Intact weapons are left unchanged without charge. `restore_repaired_weapon()` is the underlying state transition, not the purchase entry point.

Remaining repair decision: whether the Repair UI selects health/weapons individually or repairs everything together. A combined repair transaction must calculate its complete cost before modifying gold or resources.

## Required: heat and resource actions

The heat script handles edits whose value is exactly `TRUE`. Unchecking a checkbox does not change resources. A merged range is treated as its first cell.

| Action | Source trigger | Exact state change | Proposed app control |
|---|---|---|---|
| Repair | Zoid!A6 | Copy calculated health D14 into current health E14; clear trigger | Repair button |
| Rest | A4 | Set all eight heat counters to zero; clear all eight attack checkboxes and rest trigger | Rest button |
| Use heat-capable weapon | One of eight attack checkboxes | Inspect heat label above counter; add **one** if label matches `Heat:\s*[1-3]`; leave attack checkbox checked | Weapon action, subject to roll/heat clarification below |
| Use weapon without matching heat label | Same | Clear attack checkbox; no counter change | Attack roll must be separated from heat eligibility |
| Vent | One of eight vent checkboxes | Subtract one if counter is positive; otherwise leave unchanged; clear vent checkbox | Per-slot Vent button |

Repair does not clear shield damage or heat. Rest does not restore health or clear shield damage. Vent does not check whether equipment has a heat rating. There is no turn timer, automatic cooling, heat cap, or overheat penalty implemented by this script.

For normal nonnegative integer counters, venting cannot go below zero. The original script does not sanitize manually entered negative or fractional values; the app should validate its counter inputs rather than reproduce invalid states.

### Slot mapping

| Stable slot ID | Attack checkbox | Heat label | Counter | Vent checkbox |
|---|---|---|---|---|
| fixed_1 | A25 | F28 | F29 | G29 |
| fixed_2 | A30 | F33 | F34 | G34 |
| fixed_3 | A35 | F38 | F39 | G39 |
| fixed_4 | A40 | F43 | F44 | G44 |
| back | A47 | E52 | E53 | F53 |
| left | A54 | E59 | E60 | F60 |
| right | A61 | E66 | E67 | F67 |
| chest | A68 | E73 | E74 | F74 |

Fixed-weapon heat labels read Zoid_DB columns 85–88. Removable equipment reads Armaments column 16. Extract these as typed reference fields instead of parsing UI labels at runtime.

### Source quirks and app decisions

- Only Repair is explicitly scoped to the Zoid sheet. Rest and counter edits act on matching coordinates on any active sheet. App actions should target the current character's combat state, not reproduce this spreadsheet side effect.
- The source regex also matches prefixes such as `Heat: 10`. Audit actual data values before defining valid heat ratings.
- Successful heat additions leave the attack checkbox checked, so another addition requires an uncheck/check cycle. Buttons can replace this with one explicit action per press.
- The attack formulas also use these checkboxes to enable volatile d20 rolls. Script clearing of non-heat attack checkboxes may clear their displayed rolls. App roll outcomes should be retained independently of checkbox state.
- No event wiring is present in the GIF script itself. Whether it was run manually or by an installed trigger does not affect combat rules.

### Combat UI interaction still to confirm

Heat capacity and overheating behavior are now confirmed above. The original script remains documented here as the source baseline, not the full app rule set.

Proposed interaction: a Roll/Use button rolls once and adds one heat counter for eligible equipment; Vent subtracts one; Rest clears heat. Repair restores health at 10g per point and repairs broken weapons at 10,000g each. Confirm whether heat should instead be tracked with a separate Use control, particularly for non-attacking equipment.

### Required verification cases

- Repair uses the latest derived maximum health while preserving shield damage and heat.
- Rest clears every slot counter while preserving health and shield damage.
- Repeated eligible uses add one each; displayed heat rating does not multiply the increment.
- Vent at zero remains zero; vent at a positive integer subtracts one.
- Non-heat weapons can roll without accumulating heat.
- Refreshing or saving a character does not roll dice or change heat.
- Save/reopen preserves all eight counters and health independently of derived stats.

## Optional: GIF display

`updateQuadGifs()` reads the selected Zoid from **Zoid!C4**, despite the stale comment mentioning C2. It finds the first exact match in Zoid_Gifs column A, then uses columns B–E as four image sources at G25, G30, G35, and G40.

On a match, it removes existing images at those anchors and inserts available replacements. Drive links are loaded through DriveApp; other HTTP links are inserted directly. Missing matches leave existing images in place. Image errors are logged. This script does not modify character statistics, damage, heat, or game rules.

Treat this as an optional visual feature, deferred from the first playable version. Keep the source script and data for reference. If included later, map each Zoid to bundled local image files and render them with Flet; no Drive access, remote URLs, or Apps Script runtime is needed.
