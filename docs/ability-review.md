# Remaining ability review

Reviewed against local `abilities.json`, descriptions, and implemented Python paths. Dashboard-origin findings remain deferred unless the owner elects to address their gameplay behavior.

## Calculation discrepancies

| Family | Current behavior / gap | Decision or correction needed |
|---|---|---|
| **Resolved: Expert stacking** | All six families affect every eligible slot using order-independent tag matching. Advantage text is removed. Rifle Expert requires Ranged + Bullet. | Each weapon receives the largest applicable active Expert bonus, plus active Anti-Air Pro if it has the Anti-Air tag. Other Expert ties apply once; selection is independent per weapon and ability slot order. |
| Type abilities | Zoid type is substring-matched to ability names; broader Mammal/Dinosaur category relationships are not explicitly modeled. | Define applicable types/categories if broad proficiency abilities should include named subtypes. |

## Player-managed abilities: tracking only

Owner confirmed these abilities need only active/inactive ownership tracking and descriptions. No automated action handling is required.

| Family | Intended effect from descriptions | Implementation gap |
|---|---|---|
| Melee / Ranged Multi Attack | Additional attacks per turn | Player managed |
| Armor Breaker | Increase defense reduction | Player managed |
| Smoke Master | Enlarge smoke coverage | Player managed |
| Weapon Breaker | Critical melee hits can destroy target weapons | Player managed |
| Counter Attack | React to an enemy rolling a natural 1 | Player managed |

Related feat: **Demolitionist** should vent every weapon rather than only the selected weapon. It remains descriptive and needs integration with the combat controller.

## Completed in the current milestone

- Laser, Missile, Particle, Melee, Rifle Expert and Anti-Air Pro bonuses now reach all eight qualifying weapon slots. Expert ranks 3/4 no longer grant or describe advantage.
- Use the strongest applicable active bonus among Laser, Missile, Particle, Melee, and Rifle Expert. **Anti-Air Pro is an exception:** add its bonus on top when active and the weapon has the Anti-Air tag, even if no other Expert applies. Other bonus sources (pilot, size, activated Organoid, equipment, fixed upgrades, contextual Sniper) retain their own rules.
- Melee tags are tracking labels with no automatic damage/status mechanics. Tags still determine which Expert abilities qualify; Piercing, Electrical, etc. do not independently apply extra effects.
- Explicitly ranged Piercing tags are replaced with Bullet, including declared Ranged armaments. Melee Piercing is retained as a player-managed tag. Source corrections are retained in record metadata. Legacy equipment lacking an explicit Ranged class is still subject to the tag audit rather than inferred from its damage element.
- Owner-approved tag cleanup applies to all weapon tag fields: Anti-Ait becomes Anti-Air; Slashing and Bludgeon are removed; Freeze, Electric, Electrical, and Lighting become a single Electrical tag. Duplicate tags are removed and malformed separators normalized. Melee Piercing is retained. Original values remain in correction metadata and the source inventory.
- `docs/generated/melee-tags.md` and `.json` inventory the current cleaned melee tags and examples. `tools/audit_melee_tags.py` reproduces the inventory offline.

- Fleet Footed's four confirmed speed bonuses while active.
- Sniper rank-based to-hit for active skills on Long Range ranged attack previews.
- Comeback rank-based 20/30/40/50% damage at <=20% current maximum health.
- True Tank adds its bonus per enabled defensive item (positive Defense field), following the existing per-item activation rules.
- Shield Master adds its flat bonus once to combined positive Shield HP, from any active ability slot and any contributing source. It does not create a shield by itself.
- Evasion Master grants +1 Armor per rank per enabled reaction-boosting item, including fixed equipment with reaction modifiers. It no longer grants extra Reaction.
- Economized Shooting grants +1 maximum heat to heat-rated weapons while active. Calculated weapons expose `maximum_heat` and `heat_capacity_bonus`; pass the current bonus to `use_weapon()`. Deactivation lowers capacity without clearing heat or immediately breaking the weapon. A subsequent use at/above capacity works once and then breaks it.
- Wimp, Cross Eyed, Slowpoke, Bad Armor and all ranks are removed from runtime catalogs. Conversion records the retired source rows; the original workbook is retained. Retired ability IDs are rejected.

## Range input follow-up

Use mutually exclusive Close / Normal / Long choices for ranged attacks only. Exactly half maximum range is confirmed **Normal**. `range_band_for_distance()` and optional attack distance implement this boundary. Other overlapping Close/Long distances for very short maximum ranges require explicit selection instead of guessing. Legacy weapons missing Ranged/Melee tags still need data cleanup.
