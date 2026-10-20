from dataclasses import replace
import unittest

from zoids_app.catalog import Catalog
from zoids_app.characters import (OwnedEquipment, acquire_equipment, acquire_zoid, available_equipment,
    equip_owned_equipment, equipment_assignments, new_character, restore_roster_selection,
    return_equipment_to_inventory, switch_zoid, validate_character)
from zoids_app.combat import RuleError
from zoids_app.stats import calculate_stats
from test_support import established_character as new_character


class InventoryTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.catalog = Catalog()

    def pilot(self, item="Particle Cannon", quantity=1):
        return acquire_equipment(new_character(self.catalog), item, quantity, self.catalog)

    def equip(self, character, slot, copy_id=None):
        return equip_owned_equipment(character, slot, copy_id, self.catalog)

    def test_duplicate_types_are_distinct_owned_copies_and_invalid_acquisitions_fail(self):
        character = self.pilot(quantity=3)
        self.assertEqual(len({i.id for i in character.inventory}), 3)
        self.assertEqual({i.armament for i in character.inventory}, {"armaments:particle_cannon"})
        self.assertEqual(character.build.equipment, (None,) * 4)
        for quantity in (0, -1, True, 1.5):
            with self.assertRaises(RuleError):
                acquire_equipment(character, "Particle Cannon", quantity, self.catalog)
        for item in ("WEAPONS", "ASSIST", "unknown"):
            with self.assertRaises(RuleError):
                acquire_equipment(character, item, catalog=self.catalog)

    def test_only_available_owned_compatible_copies_can_be_attached(self):
        character = self.pilot(quantity=2)
        first, second = character.inventory
        character = self.equip(character, "left", first.id)
        self.assertNotIn(first, available_equipment(character, "right", self.catalog))
        self.assertIn(first, available_equipment(character, "left", self.catalog))
        for slot, item_id in (("right", first.id), ("back", second.id), ("right", "armaments:particle_cannon"), ("right", "unowned")):
            with self.assertRaises(RuleError):
                self.equip(character, slot, item_id)
        character = self.equip(character, "right", second.id)
        self.assertEqual(calculate_stats(character.build, self.catalog)["carry_load"], 40)
        self.assertEqual(len(character.inventory), 2)

    def test_unequipping_preserves_the_copy_and_resets_only_its_activation(self):
        character = self.pilot("E-Shield Generator")
        copy_id = character.inventory[0].id
        character = self.equip(character, "back", copy_id)
        character = replace(character, current_health=27, gold=300,
            build=replace(character.build, equipment_active=(True, False, False, False)))
        self.assertEqual(calculate_stats(character.build, self.catalog)["shields"], 200)
        # Selecting the same physical copy should not turn it off.
        self.assertTrue(self.equip(character, "back", copy_id).build.equipment_active[0])
        character = self.equip(character, "back")
        self.assertEqual(character.inventory[0].id, copy_id)
        self.assertEqual(equipment_assignments(character), {})
        self.assertFalse(character.build.equipment_active[0])
        self.assertEqual(calculate_stats(character.build, self.catalog)["shields"], 0)
        self.assertEqual((character.current_health, character.gold), (27, 300))

    def cau_pilot(self):
        character = acquire_zoid(self.pilot(), "Liger Zero", self.catalog)
        character = acquire_zoid(character, "Zero Jager (CAU)", self.catalog)
        liger = character.owned_zoids[-1].id
        character = switch_zoid(character, liger, catalog=self.catalog)
        copy_id = character.inventory[0].id
        character = self.equip(character, "left", copy_id)
        character = switch_zoid(character, liger, "zoids:zero_jager_cau", self.catalog)
        character = self.equip(character, "right", copy_id)
        return character, copy_id

    def test_cau_forms_reuse_a_copy_but_other_owned_zoids_cannot(self):
        character, copy_id = self.cau_pilot()
        self.assertEqual(len(equipment_assignments(character)[copy_id]), 2)
        self.assertEqual(len(character.inventory), 1)
        # Unequipping this form leaves the copy assigned through the base form.
        character = self.equip(character, "right")
        self.assertEqual(len(equipment_assignments(character)[copy_id]), 1)
        character = switch_zoid(character, character.owned_zoids[0].id, catalog=self.catalog)
        self.assertFalse(available_equipment(character, "left", self.catalog))
        with self.assertRaises(RuleError):
            self.equip(character, "left", copy_id)

    def test_return_to_inventory_clears_all_forms_and_allows_transfer(self):
        character, copy_id = self.cau_pilot()
        character = acquire_equipment(character, "Extension Armor", catalog=self.catalog)
        other = character.inventory[-1].id
        character = self.equip(character, "chest", other)
        character = replace(character, current_health=18, gold=123)
        returned = return_equipment_to_inventory(character, copy_id, self.catalog)
        self.assertEqual(returned.inventory, character.inventory)
        self.assertNotIn(copy_id, equipment_assignments(returned))
        self.assertIn(other, equipment_assignments(returned))
        self.assertEqual((returned.current_health, returned.gold), (18, 123))
        returned = switch_zoid(returned, returned.owned_zoids[0].id, catalog=self.catalog)
        returned = self.equip(returned, "left", copy_id)
        self.assertEqual(len(equipment_assignments(returned)[copy_id]), 1)

    def test_forged_builds_missing_copies_and_duplicate_inventory_ids_are_rejected(self):
        character = self.pilot()
        with self.assertRaises(RuleError):
            validate_character(replace(character, build=replace(character.build,
                equipment=(None, "Particle Cannon", None, None))), self.catalog)
        with self.assertRaises(RuleError):
            validate_character(replace(character, inventory=character.inventory * 2), self.catalog)
        equipped = self.equip(character, "left", character.inventory[0].id)
        with self.assertRaises(RuleError):
            validate_character(replace(equipped, inventory=()), self.catalog)
        with self.assertRaises(RuleError):
            validate_character(replace(equipped, inventory=(OwnedEquipment(character.inventory[0].id, "Extension Armor"),)), self.catalog)

    def test_dynamic_equipment_copies_still_resolve_against_selected_zoid(self):
        character = acquire_zoid(self.pilot("Zoid equipment slot 1"), "Zaber Fang", self.catalog)
        character = switch_zoid(character, character.owned_zoids[-1].id, catalog=self.catalog)
        character = self.equip(character, "left", character.inventory[0].id)
        weapon = calculate_stats(character.build, self.catalog)["weapons"][5]
        self.assertEqual(weapon["base_damage"], 120)
        self.assertTrue(weapon["name"])

    def test_empty_roster_can_keep_inventory_until_a_zoid_is_obtained(self):
        character = restore_roster_selection(replace(new_character(self.catalog), owned_zoids=()), self.catalog)
        character = acquire_equipment(character, "Particle Cannon", 2, self.catalog)
        self.assertFalse(available_equipment(character, "left", self.catalog))
        with self.assertRaises(RuleError):
            self.equip(character, "left", character.inventory[0].id)
        character = acquire_zoid(character, "Saberlion", self.catalog)
        self.assertEqual(len(available_equipment(character, "left", self.catalog)), 2)

    def test_inventory_copies_are_pilot_specific(self):
        first, second = self.pilot(), self.pilot()
        self.assertNotEqual(first.inventory[0].id, second.inventory[0].id)
        with self.assertRaises(RuleError):
            self.equip(first, "left", second.inventory[0].id)
