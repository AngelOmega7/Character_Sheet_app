from dataclasses import replace
import unittest

from zoids_app.catalog import Catalog
from zoids_app.combat import RuleError, WeaponState, use_weapon
from zoids_app.stats import CharacterBuild, calculate_stats


class EquipmentAbilityTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.catalog = Catalog()

    def calc(self, **kwargs):
        return calculate_stats(CharacterBuild("Saberlion", abilities=("Lion Type 1",), **kwargs), self.catalog)

    def test_retired_families_removed_in_all_ranks(self):
        records = self.catalog.tables["abilities"]["records"]
        retired = {"wimp", "cross_eyed", "slowpoke", "bad_armor"}
        self.assertFalse(any(r.get("family") in retired for r in records))
        for name in ("Wimp", "Cross Eyed 4", "Slowpoke 2", "Bad Armor 3"):
            with self.assertRaises(RuleError):
                self.catalog.find("abilities", name)

    def test_true_tank_bonus_per_defensive_item_all_ranks(self):
        base = CharacterBuild("Saberlion", equipment=("Extension Armor", "Extension Armor", "Thruster", None))
        baseline = calculate_stats(base, self.catalog)
        for rank in range(1, 5):
            name = "True Tank" if rank == 1 else f"True Tank {rank}"
            actual = calculate_stats(replace(base, abilities=(name,)), self.catalog)
            self.assertEqual(actual["current"]["defense"], baseline["current"]["defense"] + 2 * 5 * rank)
        no_defense = calculate_stats(CharacterBuild("Saberlion", abilities=("True Tank",), equipment=("Thruster", None, None, None), equipment_active=(True, False, False, False)), self.catalog)
        self.assertEqual(no_defense["current"]["defense"], 8)

    def test_shield_master_adds_to_combined_pool_not_each_item(self):
        base = CharacterBuild("Saberlion", equipment=("E-Shield Generator", "E-Shield Generator", None, None), equipment_active=(True, True, False, False))
        for rank in range(1, 5):
            name = "Shield Master" if rank == 1 else f"Shield Master {rank}"
            actual = calculate_stats(replace(base, abilities=(None, name)), self.catalog)
            self.assertEqual(actual["shields"], 400 + 25 * rank)
        no_shield = calculate_stats(CharacterBuild("Saberlion", abilities=("Shield Master",), fixed_active=(False, False, True, False)), self.catalog)
        self.assertEqual(no_shield["shields"], 0)
        org = CharacterBuild("Saberlion", organoid_enabled=True, organoid_color="White", organoid_level=5)
        baseline = calculate_stats(org, self.catalog)
        boosted = calculate_stats(replace(org, abilities=("Shield Master",)), self.catalog)
        self.assertEqual(boosted["shields"], baseline["shields"] + 25)

    def test_evasion_adds_armor_per_enabled_reaction_item_all_ranks(self):
        base = CharacterBuild("Saberlion", equipment=("Thruster", "Thruster", None, None), equipment_active=(True, False, False, False))
        baseline = calculate_stats(base, self.catalog)
        for rank in range(1, 5):
            name = "Evasion Master" if rank == 1 else f"Evasion Master {rank}"
            build = replace(base, abilities=(name,))
            actual = calculate_stats(build, self.catalog)
            self.assertEqual(actual["current"]["armor"], baseline["current"]["armor"] + rank)
            both = calculate_stats(replace(build, equipment_active=(True, True, False, False)), self.catalog)
            self.assertEqual(both["current"]["armor"], baseline["current"]["armor"] + 2 * rank)
            self.assertEqual(actual["current"]["reaction"], baseline["current"]["reaction"])

    def test_economized_capacity_and_breakage(self):
        build = CharacterBuild("Saberlion", abilities=("Economized Shooting",), equipment=("Particle Cannon", None, None, None))
        actual = calculate_stats(build, self.catalog)
        weapon = actual["weapons"][4]
        self.assertEqual((weapon["heat_rating"], weapon["maximum_heat"]), (3, 4))
        self.assertIsNone(actual["weapons"][0]["maximum_heat"])
        state = WeaponState(3)
        for _ in range(4):
            state = use_weapon(state, heat_capacity_bonus=weapon["heat_capacity_bonus"]).weapon
            self.assertFalse(state.broken)
        self.assertTrue(use_weapon(state, heat_capacity_bonus=1).weapon.broken)
        self.assertTrue(use_weapon(state, heat_capacity_bonus=0).weapon.broken)
        disabled = calculate_stats(replace(build, abilities=(), inactive_abilities=("Economized Shooting",)), self.catalog)
        self.assertEqual(disabled["weapons"][4]["maximum_heat"], 3)
        self.assertEqual(use_weapon(WeaponState(), heat_capacity_bonus=1).weapon, WeaponState())

    def test_player_managed_abilities_remain_selectable_without_stat_effects(self):
        names = ("Melee Multi Attack", "Smoke Master", "Armor Breaker", "Weapon Breaker 1", "Counter Attack")
        baseline = calculate_stats(CharacterBuild("Saberlion"), self.catalog)
        for name in names:
            self.assertEqual(self.catalog.find("abilities", name)["handling"], "player_managed")
            self.assertEqual(calculate_stats(CharacterBuild("Saberlion", abilities=(name,)), self.catalog), baseline)


if __name__ == "__main__":
    unittest.main()
