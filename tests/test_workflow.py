from contextlib import closing
from dataclasses import asdict, replace
import json
from pathlib import Path
import sqlite3
import tempfile
import unittest
from unittest.mock import patch

from zoids_app.catalog import Catalog
from zoids_app.characters import (FixedWeaponCondition, Material, acquire_equipment, acquire_zoid,
    equip_owned_equipment, new_character, set_upgrades, switch_zoid, validate_character)
from zoids_app.combat import RuleError, WeaponCondition
from zoids_app.combat_controller import combat_snapshot, weapon_action
from zoids_app.commerce import (change_upgrade, detach_cau, purchase_zoid, quote_purchase,
                                recipe, set_known_design, set_material)
from zoids_app.stats import CharacterBuild, Upgrades, calculate_stats
from zoids_app.storage import CharacterStore, SAVE_VERSION
from zoids_app.transport import load_zoid, select_transport
from test_support import established_character


class WorkflowTests(unittest.TestCase):
    def setUp(self):
        self.catalog = Catalog()

    def buy(self, c, name, *, override=False, **kwargs):
        quote = quote_purchase(c, name, catalog=self.catalog, **kwargs)
        return purchase_zoid(c, quote, override=override, catalog=self.catalog)

    def funded(self, c, name):
        data = recipe(self.catalog, name)
        c = replace(c, gold=1000000)
        c = set_known_design(c, name, catalog=self.catalog)
        for material in (data["core"], data["parts"]):
            if material:
                c = set_material(c, material, 3, self.catalog)
        return c

    def test_starter_has_ten_thousand_gold_no_organoid_and_waives_requirements(self):
        c = new_character(self.catalog)
        self.assertEqual((c.gold, c.build.organoid_color, c.owned_zoids), (10000, "None", ()))
        c = self.buy(c, "Allosaurer", starter=True)  # Requires Godos normally.
        self.assertEqual(c.gold, 3000)
        self.assertEqual(c.owned_zoids[0].base_zoid, "zoids:allosaurer")
        self.assertFalse(c.starter_pending)
        for name in ("Liger Zero", "Cannon Tortoise BC"):
            with self.assertRaises(RuleError):
                quote_purchase(new_character(self.catalog), name, starter=True, catalog=self.catalog)

    def test_purchase_checks_and_consumes_exact_material_quantities_and_gold(self):
        c = established_character(self.catalog)
        c = self.funded(c, "Geno Saurer")
        before = c
        c = self.buy(c, "Geno Saurer")
        self.assertEqual(c.gold, 920000)
        self.assertEqual({i.name: i.quantity for i in c.materials}, {"Zoid Core GS": 2, "Normal OS": 2})
        self.assertEqual(len(c.owned_zoids), 2)
        with self.assertRaises(RuleError):
            self.buy(replace(before, known_zoids=()), "Geno Saurer")
        with self.assertRaises(RuleError):
            self.buy(replace(before, materials=()), "Geno Saurer")
        with self.assertRaises(RuleError):
            self.buy(replace(before, gold=0), "Geno Saurer")

    def test_override_consumes_nothing_and_duplicate_zoids_are_independent(self):
        c = established_character(self.catalog)
        first = c.owned_zoids[0].id
        c = self.buy(c, "Saberlion", override=True)
        self.assertEqual(c.gold, 0)
        self.assertEqual(len(c.owned_zoids), 2)
        self.assertNotEqual(c.active_zoid_id, first)
        self.assertEqual({o.base_zoid for o in c.owned_zoids}, {"zoids:saberlion"})
        c = set_upgrades(c, Upgrades(speed=2), self.catalog)
        self.assertEqual(switch_zoid(c, first, catalog=self.catalog).build.upgrades.speed, 0)

    def test_base_consumption_requires_no_caus_and_replacement_starts_without_upgrades(self):
        c = acquire_zoid(established_character(self.catalog), "Shield Liger", self.catalog)
        base = c.owned_zoids[-1].id
        c = switch_zoid(c, base, catalog=self.catalog)
        c = set_upgrades(c, Upgrades(speed=3), self.catalog)
        c = acquire_equipment(c, "Particle Cannon", catalog=self.catalog)
        c = equip_owned_equipment(c, "left", c.inventory[0].id, self.catalog)
        c = acquire_zoid(c, "Shield Liger DCS", self.catalog, host_id=base)
        c = self.funded(c, "Blade Liger")
        with self.assertRaises(RuleError):
            self.buy(c, "Blade Liger", base_id=base)
        c = detach_cau(c, base, "zoids:shield_liger_dcs", self.catalog)
        gold = c.gold
        c = self.buy(c, "Blade Liger", base_id=base)
        self.assertEqual(c.gold, gold - 32000)
        self.assertNotIn(base, {o.id for o in c.owned_zoids})
        self.assertEqual(c.build.upgrades, Upgrades())
        self.assertEqual(c.build.equipment, (None,) * 4)
        self.assertEqual(len(c.inventory), 1)

    def test_predecessor_cau_replaced_and_refund_returns_its_parts(self):
        c = acquire_zoid(established_character(self.catalog), "Shield Liger", self.catalog)
        host = c.owned_zoids[-1].id
        c = self.funded(c, "Shield Liger DCS")
        c = self.buy(c, "Shield Liger DCS", host_id=host)
        c = self.funded(c, "Shield Liger DCS-J")
        c = self.buy(c, "Shield Liger DCS-J", host_id=host)
        owner = next(o for o in c.owned_zoids if o.id == host)
        self.assertEqual({f.zoid for f in owner.forms}, {"zoids:shield_liger", "zoids:shield_liger_dcs_j"})
        before = {i.name: i.quantity for i in c.materials}.get("DCS Unit", 0)
        gold = c.gold
        c = detach_cau(c, host, "zoids:shield_liger_dcs_j", self.catalog)
        self.assertEqual(c.gold, gold + 12500)
        self.assertEqual({i.name: i.quantity for i in c.materials}["DCS Unit"], before + 1)
        self.assertEqual(c.build.zoid, "zoids:shield_liger")

    def test_override_cau_refunds_csv_value_and_virtual_predecessor_parts(self):
        c = acquire_zoid(established_character(self.catalog), "Zaber Fang", self.catalog)
        host = c.owned_zoids[-1].id
        c = self.buy(c, "Zaber Fang TS", host_id=host, override=True)
        self.assertEqual(c.gold, 0)
        c = detach_cau(c, host, "zoids:zaber_fang_ts", self.catalog)
        self.assertEqual(c.gold, 1000)
        self.assertEqual({i.name: i.quantity for i in c.materials}, {"Tiger Soul": 1, "Assault Unit": 1})

    def test_killer_spiner_retains_host_and_consumes_separate_killer_dome(self):
        c = acquire_zoid(established_character(self.catalog), "Dark Spiner", self.catalog)
        host = c.owned_zoids[-1].id
        c = acquire_zoid(c, "Killer Dome", self.catalog)
        consumed = c.owned_zoids[-1].id
        c = self.funded(c, "Killer Spiner")
        c = self.buy(c, "Killer Spiner", host_id=host, base_id=consumed)
        self.assertIn(host, {o.id for o in c.owned_zoids})
        self.assertNotIn(consumed, {o.id for o in c.owned_zoids})
        self.assertEqual(c.build.zoid, "zoids:killer_spiner")

    def test_upgrades_charge_each_tier_and_refund_full_removed_tier(self):
        c = replace(established_character(self.catalog), gold=65000)
        c = change_upgrade(c, "speed", 1, catalog=self.catalog)
        c = change_upgrade(c, "damage", 1, 0, self.catalog)
        c = change_upgrade(c, "damage", 1, 0, self.catalog)
        c = change_upgrade(c, "damage", 1, 0, self.catalog)
        self.assertEqual(c.gold, 0)
        with self.assertRaises(RuleError):
            change_upgrade(c, "damage", 1, 0, self.catalog)
        c = change_upgrade(c, "damage", -1, 0, self.catalog)
        self.assertEqual(c.gold, 30000)
        self.assertEqual(c.build.upgrades.damage[0], 2)
        with self.assertRaises(RuleError):
            change_upgrade(c, "damage", 1, 2, self.catalog)  # Smoke unit.

    def test_transport_size_capacity_duplicates_and_type_change_unload(self):
        c = established_character(self.catalog)
        c = acquire_zoid(c, "Saberlion", self.catalog)
        c = acquire_zoid(c, "Liger Zero", self.catalog)
        c = select_transport(c, "Gustav", self.catalog)
        for owner in c.owned_zoids[:2]:
            c = load_zoid(c, owner.id, catalog=self.catalog)
        self.assertEqual(len(c.loaded_zoids), 2)
        with self.assertRaises(RuleError):
            load_zoid(c, c.owned_zoids[2].id, catalog=self.catalog)
        c = load_zoid(c, c.owned_zoids[0].id, False, self.catalog)
        with self.assertRaises(RuleError):
            load_zoid(c, c.owned_zoids[2].id, catalog=self.catalog)  # Large exceeds Medium.
        c = select_transport(c, "Hover Cargo", self.catalog)
        self.assertEqual(c.loaded_zoids, ())
        c = load_zoid(c, c.owned_zoids[2].id, catalog=self.catalog)
        c = select_transport(c, None, self.catalog)
        self.assertEqual(c.loaded_zoids, ())
        self.assertEqual(len(c.owned_zoids), 3)

    def test_npc_none_liger_and_fixed_weapon_layout(self):
        b = CharacterBuild("Saberlion", pilot_style="NPC", pilot_level=20, organoid_color="None")
        stats = calculate_stats(b, self.catalog)
        self.assertEqual(stats["pilot"]["health"], stats["base"]["health"])
        self.assertEqual(stats["pilot"]["armor"], stats["base"]["armor"])
        self.assertEqual(stats["weapons"][0]["to_hit"], stats["weapons"][0]["base_to_hit"])
        self.assertEqual(self.catalog.find("zoids", "Saberlion")["fields"]["type"], "Liger")
        self.assertEqual(self.catalog.find("abilities", "Lion Type 1")["name"], "Liger Type 1")
        for name, slot, weapon in (("Lightning Saix", 1, "Pulse Laser Gun:"), ("Lightning Saix BS", 1, "Pulse Laser Gun:"),
                                   ("Shadow Fox", 2, "Laser Vulcan Gun"), ("Command Wolf IS", 2, "Long Range Rifle")):
            record = self.catalog.find("zoids", name)
            actual = calculate_stats(CharacterBuild(record["id"]), self.catalog)
            self.assertEqual(actual["weapons"][slot]["name"], weapon)
            self.assertIsNotNone(record["fixed_weapon_ids"][slot])
            self.assertIsNone(self.catalog.column(record, 47))

    def test_utilities_do_not_roll_and_csv_corrections_are_applied(self):
        c = acquire_zoid(established_character(self.catalog), "Liger Zero", self.catalog)
        c = switch_zoid(c, c.owned_zoids[-1].id, catalog=self.catalog)
        with patch("zoids_app.combat_controller.random.randint") as die:
            result = weapon_action(c, "fixed_2", "use", catalog=self.catalog)
            die.assert_not_called()
            self.assertIsNone(combat_snapshot(result.character, self.catalog)[1]["fixed_2"]["condition"].last_roll)
        self.assertEqual(recipe(self.catalog, "Jagged Stinger")["base_zoid"], "zoids:death_stinger")
        self.assertEqual(recipe(self.catalog, "Death Stinger")["core"], "Zoid Core DS")
        self.assertEqual(recipe(self.catalog, "Saberlion")["core"], "Zoid Core SS")

    def test_workflow_state_roundtrip_and_v7_variant_migration_preserve_instances(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "save.sqlite3"
            store = CharacterStore(path, self.catalog)
            c = self.buy(new_character(self.catalog), "Saberlion", starter=True)
            c = set_material(c, "Zoid Core H1", 2, self.catalog)
            c = set_known_design(c, "Godos", catalog=self.catalog)
            c = select_transport(c, "Gustav", self.catalog)
            c = load_zoid(c, c.active_zoid_id, catalog=self.catalog)
            c = replace(c, transport_notes="Trip A")
            saved = store.save(c)
            self.assertEqual(CharacterStore(path, self.catalog).load(c.id), saved)
            # Two legacy standalone variants must remain separate owned instances.
            raw = asdict(established_character(self.catalog))
            owner = raw["owned_zoids"][0]
            owner["base_zoid"] = owner["active_form"] = "zoids:shield_liger_dcs"
            owner["forms"][0]["zoid"] = "zoids:shield_liger_dcs"
            owner["frame"]["speed"] = 2
            r = self.catalog.find("zoids", "Shield Liger DCS")
            old_key = r["legacy_fixed_weapon_ids"][0]
            owner["weapons"] = [{"weapon_id": old_key, "damage": 3, "to_hit": 1}]
            owner["weapon_conditions"] = [{"weapon_id": old_key, "condition": {"heat": 0, "broken": False, "last_roll": 17}}]
            second = json.loads(json.dumps(owner))
            second["id"] = "second-instance"
            second["frame"]["speed"] = 1
            raw["owned_zoids"] = [owner, second]
            raw["build"]["zoid"] = "zoids:shield_liger_dcs"
            raw["gold"] = 88
            with closing(sqlite3.connect(path)) as db, db:
                db.execute("DELETE FROM characters")
                db.execute("INSERT INTO characters(id,name,payload) VALUES(?,?,?)", (raw["id"], raw["name"], json.dumps({"save_version": 7, "character": raw})))
                db.execute("PRAGMA user_version=7")
            migrated = CharacterStore(path, self.catalog).load(raw["id"])
            self.assertEqual(len(migrated.owned_zoids), 2)
            self.assertEqual({o.base_zoid for o in migrated.owned_zoids}, {"zoids:shield_liger"})
            self.assertEqual([o.frame.speed for o in migrated.owned_zoids], [2, 1])
            self.assertEqual(migrated.gold, 88)
            self.assertEqual(migrated.build.upgrades.damage[0], 3)
            self.assertEqual(combat_snapshot(migrated, self.catalog)[1]["fixed_1"]["condition"].last_roll, 17)
            self.assertEqual(CharacterStore(path, self.catalog).load(raw["id"]), migrated)
