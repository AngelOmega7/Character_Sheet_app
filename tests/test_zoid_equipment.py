from dataclasses import asdict
import json
from pathlib import Path
import tempfile
import unittest

from tools.audit_zoid_equipment import equipment_audit
from zoids_app.catalog import Catalog
from zoids_app.characters import (acquire_equipment, acquire_zoid, available_equipment,
                                  delete_equipment, equip_owned_equipment, new_character,
                                  return_equipment_to_inventory, switch_zoid)
from zoids_app.commerce import purchase_zoid, quote_purchase
from zoids_app.combat import RuleError
from zoids_app.combat_controller import weapon_action
from zoids_app.equipment import SLOT_COLUMNS, eligible_equipment
from zoids_app.stats import calculate_stats
from zoids_app.storage import CharacterStore


class ZoidEquipmentTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.catalog = Catalog()

    def pilot(self, name):
        record = self.catalog.find("zoids", name)
        character = acquire_zoid(new_character(), record["ownership_base_id"], self.catalog)
        if record["id"] != record["ownership_base_id"]:
            character = acquire_zoid(character, record["id"], self.catalog)
            character = switch_zoid(character, character.active_zoid_id, record["id"], self.catalog)
        # Mount-placement and legacy-save tests construct their own inventory.
        for item in character.inventory:
            character = return_equipment_to_inventory(character, item.id, self.catalog)
            character = delete_equipment(character, item.id, self.catalog)
        return character

    def test_starter_purchase_grants_and_equips_cannon_and_persists(self):
        for name in ("Command Wolf", "Zaber Fang Old"):
            with self.subTest(name=name):
                pilot = new_character()
                quote = quote_purchase(pilot, name, starter=True, catalog=self.catalog)
                pilot = purchase_zoid(pilot, quote, catalog=self.catalog)
                self.assertEqual(len(pilot.inventory), 1)
                cannon = pilot.inventory[0]
                self.assertEqual(pilot.build.equipment, (cannon.armament, None, None, None))
                self.assertEqual(pilot.owned_zoids[0].forms[0].equipment_ids, (cannon.id, None, None, None))
                with tempfile.TemporaryDirectory() as directory:
                    store = CharacterStore(Path(directory) / "save.db", self.catalog)
                    self.assertEqual(store.load(store.save(pilot).id), pilot)

    def test_later_acquisitions_get_distinct_copies_without_changing_active_loadout(self):
        pilot = acquire_zoid(new_character(), "Command Wolf", self.catalog)
        original = pilot.owned_zoids[0]
        for _ in range(2):
            pilot = acquire_zoid(pilot, "Great Zaber", self.catalog)
            self.assertEqual(pilot.owned_zoids[0], original)
            self.assertEqual(pilot.active_zoid_id, original.id)
            form = pilot.owned_zoids[-1].forms[0]
            self.assertEqual(form.equipment, ("armaments:zoid_equipment_slot_1", "armaments:zoid_equipment_slot_2", None, None))
            self.assertEqual(form.equipment_ids[:2], tuple(i.id for i in pilot.inventory[-2:]))
        self.assertEqual(len({i.id for i in pilot.inventory}), 5)

    def test_later_purchase_equips_both_great_zaber_weapons(self):
        pilot = new_character()
        pilot = purchase_zoid(pilot, quote_purchase(pilot, "Command Wolf", starter=True, catalog=self.catalog), catalog=self.catalog)
        quote = quote_purchase(pilot, "Great Zaber", catalog=self.catalog)
        pilot = purchase_zoid(pilot, quote, override=True, catalog=self.catalog)
        self.assertEqual(pilot.build.zoid, "zoids:great_zaber")
        self.assertEqual(pilot.build.equipment, ("armaments:zoid_equipment_slot_1", "armaments:zoid_equipment_slot_2", None, None))
        self.assertEqual(len(pilot.inventory), 3)

    def test_cau_grants_utility_and_switching_does_not_grant_it_again(self):
        pilot = acquire_zoid(new_character(), "Liger Zero", self.catalog)
        pilot = acquire_zoid(pilot, "Zero X (CAU)", self.catalog)
        self.assertEqual(len(pilot.inventory), 1)
        form = pilot.owned_zoids[0].forms[-1]
        self.assertEqual(form.equipment_ids, (pilot.inventory[0].id, None, None, None))
        pilot = switch_zoid(pilot, pilot.active_zoid_id, form.zoid, self.catalog)
        self.assertEqual(pilot.build.equipment, form.equipment)
        pilot = switch_zoid(pilot, pilot.active_zoid_id, "zoids:liger_zero", self.catalog)
        pilot = switch_zoid(pilot, pilot.active_zoid_id, form.zoid, self.catalog)
        self.assertEqual(len(pilot.inventory), 1)
        with self.assertRaises(RuleError):
            acquire_zoid(pilot, form.zoid, self.catalog)

    def acquire(self, character, template):
        return acquire_equipment(character, f"armaments:zoid_equipment_slot_{template}", catalog=self.catalog)

    def test_named_cost_entries_and_simultaneous_mount_audit(self):
        result = equipment_audit(self.catalog)
        self.assertFalse(result["missing_cost_items"])
        self.assertFalse(result["unknown_zoids"])
        self.assertEqual(len(result["designs"]), 12)
        self.assertEqual(sum(len(d["items"]) for d in result["designs"]), 13)
        for design in result["designs"]:
            self.assertTrue(design["assignments"], design["name"])
        self.assertEqual([d["name"] for d in result["designs"] if len(d["items"]) > 1], ["Great Zaber"])

    def test_all_zoid_specific_utilities_fit_slots_five_through_eight(self):
        cases = (("Diablo Tiger", 4, 15, 3), ("Zero X (CAU)", 1, 10, 3),
                 ("Shadow Fox", 4, 5, 3), ("Mad Thunder", 4, 30, 2))
        for name, template, weight, cost in cases:
            pilot = self.acquire(self.pilot(name), template)
            item = pilot.inventory[-1]
            baseline = calculate_stats(pilot.build, self.catalog)
            for index, slot in enumerate(SLOT_COLUMNS):
                with self.subTest(zoid=name, slot=index + 5):
                    self.assertIn(item, available_equipment(pilot, slot, self.catalog))
                    mounted = equip_owned_equipment(pilot, slot, item.id, self.catalog)
                    stats = calculate_stats(mounted.build, self.catalog)
                    weapon = stats["weapons"][index + 4]
                    self.assertIsNotNone(weapon["name"])
                    self.assertIsNotNone(weapon["effect"])
                    self.assertEqual(weapon["energy_cost"], cost)
                    self.assertEqual(stats["carry_load"], weight)
                    if name == "Mad Thunder":
                        self.assertEqual(stats["current"]["defense"], baseline["current"]["defense"] + 200)
                    used = weapon_action(mounted, slot, "use", catalog=self.catalog).character
                    self.assertEqual(used.current_energy, mounted.current_energy - cost)
                    self.assertIsNone(used.inventory[-1].condition.last_roll)

    def test_konig_missiles_mount_on_either_arm_but_not_assist_only_slots(self):
        pilot = self.acquire(self.pilot("Konig Wolf DSR (CAU)"), 2)
        item = pilot.inventory[-1]
        for slot in ("back", "chest"):
            self.assertNotIn(item, available_equipment(pilot, slot, self.catalog))
            with self.assertRaises(RuleError):
                equip_owned_equipment(pilot, slot, item.id, self.catalog)
        for index, slot in ((5, "left"), (6, "right")):
            mounted = equip_owned_equipment(pilot, slot, item.id, self.catalog)
            stats = calculate_stats(mounted.build, self.catalog)
            self.assertIn("Dual Sniper Rifle", stats["weapons"][1]["name"])
            missiles = stats["weapons"][index]
            self.assertIn("5-Shot Missile Pod", missiles["name"])
            self.assertEqual((missiles["base_damage"], missiles["energy_cost"]), (120, 10))
            self.assertEqual(stats["carry_load"], 18)
            with tempfile.TemporaryDirectory() as directory:
                store = CharacterStore(Path(directory) / "save.db", self.catalog)
                self.assertEqual(store.load(store.save(mounted).id), mounted)

    def test_great_zaber_both_weapons_mount_simultaneously_with_distinct_stats(self):
        pilot = self.acquire(self.acquire(self.pilot("Great Zaber"), 1), 2)
        cannon, rifle = pilot.inventory
        for cannon_slot, rifle_slot in (("back", "left"), ("right", "left")):
            with self.subTest(cannon=cannon_slot, rifle=rifle_slot):
                mounted = equip_owned_equipment(pilot, cannon_slot, cannon.id, self.catalog)
                mounted = equip_owned_equipment(mounted, rifle_slot, rifle.id, self.catalog)
                stats = calculate_stats(mounted.build, self.catalog)
                weapons = {w["slot"]: w for w in stats["weapons"]}
                self.assertIn("Double Beam Cannon", weapons[cannon_slot]["name"])
                self.assertIn("20mm Solid Rifle", weapons[rifle_slot]["name"])
                self.assertEqual((weapons[cannon_slot]["energy_cost"], weapons[rifle_slot]["energy_cost"]), (7, 6))
                self.assertEqual((weapons[cannon_slot]["base_damage"], weapons[rifle_slot]["base_damage"]), (200, 200))
                self.assertEqual(stats["carry_load"], 32)
                used = weapon_action(mounted, cannon_slot, "use", catalog=self.catalog).character
                used = weapon_action(used, rifle_slot, "use", catalog=self.catalog).character
                self.assertEqual(used.current_energy, mounted.current_energy - 13)
                with tempfile.TemporaryDirectory() as directory:
                    store = CharacterStore(Path(directory) / "save.db", self.catalog)
                    loaded = store.load(store.save(used).id)
                    self.assertEqual(loaded, used)
                    self.assertEqual(calculate_stats(loaded.build, self.catalog), stats)
        for slot in ("back", "right", "chest"):
            with self.assertRaises(RuleError):
                equip_owned_equipment(pilot, slot, rifle.id, self.catalog)

    def test_source_template_classification_depends_on_selected_zoid(self):
        template = self.catalog.find("armaments", "armaments:zoid_equipment_slot_1")
        self.assertIn(template, eligible_equipment("Zero X (CAU)", "chest", self.catalog))
        self.assertNotIn(template, eligible_equipment("Zaber Fang", "chest", self.catalog))
        self.assertNotIn(template, eligible_equipment("Saberlion", "chest", self.catalog))

    def test_old_save_moves_rifle_to_slot_six_preserving_other_copy_and_energy(self):
        pilot = self.acquire(self.acquire(self.pilot("Great Zaber"), 1), 2)
        cannon, rifle = pilot.inventory
        pilot = equip_owned_equipment(pilot, "back", cannon.id, self.catalog)
        pilot = equip_owned_equipment(pilot, "left", rifle.id, self.catalog)
        values = asdict(pilot)
        # Simulate a schema-12 save with rifle in slot 5 and cannon in slot 6.
        for fields in (values["build"], values["owned_zoids"][0]["forms"][0]):
            fields["equipment"] = [rifle.armament, cannon.armament, None, None]
            fields["equipment_active"] = [True, False, False, False]
        values["owned_zoids"][0]["forms"][0]["equipment_ids"] = [rifle.id, cannon.id, None, None]
        with tempfile.TemporaryDirectory() as directory:
            store = CharacterStore(Path(directory) / "save.db", self.catalog)
            loaded = store.import_character(json.dumps({"save_version": 12, "character": values}))
            self.assertEqual(loaded.build.equipment, pilot.build.equipment)
            self.assertEqual(loaded.build.equipment_active, (False, True, False, False))
            self.assertEqual(loaded.inventory, pilot.inventory)
            self.assertEqual(loaded.current_energy, pilot.current_energy)
            self.assertEqual(store.load(loaded.id), loaded)

    def test_old_extra_rifle_copy_returns_to_inventory(self):
        pilot = self.acquire(self.acquire(self.pilot("Great Zaber"), 2), 2)
        first, second = pilot.inventory
        pilot = equip_owned_equipment(pilot, "left", first.id, self.catalog)
        values = asdict(pilot)
        for fields in (values["build"], values["owned_zoids"][0]["forms"][0]):
            fields["equipment"] = [second.armament, first.armament, None, None]
        values["owned_zoids"][0]["forms"][0]["equipment_ids"] = [second.id, first.id, None, None]
        with tempfile.TemporaryDirectory() as directory:
            store = CharacterStore(Path(directory) / "save.db", self.catalog)
            loaded = store.import_character(json.dumps({"save_version": 12, "character": values}))
            self.assertEqual(loaded.build.equipment, pilot.build.equipment)
            self.assertEqual(loaded.inventory, pilot.inventory)
            self.assertEqual(loaded.owned_zoids[0].forms[0].equipment_ids, (None, first.id, None, None))
