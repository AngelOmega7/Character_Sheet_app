from dataclasses import replace
import unittest
from unittest.mock import patch

from zoids_app.catalog import Catalog
from test_support import established_character
from zoids_app.characters import (FixedWeaponCondition, PilotDetails, acquire_equipment, acquire_zoid,
    assign_pilot_ability, equip_owned_equipment, learn_pilot_ability, new_character,
    return_equipment_to_inventory, switch_zoid, validate_character)
from zoids_app.combat import RepairConfirmationRequired, RuleError, WeaponCondition
from zoids_app.combat_controller import attack_preview, combat_snapshot, repair_character_health, start_turn, weapon_action


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

    def test_energy_spent_once_and_unaffordable_use_is_atomic(self):
        character = self.pilot()
        character = self.act(character)
        self.assertEqual(character.current_energy, 8)
        self.assertEqual(self.condition(character), WeaponCondition(False, 10))
        before = character
        with self.assertRaises(RuleError):
            self.act(character)
        self.assertEqual(character, before)
        self.assertEqual(self.roll.call_count, 1)
        character = self.act(replace(character, current_energy=12))
        self.assertEqual(character.current_energy, 0)
        self.assertFalse(self.condition(character).broken)

    def test_condition_follows_copy_but_energy_stays_with_chassis(self):
        character = self.act(self.pilot(2))
        old_id, copy_id = character.active_zoid_id, character.inventory[0].id
        character = return_equipment_to_inventory(character, copy_id, self.catalog)
        character = acquire_zoid(character, "Liger Zero", self.catalog)
        character = switch_zoid(character, character.owned_zoids[-1].id, catalog=self.catalog)
        self.assertEqual(character.current_energy, 18)
        character = equip_owned_equipment(character, "right", copy_id, self.catalog)
        self.assertEqual(self.condition(character, "right").last_roll, 10)
        character = self.act(character, slot="right")
        self.assertEqual(character.current_energy, 6)
        character = switch_zoid(character, old_id, catalog=self.catalog)
        self.assertEqual(character.current_energy, 8)

    def test_forms_share_energy_and_weapon_conditions(self):
        character = acquire_zoid(new_character(), "Berserk Fury", self.catalog)
        character = acquire_zoid(character, "Sturm Fury (CAU)", self.catalog)
        owner = character.owned_zoids[0]
        character = replace(character, current_energy=40)
        character = self.act(character, slot="fixed_2")
        character = switch_zoid(character, owner.id, "zoids:sturm_fury_cau", self.catalog)
        self.assertEqual(character.current_energy, 15)
        self.assertEqual(self.condition(character, "fixed_2").last_roll, 10)
        key = self.catalog.find("zoids", "Berserk Fury")["fixed_weapon_ids"][3]
        owner = replace(character.owned_zoids[0], weapon_conditions=(FixedWeaponCondition(key, WeaponCondition(True)),))
        character = replace(character, owned_zoids=(owner,))
        self.assertTrue(self.condition(character, "fixed_3").broken)
        with self.assertRaises(RuleError):
            self.act(character, slot="fixed_3")

    def test_start_turn_caps_energy_and_preserves_other_resources(self):
        character = self.act(self.pilot(2))
        character = replace(character, current_health=27, gold=123,
                            build=replace(character.build, shield_adjustment=19))
        before = character
        result = start_turn(character, self.catalog).character
        self.assertEqual(result.current_energy, 10)
        self.assertEqual(result.inventory, before.inventory)
        self.assertEqual((result.current_health, result.gold, result.build.shield_adjustment), (27, 123, 19))
        capped = start_turn(replace(result, current_energy=19), self.catalog).character
        self.assertEqual(capped.current_energy, 21)
        self.assertEqual(start_turn(capped, self.catalog).character, capped)

    def test_economized_reduces_spending_demolitionist_is_manual_and_vent_is_rejected(self):
        character = self.pilot()
        baseline = combat_snapshot(character, self.catalog)[0]
        character = learn_pilot_ability(character, "Economized Shooting", self.catalog)
        character = assign_pilot_ability(character, 0, "Economized Shooting", self.catalog)
        character = replace(character, pilot_details=PilotDetails(feats=("Demolitionist",)))
        self.assertEqual(combat_snapshot(character, self.catalog)[0]["weapons"][5]["energy_cost"], 10)
        self.assertEqual(self.act(character).current_energy, 10)
        without_feat = replace(character, pilot_details=PilotDetails())
        self.assertEqual(combat_snapshot(character, self.catalog)[0], combat_snapshot(without_feat, self.catalog)[0])
        with self.assertRaises(RuleError):
            self.act(character, "vent")

    def test_repair_confirmation_and_affordability_are_atomic(self):
        character = replace(self.pilot(), current_health=20, gold=10100)
        character = replace(character, inventory=(replace(character.inventory[0], condition=WeaponCondition(True, 10)),))
        with self.assertRaises(RepairConfirmationRequired):
            self.act(character, "repair")
        with self.assertRaises(RuleError):
            self.act(replace(character, gold=9999), "repair", confirmed=True)
        repaired = self.act(character, "repair", confirmed=True)
        self.assertEqual((repaired.gold, repaired.current_health, repaired.current_energy), (100, 20, 20))
        self.assertEqual(self.condition(repaired), WeaponCondition(False, 10))
        self.assertEqual(self.act(repaired, "repair"), repaired)

    def test_health_repair_preserves_energy_and_roll(self):
        character = self.act(replace(self.pilot(), current_health=120, gold=100))
        repaired = repair_character_health(character, 5, self.catalog)
        self.assertEqual((repaired.character.current_health, repaired.character.gold, repaired.cost), (125, 50, 50))
        self.assertEqual(repaired.character.current_energy, character.current_energy)
        self.assertEqual(self.condition(repaired.character), self.condition(character))

    def test_preview_and_snapshot_never_spend_or_roll(self):
        character = replace(self.pilot(), current_health=27)
        for ability, slot in (("Sniper 4", 0), ("Comeback", 1)):
            character = learn_pilot_ability(character, ability, self.catalog)
            character = assign_pilot_ability(character, slot, ability, self.catalog)
        before = character
        normal = attack_preview(character, "left", range_band="normal", catalog=self.catalog)
        long = attack_preview(character, "left", range_band="long", catalog=self.catalog)
        self.assertEqual(long["to_hit"], normal["to_hit"] + 4)
        self.assertEqual(long["damage"], 78)
        self.assertEqual(character, before)
        self.roll.assert_not_called()

    def test_zero_cost_attack_and_paid_utility(self):
        character = acquire_zoid(new_character(), "Zaber Fang", self.catalog)
        character = self.act(replace(character, current_energy=0), slot="fixed_1")
        self.assertEqual(character.current_energy, 0)
        self.roll.assert_called_once_with(1, 20)
        character = acquire_zoid(new_character(), "Berserk Fury", self.catalog)
        character = self.act(character, slot="fixed_3")
        self.assertEqual(character.current_energy, 15)
        self.assertIsNone(self.condition(character, "fixed_3").last_roll)
        self.assertEqual(self.roll.call_count, 1)

    def test_invalid_current_energy_rejected(self):
        for energy in (-1, True, 1.5, 22):
            with self.assertRaises(RuleError):
                validate_character(replace(self.pilot(), current_energy=energy), self.catalog)
