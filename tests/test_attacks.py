from dataclasses import replace
from decimal import Decimal
import unittest

from zoids_app.attacks import calculate_attack, range_band_for_distance
from zoids_app.catalog import Catalog
from zoids_app.combat import RuleError
from zoids_app.stats import CharacterBuild, Upgrades, calculate_stats


class ConditionalAbilityTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.catalog = Catalog()

    def attack(self, build, health=100, slot="fixed_1", band=None):
        return calculate_attack(build, slot, current_health=health, range_band=band, catalog=self.catalog)

    def test_fleet_footed_all_ranks_active_only(self):
        base = CharacterBuild("Saberlion")
        baseline = calculate_stats(base, self.catalog)
        for name, bonus in (("Fleet Footed", 50), ("Fleet Footed 2", 100), ("Fleet Footed 3", 150), ("FLeet Footed 4", 200)):
            with self.subTest(name=name):
                active = calculate_stats(replace(base, abilities=(name,)), self.catalog)
                inactive = calculate_stats(replace(base, inactive_abilities=(name,)), self.catalog)
                self.assertEqual(active["current"]["speed"], baseline["current"]["speed"] + bonus)
                self.assertEqual(active["pilot"]["speed"], baseline["pilot"]["speed"])
                self.assertEqual(inactive, baseline)

    def test_half_maximum_range_is_normal_and_does_not_trigger_sniper(self):
        self.assertEqual(range_band_for_distance(250, 500), "normal")
        self.assertEqual(range_band_for_distance(251, 500), "long")
        self.assertEqual(range_band_for_distance(60, 500), "close")
        build = CharacterBuild("Saberlion", abilities=("Sniper 4",), equipment=("Particle Cannon", None, None, None))
        maximum = calculate_stats(build, self.catalog)["current"]["range"]
        actual = calculate_attack(build, "back", current_health=100, distance=maximum / 2, catalog=self.catalog)
        self.assertEqual(actual["range_band"], "normal")
        self.assertEqual(actual["sniper_bonus"], 0)

    def test_sniper_ranks_only_apply_at_long_range_to_ranged_attacks(self):
        base = CharacterBuild("Saberlion", equipment=("Particle Cannon", None, None, None))
        baseline = self.attack(base, slot="back", band="long")
        for rank in range(1, 5):
            build = replace(base, abilities=(f"Sniper {rank}",))
            for band in ("close", "normal", "long"):
                actual = self.attack(build, slot="back", band=band)
                self.assertEqual(actual["sniper_bonus"], rank if band == "long" else 0)
                self.assertEqual(actual["to_hit"], baseline["to_hit"] + actual["sniper_bonus"])
            self.assertEqual(self.attack(build, band="long")["sniper_bonus"], 0)
            self.assertIsNone(self.attack(build, band="long")["range_band"])
        inactive = replace(base, inactive_abilities=("Sniper 4",))
        self.assertEqual(self.attack(inactive, slot="back", band="long"), baseline)

    def test_ranged_attacks_require_one_valid_range_selection(self):
        build = CharacterBuild("Saberlion", equipment=("Particle Cannon", None, None, None))
        for band in (None, "close,long", "unknown"):
            with self.assertRaises(RuleError):
                self.attack(build, slot="back", band=band)

    def test_comeback_exact_twenty_percent_and_above_all_ranks(self):
        # Default Saberlion max health is 135, so 27 is exactly 20%.
        for name, percent, damage in (("Comeback", "0.2", 42), ("Comeback 2", "0.3", 46), ("Comeback 3", "0.4", 49), ("Comeback 4", "0.5", 53)):
            build = CharacterBuild("Saberlion", abilities=(name,))
            at_threshold = self.attack(build, health=27)
            self.assertEqual(at_threshold["maximum_health"], 135)
            self.assertEqual(at_threshold["comeback_percent"], Decimal(percent))
            self.assertEqual(at_threshold["damage"], damage)
            self.assertEqual(self.attack(build, health=28)["damage"], 35)
            self.assertEqual(self.attack(build, health=0)["damage"], damage)
            inactive = replace(build, abilities=(), inactive_abilities=(name,))
            self.assertEqual(self.attack(inactive, health=27)["damage"], 35)

    def test_comeback_applies_to_ranged_damage_and_upgraded_fixed_damage(self):
        build = CharacterBuild("Saberlion", abilities=("Comeback",), equipment=("Particle Cannon", None, None, None), upgrades=Upgrades(damage=(1, 0, 0, 0)))
        self.assertEqual(self.attack(build, health=27)["damage"], 66)
        self.assertEqual(self.attack(build, health=27, slot="back", band="normal")["damage"], 78)
        enabled = replace(build, organoid_enabled=True, organoid_color="Black", organoid_level=5)
        self.assertEqual(self.attack(enabled, health=27)["damage"], 80)

    def test_comeback_uses_current_derived_maximum_health(self):
        base = CharacterBuild("Saberlion", abilities=("Comeback",))
        self.assertEqual(self.attack(base, health=28)["comeback_percent"], 0)
        boosted = replace(base, abilities=("Comeback", "Small Expert"))
        self.assertEqual(self.attack(boosted, health=28)["comeback_percent"], Decimal("0.2"))

    def test_invalid_health_and_empty_weapon_rejected(self):
        base = CharacterBuild("Saberlion")
        for health in (-1, True):
            with self.assertRaises(RuleError):
                self.attack(base, health=health)
        for slot in ("back", "fixed_3", "unknown"):
            with self.assertRaises(RuleError):
                self.attack(base, slot=slot)


if __name__ == "__main__":
    unittest.main()
