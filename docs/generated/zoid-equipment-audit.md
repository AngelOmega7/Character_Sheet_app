# Zoid-specific equipment audit

Every named entry in the Zoid energy-cost spreadsheet maps to an implemented fixed or removable item. No missing named items were found.

Great Zaber and Buster Fury are absent from that spreadsheet; their approved app entries were also checked. Great Zaber and Shadow Fox each have two removable Zoid-specific items that can be equipped simultaneously.

Source E5–E8 identifies the catalog lookup. Weapons use Weapon and Assist slots, subject to explicit mounting restrictions: Great Zaber's 20mm Solid Rifle uses slot 6; the four restored unique weapons use slot 5. Named non-weapon equipment uses either Assist or Weapon and Assist slots, including slots 5–8 on every design listed below. One physical copy still occupies only one slot per form.

| Zoid | Item | Type | Source | Allowed slots | Energy cost |
| --- | --- | --- | --- | --- | --- |
| Zaber Fang Old | Double Beam Cannon | Weapon | E5 | 5, 6, 7 | 6 |
| Zaber Fang | Double Beam Cannon | Weapon | E5 | 5, 6, 7 | 6 |
| Zaber Fang RS (CAU) | Double Beam Cannon | Weapon | E5 | 5, 6, 7 | 6 |
| Proto Zaber | Double Beam Cannon | Weapon | E5 | 5, 6, 7 | 7 |
| Great Zaber | Double Beam Cannon | Weapon | E5 | 5, 6, 7 | 7 |
| Great Zaber | 20mm Solid Rifle | Weapon | E6 | 6 | 6 |
| Diablo Tiger | Auto Repair Unit | Assist | E8 | 5, 6, 7, 8 | 3 |
| Atak Kat | Double Beam Cannon | Weapon | E5 | 5, 6, 7 | 3 |
| Lightning Saix | Pulse Laser Gun | Weapon | E5 | 5 | 6 |
| Lightning Saix BS | Pulse Laser Gun | Weapon | E5 | 5 | 8 |
| Zero X (CAU) | Stealth Generator | Assist | E5 | 5, 6, 7, 8 | 3 |
| Command Wolf | Double Beam Cannon | Weapon | E5 | 5, 6, 7 | 3 |
| Command Wolf IS (CAU) | Long Range Rifle | Weapon | E5 | 5 | 6 |
| Shadow Fox | Laser Vulcan Gun | Weapon | E5 | 5 | 8 |
| Shadow Fox | Optical Camouflage | Assist | E8 | 5, 6, 7, 8 | 3 |
| Konig Wolf DSR (CAU) | 5-Shot Missile Pod | Weapon | E6 | 6, 7 | 10 |
| Mad Thunder | Anti-Particle Beam Shield | Assist | E8 | 5, 6, 7, 8 | 2 |

## Multiple removable items

- Great Zaber: Double Beam Cannon in slot 5; 20mm Solid Rifle in slot 6.
- Great Zaber: Double Beam Cannon in slot 7; 20mm Solid Rifle in slot 6.
- Shadow Fox: Laser Vulcan Gun in slot 5; Optical Camouflage in slot 6.
- Shadow Fox: Laser Vulcan Gun in slot 5; Optical Camouflage in slot 7.
- Shadow Fox: Laser Vulcan Gun in slot 5; Optical Camouflage in slot 8.

The Konig Wolf DSR's Dual Sniper Rifle is already fixed equipment; its removable 5-Shot Missile Pod can mount in slot 6 or 7 alongside it.

Lightning Saix/BS Pulse Laser Gun, Command Wolf IS Long Range Rifle, and Shadow Fox Laser Vulcan Gun are restored to Zoid-specific removable slot 5. Their Energy costs, damage, and accuracy follow the removable item.

Reproduce with `python3 -m tools.audit_zoid_equipment`.
