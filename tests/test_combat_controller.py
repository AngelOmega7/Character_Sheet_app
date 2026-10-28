from dataclasses import replace
import unittest
from unittest.mock import patch

from zoids_app.catalog import Catalog
from test_support import established_character
from zoids_app.characters import (FixedWeaponCondition, PilotDetails, acquire_equipment, acquire_zoid, assign_pilot_ability,
    equip_owned_equipment, learn_pilot_ability, new_character, return_equipment_to_inventory, switch_zoid)
from zoids_app.combat import RepairConfirmationRequired, RuleError, WeaponCondition
from zoids_app.combat_controller import attack_preview, combat_snapshot, repair_character_health, rest_active_loadout, weapon_action


class CombatControllerTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.catalog = Catalog()

    def setUp(self):
        patcher = patch("zoids_app.combat_controller.random.randint", return_value=10)
        self.roll = patcher.start()
        self.addCleanup(patcher.stop)

    def pilot(self, copies=1):
        character = acquire_equipment(established_character(self.catalog), "Particle Cannon", copies, self.catalog)
        return equip_owned_equipment(character, "left", character.inventory[0].id, self.catalog)

    def act(self, character, action="use", slot="left", **kwargs):
        return weapon_action(character, slot, action, catalog=self.catalog, **kwargs).character

    def condition(self, character, slot="left"):
        return combat_snapshot(character, self.catalog)[1][slot]["condition"]

    def test_heat_and_breakage_follow_the_copy_after_transfer(self):
        character = self.pilot(2)
        copy_id = character.inventory[0].id
        for _ in range(4):
            character = self.act(character)
        self.assertEqual(self.condition(character), WeaponCondition(4, True, 10))
        self.assertEqual(character.inventory[1].condition, WeaponCondition())
        before = character
        with self.assertRaises(RuleError):
            self.act(character)
        self.assertEqual(character, before)
        character = return_equipment_to_inventory(character, copy_id, self.catalog)
        character = acquire_zoid(character, "Liger Zero", self.catalog)
        character = switch_zoid(character, character.owned_zoids[-1].id, catalog=self.catalog)
        character = equip_owned_equipment(character, "right", copy_id, self.catalog)
        self.assertEqual(self.condition(character, "right"), WeaponCondition(4, True, 10))
        with self.assertRaises(RuleError):
            self.act(character, slot="right")

    def test_fixed_conditions_follow_shared_weapons_across_cau_forms_and_slots(self):
        character = acquire_zoid(new_character(self.catalog), "Berserk Fury", self.catalog)
        character = acquire_zoid(character, "Sturm Fury (CAU)", self.catalog)
        owner = character.owned_zoids[-1]
        character = switch_zoid(character, owner.id, catalog=self.catalog)
        character = self.act(character, slot="fixed_2")  # Rated 1; first use safe.
        character = switch_zoid(character, owner.id, "zoids:sturm_fury_cau", self.catalog)
        self.assertEqual(self.condition(character, "fixed_2"), WeaponCondition(1, False, 10))
        character = self.act(character, slot="fixed_2")
        character = switch_zoid(character, owner.id, "zoids:berserk_fury", self.catalog)
        self.assertEqual(self.condition(character, "fixed_2"), WeaponCondition(2, True, 10))
        # A shared claw moves from slot 4 to slot 3; condition uses identity, not position.
        owner = character.owned_zoids[-1]
        key = self.catalog.find("zoids", "Berserk Fury")["fixed_weapon_ids"][3]
        owner = replace(owner, weapon_conditions=(*owner.weapon_conditions, FixedWeaponCondition(key, WeaponCondition(0, True))))
        character = replace(character, owned_zoids=(*character.owned_zoids[:-1], owner))
        character = switch_zoid(character, owner.id, "zoids:sturm_fury_cau", self.catalog)
        self.assertTrue(self.condition(character, "fixed_3").broken)

    def test_vent_and_rest_preserve_broken_health_shield_damage_and_gold(self):
        character = self.pilot(2)
        character = replace(character, current_health=27, gold=123,
                            build=replace(character.build, shield_adjustment=19))
        for _ in range(4):
            character = self.act(character)
        character = replace(character, inventory=(character.inventory[0], replace(character.inventory[1], condition=WeaponCondition(2))))
        character = self.act(character, "vent")
        self.assertEqual(self.condition(character), WeaponCondition(3, True, 10))
        rested = rest_active_loadout(character, self.catalog).character
        self.assertEqual(self.condition(rested), WeaponCondition(0, True, 10))
        self.assertEqual(rested.inventory[1].condition.heat, 2)  # Unattached copy is not in this loadout.
        self.assertEqual((rested.current_health, rested.gold, rested.build.shield_adjustment), (27, 123, 19))

    def test_demolitionist_vents_two_from_only_selected_copy_and_clamps_at_zero(self):
        character = self.pilot(2)
        character = equip_owned_equipment(character, "right", character.inventory[1].id, self.catalog)
        for _ in range(4):
            character = self.act(character)
        character = self.act(character, slot="right")
        character = replace(character, pilot_details=PilotDetails(feats=("Demolitionist",)))
        result = weapon_action(character, "left", "vent", catalog=self.catalog)
        self.assertIn("Vented 2 heat", result.message)
        self.assertEqual(self.condition(result.character), WeaponCondition(2, True, 10))
        self.assertEqual(self.condition(result.character, "right"), self.condition(character, "right"))
        cooled = self.act(result.character, "vent", slot="right")
        self.assertEqual(self.condition(cooled, "right").heat, 0)
        without_feat = replace(result.character, pilot_details=PilotDetails())
        self.assertEqual(self.condition(self.act(without_feat, "vent")).heat, 1)

    def test_demolitionist_applies_to_fixed_weapons_without_repairing_them(self):
        character = acquire_zoid(new_character(self.catalog), "Berserk Fury", self.catalog)
        character = switch_zoid(character, character.owned_zoids[-1].id, catalog=self.catalog)
        for _ in range(2):
            character = self.act(character, slot="fixed_2")
        character = replace(character, pilot_details=PilotDetails(feats=("feats:demolitionist",)))
        cooled = self.act(character, "vent", slot="fixed_2")
        self.assertEqual(self.condition(cooled, "fixed_2"), WeaponCondition(0, True, 10))

    def test_rest_does_not_clear_form_specific_weapons_outside_active_loadout(self):
        character = acquire_zoid(new_character(self.catalog), "Liger Zero", self.catalog)
        character = acquire_zoid(character, "Zero Panzer (CAU)", self.catalog)
        owner = character.owned_zoids[-1]
        character = switch_zoid(character, owner.id, "zoids:zero_panzer_cau", self.catalog)
        character = self.act(character, slot="fixed_2")
        character = switch_zoid(character, owner.id, "zoids:liger_zero", self.catalog)
        character = rest_active_loadout(character, self.catalog).character
        character = switch_zoid(character, owner.id, "zoids:zero_panzer_cau", self.catalog)
        self.assertEqual(self.condition(character, "fixed_2").heat, 1)

    def test_repair_confirmation_and_affordability_are_atomic(self):
        character = replace(self.pilot(), current_health=20, gold=10100)
        for _ in range(4):
            character = self.act(character)
        with self.assertRaises(RepairConfirmationRequired):
            self.act(character, "repair")
        self.assertEqual((character.gold, self.condition(character).broken), (10100, True))
        with self.assertRaises(RuleError):
            self.act(replace(character, gold=9999), "repair", confirmed=True)
        repaired = self.act(character, "repair", confirmed=True)
        self.assertEqual((repaired.gold, repaired.current_health), (100, 20))
        self.assertEqual(self.condition(repaired), WeaponCondition(0, False, 10))
        used = self.act(repaired)
        self.assertEqual(self.condition(self.act(used, "repair")), WeaponCondition(1, False, 10))
        self.assertEqual(self.act(used, "repair").gold, 100)

    def test_health_repair_uses_latest_maximum_and_does_not_cool_weapons(self):
        character = self.pilot()
        character = replace(character, current_health=120, gold=100,
                            build=replace(character.build, shield_adjustment=9))
        character = self.act(character)
        repaired = repair_character_health(character, 5, self.catalog)
        self.assertEqual((repaired.character.current_health, repaired.character.gold, repaired.cost), (125, 50, 50))
        self.assertEqual(self.condition(repaired.character).heat, 1)
        self.assertEqual(repaired.character.build.shield_adjustment, 9)
        with self.assertRaises(RuleError):
            repair_character_health(repaired.character, catalog=self.catalog)
        boosted = replace(repaired.character, gold=100000,
            build=replace(repaired.character.build, organoid_enabled=True, organoid_color="White", organoid_level=40))
        maximum = combat_snapshot(boosted, self.catalog)[0]["pilot"]["health"]
        full = repair_character_health(boosted, catalog=self.catalog)
        self.assertEqual(full.character.current_health, maximum)
        self.assertEqual(full.cost, (maximum - 125) * 10)
        self.assertEqual(self.condition(full.character).heat, 1)

    def test_attack_previews_apply_context_without_heat_or_resource_changes(self):
        character = replace(self.pilot(), current_health=27)
        for ability, slot in (("Sniper 4", 0), ("Comeback", 1)):
            character = learn_pilot_ability(character, ability, self.catalog)
            character = assign_pilot_ability(character, slot, ability, self.catalog)
        before = character
        maximum_range = combat_snapshot(character, self.catalog)[0]["current"]["range"]
        normal = attack_preview(character, "left", distance=maximum_range / 2, catalog=self.catalog)
        long = attack_preview(character, "left", distance=maximum_range / 2 + 1, catalog=self.catalog)
        self.assertEqual(long["to_hit"], normal["to_hit"] + 4)
        self.assertEqual(long["damage"], 78)
        self.assertEqual(attack_preview(replace(character, current_health=28), "left", range_band="normal", catalog=self.catalog)["damage"], 65)
        self.assertEqual(character, before)
        self.assertEqual(self.condition(character), WeaponCondition())

    def test_economized_activation_changes_capacity_without_resetting_heat(self):
        character = self.pilot()
        for _ in range(3):
            character = self.act(character)
        character = learn_pilot_ability(character, "Economized Shooting", self.catalog)
        character = assign_pilot_ability(character, 0, "Economized Shooting", self.catalog)
        character = self.act(character)
        self.assertEqual(self.condition(character), WeaponCondition(4, False, 10))
        character = assign_pilot_ability(character, 0, catalog=self.catalog)
        self.assertEqual(self.condition(character), WeaponCondition(4, False, 10))
        character = self.act(character)
        self.assertEqual(self.condition(character), WeaponCondition(5, True, 10))

    def test_unrated_use_rolls_once_and_other_actions_keep_the_result(self):
        character = self.pilot()
        self.roll.side_effect = [1, 20]
        character = self.act(character, slot="fixed_1")
        self.assertEqual(self.condition(character, "fixed_1"), WeaponCondition(0, False, 1))
        character = self.act(character, slot="fixed_1")
        self.assertEqual(self.condition(character, "fixed_1"), WeaponCondition(0, False, 20))
        character = self.act(character, "vent", "fixed_1")
        character = self.act(character, "repair", "fixed_1")
        character = rest_active_loadout(character, self.catalog).character
        attack_preview(character, "fixed_1", catalog=self.catalog)
        combat_snapshot(character, self.catalog)
        self.assertEqual(self.condition(character, "fixed_1").last_roll, 20)
        self.assertIsNone(self.condition(character).last_roll)
        self.assertEqual(self.roll.call_count, 2)
        self.assertEqual(self.roll.call_args_list, [unittest.mock.call(1, 20)] * 2)
        for invalid in (0, 21, -1, True, 1.5, "20"):
            with self.assertRaises(RuleError):
                WeaponCondition(last_roll=invalid)

    def test_overheating_final_use_rolls_but_rejected_use_does_not(self):
        character = self.pilot()
        for _ in range(3):
            character = self.act(character)
        self.roll.return_value = 20
        character = self.act(character)
        self.assertEqual(self.condition(character), WeaponCondition(4, True, 20))
        self.assertEqual(self.roll.call_count, 4)
        before = character
        with self.assertRaises(RuleError):
            self.act(character)
        with self.assertRaises(RuleError):
            self.act(character, slot="back")
        self.assertEqual(character, before)
        self.assertEqual(self.roll.call_count, 4)
