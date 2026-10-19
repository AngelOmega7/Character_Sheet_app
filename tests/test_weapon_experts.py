from dataclasses import replace
import unittest

from zoids_app.catalog import Catalog
from zoids_app.stats import CharacterBuild, calculate_stats
from zoids_app.tags import weapon_tags
from tools.convert_reference_data import clean_weapon_tags


class WeaponExpertTests(unittest.TestCase):
    def test_strongest_expert_plus_anti_air_independent_of_order(self):
        catalog = Catalog()
        zoid = catalog.find("zoids", "Saberlion")
        for column in (16, 22, 33, 44):
            zoid["fields"][catalog.tables["zoids"]["columns"][column - 1]] = "Melee, Energy, Anti-Air"
        catalog.find("armaments", "Particle Cannon")["fields"]["damage_type"] = "Ranged, Energy, Anti-Air"
        build = CharacterBuild("Saberlion", equipment=("Particle Cannon",) * 4)
        baseline = calculate_stats(build, catalog)
        abilities = ("Laser Expert 4", "Melee Expert 3", "Anti-Air Pro 4")
        for order in (abilities, tuple(reversed(abilities))):
            actual = calculate_stats(replace(build, abilities=order), catalog)
            for before, after in zip(baseline["weapons"], actual["weapons"]):
                self.assertEqual(after["to_hit"] - before["to_hit"], 9)

    def test_anti_air_requires_tag_and_active_ability(self):
        catalog = Catalog()
        zoid = catalog.find("zoids", "Saberlion")
        key = catalog.tables["zoids"]["columns"][15]
        zoid["fields"][key] = "Melee, Energy"
        build = CharacterBuild("Saberlion", abilities=("Laser Expert 2",))
        baseline = calculate_stats(build, catalog)
        without_tag = calculate_stats(replace(build, abilities=("Laser Expert 2", "Anti-Air Pro 4")), catalog)
        self.assertEqual(without_tag["weapons"][0]["to_hit"], baseline["weapons"][0]["to_hit"])
        zoid["fields"][key] = "Melee, Energy, Anti-Air"
        inactive = calculate_stats(replace(build, inactive_abilities=("Anti-Air Pro 4",)), catalog)
        self.assertEqual(inactive["weapons"][0]["to_hit"], baseline["weapons"][0]["to_hit"])

    def test_expert_selection_is_per_weapon_and_ignores_inactive_abilities(self):
        catalog = Catalog()
        zoid = catalog.find("zoids", "Saberlion")
        zoid["fields"][catalog.tables["zoids"]["columns"][15]] = "Melee, Energy"
        build = CharacterBuild("Saberlion", equipment=("Particle Cannon", None, None, None))
        baseline = calculate_stats(build, catalog)
        actual = calculate_stats(replace(build, abilities=("Laser Expert 4", "Melee Expert 2"), inactive_abilities=("Anti-Air Pro 4",)), catalog)
        self.assertEqual(actual["weapons"][0]["to_hit"] - baseline["weapons"][0]["to_hit"], 4)
        self.assertEqual(actual["weapons"][1]["to_hit"] - baseline["weapons"][1]["to_hit"], 2)
        self.assertEqual(actual["weapons"][4]["to_hit"], baseline["weapons"][4]["to_hit"])

    def test_tied_experts_do_not_stack_with_each_other(self):
        catalog = Catalog()
        zoid = catalog.find("zoids", "Saberlion")
        zoid["fields"][catalog.tables["zoids"]["columns"][15]] = "Melee, Energy"
        build = CharacterBuild("Saberlion")
        baseline = calculate_stats(build, catalog)
        actual = calculate_stats(replace(build, abilities=("Laser Expert 2", "Melee Expert 2")), catalog)
        self.assertEqual(actual["weapons"][0]["to_hit"] - baseline["weapons"][0]["to_hit"], 2)

    def test_owner_tag_cleanup_deduplicates_and_preserves_unrelated_tags(self):
        self.assertEqual(clean_weapon_tags("Melee, Freeze, Slashing, Lighting"), "Melee, Electrical")
        self.assertEqual(clean_weapon_tags("Melee, Electric, Electrical, Freeze, Bludgeon, Energy"), "Melee, Electrical, Energy")
        self.assertEqual(clean_weapon_tags("Melee, Anti-Ait, Slashing"), "Melee, Anti-Air")
        self.assertEqual(clean_weapon_tags("Melee. Slashing, Energy"), "Melee, Energy")
        self.assertEqual(clean_weapon_tags("Melee Piercing"), "Melee, Piercing")
        self.assertEqual(clean_weapon_tags("Ranged, Bullet, Anti-Air"), "Ranged, Bullet, Anti-Air")
        self.assertIsNone(clean_weapon_tags(None))

    def test_retired_tags_removed_from_all_live_weapon_tag_fields(self):
        catalog = Catalog()
        retired = {"anti-ait", "slashing", "bludgeon", "freeze", "electric", "lighting"}
        for dataset, columns in (("zoids", (16, 22, 33, 44, 50, 58)), ("armaments", (3,))):
            for record in catalog.tables[dataset]["records"]:
                for column in columns:
                    key = catalog.tables[dataset]["columns"][column - 1]
                    self.assertFalse(weapon_tags(record["fields"][key]) & retired)

    def test_corrected_anti_air_tag_receives_expert_bonus(self):
        catalog = Catalog()
        base = CharacterBuild("Griffin", pilot_level=100)
        baseline = calculate_stats(base, catalog)
        expert = calculate_stats(replace(base, abilities=("Anti-Air Pro",)), catalog)
        index = next(i for i, w in enumerate(baseline["weapons"]) if w["name"] and "Buster Claw" in w["name"])
        self.assertIn("anti-air", weapon_tags(baseline["weapons"][index]["damage_type"]))
        self.assertEqual(expert["weapons"][index]["to_hit"], baseline["weapons"][index]["to_hit"] + 2)

    def test_all_expert_families_apply_to_every_eligible_slot(self):
        for ability, tags, bonus in (("Laser Expert 4", "Energy, Ranged", 4), ("Missile Expert 3", "Ranged, Explosive", 3), ("Particle Expert 2", "Ranged, Particle", 2), ("Melee Expert", "Melee, Piercing", 1), ("Rifle Expert 4", " Bullet, Energy, RANGED ", 4), ("Anti-Air Pro 4", "Ranged, Anti-Air", 5)):
            with self.subTest(ability=ability):
                catalog = Catalog()
                zoid = catalog.find("zoids", "Saberlion")
                for column in (16, 22, 33, 44):
                    zoid["fields"][catalog.tables["zoids"]["columns"][column - 1]] = tags
                catalog.find("armaments", "Particle Cannon")["fields"]["damage_type"] = tags
                build = CharacterBuild("Saberlion", equipment=("Particle Cannon",) * 4)
                base = calculate_stats(build, catalog)
                active = calculate_stats(replace(build, abilities=(ability,)), catalog)
                for before, after in zip(base["weapons"], active["weapons"]):
                    self.assertEqual(after["to_hit"] - before["to_hit"], bonus)
                self.assertEqual(calculate_stats(replace(build, inactive_abilities=(ability,)), catalog), base)

    def test_rifle_requires_both_ranged_and_bullet(self):
        catalog = Catalog()
        build = CharacterBuild("Saberlion", equipment=("Particle Cannon", None, None, None))
        for tags in ("Melee, Piercing", "Ranged, Energy", "Melee, Bullet", "Bullet", "Ranged, Piercing"):
            catalog.find("armaments", "Particle Cannon")["fields"]["damage_type"] = tags
            base = calculate_stats(build, catalog)
            active = calculate_stats(replace(build, abilities=("Rifle Expert 4",)), catalog)
            self.assertEqual(base["weapons"][4]["to_hit"], active["weapons"][4]["to_hit"])

    def test_expert_descriptions_have_no_advantage(self):
        catalog = Catalog()
        for record in catalog.tables["abilities"]["records"]:
            if record.get("family") in {"laser_expert", "missile_expert", "particle_expert", "melee_expert", "rifle_expert"}:
                self.assertNotIn("advantage", record["fields"]["description"].lower())
                if record["family"] == "rifle_expert":
                    self.assertEqual(weapon_tags(record["fields"]["damage_type"]), {"ranged", "bullet"})

    def test_ranged_piercing_converted_melee_piercing_preserved(self):
        catalog = Catalog()
        for dataset, columns in (("zoids", (16, 22, 33, 44, 50, 58)), ("armaments", (3,))):
            for record in catalog.tables[dataset]["records"]:
                for column in columns:
                    key = catalog.tables[dataset]["columns"][column - 1]
                    tags = weapon_tags(record["fields"][key])
                    if "ranged" in tags and "melee" not in tags:
                        self.assertNotIn("piercing", tags)
        saber = catalog.find("zoids", "Saberlion")
        self.assertIn("piercing", weapon_tags(catalog.column(saber, 44)))

    def test_legacy_melee_separators_remain_recognizable(self):
        self.assertEqual(weapon_tags("Melee Piercing"), {"melee", "piercing"})
        self.assertEqual(weapon_tags("Melee. Slashing, Energy"), {"melee", "slashing", "energy"})


if __name__ == "__main__":
    unittest.main()
