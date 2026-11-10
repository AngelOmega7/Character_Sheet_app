"""Refresh the text guides' Energy values while preserving editorial prices."""
import re
from pathlib import Path

from tools.import_energy import update_companion
from zoids_app.catalog import Catalog
from zoids_app.equipment import (SLOT_COLUMNS, ZOID_EQUIPMENT_COLUMNS,
                                 eligible_equipment, resolved_equipment_name)

ROOT = Path(__file__).resolve().parents[1]
RULES = """ENERGY RULES (energy-v17)
EPT means Energy Per Turn. Start Turn adds EPT once at the beginning of your
turn, capped at maximum Energy. New Zoids start at half maximum, rounded down.
Rest sets current Energy to half the equipped maximum, rounded down, whether
it was previously higher or lower. Rest does not heal or repair the Zoid.
Use spends the displayed Energy Cost. Insufficient Energy or a broken weapon
prevents use; spending exactly your remaining Energy is allowed. Zero-cost
items remain usable at zero Energy. Heat, overheating, and Vent are retired;
using a weapon no longer breaks it. Utility systems also pay their listed cost.
Equipping, loading, repairing, and changing forms do not recharge Energy.
CAU forms share their chassis's pool; a lower maximum clamps current Energy.

Economized Shooting has four ranks: while active, reduce Ranged-tagged weapon
costs by 2/4/6/8, minimum zero. Higher ranks replace lower ranks, rather than
stacking. This applies to fixed, generic, and Zoid-specific weapons.
Demolitionist: Once per Rest, you may completely fill your Zoid's Energy.
Track that limit at the table and set current Energy to its maximum when used.

EPT upgrades add +1 EPT each with no cap. Rank N costs 10,000g x 2^(N-1):
10,000g, 20,000g, 40,000g, 80,000g, and so on. Removing a rank refunds its
full purchase price. These chassis upgrades follow CAU forms and do not
increase maximum Energy, refill current Energy, or change the Rest fraction.
Listed EPT and costs are base catalog values before upgrades or abilities.

Physics Reinforcer Unit: passive, weight 3, +100 maximum Health after stat
multipliers; does not heal. Energy Reinforcer Unit: passive, weight 3,
+20 maximum Energy; does not refill Energy. Removing it clamps current Energy.
Energy Container: active, weight 10, restores 20 Energy immediately, capped at
maximum. No usage limit or consumption is specified. All three cost 0 Energy.
Compatible equipped Reinforcer copies contribute their bonuses independently.

"""


def rules(text, heading):
    text = re.sub(r"ENERGY RULES \(energy-v17\).*?(?=" + re.escape(heading) + ")",
                  "", text, flags=re.S)
    return text.replace(heading, RULES + heading, 1)


