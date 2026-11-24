# SRD supplement integration

## Subsequent handbook review

The integration record below describes the initial SRD import. The owner's
later handbook edits supersede its earlier unresolved-rule notes:

- Overload now reduces removable as well as fixed base weapon accuracy.
- Successful AoE avoidance (including a tie) halves damage. Live weapon
  descriptions and both apps' combat help now state this rule.
- Small Expert 3/4 retain rank 2 critical protection; Counter Attack 2 triggers
  on 5 or lower; Ranged Multi Attack grants 1/2/3/4 extra attacks.
- Smoke Master coverage is 15/15/45/45m. Pit Stop uses one action and allows
  returning on the following turn. Ability/feat descriptions are updated;
  target-dependent effects and action timing remain table-managed.
- Normal OS rounds half pilot level down. The sheet's Normal OS option derives
  this level automatically, up to its supported cap of 40; manual levels remain
  available and existing saves default to manual mode.
- Appendix B now omits questions settled by the revised chapters, including
  initiative ties, advantage cancellation, bonus-action allowance, inheritance,
  Multi Attack wording, Normal OS rounding, Pit Stop timing, Feint duration,
  Slowed's default reduction, and advancement. Shield damage allocation and
  equal-HP shutdown ties remain narrower questions after the new shield text.

The unmarked edits to shield activation/restoration and unaffordable upkeep
are recorded in the handbook; the app changes in this review implement the
asterisk-marked requests. Existing shield/turn automation is still described
in `docs/energy-rules.md` and the tracker README.

## Sources and precedence

- Supplementary source: `source/ZOIDS TTRPG SRD.txt` (600 lines).
- Updated rulebook: `ZOIDS_Pilots_Handbook.txt`.
- The handbook as it existed before this integration takes precedence over
  conflicting SRD material. Its existing user-edited introduction was retained.
- This is a documentation integration. Imported tabletop rules are not claims
  of new validation, controls, or automation in either app.

## Source coverage

| Old SRD section / lines | Treatment in the handbook |
| --- | --- |
| Terms, 32–36 | d20, advantage, and disadvantage in Chapter 1; quick reference updated. |
| Attributes and personality, 45–64 | Starting 1/2/3 allocation, personality/color guidance, and attribute checks in Chapter 1. Additional starting-point ambiguity retained in Appendix B. |
| Ability learning, 67–76 | One initial ability, learning or upgrading on level gain, rank prerequisite levels, and long-rest swaps in Chapter 1. Apps remain manual recordkeepers for these requirements. |
| Old ability list, 79–119 | Current Chapter 6 retained. Superseded numbers and effects not imported. Ranged Multi Attack's copied Melee text does not resolve its current rank-4 wording. |
| Pilot creation, 124–147 | Existing starter list retained; development-facility style changes added. Conflicting extra Attribute point and odd-level upgrade language flagged rather than silently awarded. |
| Advancement and feats, 150–173 | Milestone guidelines, Attribute gains every four levels, and feats every ten levels integrated into Chapters 1 and 7. Demolitionist's free-action timing added; current Deadshot effect retained. |
| Statistics, 182–221 | Armor target number, Defense subtraction/minimum, typed protection, Health-scale conversion, initiative/AoE role of Reaction, maximum combat Range, negligible human supplies, and encounter-start half-Energy reset integrated into Chapters 2 and 4. |
| Organoids, 224–247 | OS types, level formulas, color determination, activation action, Wild OS behavior, cockpit requirements, and shutdown triggers integrated into Chapter 8. Current 0–40 support and existing resource bonuses preserved. |
| Equipment activation, 249–256 | Standard-action activation, speed activation/Dash, movement requirements, and targeting-equipment restrictions integrated into Chapter 3, subject to newer bonus-action permissions. |
| Development and salvage, 259–286 | Core reuse/recovery, components, generic parts, paint prices, selective salvage, and ancestor Zi Data integrated into Chapter 10. Existing recipes and financial rules remain authoritative. Manual salvage credits are distinguished from app transactions. |
| Old upgrades, 289–310 | Current Chapter 9 retained. No restoration of obsolete five-point caps on all tracks, per-weapon tracks, or old weapon-upgrade prices. |
| Movement, 317–363 | Chapter 11 added: grid movement, narrative travel, jumping, flight/swimming, stealth, difficult terrain, and Coasting. |
| Initiative/turns, 366–386 | Reaction initiative, six-second rounds, move/standard actions, free speech, and split movement integrated into Chapter 4. No-bonus-actions prohibition rejected. |
| Attack resolution, 389–403 | Armor ties, strict AoE avoidance comparison, normal shield absorption, Defense damage, recharge tracking, and effects integrated into Chapters 4 and 5. Current Energy payment on Use retained. |
| Critical hits/misses, 406–412 | Natural 20 criticals, default Defense bypass, critical shield failure/overflow, natural 1 misses, jams, and immediate Mental jam-clearing checks integrated into Chapter 4. Jam distinguished from broken equipment. |
| Equipment and actions, 415–431 | G-force checks, targeting activation, Aim, Dodge, and Feint integrated into Chapters 3, 4, and 12. Feint's missing duration/check remains unresolved. |
| CAS and range, 434–445 | Station/start action plus two subsequent standard actions added to Chapter 10. Range disadvantage and weapon exceptions added to Chapters 3 and 4, preserving current range-band boundaries. |
| Energy/reactions, 448–455 | Charge Energy action and one-reaction allowance/opportunity attacks integrated into Chapter 4. Current upkeep, caps, and affordability rules preserved. |
| System Down/Core damage, 458–461 | Emergency repair totals, damage thresholds, and Laboratory recovery integrated into Chapter 4. |
| Repairs, 464–468 | Facilities, repair kits, and current matching repair prices integrated into Chapter 9. Exact time and ambiguous Z-kit percentage remain unresolved. |
| Pilot checks, 471–483 | Physical consciousness/G-force and Mental repair checks integrated. Existing Mental contribution retained without double-counting initiative. Social's old underlevel exception omitted. |
| Conditions/table, 495–578 | Chapter 12 added with all listed conditions and defined modifiers. Specific newer smoke/invisibility protection overrides old targeted-attack concealment treatment. |
| Weapon properties, 586–600 | Chapter 3 expanded with range properties, size-specific Reach, damage types, Electrical, Acid/Defense, Homing, and Piercing; current matching/tag and ability exceptions preserved. |
| On-foot chapter listed in contents | No corresponding chapter exists in the file. Did not fabricate on-foot Health, weapon profiles, or a complete personal-combat system. |

