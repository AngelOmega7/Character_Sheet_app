from dataclasses import asdict, replace
import json
from pathlib import Path
import tempfile
import unittest

from zoids_app.catalog import Catalog
from zoids_app.characters import (FixedWeaponCondition, acquire_equipment, acquire_zoid,
    equip_owned_equipment, new_character, switch_zoid, validate_character)
from zoids_app.combat import RuleError, WeaponCondition
from zoids_app.combat_controller import combat_snapshot, weapon_action
from zoids_app.equipment import eligible_equipment
from zoids_app.storage import CharacterStore


class RestoredWeaponTests(unittest.TestCase):
    def setUp(self):
        self.catalog = Catalog()
        self.records = [r for r in self.catalog.tables["zoids"]["records"] if r.get("removable_weapon_restore")]

    def acquire(self, record, catalog):
        c = acquire_zoid(new_character(), record["ownership_base_id"], catalog)
        if record["id"] != record["ownership_base_id"]:
            c = acquire_zoid(c, record["id"], catalog)
            c = switch_zoid(c, c.active_zoid_id, record["id"], catalog)
        return c

    def old_catalog(self):
        catalog = Catalog()
        columns = catalog.tables["zoids"]["columns"]
        for record in catalog.tables["zoids"]["records"]:
            move = record.pop("removable_weapon_restore", None)
            if not move:
                continue
            index = move["fixed_slot"] - 1
            start = (13, 19, 30, 41)[index]
            for source, target in zip((47, 48, 49, 50, 51), range(start, start + 5)):
                record["fields"][columns[target - 1]] = record["fields"][columns[source - 1]]
                record["fields"][columns[source - 1]] = None
            record["fields"][columns[51]] = None
            record["fixed_weapon_ids"][index] = move["fixed_weapon_id"]
            record["energy_costs"][index] = record["energy_costs"][4]
            record["energy_costs"][4] = None
            record["zoid_equipment_mounts"].pop(move["template"])
        return catalog

    def test_new_acquisitions_equip_slot_five_and_weapon_is_removable(self):
        self.assertEqual(len(self.records), 4)
        for record in self.records:
            with self.subTest(zoid=record["name"]):
                c = self.acquire(record, self.catalog)
                move = record["removable_weapon_restore"]
                stats, weapons = combat_snapshot(c, self.catalog)
                self.assertEqual(c.build.equipment[0], move["template"])
                self.assertEqual(stats["weapons"][4]["energy_cost"], record["energy_costs"][4])
                self.assertFalse(stats["weapons"][move["fixed_slot"] - 1]["name"])
                item = self.catalog.find("armaments", move["template"])
                self.assertIn(item, eligible_equipment(record["id"], "back", self.catalog))
                for slot in ("left", "right", "chest"):
                    self.assertNotIn(item, eligible_equipment(record["id"], slot, self.catalog))
                c = equip_owned_equipment(c, "back", None, self.catalog)
                with self.assertRaises(RuleError):
                    weapon_action(c, "back", "use", catalog=self.catalog)

    def test_v15_migration_preserves_condition_resources_and_displaced_equipment(self):
        old_catalog = self.old_catalog()
        for record in self.records:
            with self.subTest(zoid=record["name"]), tempfile.TemporaryDirectory() as directory:
                c = self.acquire(record, old_catalog)
                c = acquire_equipment(c, "Particle Cannon", catalog=old_catalog)
                displaced = c.inventory[-1]
                c = equip_owned_equipment(c, "back", displaced.id, old_catalog)
                move = record["removable_weapon_restore"]
                flags = [False] * 4
                flags[move["fixed_slot"] - 1] = True
                owner = c.owned_zoids[0]
                owner = replace(owner, weapon_conditions=(*owner.weapon_conditions,
                    FixedWeaponCondition(move["fixed_weapon_id"], WeaponCondition(True, 17))))
                c = validate_character(replace(c, current_health=19, current_energy=7,
                    build=replace(c.build, fixed_active=tuple(flags)), owned_zoids=(owner,)), old_catalog)
                store = CharacterStore(Path(directory) / "save.db", self.catalog)
                result = store.import_character(json.dumps({"save_version": 15, "character": asdict(c)}))
                active = next(f for f in result.owned_zoids[0].forms if f.zoid == result.build.zoid)
                item = next(i for i in result.inventory if i.id == active.equipment_ids[0])
                self.assertEqual(item.armament, move["template"])
                self.assertEqual(item.condition, WeaponCondition(True, 17))
                self.assertTrue(result.build.equipment_active[0])
                self.assertFalse(result.build.fixed_active[move["fixed_slot"] - 1])
                self.assertIn(displaced, result.inventory)
                self.assertNotIn(displaced.id, active.equipment_ids)
                self.assertEqual((result.current_health, result.current_energy), (19, 7))
                self.assertNotIn(move["fixed_weapon_id"], [w.weapon_id for w in result.owned_zoids[0].weapon_conditions])
                self.assertEqual(store.load(result.id), result)
