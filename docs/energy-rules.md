# Energy rules — energy-v17 / save schema 14

Heat ratings, counters, overheating, Vent, and heat-clearing Rest are removed.
These rules supersede heat references in historical workbook/script audits.

## Combat

- Each Zoid/form has total energy, recharge per turn, and named weapon/system costs.
- **Use** deducts the displayed cost from the active chassis's current energy.
  Insufficient energy or a broken weapon rejects the entire action, without a
  roll or resource change. Spending exactly the remaining energy is allowed;
  zero-cost weapons remain usable at zero energy. Uses no longer break weapons.
- Numerical-damage weapons roll one d20 on successful Use; utilities spend their
  listed cost without rolling. Resolve effects at the table. Activation toggles
  retain their stat-calculation role; use a system's Use button to pay its cost.
- Press **Start Turn** once when your turn begins: add that form's recharge,
  capped at total energy. This is an explicit turn action, not a clock or a
  recharge on render, load, equipment change, or form switch.
- **Rest** sets the active Zoid's current Energy to half its equipped maximum,
  rounded down to a whole point. This is an assignment, so resting reduces Energy
  that was above half as well as raising Energy that was below half. It does not
  change health, gold, shield damage, weapon conditions, rolls, or other Zoids.
- Current energy can also be edited through Combat resources, from zero to total.
  Health and Energy bars show current/maximum resources.
- Current energy belongs to each physical owned chassis. CAU forms share the
  pool; moving to a lower-capacity form clamps it, and moving back never refills
  it. Separate Zoids retain independent pools. New Zoids and missing Energy values
  default to half of maximum, rounded down. Existing saved values are preserved.
- Repairs retain their prior prices and broken-weapon handling. Repair, previews,
  and stat recalculation do not recharge energy. Existing broken flags remain.
- Transport reference panels show energy/recharge/costs; Transport remains a
  GM-managed reference/cargo selection, outside the playable combat roster.

## Reinforcer units and Energy Container

- **Physics Reinforcer Unit:** passive, weight 3, +100 maximum Health as a flat
  bonus after pilot/Organoid multipliers. Does not heal current Health.
- **Energy Reinforcer Unit:** passive, weight 3, +20 maximum Energy. Does not
  refill current Energy. Rest, recharge, Energy Container, manual edits, and saved
  resources use the boosted maximum. Removing the unit or switching to a form
  without it clamps current Energy to the resulting maximum.
- **Energy Container:** active, weight 10, restores 20 Energy when activated,
  capped at the current maximum. Its **Activate** button performs the resource
  action immediately, without a d20 or a persistent activation toggle. Rendering,
  equipping, and loading a save never activate it. No usage limit or consumption
  has been specified. All three items cost zero Energy to use.

Compatible equipped copies contribute their passive bonuses independently.

## EPT upgrades

EPT means **Energy Per Turn**. Each EPT upgrade adds 1 to the selected form's base
recharge rate, with no upgrade cap. The price of rank N is **10,000g × 2^(N−1)**:
10,000g, 20,000g, 40,000g, 80,000g, and so on. Minus refunds the removed rank's
full price. Unaffordable upgrades make no changes. EPT upgrades follow the owned
chassis across CAU forms and persist with retained FUZOR frames and component
history. They affect Start Turn recharge, not maximum Energy, current Energy,
or the half-maximum Rest value.

Each upgrade box shows the selected form's raw base stat to its right, before
pilot bonuses, equipment, penalties, or upgrades. Accuracy has no single chassis
base stat, so it lists each fixed weapon's catalog to-hit value instead.

## Data and mapping

`docs/Energy_Addition.ods` supplies Zoid totals, recharge, and named equipment
costs; `docs/Generic_Energy.ods` supplies generic equipment costs. Approved blank
generic costs mean zero. Zoid-specific templates use the Zoid's cost even when
mounted in another compatible slot; generic copies use their generic cost.
The current app's weapon positions are retained.

Zoid-specific removable items use source E5–E8 as lookup identities, not mounting
restrictions. Utility items fit Assist and Weapon and Assist slots (5–8 on their
current designs). Konig Wolf DSR's missile pod fits slots 6 or 7. Great Zaber's
20mm Solid Rifle is restricted to slot 6; its Double Beam Cannon can be equipped
alongside it in slot 5 or 7. See `generated/zoid-equipment-audit.md` for the complete
13-item, 12-design audit and reproduction command. No named cost entries are missing.

`docs/generated/energy-mapping.md` records moved positions and approved additions,
including all three newly defined generic equipment items above.

Reimport with `python3 -m tools.import_energy`. This dedicated importer is the
verified update path. The full reference converter is wired to apply energy
after source conversion, but its existing source reconstruction currently fails
on the absent Great Zaber purchase mapping before reaching that step. It needs
the separately authored Zoid additions incorporated before a full rebuild can
work. Missing/ambiguous energy names or costs fail import rather than silently
becoming free. The companion is updated with total energy, recharge, and each
listed weapon/system's cost.

## Pilot options

| Option | Previous effect | Current rules |
| --- | --- | --- |
| Economized Shooting (ability) | +1 maximum heat for each heat-rated weapon while active; originally a one-use overheating exception | Four ranks reduce Ranged-tagged weapon Energy Cost by 2/4/6/8 while active, minimum 0. Applies to fixed, generic, and Zoid-specific equipment. Higher ranks replace lower ranks in the same family. Existing selections remain rank 1. |
| Demolitionist (feat) | Vent 2 heat instead of 1 from one selected weapon | Player-tracked: “Once per Rest, you may completely fill your Zoid's Energy.” Set current Energy to its displayed maximum when using the feat, and track the once-per-Rest limit at the table. |

Inactive Economized Shooting does not reduce costs. Demolitionist has no
automatic refill or Rest tracking.

## Save migration

Schema 12 migrates prior saves/exports transactionally: discard retired heat
counters, preserve broken flags, last rolls, identities, health, gold, loadouts,
pilot options, and retirement archives. Initialize each owned chassis (including
stored pre-fusion components) at half its selected form's maximum energy, rounded down. Later saves
and exports persist current energy; reopening never refills it.

Schema 13 moves older Great Zaber rifle loadouts into slot 6, swapping the former
slot-6 item into the rifle's previous legal mount. Copy IDs, conditions, activation
flags, and energy are preserved. Extra rifle copies remain owned but are unassigned
when slot 6 already contains a rifle.

Schema 14 adds the saved EPT upgrade count. Earlier saves default it to zero;
their recorded current Energy and other resources remain unchanged.