## Conflicts resolved in favor of the existing handbook

- Keep Iron Defense 10/20/30/40, Shield Master 100/150/200/250, revised True
  Tank 5/10/10/10 Armor caps and critical protection, and the current Armor
  Breaker, Evasion Master, Smoke Master, Sniper, and Weapon Expert effects.
- Anti-Air Pro remains a target-based ability. The SRD's separate Anti-Air
  weapon property supplements it, rather than restoring a tag requirement.
- Laser Expert matches Laser; Rifle Expert matches Ranged plus Bullet.
- Preserve the new bonus-action permissions. Do not infer a general bonus-action
  count from the old prohibition, which cannot coexist with those permissions.
- Retain current Deadshot, supplement Demolitionist only with free-action timing.
- Preserve current Energy costs, the minimum reduced cost of 2, recharge-then-
  upkeep order, Organoid upkeep exemption, and payment when using equipment.
- Preserve current persistent shield damage and combined pool. Add the old
  ordinary/critical overflow distinction, but leave multi-source critical
  shutdown allocation unresolved because the SRD assumes a single shield.
- Smoke/invisibility still prevents targeted attacks. The old Concealed
  modifier is not permission to attack through that prohibition.
- Keep current frame upgrades, prices, caps, no player minimum-Zoid-level
  penalty, ownership rules, sale/detachment refunds, and FUZOR procedures.
- Retain exact current range bands, including Close priority and inclusive
  Normal half-range boundary; use maximum Range as an inclusive combat limit.

## Editorial reconciliation within the SRD

- Use size-specific Melee Reach from the property entry instead of treating
  the general 30m melee summary as overriding LL/XL Reach.
- Use movement equal to Speed per move action, not six times Speed. This follows
  the explicit turn procedure and the SRD's stated abstraction.
- Use the explicit running-jump rounding rule rather than its unrounded example.
- Use the explicit end-of-turn shutdown on a failed G-force check from the
  Pilot Attribute section; the activation section does not specify that timing.
- Dodge's +10 Armor/Reaction and table's -10 incoming modifier represent the
  same benefit, not two cumulative benefits from the same action.
- Use Normal OS's stated level formula, not the incompatible level-13 example
  for a level-20 pilot. Preserve the handbook's supported 0–40 range.
- Read Homing's pre-"armor" halving in the context of the SRD's own definitions:
  Armor determines a hit, while Defense mitigates damage. No second subtraction
  of Armor from damage is introduced.
- Preserve unresolved internal ambiguities explicitly: starting Attribute point,
  odd-level ability award, Electrical d100 cutoffs/recovery, Limited OS fallback,
  and other items narrowed in Appendix B.

## Appendix B maintenance

Moved established procedures into their chapters instead of continuing to list
all foundational combat, milestone advancement, feat awards, repair facilities,
and basic CAS timing as missing rules. Retained only narrower gaps, conflicting
source details, and interactions with newer effects that neither text settles.
