"""BLOX restoration and atomic multi-chassis FUZOR builds."""
from dataclasses import replace
import json
from pathlib import Path
import tempfile
import unittest

from zoids_app.abilities import AbilityLoadout, activate_ability, learn_ability
from zoids_app.catalog import Catalog
from zoids_app.characters import FixedWeaponCondition, acquire_equipment, acquire_zoid, equip_owned_equipment, new_character, set_upgrades, switch_zoid, validate_character
from zoids_app.combat import RuleError, WeaponCondition
from zoids_app.commerce import purchase_zoid, quote_purchase, recipe, sell_zoid, set_known_design
from zoids_app.stats import CharacterBuild, Upgrades, calculate_stats
from zoids_app.storage import CharacterStore
from zoids_app.transport import load_zoid, select_transport


RECIPES = {
    "Fuzor Dragon": ("Leo Blaze", "Unenlagia", "Mosasledge", "Nightwise"),
    "Chimera Dragon": ("Diplo Gun", "Shell Karn", "Demon's Head", "Flyscissors"),
    "Gojulox": ("Diplo Gun", "Shell Karn", "Demon's Head", "Leo Blaze", "Unenlagia", "Nightwise"),
    "2-Arm Lizard": ("Leo Blaze", "Unenlagia"),
    "Griffin": ("Leo Blaze", "Unenlagia", "Buster Eagle"),
    "Lord Gale": ("Diplo Gun", "Shell Karn", "Demon's Head", "Flyscissors"),
}


