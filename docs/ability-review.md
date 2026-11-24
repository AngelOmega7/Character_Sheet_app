# Remaining ability review

Reviewed against local `abilities.json`, descriptions, and implemented Python paths. Dashboard-origin findings remain deferred unless the owner elects to address their gameplay behavior.

## Calculation discrepancies

| Family | Current behavior / gap | Decision or correction needed |
|---|---|---|
| **Resolved: Expert stacking** | Laser, Missile, Particle, Melee, and Rifle Expert affect eligible slots using order-independent tag matching. Rifle Expert requires Ranged + Bullet. | Each weapon receives the largest applicable active Expert bonus. Ties apply once; selection is independent per weapon and ability slot order. Anti-Air Pro is player-managed against flying Zoids. |
| **Resolved: Type abilities** | Explicit `eligible_types` metadata replaces substring matching. | Owner confirmed exact listed game types: Mammal does not cover Lion/Tiger/Wolf/Gorilla, and Dinosaur, Land does not cover Raptor/T-Rex. Matching ignores case and surrounding whitespace. |
| **Resolved: Laser Expert** | All ranks require the Laser tag. | Ranged Energy becomes Laser. Retained melee Energy does not qualify for Laser Expert. |

## Player-managed abilities: tracking only

Owner confirmed these abilities need only active/inactive ownership tracking and descriptions. No automated action handling is required.

| Family | Intended effect from descriptions | Implementation gap |
|---|---|---|
| Melee / Ranged Multi Attack | Additional attacks per turn | Player managed |
| Armor Breaker | Attack versus reaction; on hit, reduce armor by rank instead of dealing damage | Player managed |
| Smoke Master | Enlarge smoke coverage | Player managed |
| Weapon Breaker | Critical melee hits can destroy target weapons | Player managed |
| Counter Attack | React to an enemy rolling a natural 1 | Player managed |

**Economized Shooting** has four ranks, reducing Ranged-tagged weapon Energy Costs by 2/4/6/8 while active (minimum 2; costs already below 2 are unchanged). **Demolitionist** is player-tracked: “Once per Rest, you may completely fill your Zoid's Energy.” Full rules and previous effects are tracked in `energy-rules.md`.

All seven feats have saved selection slots and visible descriptions in the Pilot feats panel. Phalanx Fire/Scrappy do not trigger automatic advantage rolls. Physical/Social and pilot notes are tracking-only. Mental keeps its existing calculation rule. Inactive abilities can be removed from ownership using their Remove buttons, then learned again later if desired.

## Completed in the current milestone

- Flet ability management: learn new families inactive, permanently replace owned lower ranks, assign/deactivate six active slots, enforce one active size ability, and display inactive ownership and descriptions. Validated character transitions preserve health/resources and save ownership pilot-wide through Zoid/CAU switches.
- Flet Organoid color/level/activation controls recalculate stats immediately. Selected settings are validated even while deactivated, persist with the pilot, and preserve current health. Only White generates shields using Organoid level. Weapon-card previews include selected range and current-health context, alongside Use/Start Turn/repair actions.
- Laser, Missile, Particle, Melee, and Rifle Expert grant +2/+3/+4/+5 to hit across all eight qualifying weapon slots. Ranks 2/3/4 grant critical hits on rolls of 19/18/18; rank 4 critical hits deal double damage. Critical hits are resolved at the table.
- Use the strongest applicable active bonus among those five Expert families. **Anti-Air Pro is player-managed:** +2/+3/+4/+5 to hit for all attacks against flying Zoids, regardless of weapon tags. Other bonus sources (pilot, size, activated Organoid, equipment, fixed upgrades, contextual Sniper) retain their own rules.
- Melee Multi Attack ranks 2–4 allow only two melee attacks against one target per action; additional attacks need a new target. Ranged Multi Attack ranks 2–4 allow each ranged weapon to fire only twice per action; additional attacks require another ranged weapon.
- Melee tags are tracking labels with no automatic damage/status mechanics. Tags still determine which Expert abilities qualify; Piercing, Electrical, etc. do not independently apply extra effects.
- Explicitly ranged Piercing tags are replaced with Bullet, including declared Ranged armaments. Melee Piercing is retained as a player-managed tag. Source corrections are retained in record metadata. Legacy equipment lacking an explicit Ranged class is still subject to the tag audit rather than inferred from its damage element.
- Owner-approved tag cleanup applies to all weapon tag fields: Anti-Ait becomes Anti-Air; Slashing and Bludgeon are removed; Freeze, Electric, Electrical, and Lighting become a single Electrical tag. Duplicate tags are removed and malformed separators normalized. Melee Piercing is retained. Original values remain in correction metadata and the source inventory.
- `docs/generated/melee-tags.md` and `.json` inventory the current cleaned melee tags and examples. `tools/audit_melee_tags.py` reproduces the inventory offline.

- Fleet Footed's four confirmed speed bonuses while active.
- Sniper grants +2/+4/+6/+8 to hit for active skills on Long Range ranged attack previews.
- Comeback rank-based 20/30/40/50% damage at <=20% current maximum health.
- True Tank adds 1 Armor per full 10 total Defense from enabled removable equipment, capped at 5/10/10/10 by rank. It does not add Defense or count fixed equipment, upgrades, or temporary Defense modifiers. Rank 3 subtracts half your Defense from critical-hit damage taken; rank 4 subtracts your full Defense, resolved at the table.
- Shield Master adds its flat bonus once to combined positive Shield HP, from any active ability slot and any contributing source. It does not create a shield by itself.
- Evasion Master imposes a minus 4/8/12/16 penalty to hit on attacks against your Reaction. This incoming-attack effect is player-managed and grants no Armor or Reaction bonus.
- Energy rules replace Heat and Vent entirely. Economized Shooting applies automatic cost reduction; Demolitionist is tracked at the table.
- Wimp, Cross Eyed, Slowpoke, Bad Armor and all ranks are removed from runtime catalogs. Conversion records the retired source rows; the original workbook is retained. Retired ability IDs are rejected.

## Range input follow-up

Use mutually exclusive Close / Normal / Long choices for ranged attacks only. Close is <=60m and takes priority. Normal is >60m and <=half maximum range; Long is >60m and >half maximum range. `range_band_for_distance()` and optional attack distance implement these boundaries, including short maximum ranges. Ranged Piercing becomes Ranged + Bullet. Ranged Energy becomes Laser; explicit class/prose tags are restored, and Zaber Fang RS's cannon is Ranged + Laser. See `rules-review.md` for the completed classification audit and Zaber Fang's restored fixed weapons.
