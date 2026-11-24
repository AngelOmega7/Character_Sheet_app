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

    def test_true_tank_uses_combined_removable_defense_all_ranks(self):
        base = CharacterBuild("Saberlion", equipment=("Extension Armor", "Extension Armor", "Thruster", None))
        baseline = calculate_stats(base, self.catalog)
        for rank in range(1, 5):
            name = "True Tank" if rank == 1 else f"True Tank {rank}"
            actual = calculate_stats(replace(base, abilities=(name,)), self.catalog)
            self.assertEqual(actual["current"]["defense"], baseline["current"]["defense"])
            self.assertEqual(actual["current"]["armor"], baseline["current"]["armor"] + 1)
        no_defense = calculate_stats(CharacterBuild("Saberlion", abilities=("True Tank",), equipment=("Thruster", None, None, None), equipment_active=(True, False, False, False)), self.catalog)
        self.assertEqual(no_defense["current"]["defense"], 8)

    def test_true_tank_rounding_caps_and_activation(self):
        catalog = Catalog()
        item = catalog.find("armaments", "Extension Armor")
        defense_key = catalog.tables["armaments"]["columns"][5]
        base = CharacterBuild("Saberlion", equipment=("Extension Armor", None, None, None), defense_up=100)
        for defense, expected in ((9, 0), (19, 1), (250, None)):
            item["fields"][defense_key] = defense
            baseline = calculate_stats(base, catalog)
            for rank in range(1, 5):
                name = "True Tank" if rank == 1 else f"True Tank {rank}"
                actual = calculate_stats(replace(base, abilities=(name,)), catalog)
                self.assertEqual(actual["current"]["armor"] - baseline["current"]["armor"],
                                 5 * rank if expected is None else expected)
                self.assertEqual(actual["current"]["defense"], baseline["current"]["defense"])
                self.assertEqual(calculate_stats(replace(base, inactive_abilities=(name,)), catalog), baseline)
        catalog.find("armaments", "Thruster")["fields"]["defense"] = 20
        base = CharacterBuild("Saberlion", equipment=("Thruster", None, None, None), abilities=("True Tank",))
        inactive = calculate_stats(base, catalog)
        active = calculate_stats(replace(base, equipment_active=(True, False, False, False)), catalog)
        self.assertEqual(active["current"]["armor"], inactive["current"]["armor"] + 2)

    def test_iron_defense_all_ranks(self):
        base = CharacterBuild("Saberlion")
        baseline = calculate_stats(base, self.catalog)["current"]["defense"]
        for rank in range(1, 5):
            name = "Iron Defense" if rank == 1 else f"Iron Defense {rank}"
            actual = calculate_stats(replace(base, abilities=(name,)), self.catalog)
            self.assertEqual(actual["current"]["defense"], baseline + 10 * rank)

    def test_shield_master_adds_to_combined_pool_not_each_item(self):
        base = CharacterBuild("Saberlion", equipment=("E-Shield Generator", "E-Shield Generator", None, None), equipment_active=(True, True, False, False))
        for rank in range(1, 5):
            name = "Shield Master" if rank == 1 else f"Shield Master {rank}"
            actual = calculate_stats(replace(base, abilities=(None, name)), self.catalog)
            self.assertEqual(actual["shields"], 400 + (100, 150, 200, 250)[rank - 1])
        no_shield = calculate_stats(CharacterBuild("Saberlion", abilities=("Shield Master",), fixed_active=(False, False, True, False)), self.catalog)
        self.assertEqual(no_shield["shields"], 0)
        org = CharacterBuild("Saberlion", organoid_enabled=True, organoid_color="White", organoid_level=5)
        baseline = calculate_stats(org, self.catalog)
        boosted = calculate_stats(replace(org, abilities=("Shield Master",)), self.catalog)
        self.assertEqual(boosted["shields"], baseline["shields"] + 100)

    def test_evasion_is_player_managed_without_armor_or_reaction_bonus(self):
        base = CharacterBuild("Saberlion", equipment=("Thruster", "Thruster", None, None), equipment_active=(True, False, False, False))
        baseline = calculate_stats(base, self.catalog)
        for rank in range(1, 5):
            name = "Evasion Master" if rank == 1 else f"Evasion Master {rank}"
            build = replace(base, abilities=(name,))
            actual = calculate_stats(build, self.catalog)
            self.assertEqual(actual, baseline)
            record = self.catalog.find("abilities", name)
            self.assertEqual(record["handling"], "player_managed")
            self.assertEqual(record["fields"]["description"],
                f"Attacks that would be made against your Reaction have a minus {4 * rank} penalty to hit you.")
            both = calculate_stats(replace(build, equipment_active=(True, True, False, False)), self.catalog)
            self.assertEqual(both, calculate_stats(replace(base, equipment_active=(True, True, False, False)), self.catalog))
            self.assertEqual(actual["current"]["reaction"], baseline["current"]["reaction"])

    def test_economized_active_rank_one_reduces_energy_cost(self):
        build = CharacterBuild("Saberlion", abilities=("Economized Shooting",), equipment=("Particle Cannon", None, None, None))
        actual = calculate_stats(build, self.catalog)
        disabled = calculate_stats(replace(build, abilities=(), inactive_abilities=("Economized Shooting",)), self.catalog)
        self.assertEqual(actual["weapons"][4]["energy_cost"], 10)
        self.assertEqual(disabled["weapons"][4]["energy_cost"], 12)
        self.assertEqual(actual["weapons"][0], disabled["weapons"][0])

    def test_player_managed_abilities_remain_selectable_without_stat_effects(self):
        names = ("Melee Multi Attack", "Smoke Master", "Armor Breaker", "Weapon Breaker 1", "Counter Attack")
        baseline = calculate_stats(CharacterBuild("Saberlion"), self.catalog)
        for name in names:
            self.assertEqual(self.catalog.find("abilities", name)["handling"], "player_managed")
            self.assertEqual(calculate_stats(CharacterBuild("Saberlion", abilities=(name,)), self.catalog), baseline)


if __name__ == "__main__":
    unittest.main()
