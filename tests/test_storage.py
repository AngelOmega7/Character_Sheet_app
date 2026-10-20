from contextlib import closing
from dataclasses import asdict, replace
import json
from pathlib import Path
import sqlite3
import tempfile
import unittest
from unittest.mock import patch

from zoids_app.catalog import Catalog
from zoids_app.characters import acquire_equipment, acquire_zoid, assign_pilot_ability, equip_owned_equipment, learn_pilot_ability, new_character, set_upgrades, switch_zoid
from zoids_app.combat import RuleError
from zoids_app.combat_controller import combat_snapshot, weapon_action
from zoids_app.stats import CharacterBuild, Upgrades, calculate_stats
from zoids_app.storage import CharacterStore, SAVE_VERSION
from test_support import established_character as new_character


class StorageTests(unittest.TestCase):
    def setUp(self):
        self.directory = tempfile.TemporaryDirectory()
        self.addCleanup(self.directory.cleanup)
        self.path = Path(self.directory.name) / "nested/characters.sqlite3"
        self.catalog = Catalog()
        self.store = CharacterStore(self.path, self.catalog)

    def test_restart_roundtrip_preserves_state_and_recalculates(self):
        character = new_character(self.catalog)
        character = acquire_equipment(character, "Particle Cannon", catalog=self.catalog)
        character = equip_owned_equipment(character, "left", character.inventory[-1].id, self.catalog)
        build = character.build
        build = replace(build, equipment_active=(False, True, False, False),
                        shield_adjustment=17, abilities=("Small Expert",),
                        inactive_abilities=("Sniper 4",))
        character = replace(character, name="Pilot Ω", build=build, current_health=12, gold=12345)
        saved = self.store.save(character)
        restarted = CharacterStore(self.path, self.catalog)
        loaded = restarted.load(character.id)
        self.assertEqual(saved, loaded)
        self.assertEqual(loaded.build.equipment[1], "armaments:particle_cannon")
        self.assertEqual(loaded.build.abilities, ("abilities:small_expert",))
        self.assertEqual(loaded.current_health, 12)
        self.assertEqual(calculate_stats(saved.build), calculate_stats(loaded.build))
        with closing(sqlite3.connect(self.path)) as db:
            payload = json.loads(db.execute("SELECT payload FROM characters").fetchone()[0])
        self.assertNotIn("current", payload["character"])
        self.assertIn("data_version", payload)

    def test_multiple_characters_and_updates_are_independent(self):
        first, second = new_character(self.catalog), new_character(self.catalog)
        self.store.save(first)
        self.store.save(second)
        self.store.save(replace(first, name="Updated", gold=42))
        self.assertEqual(len(self.store.list_characters()), 2)
        self.assertEqual(self.store.load(first.id).gold, 42)
        self.assertEqual(self.store.load(second.id).gold, 0)

    def test_invalid_save_leaves_previous_character_intact(self):
        original = self.store.save(new_character(self.catalog))
        for candidate in (replace(original, name=" "), replace(original, current_health=-1),
                          replace(original, build=replace(original.build, equipment=("Particle Cannon", None, None, None))),
                          replace(original, build=replace(original.build, zoid="unknown"))):
            with self.assertRaises(RuleError):
                self.store.save(candidate)
            self.assertEqual(self.store.load(original.id), original)

    def test_future_database_version_is_not_modified(self):
        with closing(sqlite3.connect(self.path)) as db, db:
            db.execute("PRAGMA user_version=99")
        with self.assertRaises(RuleError):
            CharacterStore(self.path)
        with closing(sqlite3.connect(self.path)) as db:
            self.assertEqual(db.execute("PRAGMA user_version").fetchone()[0], 99)

    def test_corrupt_and_future_character_saves_are_reported(self):
        original = self.store.save(new_character(self.catalog))
        for payload in ("not json", json.dumps({"save_version": 99}), json.dumps({"save_version": 1, "character": {}})):
            with closing(sqlite3.connect(self.path)) as db, db:
                db.execute("UPDATE characters SET payload=? WHERE id=?", (payload, original.id))
            with self.assertRaises(RuleError):
                self.store.load(original.id)
        with self.assertRaises(RuleError):
            self.store.load("missing")

    def test_recalculation_does_not_heal_or_reset_resources(self):
        character = replace(new_character(self.catalog), current_health=15, gold=300)
        character = replace(character, build=replace(character.build, pilot_level=20, shield_adjustment=50))
        self.store.save(character)
        loaded = self.store.load(character.id)
        self.assertEqual((loaded.current_health, loaded.gold, loaded.build.shield_adjustment), (15, 300, 50))

    def test_entire_owned_roster_survives_restart_and_form_switch(self):
        character = acquire_zoid(new_character(self.catalog), "Liger Zero", self.catalog)
        liger_id = character.owned_zoids[-1].id
        character = acquire_zoid(character, "Zero Jager (CAU)", self.catalog)
        character = switch_zoid(character, liger_id, catalog=self.catalog)
        character = set_upgrades(character, Upgrades(speed=4, damage=(1, 0, 3, 0)), self.catalog)
        character = switch_zoid(character, liger_id, "zoids:zero_jager_cau", self.catalog)
        character = set_upgrades(character, replace(character.build.upgrades, damage=(1, 2, 0, 3)), self.catalog)
        saved = self.store.save(character)
        loaded = CharacterStore(self.path).load(saved.id)
        self.assertEqual(loaded, saved)
        base = switch_zoid(loaded, liger_id, "zoids:liger_zero", self.catalog)
        self.assertEqual(base.build.upgrades.damage, (1, 0, 3, 0))
        self.assertEqual(base.build.upgrades.speed, 4)
        jager = switch_zoid(base, liger_id, "zoids:zero_jager_cau", self.catalog)
        self.assertEqual(jager.build.upgrades.damage, (1, 2, 0, 3))
        self.assertEqual(loaded.owned_zoids[0].frame.speed, 0)

    def legacy_payload(self, zoid):
        values = asdict(new_character(self.catalog))
        values.pop("owned_zoids")
        values.pop("active_zoid_id")
        values["name"] = "Legacy pilot"
        values["current_health"] = 71
        values["gold"] = 1234
        values["build"] = asdict(CharacterBuild(zoid, pilot_level=20,
            equipment=(None, "Particle Cannon", None, None),
            upgrades=Upgrades(speed=2, damage=(1, 0, 0, 3)) if "CAU" in zoid else Upgrades(speed=2, damage=(1, 0, 3, 0))))
        return values["id"], json.dumps({"save_version": 1, "data_version": "equipment-rules-v8", "character": values})

    def test_v1_migration_preserves_base_and_cau_upgrades_and_resources(self):
        for zoid in ("Liger Zero", "Zero Jager (CAU)"):
            with self.subTest(zoid=zoid):
                character_id, payload = self.legacy_payload(zoid)
                with closing(sqlite3.connect(self.path)) as db, db:
                    db.execute("DELETE FROM characters")
                    db.execute("INSERT INTO characters(id,name,payload) VALUES (?,?,?)", (character_id, "Legacy pilot", payload))
                    db.execute("PRAGMA user_version=1")
                migrated = CharacterStore(self.path, self.catalog).load(character_id)
                self.assertEqual(len(migrated.owned_zoids), 1)
                owned = migrated.owned_zoids[0]
                self.assertEqual(owned.base_zoid, "zoids:liger_zero")
                self.assertEqual(len(owned.forms), 2 if "CAU" in zoid else 1)
                self.assertEqual((migrated.current_health, migrated.gold), (71, 1234))
                self.assertEqual(migrated.build.equipment[1], "armaments:particle_cannon")
                base = switch_zoid(migrated, owned.id, "zoids:liger_zero", self.catalog)
                self.assertEqual(base.build.upgrades.speed, 2)
                self.assertEqual(base.build.upgrades.damage, (1, 0, 3, 0))
                with closing(sqlite3.connect(self.path)) as db:
                    self.assertEqual(db.execute("PRAGMA user_version").fetchone()[0], SAVE_VERSION)
                    self.assertEqual(json.loads(db.execute("SELECT payload FROM characters").fetchone()[0])["save_version"], SAVE_VERSION)

    def test_failed_migration_rolls_back_all_rows_and_version(self):
        character_id, payload = self.legacy_payload("Liger Zero")
        with closing(sqlite3.connect(self.path)) as db, db:
            db.execute("INSERT INTO characters(id,name,payload) VALUES (?,?,?)", (character_id, "Legacy pilot", payload))
            db.execute("INSERT INTO characters(id,name,payload) VALUES (?,?,?)", ("broken", "Broken", "not json"))
            db.execute("PRAGMA user_version=1")
        with self.assertRaises(RuleError):
            CharacterStore(self.path, self.catalog)
        with closing(sqlite3.connect(self.path)) as db:
            self.assertEqual(db.execute("PRAGMA user_version").fetchone()[0], 1)
            self.assertEqual(db.execute("SELECT payload FROM characters WHERE id=?", (character_id,)).fetchone()[0], payload)

    def test_ability_rank_replacement_and_organoid_settings_survive_restart(self):
        character = replace(new_character(self.catalog), current_health=11, gold=230)
        character = learn_pilot_ability(character, "Small Expert", self.catalog)
        character = assign_pilot_ability(character, 2, "Small Expert", self.catalog)
        character = learn_pilot_ability(character, "Small Expert 4", self.catalog)
        character = learn_pilot_ability(character, "Sniper 4", self.catalog)
        character = replace(character, build=replace(character.build, organoid_color="White", organoid_level=40,
                                                       organoid_enabled=True, shield_adjustment=19))
        saved = self.store.save(character)
        loaded = CharacterStore(self.path, self.catalog).load(saved.id)
        self.assertEqual(loaded, saved)
        self.assertEqual(loaded.build.abilities, (None, None, "abilities:small_expert_4"))
        self.assertEqual(loaded.build.inactive_abilities, ("abilities:sniper_4",))
        self.assertEqual((loaded.current_health, loaded.gold, loaded.build.shield_adjustment), (11, 230, 19))
        self.assertEqual(calculate_stats(loaded.build, self.catalog)["shields"], 131)  # White level 40: 150, less 19 damage.
        with self.assertRaises(RuleError):
            learn_pilot_ability(loaded, "Small Expert", self.catalog)

    def test_disabled_organoid_settings_are_validated_before_save(self):
        original = self.store.save(new_character(self.catalog))
        for changes in ({"organoid_level": 41}, {"organoid_color": "Green"}):
            with self.assertRaises(RuleError):
                self.store.save(replace(original, build=replace(original.build, **changes)))
            self.assertEqual(self.store.load(original.id), original)

    def test_loose_and_attached_equipment_copies_survive_restart(self):
        character = acquire_equipment(new_character(self.catalog), "Particle Cannon", 2, self.catalog)
        copy_id = character.inventory[0].id
        character = equip_owned_equipment(character, "left", copy_id, self.catalog)
        saved = self.store.save(character)
        restarted = CharacterStore(self.path, self.catalog)
        loaded = restarted.load(saved.id)
        self.assertEqual(loaded, saved)
        self.assertEqual(loaded.owned_zoids[0].forms[0].equipment_ids[1], copy_id)
        unloaded = equip_owned_equipment(loaded, "left", None, self.catalog)
        restarted.save(unloaded)
        self.assertEqual(restarted.load(saved.id).inventory, saved.inventory)
        self.assertEqual(restarted.load(saved.id).build.equipment, (None,) * 4)

    def test_v3_equipment_migration_shares_across_forms_not_across_zoids(self):
        character = acquire_zoid(new_character(self.catalog), "Liger Zero", self.catalog)
        character = acquire_zoid(character, "Zero Jager (CAU)", self.catalog)
        values = asdict(character)
        values.pop("inventory")
        cannon = "armaments:particle_cannon"
        shield = "armaments:e_shield_generator"
        values["build"]["equipment"] = [None, cannon, None, None]
        values["build"]["equipment_active"] = [False, True, False, False]
        saber, liger = values["owned_zoids"]
        saber["forms"][0]["equipment"] = [None, cannon, None, None]
        saber["forms"][0]["equipment_active"] = [False, True, False, False]
        liger["forms"][0]["equipment"] = [None, cannon, cannon, None]
        liger["forms"][1]["equipment"] = [shield, cannon, None, None]
        for owner in values["owned_zoids"]:
            for form in owner["forms"]:
                form.pop("equipment_ids")
        payload = json.dumps({"save_version": 3, "data_version": "transport-split-v10", "character": values})
        with closing(sqlite3.connect(self.path)) as db, db:
            db.execute("INSERT INTO characters(id,name,payload) VALUES(?,?,?)", (character.id, character.name, payload))
            db.execute("PRAGMA user_version=3")
        migrated_store = CharacterStore(self.path, self.catalog)
        migrated = migrated_store.load(character.id)
        self.assertEqual(len(migrated.inventory), 4)
        self.assertEqual(sum(i.armament == cannon for i in migrated.inventory), 3)
        saber, liger = migrated.owned_zoids
        self.assertNotEqual(saber.forms[0].equipment_ids[1], liger.forms[0].equipment_ids[1])
        self.assertEqual(liger.forms[0].equipment_ids[1], liger.forms[1].equipment_ids[1])
        self.assertNotEqual(liger.forms[0].equipment_ids[1], liger.forms[0].equipment_ids[2])
        self.assertTrue(migrated.build.equipment_active[1])
        self.assertEqual(migrated.build.equipment[1], cannon)
        self.assertEqual(CharacterStore(self.path, self.catalog).load(character.id), migrated)

    def test_combat_conditions_and_resources_survive_restart_and_cau_switch(self):
        character = acquire_zoid(new_character(self.catalog), "Berserk Fury", self.catalog)
        character = acquire_zoid(character, "Sturm Fury (CAU)", self.catalog)
        owner = character.owned_zoids[-1].id
        character = switch_zoid(character, owner, catalog=self.catalog)
        character = acquire_equipment(character, "Particle Cannon", catalog=self.catalog)
        copy_id = character.inventory[0].id
        character = equip_owned_equipment(character, "left", copy_id, self.catalog)
        with patch("zoids_app.combat_controller.random.randint", side_effect=[3, 20, 7]):
            for slot in ("fixed_2", "fixed_2", "left"):
                character = weapon_action(character, slot, "use", catalog=self.catalog).character
        character = equip_owned_equipment(character, "left", None, self.catalog)
        character = replace(character, current_health=30, gold=20000, build=replace(character.build, shield_adjustment=19))
        saved = self.store.save(character)
        loaded = CharacterStore(self.path, self.catalog).load(saved.id)
        self.assertEqual(loaded, saved)
        self.assertEqual((loaded.current_health, loaded.gold, loaded.build.shield_adjustment), (30, 20000, 19))
        self.assertEqual(loaded.inventory[0].condition.heat, 1)
        self.assertEqual(loaded.inventory[0].condition.last_roll, 7)
        self.assertIsNone(loaded.build.equipment[1])
        switched = switch_zoid(loaded, owner, "zoids:sturm_fury_cau", self.catalog)
        condition = combat_snapshot(switched, self.catalog)[1]["fixed_2"]["condition"]
        self.assertEqual((condition.heat, condition.broken), (2, True))
        self.assertEqual(condition.last_roll, 20)

    def test_v4_migration_preserves_inventory_ids_and_initializes_conditions(self):
        character = acquire_equipment(new_character(self.catalog), "Particle Cannon", catalog=self.catalog)
        character = equip_owned_equipment(character, "left", character.inventory[0].id, self.catalog)
        values = asdict(character)
        for item in values["inventory"]:
            item.pop("condition")
        for owner in values["owned_zoids"]:
            owner.pop("weapon_conditions")
        payload = json.dumps({"save_version": 4, "data_version": "transport-split-v10", "character": values})
        with closing(sqlite3.connect(self.path)) as db, db:
            db.execute("INSERT INTO characters(id,name,payload) VALUES(?,?,?)", (character.id, character.name, payload))
            db.execute("PRAGMA user_version=4")
        loaded = CharacterStore(self.path, self.catalog).load(character.id)
        self.assertEqual(loaded, character)
        self.assertEqual(loaded.inventory[0].id, character.inventory[0].id)
        self.assertEqual(loaded.inventory[0].condition.heat, 0)
        self.assertFalse(loaded.inventory[0].condition.broken)

    def test_v5_migration_preserves_conditions_without_inventing_rolls(self):
        character = acquire_equipment(new_character(self.catalog), "Particle Cannon", catalog=self.catalog)
        character = equip_owned_equipment(character, "left", character.inventory[0].id, self.catalog)
        for _ in range(4):
            character = weapon_action(character, "left", "use", catalog=self.catalog).character
        character = weapon_action(character, "fixed_1", "use", catalog=self.catalog).character
        values = asdict(character)
        for item in values["inventory"]:
            item["condition"].pop("last_roll")
        for owner in values["owned_zoids"]:
            for weapon in owner["weapon_conditions"]:
                weapon["condition"].pop("last_roll")
        with closing(sqlite3.connect(self.path)) as db, db:
            db.execute("INSERT INTO characters(id,name,payload) VALUES(?,?,?)", (character.id, character.name,
                json.dumps({"save_version": 5, "data_version": "transport-split-v10", "character": values})))
            db.execute("PRAGMA user_version=5")
        with patch("zoids_app.combat_controller.random.randint") as roll:
            loaded = CharacterStore(self.path, self.catalog).load(character.id)
            self.assertEqual((loaded.inventory[0].condition.heat, loaded.inventory[0].condition.broken), (4, True))
            self.assertIsNone(loaded.inventory[0].condition.last_roll)
            self.assertIsNone(combat_snapshot(loaded, self.catalog)[1]["fixed_1"]["condition"].last_roll)
            self.assertEqual(loaded.inventory[0].id, character.inventory[0].id)
            roll.assert_not_called()
