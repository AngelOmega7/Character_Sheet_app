from dataclasses import replace
import unittest

from tools.convert_reference_data import clean_weapon_tags
from zoids_app.attacks import calculate_attack
from zoids_app.catalog import Catalog
from zoids_app.stats import CharacterBuild, calculate_stats
from zoids_app.tags import weapon_tags


class RuleReviewTests(unittest.TestCase):
    def setUp(self):
        self.catalog = Catalog()

    def test_type_abilities_match_whole_listed_types_without_biological_groups(self):
        for zoid_type, broad in (("Lion", "Mammal Type 5"), ("Tiger", "Mammal Type 5"),
                                 ("Wolf", "Mammal Type 5"), ("Gorilla", "Mammal Type 5"),
                                 ("Raptor", "Dinosaur, Land Type 5"), ("T-Rex", "Dinosaur, Land Type 5")):
            zoid = next(r for r in self.catalog.tables["zoids"]["records"] if r["fields"]["type"].strip() == zoid_type)
            build = CharacterBuild(zoid["id"], abilities=(broad,))
            self.assertEqual(calculate_stats(build, self.catalog)["bonus_levels"], 0)
            build = replace(build, abilities=(broad, f"{zoid_type} Type 1"))
            self.assertEqual(calculate_stats(build, self.catalog)["bonus_levels"], 5)
        record = self.catalog.find("zoids", "Saberlion")
        record["fields"]["type"] = " lion "
        self.assertEqual(calculate_stats(CharacterBuild("Saberlion", abilities=("Lion Type 1",)), self.catalog)["bonus_levels"], 5)
        record["fields"]["type"] = "Li"
        self.assertEqual(calculate_stats(CharacterBuild("Saberlion", abilities=("Lion Type 1",)), self.catalog)["bonus_levels"], 0)

    def test_declared_ranged_armaments_have_class_tags_and_no_energy(self):
        for record in self.catalog.tables["armaments"]["records"]:
            if record["kind"] == "record" and str(record["fields"]["weapon_class"]).strip().casefold() == "ranged":
                tags = weapon_tags(record["fields"]["damage_type"])
                self.assertIn("ranged", tags, record["name"])
                self.assertNotIn("energy", tags, record["name"])
        self.assertEqual(clean_weapon_tags("Ranged, Energy, Laser, Piercing, Bullet"), "Ranged, Laser, Bullet")
        self.assertEqual(clean_weapon_tags("Melee, Energy"), "Melee, Energy")

    def test_zoid_specific_lasers_receive_sniper_and_laser_expert_bonuses(self):
        build = CharacterBuild("Lightning Saix", pilot_level=20, equipment=(None, "armaments:zoid_equipment_slot_1", None, None))
        base = calculate_attack(build, "left", current_health=100, range_band="long", catalog=self.catalog)
        self.assertTrue(base["ranged"])
        expert = calculate_attack(replace(build, abilities=("Laser Expert 4", "Sniper 4")), "left",
                                  current_health=100, range_band="long", catalog=self.catalog)
        self.assertEqual(expert["to_hit"], base["to_hit"] + 8)
        rs = self.catalog.find("zoids", "Zaber Fang RS")
        self.assertEqual(weapon_tags(self.catalog.column(rs, 50)), {"ranged", "laser"})
        self.assertEqual(rs["corrections"]["damage_type_50"]["original"], "Energy")

    def test_laser_expert_requires_laser_not_retained_melee_energy(self):
        armament = self.catalog.find("armaments", "Particle Cannon")
        for tags, expected in (("Melee, Energy", 0), ("Ranged, Energy", 0), ("Ranged, Particle", 0), ("Ranged, Laser", 4)):
            armament["fields"]["damage_type"] = tags
            build = CharacterBuild("Saberlion", equipment=(None, "Particle Cannon", None, None))
            base = calculate_stats(build, self.catalog)["weapons"][5]["to_hit"]
            expert = calculate_stats(replace(build, abilities=("Laser Expert 4",)), self.catalog)["weapons"][5]["to_hit"]
            self.assertEqual(expert - base, expected)

    def test_zaber_fang_restored_weapon_slots_and_expert_matching(self):
        build = CharacterBuild("Zaber Fang", pilot_level=20)
        weapons = calculate_stats(build, self.catalog)["weapons"]
        self.assertEqual(weapons[2]["name"], "Laser Machine Gun")
        self.assertEqual(weapons[2]["base_damage"], 45)
        self.assertEqual(weapons[2]["base_to_hit"], weapons[1]["base_to_hit"])
        self.assertEqual(weapon_tags(weapons[2]["damage_type"]), {"ranged", "laser", "close range"})
        self.assertEqual(weapon_tags(weapons[1]["damage_type"]), {"ranged", "particle"})
        self.assertIn("Killer Saber", weapons[3]["name"])
        self.assertEqual((weapons[3]["base_damage"], weapons[3]["base_to_hit"]), (140, 13))
        boosted = calculate_stats(replace(build, abilities=("Laser Expert 4", "Particle Expert 3")), self.catalog)["weapons"]
        self.assertEqual(boosted[1]["to_hit"] - weapons[1]["to_hit"], 3)
        self.assertEqual(boosted[2]["to_hit"] - weapons[2]["to_hit"], 4)
        self.assertEqual(boosted[3]["to_hit"], weapons[3]["to_hit"])
