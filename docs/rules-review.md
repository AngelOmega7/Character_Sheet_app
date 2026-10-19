# Step 5: rules review decisions

Implemented ruleset: `owner-corrected-v13`. Reference data: `laser-and-types-v11`. The source workbook/inventory is preserved; corrections are applied by `tools/convert_reference_data.py` and recorded in catalog metadata.

## Type abilities — resolved

Owner confirmed **exact listed game types**, ignoring capitalization and surrounding whitespace. No biological hierarchy is inferred:

- Mammal Type applies to Mammal, not Lion/Tiger/Wolf/Gorilla.
- Dinosaur, Land Type applies to Dinosaur, Land, not Raptor/T-Rex.
- Dinosaur, Flying, Reptile, and the other categories are likewise distinct.

The converter emits `eligible_types` for Type abilities. Runtime matching uses complete categories instead of substring searches in ability names. Existing rank bonuses are unchanged.

## Ranged classification and Laser tags — resolved

The audit found 61 Armaments records with a declared Ranged class but no Ranged tag. Their class is now reflected in the tags. Six additional Zoid-specific weapons explicitly say Ranged in their name/effect prose; those tags are restored. Zaber Fang RS's Double Beam Cannon is explicitly Ranged + Laser by owner decision.

- Every ranged Energy tag becomes **Laser**, preserving other applicable tags.
- Ranged Piercing remains **Bullet** under the earlier decision.
- **Laser Expert matches Laser tags only**. Retained Energy tags on melee weapons do not qualify.
- Melee Energy is retained; there is no blanket Energy-to-Laser conversion for melee.

Range controls, Sniper, and Expert matching now see the same explicit classification. Correction metadata retains original tags. The current audit finds no Ranged + Energy combinations and no named, positive-damage Zoid attack missing Melee/Ranged in the live tag columns. Utility/empty slots are not inferred to be attacks from zero or missing damage.

## Zaber Fang fixed weapons — restored

The previously unnamed damage-45 fourth slot was a missing weapon. Owner supplied this layout:

| Slot | Weapon | Base damage | Base to-hit | Tags |
|---|---|---:|---:|---|
| 1 | 3 Barrel Shock Cannon | 120 | 14 | Ranged, Explosive |
| 2 | 20mm | 120 | 17 | Ranged, Particle |
| 3 | Laser Machine Gun | 45 | 17 | Ranged, Laser, Close Range |
| 4 | Killer Saber | 140 | 13 | Melee |

Killer Saber's original effect text and other values move with it. No new effect text or heat rating was invented for Laser Machine Gun. Close Range remains a tag under the existing tag rules.

Schema v7 migrates prior positional builds and activation flags. Owned upgrade/condition identities already belong to Killer Saber, so reprojecting them into slot 4 preserves upgrades, condition, and last d20 results. Laser Machine Gun receives none of Killer Saber's upgrades or rolls. V1 pre-roster saves have their positional upgrade points moved before ownership is created.

## Still deferred

- Dashboard armor-ability bonuses conditional on a size match.
- Dashboard Organoid damage using the to-hit column.
- Purchasing/building prices and required parts: awaiting the owner's table.
- Transport rules: awaiting the owner's design; required before Step 7 completion.

The first two retain their earlier explicit deferrals. This review does not claim complete spreadsheet parity or implement the deferred purchase/Transport systems.
