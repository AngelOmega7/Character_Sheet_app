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
                                recipe, sell_zoid, set_known_design, set_material)
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

    def test_starter_waives_materials_and_database_but_disallows_base_requirements(self):
        c = new_character(self.catalog)
        self.assertEqual((c.gold, c.build.organoid_color, c.owned_zoids), (10000, "None", ()))
        c = self.buy(c, "Godos", starter=True)  # Core and known-design requirements waived.
        self.assertEqual(c.gold, 0)
        self.assertEqual(c.owned_zoids[0].base_zoid, "zoids:godos")
        self.assertFalse(c.starter_pending)
        for name in ("Liger Zero", "Cannon Tortoise BC", "Allosaurer", "Iguan", "Zaber Fang"):
            with self.assertRaises(RuleError):
                quote_purchase(new_character(self.catalog), name, starter=True, catalog=self.catalog)

    def test_sale_refunds_chassis_and_all_owned_caus_and_preserves_equipment(self):
        c = established_character(self.catalog)
        remaining = c.active_zoid_id
        c = acquire_zoid(c, "Liger Zero", self.catalog)
        sold = c.owned_zoids[-1].id
        for form in ("Zero Jager (CAU)", "Zero Panzer (CAU)"):
            c = acquire_zoid(c, form, self.catalog, host_id=sold)
        c = switch_zoid(c, sold, "zoids:zero_jager_cau", self.catalog)
        c = set_upgrades(c, Upgrades(speed=2), self.catalog)
        c = acquire_equipment(c, "Particle Cannon", catalog=self.catalog)
        c = equip_owned_equipment(c, "left", c.inventory[0].id, self.catalog)
        c = set_material(c, "Jager Unit", 3, self.catalog)
        c = select_transport(c, "Whale King", self.catalog)
        c = load_zoid(c, remaining, catalog=self.catalog)
        c = load_zoid(c, sold, catalog=self.catalog)
        result = sell_zoid(c, sold, self.catalog)
        self.assertEqual(result.gold, 82500)  # (75,000 + 15,000 + 20,000) * .75
        self.assertEqual(result.inventory, c.inventory)
        self.assertEqual(result.materials, c.materials)  # Sale does not also detach/refund Parts.
        self.assertEqual(result.active_zoid_id, remaining)
        self.assertEqual(result.loaded_zoids, (remaining,))
        self.assertEqual(len(result.owned_zoids), 1)
        self.assertEqual(result.build.equipment, (None,) * 4)
        with self.assertRaises(RuleError):
            sell_zoid(result, sold, self.catalog)

    def test_sale_targets_one_duplicate_instance_and_can_leave_an_empty_roster(self):
        c = established_character(self.catalog)
        first = c.active_zoid_id
        c = acquire_zoid(c, "Saberlion", self.catalog)
        second = c.owned_zoids[-1].id
        c = sell_zoid(c, second, self.catalog)
        self.assertEqual(c.active_zoid_id, first)
        self.assertEqual(c.gold, 4500)
        c = sell_zoid(c, first, self.catalog)
        self.assertEqual(c.gold, 9000)
        self.assertEqual((c.owned_zoids, c.active_zoid_id, c.build.zoid), ((), "", ""))
        self.assertFalse(c.starter_pending)
        with tempfile.TemporaryDirectory() as directory:
            store = CharacterStore(Path(directory) / "sale.sqlite3", self.catalog)
            self.assertEqual(store.load(store.save(c).id), c)

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

    def test_second_cau_expansion_consumes_component_and_retains_host(self):
        for host_name, form_name, component, cost in (
                ("Berserk Fury", "Buster Fury", "Buster Eagle", 50000),
                ("Liger Zero", "Zero Falcon", "Jet Falcon", 20000),
                ("Liger Zero", "Zero Phoenix", "Fire Phoenix", 20000)):
            with self.subTest(form=form_name):
                form = self.catalog.find("zoids", form_name)
                self.assertEqual(form["name"], form_name + " (CAU)")
                self.assertEqual(form["ownership_base_id"], self.catalog.find("zoids", host_name)["id"])
                c = acquire_zoid(replace(new_character(self.catalog), starter_pending=False), host_name, self.catalog)
                host = c.active_zoid_id
                c = set_upgrades(c, Upgrades(speed=2), self.catalog)
                c = self.funded(c, form_name)
                with self.assertRaises(RuleError):
                    self.buy(c, form_name, host_id=host)
                c = acquire_zoid(c, component, self.catalog)
                consumed = c.owned_zoids[-1].id
                gold = c.gold
                c = self.buy(c, form_name, host_id=host, base_id=consumed)
                self.assertEqual(c.gold, gold - cost)
                self.assertEqual([o.id for o in c.owned_zoids], [host])
                self.assertEqual(c.build.zoid, form["id"])
                self.assertEqual(c.build.upgrades.speed, 2)
                with tempfile.TemporaryDirectory() as directory:
                    store = CharacterStore(Path(directory) / "cau.sqlite3", self.catalog)
                    self.assertEqual(store.load(store.save(c).id), c)
                c = detach_cau(c, host, form["id"], self.catalog)
                self.assertEqual(c.build.zoid, form["ownership_base_id"])
                self.assertEqual(c.gold, gold - cost // 2)

    def test_saved_standalone_expansion_form_migrates_and_preserves_condition(self):
        for name in ("Zero Falcon", "Zero Phoenix"):
            with self.subTest(form=name), tempfile.TemporaryDirectory() as directory:
                c = acquire_zoid(new_character(self.catalog), "Liger Zero", self.catalog)
                host = c.active_zoid_id
                c = acquire_zoid(c, name, self.catalog, host_id=host)
                form = self.catalog.find("zoids", name)
                c = switch_zoid(c, host, form["id"], self.catalog)
                c = set_upgrades(c, Upgrades(speed=2, damage=(0, 0, 0, 3)), self.catalog)
                c = weapon_action(c, "fixed_4", "use", catalog=self.catalog).character
                store = CharacterStore(Path(directory) / "old.sqlite3", self.catalog)
                store.save(c)
                with closing(sqlite3.connect(store.path)) as db, db:
                    payload = json.loads(db.execute("SELECT payload FROM characters").fetchone()[0])
                    payload["data_version"] = "workflow-v12"
                    owner = payload["character"]["owned_zoids"][0]
                    owner["base_zoid"] = form["id"]
                    owner["forms"] = [f for f in owner["forms"] if f["zoid"] == form["id"]]
                    for collection in ("weapons", "weapon_conditions"):
                        owner[collection] = [w for w in owner[collection] if w["weapon_id"] in form["fixed_weapon_ids"]]
                        for weapon in owner[collection]:
                            weapon["weapon_id"] = weapon["weapon_id"].replace("zoids:liger_zero:", form["id"] + ":")
                    db.execute("UPDATE characters SET payload=?", (json.dumps(payload),))
                loaded = store.load(c.id)
                self.assertEqual(loaded.build, c.build)
                self.assertEqual(loaded.active_zoid_id, host)
                self.assertEqual(loaded.owned_zoids[0].base_zoid, "zoids:liger_zero")
                self.assertEqual(loaded.owned_zoids[0].weapon_conditions, c.owned_zoids[0].weapon_conditions)
                store.save(loaded)
                self.assertEqual(store.load(c.id), loaded)

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