def refresh():
    catalog = Catalog()
    update_companion(catalog.tables)
    path = ROOT / 'ZOIDS_Companion.txt'
    path.write_text(rules(path.read_text(), 'CONTENTS - BASE ZOID FAMILIES'))

    path = ROOT / 'Equipment_Guide.txt'
    text = path.read_text()
    text = text.replace('91 catalog weapons; 7 Zoid-specific removable weapon entries.',
                        '91 catalog weapons; 9 Zoid-specific removable weapon entries.')
    text = re.sub(r'\d+ catalog assist items; 4 Zoid-specific assist entries\.',
                  '66 catalog assist items; 4 Zoid-specific assist entries.', text)
    text = text.replace('conditions. Missing values mean not listed, not zero. Heat and other optional\n'
                        'modifiers appear wherever recorded. Effects preserve the catalog wording,',
                        'conditions. Missing stat values mean not listed, not zero. Energy Costs\n'
                        'include explicit zeroes. Effects preserve the catalog wording,')
    text = text.replace('Zoid-specific entries retain their source slot types and restrictions.',
                        'Zoid-specific entries list allowed overall slots (5-8). Source E5-E8\n'
                        'identifies the item, not a mounting restriction. Utility equipment can\n'
                        'use Assist or Weapon and Assist slots. Costs follow the item identity;\n'
                        'Zoid-specific costs can differ from similarly named generic items.')
    text = re.sub(r'^  Heat: \d+ \| ', '  ', text, flags=re.M)
    text = re.sub(r'^  Heat: \d+\n', '', text, flags=re.M)
    text = re.sub(r'^  Energy cost: \d+\n', '', text, flags=re.M)

    # Add new catalog items once; keep the existing numbered reference stable.
    for code, name in [('A064', 'Physics Reinforcer Unit'), ('A065', 'Energy Reinforcer Unit'),
                       ('A066', 'Energy Container')]:
        if f'[{code}]' in text:
            continue
        record = catalog.find('armaments', name)
        f = record['fields']
        text = text.replace('CONTENTS - ZOID-SPECIFIC ASSIST EQUIPMENT',
                            f'{code}  {name}\n\nCONTENTS - ZOID-SPECIFIC ASSIST EQUIPMENT', 1)
        block = (f"{'-' * 78}\n[{code}] {name}\n{'-' * 78}\n"
                 f"  Slot eligibility: Assist or Weapon and Assist\n"
                 f"  Weight: {f['weight']}\n  Activation: {f['activation']}\n"
                 f"  Effect: {f['effect']}\n\n")
        text = text.replace('\nZOID-SPECIFIC ASSIST EQUIPMENT\n', '\n' + block + 'ZOID-SPECIFIC ASSIST EQUIPMENT\n', 1)

    for code, name, damage_type, hit, weight, description in [
        ('Z08', 'Double Beam Cannon', 'Ranged, Laser', 18, 17,
         'Back mounted energy cannon. Targets a single opponent.'),
        ('Z09', '20mm Solid Rifle', 'Ranged, Long Range, Bullet', 17, 15,
         'Shoulder mounted long-range rifle. Targets a single opponent.')]:
        entry = f'{code}  {name} - Great Zaber'
        if entry not in text:
            text = text.replace('CONTENTS - SECTION 2: ASSIST EQUIPMENT',
                                entry + '\n\nCONTENTS - SECTION 2: ASSIST EQUIPMENT', 1)
        if f'[{code}]' in text:
            continue
        block = (f"{'-' * 78}\n[{code}] {name} - Great Zaber\n{'-' * 78}\n"
                 f"  Listed on: Great Zaber\n  Damage: 200 | To hit: {hit}\n"
                 f"  Damage type: {damage_type}\n  Weight: {weight}\n  Effect: {description}\n\n")
        marker = '=' * 78 + '\nSECTION 2'
        assert marker in text
        text = text.replace(marker, block + marker, 1)

    armaments = {r['name'].split(':', 1)[0].strip(): r for r in catalog.tables['armaments']['records'] if r['kind'] == 'record'}
    specific = {}
    for zoid in catalog.tables['zoids']['records']:
        for i, (column, _) in enumerate(ZOID_EQUIPMENT_COLUMNS):
            if not catalog.column(zoid, column):
                continue
            template = catalog.find('armaments', f'armaments:zoid_equipment_slot_{i + 1}')
            name = resolved_equipment_name(template, zoid, catalog)
            slots = [str(j + 5) for j, slot in enumerate(SLOT_COLUMNS)
                     if template in eligible_equipment(zoid['id'], slot, catalog)]
            specific[f'{name} - {zoid["name"]}'] = (zoid['energy_costs'][i + 4], i + 5, slots)

    blocks = re.split(r'(?=^\[[^]]+\] )', text, flags=re.M)
    seen = set()
    for i in range(1, len(blocks)):
        block = blocks[i]
        code, name = re.match(r'\[([^]]+)\] (.+)', block).groups()
        seen.add(name)
        if code.startswith('Z'):
            cost, source, slots = specific[name]
            block = re.sub(r' \| Removable slot: \d+', '', block)
            block = re.sub(r'^  (?:Source slot type|Source identity|Allowed slots):.*\n', '', block, flags=re.M)
            detail = f'  Source identity: E{source}\n  Allowed slots: {", ".join(slots)}\n'
        else:
            cost = armaments[name]['energy_cost']
            detail = ''
        lines = block.splitlines(keepends=True)
        lines.insert(2, f'  Energy cost: {cost}\n' + detail)
        blocks[i] = ''.join(lines)
    assert set(armaments) <= seen, set(armaments) - seen
    assert set(specific) <= seen, set(specific) - seen
    text = rules(''.join(blocks), 'CONTENTS - CATALOG WEAPONS')
    path.write_text(text)
    print(f'Updated both guides: {len(armaments)} generic and {len(specific)} Zoid-specific equipment costs.')


if __name__ == '__main__':
    refresh()
