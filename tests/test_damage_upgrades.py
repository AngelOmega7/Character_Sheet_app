from dataclasses import asdict, replace
import json
from pathlib import Path
import tempfile
import unittest

from zoids_app.attacks import calculate_attack
from zoids_app.catalog import Catalog
from zoids_app.characters import acquire_zoid, new_character, set_upgrades, switch_zoid
from zoids_app.combat import RuleError
from zoids_app.commerce import change_upgrade
from zoids_app.stats import CharacterBuild, Upgrades, calculate_stats
from zoids_app.storage import CharacterStore
from zoids_app.tags import weapon_tags
from zoids_app.upgrade_rules import upgrade_price


class DamageUpgradeTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.catalog = Catalog()

    def test_matching_fixed_generic_and_zoid_specific_weapons_get_flat_bonus(self):
        for zoid in ("Shadow Fox", "Lightning Saix"):
            build = CharacterBuild(zoid, abilities=("Comeback 4",), organoid_enabled=True,
                organoid_color="Black", organoid_level=40,
                equipment=("armaments:zoid_equipment_slot_1", "Acid Blade", "Particle Cannon", "Energy Container"))
            boosted = replace(build, upgrades=Upgrades(melee_damage=2, ranged_damage=3))
            before = calculate_stats(build, self.catalog)
            after = calculate_stats(boosted, self.catalog)
            for base, upgraded in zip(before["weapons"], after["weapons"]):
                with self.subTest(zoid=zoid, slot=base["slot"]):
                    if not base["name"] or base["base_damage"] is None:
                        self.assertEqual(upgraded["damage_upgrade"], 0)
                        continue
                    tags = weapon_tags(base["damage_type"])
                    bonus = 40 if "melee" in tags else 60 if "ranged" in tags else 0
                    self.assertEqual(upgraded["damage_upgrade"], bonus)
                    self.assertEqual(upgraded["damage_bonus"], base["damage_bonus"] + bonus)
                    for hp in (1, 10000):
                        baseline = calculate_attack(build, base["slot"], current_health=hp, range_band="normal", catalog=self.catalog)
                        result = calculate_attack(boosted, base["slot"], current_health=hp, range_band="normal", catalog=self.catalog)
                        self.assertEqual(result["damage"], baseline["damage"] + bonus)
                        self.assertEqual(result["to_hit"], baseline["to_hit"])
                    self.assertEqual(upgraded["energy_cost"], base["energy_cost"])

    def test_costs_caps_and_refunds_match_defense(self):
        for field in ("melee_damage", "ranged_damage"):
            with self.subTest(field=field):
                c = replace(acquire_zoid(new_character(), "Command Wolf", self.catalog), gold=100000)
                for rank in range(1, 6):
                    before = c.gold
                    c = change_upgrade(c, field, 1, catalog=self.catalog)
                    self.assertEqual(getattr(c.build.upgrades, field), rank)
                    self.assertEqual(before - c.gold, upgrade_price("defense", rank))
                self.assertEqual(c.gold, 25000)
                with self.assertRaises(RuleError):
                    change_upgrade(c, field, 1, catalog=self.catalog)
                for rank in range(5, 0, -1):
                    before = c.gold
                    c = change_upgrade(c, field, -1, catalog=self.catalog)
                    self.assertEqual(c.gold - before, upgrade_price("defense", rank))
                self.assertEqual(c.gold, 100000)
                with self.assertRaises(RuleError):
                    change_upgrade(c, field, -1, catalog=self.catalog)
                with self.assertRaises(RuleError):
                    change_upgrade(replace(c, gold=4999), field, 1, catalog=self.catalog)

    def test_upgrades_follow_chassis_across_cau_forms_and_save(self):
        c = acquire_zoid(new_character(), "Command Wolf", self.catalog)
        c = set_upgrades(c, Upgrades(melee_damage=4, ranged_damage=5), self.catalog)
        first = c.active_zoid_id
        c = acquire_zoid(c, "Command Wolf IS", self.catalog, host_id=first)
        form = self.catalog.find("zoids", "Command Wolf IS")["id"]
        c = switch_zoid(c, first, form, self.catalog)
        self.assertEqual((c.build.upgrades.melee_damage, c.build.upgrades.ranged_damage), (4, 5))
        c = acquire_zoid(c, "Command Wolf", self.catalog)
        c = switch_zoid(c, c.owned_zoids[-1].id, catalog=self.catalog)
        self.assertEqual((c.build.upgrades.melee_damage, c.build.upgrades.ranged_damage), (0, 0))
        c = switch_zoid(c, first, form, self.catalog)
        with tempfile.TemporaryDirectory() as directory:
            store = CharacterStore(Path(directory) / "save.db", self.catalog)
            c = store.save(c)
            self.assertEqual(store.load(c.id), c)
            imported = store.import_character(store.export_character(c.id))
            self.assertEqual(imported.build.upgrades, c.build.upgrades)

    def test_pre_v17_saves_default_damage_tracks_to_zero(self):
        c = acquire_zoid(new_character(), "Command Wolf", self.catalog)
        values = asdict(c)
        for frame in (values["build"]["upgrades"], values["owned_zoids"][0]["frame"]):
            frame.pop("melee_damage")
            frame.pop("ranged_damage")
        with tempfile.TemporaryDirectory() as directory:
            store = CharacterStore(Path(directory) / "save.db", self.catalog)
            loaded = store.import_character(json.dumps({"save_version": 16, "character": values}))
            self.assertEqual(loaded, c)