class FuzorTests(unittest.TestCase):
    def setUp(self):
        self.catalog = Catalog()

    def components(self, name):
        c = replace(new_character(self.catalog), starter_pending=False, gold=1234)
        for component in RECIPES[name]:
            c = acquire_zoid(c, component, self.catalog)
        return set_known_design(c, name, catalog=self.catalog)

    def test_all_six_recipes_consume_components_without_gold_and_save(self):
        for name, components in RECIPES.items():
            with self.subTest(name=name):
                record = self.catalog.find("zoids", name)
                self.assertTrue(record["is_fuzor"])
                self.assertEqual(record["fields"]["type"].strip(), "BLOX")
                data = recipe(self.catalog, name)
                self.assertEqual(data["cost"], 0)
                self.assertEqual(tuple(self.catalog.find("zoids", i)["name"] for i in data["blox"]), components)
                c = self.components(name)
                old_ids = {o.id for o in c.owned_zoids}
                c = purchase_zoid(c, quote_purchase(c, name, catalog=self.catalog), catalog=self.catalog)
                self.assertEqual(c.gold, 1234)
                self.assertEqual(len(c.owned_zoids), 1)
                self.assertNotIn(c.active_zoid_id, old_ids)
                self.assertEqual(c.build.zoid, record["id"])
                with tempfile.TemporaryDirectory() as directory:
                    store = CharacterStore(Path(directory) / "fuzor.sqlite3", self.catalog)
                    self.assertEqual(store.load(store.save(c).id), c)

    def test_missing_components_design_and_starters_cannot_bypass_requirements(self):
        for name in RECIPES:
            with self.subTest(name=name), self.assertRaises(RuleError):
                quote_purchase(new_character(self.catalog), name, starter=True, catalog=self.catalog)
        c = self.components("2-Arm Lizard")
        missing = replace(c, owned_zoids=c.owned_zoids[:1])
        quote = quote_purchase(missing, "2-Arm Lizard", catalog=self.catalog)
        self.assertTrue(any("Unenlagia" in issue for issue in quote.issues))
        with self.assertRaises(RuleError):
            purchase_zoid(missing, quote, catalog=self.catalog)
        unknown = replace(c, known_zoids=())
        with self.assertRaises(RuleError):
            purchase_zoid(unknown, quote_purchase(unknown, "2-Arm Lizard", catalog=self.catalog), catalog=self.catalog)
        restored = purchase_zoid(missing, quote, override=True, catalog=self.catalog)
        self.assertEqual(restored.owned_zoids[:1], missing.owned_zoids)
        self.assertEqual(restored.gold, missing.gold)

    def test_duplicate_instances_require_selection_and_preserve_unselected_chassis(self):
        c = self.components("2-Arm Lizard")
        first, other = c.owned_zoids
        c = acquire_zoid(c, "Leo Blaze", self.catalog)
        duplicate = c.owned_zoids[-1]
        self.assertTrue(quote_purchase(c, "2-Arm Lizard", catalog=self.catalog).issues)
        for invalid in ((first.id, first.id), (other.id, first.id), ("missing", other.id)):
            with self.subTest(selection=invalid), self.assertRaises(RuleError):
                purchase_zoid(c, quote_purchase(c, "2-Arm Lizard", blox_ids=invalid, catalog=self.catalog), catalog=self.catalog)
        quote = quote_purchase(c, "2-Arm Lizard", blox_ids=(duplicate.id, other.id), catalog=self.catalog)
        result = purchase_zoid(c, quote, catalog=self.catalog)
        self.assertEqual(result.owned_zoids[0], first)
        self.assertEqual(len(result.owned_zoids), 2)
        with self.assertRaises(RuleError):
            purchase_zoid(result, quote, catalog=self.catalog)

    def test_consumption_unloads_cargo_returns_equipment_and_discards_upgrades(self):
        c = self.components("2-Arm Lizard")
        c = switch_zoid(c, c.owned_zoids[0].id, catalog=self.catalog)
        c = set_upgrades(c, Upgrades(speed=3), self.catalog)
        c = acquire_equipment(c, "Particle Cannon", catalog=self.catalog)
        c = equip_owned_equipment(c, "left", c.inventory[0].id, self.catalog)
        c = select_transport(c, "Whale King", self.catalog)
        for owner in c.owned_zoids:
            c = load_zoid(c, owner.id, catalog=self.catalog)
        result = purchase_zoid(c, quote_purchase(c, "2-Arm Lizard", catalog=self.catalog), catalog=self.catalog)
        self.assertEqual(result.loaded_zoids, ())
        self.assertEqual(result.inventory, c.inventory)
        self.assertEqual(result.build.equipment, (None,) * 4)
        self.assertEqual(result.build.upgrades, Upgrades())

    def test_blox_ability_ranks_match_base_and_fuzor_types_only(self):
        loadout = AbilityLoadout()
        for rank in range(1, 6):
            ability = self.catalog.find("abilities", f"BLOX Type {rank}")
            loadout = learn_ability(loadout, ability["id"], self.catalog)
            if rank == 1:
                loadout = activate_ability(loadout, ability["id"], 0, self.catalog)
            self.assertEqual(loadout.active, (ability["id"],))
            for name in ("Leo Blaze", "Fuzor Dragon", "Buster Eagle", "Zero Phoenix"):
                stats = calculate_stats(CharacterBuild(zoid=name, abilities=loadout.active), self.catalog)
                self.assertEqual(stats["bonus_levels"], rank * 5 if name in ("Leo Blaze", "Fuzor Dragon") else 0)

    def test_base_blox_starter_uses_csv_price_and_waives_core(self):
        c = new_character(self.catalog)
        quote = quote_purchase(c, "Leo Blaze", starter=True, catalog=self.catalog)
        self.assertEqual((quote.cost, quote.materials, quote.issues), (8000, (), ()))
        result = purchase_zoid(c, quote, catalog=self.catalog)
        self.assertEqual(result.gold, 2000)
        self.assertEqual(result.build.zoid, "zoids:leo_blaze")

    def test_repeated_component_recipe_requires_distinct_owned_copies(self):
        data = recipe(self.catalog, "2-Arm Lizard")
        data["blox"] = ["zoids:leo_blaze", "zoids:leo_blaze"]
        c = replace(new_character(self.catalog), starter_pending=False)
        c = acquire_zoid(c, "Leo Blaze", self.catalog)
        c = set_known_design(c, "2-Arm Lizard", catalog=self.catalog)
        one = c.owned_zoids[0].id
        quote = quote_purchase(c, "2-Arm Lizard", blox_ids=(one, one), catalog=self.catalog)
        with self.assertRaises(RuleError):
            purchase_zoid(c, quote, catalog=self.catalog)
        c = acquire_zoid(c, "Leo Blaze", self.catalog)
        two = c.owned_zoids[-1].id
        quote = quote_purchase(c, "2-Arm Lizard", blox_ids=(one, two), catalog=self.catalog)
        result = purchase_zoid(c, quote, catalog=self.catalog)
        self.assertEqual(len(result.owned_zoids), 1)
        self.assertNotIn(result.active_zoid_id, (one, two))

    def test_sale_restores_exact_components_after_save_and_export_import(self):
        c = self.components("2-Arm Lizard")
        c = set_upgrades(c, Upgrades(speed=3, damage=(2, 0, 0, 0)), self.catalog)
        c = acquire_equipment(c, "Particle Cannon", catalog=self.catalog)
        c = equip_owned_equipment(c, "left", c.inventory[0].id, self.catalog)
        original = c.owned_zoids[0]
        weapon_id = self.catalog.find("zoids", original.base_zoid)["fixed_weapon_ids"][0]
        original = replace(original, weapon_conditions=(FixedWeaponCondition(weapon_id, WeaponCondition(2, True, 17)),))
        c = validate_character(replace(c, current_health=7, owned_zoids=(original, *c.owned_zoids[1:])), self.catalog)
        expected = tuple(replace(o, forms=tuple(replace(f, equipment=(None,) * 4, equipment_ids=(None,) * 4,
                            equipment_active=(False,) * 4) for f in o.forms)) for o in c.owned_zoids)
        fused = purchase_zoid(c, quote_purchase(c, "2-Arm Lizard", catalog=self.catalog), catalog=self.catalog)
        fused = set_upgrades(fused, Upgrades(speed=5), self.catalog)
        with tempfile.TemporaryDirectory() as directory:
            store = CharacterStore(Path(directory) / "fused.sqlite3", self.catalog)
            store.save(fused)
            imported = store.import_character(store.export_character(fused.id))
            for saved in (store.load(fused.id), store.load(imported.id)):
                restored = sell_zoid(saved, saved.active_zoid_id, self.catalog)
                self.assertEqual(restored.owned_zoids, expected)
                self.assertEqual(restored.current_health, 7)
                self.assertEqual(restored.inventory, c.inventory)
                self.assertEqual(restored.gold, c.gold)
                self.assertEqual(restored.loaded_zoids, ())
                with self.assertRaises(RuleError):
                    sell_zoid(restored, saved.active_zoid_id, self.catalog)
                rebuilt = purchase_zoid(restored, quote_purchase(restored, "2-Arm Lizard", catalog=self.catalog), catalog=self.catalog)
                self.assertEqual(sell_zoid(rebuilt, rebuilt.active_zoid_id, self.catalog).owned_zoids, expected)

    def test_old_fuzor_fallback_is_deterministic_and_override_returns_no_components(self):
        c = self.components("2-Arm Lizard")
        quote = quote_purchase(c, "2-Arm Lizard", catalog=self.catalog)
        override = purchase_zoid(c, quote, override=True, catalog=self.catalog)
        self.assertEqual(sell_zoid(override, override.active_zoid_id, self.catalog).owned_zoids, c.owned_zoids)
        fused = purchase_zoid(c, quote, catalog=self.catalog)
        with tempfile.TemporaryDirectory() as directory:
            store = CharacterStore(Path(directory) / "old.sqlite3", self.catalog)
            store.save(fused)
            document = json.loads(store.export_character(fused.id))
            document["save_version"] = 8
            del document["character"]["owned_zoids"][0]["fusion_components"]
            old = store.import_character(json.dumps(document))
            restored = sell_zoid(old, old.active_zoid_id, self.catalog)
            self.assertEqual(restored, sell_zoid(old, old.active_zoid_id, self.catalog))
            self.assertEqual([o.base_zoid for o in restored.owned_zoids], ["zoids:leo_blaze", "zoids:unenlagia"])
            self.assertTrue(all(o.frame == Upgrades() for o in restored.owned_zoids))

    def test_invalid_component_history_cannot_duplicate_owned_instances(self):
        c = self.components("2-Arm Lizard")
        fused = purchase_zoid(c, quote_purchase(c, "2-Arm Lizard", catalog=self.catalog), catalog=self.catalog)
        owner = fused.owned_zoids[0]
        for components in ((owner.fusion_components[0],) * 2,
                           (replace(owner.fusion_components[0], id=owner.id),)):
            with self.assertRaises(RuleError):
                validate_character(replace(fused, owned_zoids=(replace(owner, fusion_components=components),)), self.catalog)
