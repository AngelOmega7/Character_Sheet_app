from dataclasses import asdict, replace
import json
from pathlib import Path
import tempfile
import unittest

from zoids_app.catalog import Catalog
from zoids_app.characters import (acquire_equipment, acquire_zoid, assign_pilot_ability, equip_owned_equipment,
    learn_pilot_ability, new_character, return_equipment_to_inventory, switch_zoid, validate_character)
from zoids_app.combat import RuleError, WeaponCondition
from zoids_app.combat_controller import rest, start_turn, weapon_action
from zoids_app.stats import CharacterBuild, calculate_stats
from zoids_app.storage import CharacterStore
from zoids_app.tags import weapon_tags
from unittest.mock import patch


class EnergyDataAndMigrationTests(unittest.TestCase):
    def setUp(self):
        self.catalog = Catalog()

    def equip(self, pilot, name, slot):
        pilot = acquire_equipment(pilot, name, catalog=self.catalog)
        return equip_owned_equipment(pilot, slot, pilot.inventory[-1].id, self.catalog)

    def test_maximum_adds_actual_level_not_type_bonus_and_leveling_does_not_refill(self):
        build = CharacterBuild("Saberlion", pilot_level=10, abilities=("Lion Type 2",),
                               equipment=(None, None, None, "Energy Reinforcer Unit"))
        stats = calculate_stats(build, self.catalog)
        self.assertEqual(stats["effective_level"], 20)
        self.assertEqual(stats["energy"], 20 + 10 + 20)
        plain = calculate_stats(replace(build, abilities=()), self.catalog)
        self.assertEqual(stats["energy"], plain["energy"])
        self.assertEqual(stats["energy_recharge"], plain["energy_recharge"])
        pilot = acquire_zoid(replace(new_character(), build=CharacterBuild("", pilot_level=10)),
                             "Saberlion", self.catalog)
        self.assertEqual(pilot.current_energy, 15)
        leveled = validate_character(replace(pilot, build=replace(pilot.build, pilot_level=12)), self.catalog)
        self.assertEqual(leveled.current_energy, 15)
        self.assertEqual(rest(leveled, self.catalog).character.current_energy, 16)
        self.assertEqual(calculate_stats(leveled.build, self.catalog)["energy_recharge"], 2)
        with tempfile.TemporaryDirectory() as directory:
            store = CharacterStore(Path(directory) / "save.db", self.catalog)
            loaded = store.load(store.save(leveled).id)
            self.assertEqual(loaded.current_energy, 15)
            self.assertEqual(calculate_stats(loaded.build, self.catalog)["energy"], 32)

    def test_new_and_unspecified_energy_default_to_half_maximum_rounded_down(self):
        for name, expected in (("Saberlion", 10), ("Zaber Fang", 13)):
            pilot = acquire_zoid(new_character(), name, self.catalog)
            self.assertEqual(pilot.current_energy, expected)
            self.assertEqual(pilot.owned_zoids[0].current_energy, expected)
        pilot = self.equip(pilot, "Energy Reinforcer Unit", "chest")
        owner = replace(pilot.owned_zoids[0], current_energy=None)
        pilot = validate_character(replace(pilot, current_energy=None, owned_zoids=(owner,)), self.catalog)
        self.assertEqual(pilot.current_energy, 23)  # Equipped maximum 46, including pilot level 1.
        pilot = acquire_zoid(pilot, "Berserk Fury", self.catalog)
        self.assertEqual(pilot.owned_zoids[-1].current_energy, 20)
        self.assertEqual(pilot.current_energy, 23)

    def test_rest_sets_half_equipped_maximum_from_above_and_below(self):
        pilot = acquire_zoid(new_character(), "Zaber Fang", self.catalog)
        pilot = self.equip(pilot, "Energy Reinforcer Unit", "chest")
        pilot = acquire_zoid(pilot, "Berserk Fury", self.catalog)
        item = replace(pilot.inventory[0], condition=WeaponCondition(True, 19))
        pilot = replace(pilot, current_health=17, gold=123, inventory=(item,),
                        build=replace(pilot.build, shield_adjustment=3))
        with patch("zoids_app.combat_controller.random.randint") as roll:
            for energy in (0, 21, 22, 23, 45):
                before = validate_character(replace(pilot, current_energy=energy), self.catalog)
                rested = rest(before, self.catalog).character
                expected = validate_character(replace(before, current_energy=23), self.catalog)
                self.assertEqual(rested, expected)
                self.assertEqual(rested.owned_zoids[-1], before.owned_zoids[-1])
                self.assertEqual(rest(rested, self.catalog).character, rested)
            roll.assert_not_called()
        with self.assertRaises(RuleError):
            rest(new_character(), self.catalog)

    def test_saved_energy_is_preserved_until_rest_is_explicitly_used(self):
        pilot = acquire_zoid(new_character(), "Zaber Fang", self.catalog)
        with tempfile.TemporaryDirectory() as directory:
            store = CharacterStore(Path(directory) / "save.db", self.catalog)
            for energy in (0, 7, 25):
                saved = store.save(replace(pilot, current_energy=energy))
                loaded = store.load(saved.id)
                self.assertEqual(loaded.current_energy, energy)
                rested = store.save(rest(loaded, self.catalog).character)
                self.assertEqual(store.load(rested.id).current_energy, 13)

    def test_all_economized_ranks_reduce_only_ranged_costs_to_zero(self):
        build = CharacterBuild("Berserk Fury", equipment=("Particle Cannon", "Mini Laser", "Energy Container", None))
        baseline = calculate_stats(build, self.catalog)
        for rank in range(1, 5):
            name = "Economized Shooting" + (f" {rank}" if rank > 1 else "")
            actual = calculate_stats(replace(build, abilities=(name,)), self.catalog)
            for old, new in zip(baseline["weapons"], actual["weapons"]):
                cost = old["energy_cost"]
                if cost is not None and "ranged" in weapon_tags(old["damage_type"]):
                    cost = max(0, cost - rank * 2)
                self.assertEqual(new["energy_cost"], cost)
            disabled = calculate_stats(replace(build, inactive_abilities=(name,)), self.catalog)
            self.assertEqual(disabled, baseline)

    def test_economized_rank_upgrade_and_persistence(self):
        pilot = acquire_zoid(new_character(), "Berserk Fury", self.catalog)
        pilot = learn_pilot_ability(pilot, "Economized Shooting 1", self.catalog)
        pilot = assign_pilot_ability(pilot, 0, "Economized Shooting", self.catalog)
        for rank in (2, 3, 4):
            pilot = learn_pilot_ability(pilot, f"Economized Shooting {rank}", self.catalog)
            self.assertEqual(pilot.build.abilities, (f"abilities:economized_shooting_{rank}",))
        with self.assertRaises(RuleError):
            learn_pilot_ability(pilot, "Economized Shooting", self.catalog)
        with tempfile.TemporaryDirectory() as directory:
            store = CharacterStore(Path(directory) / "save.db", self.catalog)
            pilot = store.save(pilot)
            loaded = store.load(pilot.id)
            used = weapon_action(loaded, "fixed_2", "use", catalog=self.catalog).character
            self.assertEqual(used.current_energy, 3)  # 20 - (25 - 8)

    def test_reinforcers_are_passive_flat_bonuses_without_refilling_resources(self):
        pilot = acquire_zoid(new_character(), "Berserk Fury", self.catalog)
        pilot = replace(pilot, build=replace(pilot.build, pilot_level=40, organoid_enabled=True,
                                             organoid_color="White", organoid_level=40))
        baseline = calculate_stats(pilot.build, self.catalog)
        health, energy = pilot.current_health, pilot.current_energy
        pilot = self.equip(pilot, "Physics Reinforcer Unit", "left")
        pilot = self.equip(pilot, "Energy Reinforcer Unit", "chest")
        stats = calculate_stats(pilot.build, self.catalog)
        self.assertEqual(stats["pilot"]["health"], baseline["pilot"]["health"] + 100)
        self.assertEqual(stats["energy"], 140)
        self.assertEqual(stats["carry_load"], 6)
        self.assertEqual((pilot.current_health, pilot.current_energy), (health, energy))
        self.assertFalse(any(pilot.build.equipment_active))
        self.assertEqual(calculate_stats(replace(pilot.build, equipment_active=(True,) * 4), self.catalog), stats)
        pilot = replace(pilot, current_energy=139)
        pilot = start_turn(pilot, self.catalog).character
        self.assertEqual(pilot.current_energy, 140)
        pilot = equip_owned_equipment(pilot, "chest", None, self.catalog)
        self.assertEqual(pilot.current_energy, 120)
        pilot = equip_owned_equipment(pilot, "chest", pilot.inventory[-1].id, self.catalog)
        self.assertEqual(pilot.current_energy, 120)

    def test_equipped_energy_bonus_survives_save_switch_and_inventory_return(self):
        pilot = acquire_zoid(new_character(), "Berserk Fury", self.catalog)
        pilot = self.equip(pilot, "Energy Reinforcer Unit", "chest")
        pilot = validate_character(replace(pilot, current_energy=60), self.catalog)
        identity, item = pilot.active_zoid_id, pilot.inventory[-1].id
        pilot = acquire_zoid(pilot, "Liger Zero", self.catalog)
        pilot = switch_zoid(pilot, pilot.owned_zoids[-1].id, catalog=self.catalog)
        with tempfile.TemporaryDirectory() as directory:
            store = CharacterStore(Path(directory) / "save.db", self.catalog)
            pilot = store.load(store.save(pilot).id)
            pilot = switch_zoid(pilot, identity, catalog=self.catalog)
            self.assertEqual(pilot.current_energy, 60)
            pilot = return_equipment_to_inventory(pilot, item, self.catalog)
            self.assertEqual(pilot.current_energy, 41)

    def test_container_activation_is_capped_and_does_not_roll_or_change_other_resources(self):
        pilot = acquire_zoid(new_character(), "Berserk Fury", self.catalog)
        pilot = self.equip(pilot, "Energy Reinforcer Unit", "left")
        pilot = self.equip(pilot, "Energy Container", "chest")
        self.assertEqual(calculate_stats(pilot.build, self.catalog)["carry_load"], 13)
        with patch("zoids_app.combat_controller.random.randint") as roll:
            used = weapon_action(replace(pilot, current_energy=0), "chest", "use", catalog=self.catalog).character
            self.assertEqual(used.current_energy, 20)
            used = weapon_action(replace(used, current_energy=55), "chest", "use", catalog=self.catalog).character
            self.assertEqual(used.current_energy, 61)
            again = weapon_action(used, "chest", "use", catalog=self.catalog).character
            self.assertEqual(again, used)
            self.assertEqual((used.current_health, used.gold, used.inventory), (pilot.current_health, pilot.gold, pilot.inventory))
            roll.assert_not_called()
        broken = replace(pilot.inventory[-1], condition=WeaponCondition(True))
        pilot = replace(pilot, inventory=(*pilot.inventory[:-1], broken))
        with self.assertRaises(RuleError):
            weapon_action(pilot, "chest", "use", catalog=self.catalog)

    def test_every_zoid_and_generic_item_has_valid_energy_data(self):
        for dataset in ("zoids", "transports"):
            for record in self.catalog.tables[dataset]["records"]:
                if record["kind"] != "record":
                    continue
                with self.subTest(zoid=record["id"]):
                    self.assertIs(type(record["energy"]), int)
                    self.assertGreater(record["energy"], 0)
                    self.assertIs(type(record["energy_recharge"]), int)
                    self.assertGreaterEqual(record["energy_recharge"], 0)
                    self.assertEqual(len(record["energy_costs"]), 8)
                    for column, cost in zip((13, 19, 30, 41, 47, 54, 61, 66), record["energy_costs"]):
                        if self.catalog.column(record, column):
                            self.assertIs(type(cost), int)
                            self.assertGreaterEqual(cost, 0)
                        else:
                            self.assertIsNone(cost)
                    self.assertFalse(any("heat" in key for key in record["fields"]))
        for item in self.catalog.tables["armaments"]["records"]:
            if item["kind"] == "record":
                self.assertIs(type(item["energy_cost"]), int)
                self.assertGreaterEqual(item["energy_cost"], 0)

    def test_named_cost_mapping_retains_current_slot_positions(self):
        expected = {"Zaber Fang": [0, 3, 1, 2], "Lightning Saix": [3, 6, 1, None],
                    "Command Wolf IS (CAU)": [1, 1, 6, None]}
        for name, costs in expected.items():
            with self.subTest(name=name):
                stats = calculate_stats(CharacterBuild(name), self.catalog)
                self.assertEqual([w["energy_cost"] for w in stats["weapons"][:4]], costs)

    def test_zoid_specific_template_cost_follows_identity_not_mount_position(self):
        pilot = acquire_zoid(new_character(), "Zaber Fang", self.catalog)
        pilot = acquire_equipment(pilot, "armaments:zoid_equipment_slot_1", catalog=self.catalog)
        pilot = equip_owned_equipment(pilot, "left", pilot.inventory[0].id, self.catalog)
        stats = calculate_stats(pilot.build, self.catalog)
        self.assertEqual(stats["weapons"][5]["energy_cost"], 6)
        used = weapon_action(pilot, "left", "use", catalog=self.catalog).character
        self.assertEqual(used.current_energy, 7)

    def test_form_switch_clamps_without_refill(self):
        pilot = acquire_zoid(new_character(), "Berserk Fury", self.catalog)
        pilot = acquire_zoid(pilot, "Berserk Fury Z (CAU)", self.catalog)
        identity = pilot.active_zoid_id
        pilot = switch_zoid(pilot, identity, "zoids:berserk_fury_z_cau", self.catalog)
        self.assertEqual(pilot.current_energy, 20)
        pilot = replace(pilot, current_energy=50)
        pilot = switch_zoid(pilot, identity, "zoids:berserk_fury", self.catalog)
        self.assertEqual(pilot.current_energy, 41)
        pilot = switch_zoid(pilot, identity, "zoids:berserk_fury_z_cau", self.catalog)
        self.assertEqual(pilot.current_energy, 41)

    def test_v11_export_discards_heat_and_preserves_rolls_damage_and_pilot_options(self):
        pilot = acquire_zoid(new_character(), "Berserk Fury", self.catalog)
        pilot = acquire_equipment(pilot, "Particle Cannon", catalog=self.catalog)
        pilot = equip_owned_equipment(pilot, "left", pilot.inventory[0].id, self.catalog)
        pilot = weapon_action(replace(pilot, current_energy=40), "fixed_2", "use", catalog=self.catalog).character
        values = asdict(pilot)
        values.pop("current_energy")
        values["build"]["abilities"] = ["abilities:economized_shooting"]
        values["pilot_details"]["feats"] = ["feats:demolitionist"]
        values["current_health"] = 17
        values["gold"] = 123
        for owned in values["owned_zoids"]:
            owned.pop("current_energy")
            for weapon in owned["weapon_conditions"]:
                weapon["condition"].update(heat=2, broken=True)
        values["inventory"][0]["condition"].update(heat=4, broken=True, last_roll=19)
        with tempfile.TemporaryDirectory() as directory:
            store = CharacterStore(Path(directory) / "save.db", self.catalog)
            loaded = store.import_character(json.dumps({"save_version": 11, "character": values}))
            self.assertEqual((loaded.current_health, loaded.gold, loaded.current_energy), (17, 123, 20))
            self.assertEqual(loaded.build.abilities, ("abilities:economized_shooting",))
            self.assertEqual(loaded.pilot_details.feats, ("feats:demolitionist",))
            self.assertTrue(loaded.owned_zoids[0].weapon_conditions[0].condition.broken)
            self.assertEqual(loaded.inventory[0].condition.last_roll, 19)
            self.assertTrue(loaded.inventory[0].condition.broken)
            self.assertNotIn('"heat"', store.export_character(loaded.id))
            store.save(replace(loaded, current_energy=7))
            reopened = CharacterStore(Path(directory) / "save.db", self.catalog).load(loaded.id)
            self.assertEqual(reopened.current_energy, 7)
            imported = store.import_character(store.export_character(loaded.id))
            self.assertEqual(imported.current_energy, 7)
