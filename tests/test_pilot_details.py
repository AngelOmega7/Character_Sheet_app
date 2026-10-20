from contextlib import closing
from dataclasses import asdict, replace
import json
from pathlib import Path
import sqlite3
import tempfile
import unittest
from unittest.mock import patch

from zoids_app.catalog import Catalog
from zoids_app.characters import (PilotDetails, acquire_equipment, acquire_zoid, equip_owned_equipment,
    new_character, set_upgrades, switch_zoid, validate_character)
from zoids_app.combat import RuleError
from zoids_app.combat_controller import combat_snapshot, weapon_action
from zoids_app.stats import Upgrades, calculate_stats
from zoids_app.storage import CharacterStore, SAVE_VERSION
from test_support import established_character as new_character


class PilotDetailsTests(unittest.TestCase):
    def setUp(self):
        self.catalog = Catalog()
        self.directory = tempfile.TemporaryDirectory()
        self.addCleanup(self.directory.cleanup)
        self.path = Path(self.directory.name) / "characters.sqlite3"
        self.store = CharacterStore(self.path, self.catalog)

    def test_tracking_fields_and_feats_survive_switching_and_reload_without_stat_effects(self):
        character = acquire_zoid(new_character(self.catalog), "Liger Zero", self.catalog)
        character = acquire_zoid(character, "Zero Jager (CAU)", self.catalog)
        baseline = calculate_stats(character.build, self.catalog)
        details = PilotDetails(physical=-1, social=6, personality="Patient, curious",
            inventory_notes="Repair parts × 3\nMap and provisions", database_notes="Ruins survey\nPilot Ω",
            feats=("Phalanx Fire", None, "Demolitionist"))
        character = validate_character(replace(character, pilot_details=details), self.catalog)
        self.assertEqual(calculate_stats(character.build, self.catalog), baseline)
        self.assertEqual(character.pilot_details.feats, ("feats:phalanx_fire", None, "feats:demolitionist"))
        character = switch_zoid(character, character.owned_zoids[-1].id, "zoids:zero_jager_cau", self.catalog)
        saved = self.store.save(character)
        loaded = CharacterStore(self.path, self.catalog).load(saved.id)
        self.assertEqual(loaded, saved)
        self.assertEqual(loaded.pilot_details.inventory_notes, details.inventory_notes)
        self.assertEqual(loaded.pilot_details.personality, details.personality)

    def test_feats_do_not_automate_advantage_or_multi_weapon_venting(self):
        character = acquire_equipment(new_character(self.catalog), "Particle Cannon", 2, self.catalog)
        for slot, item in zip(("left", "right"), character.inventory):
            character = equip_owned_equipment(character, slot, item.id, self.catalog)
        character = replace(character, pilot_details=PilotDetails(feats=("Phalanx Fire", "Demolitionist")))
        with patch("zoids_app.combat_controller.random.randint", return_value=14) as roll:
            character = weapon_action(character, "left", "use", catalog=self.catalog).character
            character = weapon_action(character, "right", "use", catalog=self.catalog).character
            self.assertEqual(roll.call_count, 2)
            character = weapon_action(character, "left", "vent", catalog=self.catalog).character
            self.assertEqual(roll.call_count, 2)
        self.assertEqual([i.condition.heat for i in character.inventory], [0, 1])
        self.assertEqual([i.condition.last_roll for i in character.inventory], [14, 14])

    def test_invalid_tracking_values_cannot_overwrite_a_save(self):
        saved = self.store.save(new_character(self.catalog))
        invalid = (PilotDetails(physical=True), PilotDetails(social=1.5), PilotDetails(personality=None),
                   PilotDetails(feats=(None,) * 8), PilotDetails(feats=("Unknown feat",)))
        for details in invalid:
            with self.assertRaises(RuleError):
                self.store.save(replace(saved, pilot_details=details))
            self.assertEqual(self.store.load(saved.id), saved)

    def test_v6_migration_defaults_new_tracking_fields_without_changing_resources(self):
        character = replace(new_character(self.catalog), current_health=23, gold=55)
        with patch("zoids_app.combat_controller.random.randint", return_value=19):
            character = weapon_action(character, "fixed_1", "use", catalog=self.catalog).character
        values = asdict(character)
        values.pop("pilot_details")
        with closing(sqlite3.connect(self.path)) as db, db:
            db.execute("INSERT INTO characters(id,name,payload) VALUES(?,?,?)", (character.id, character.name,
                json.dumps({"save_version": 6, "data_version": "transport-split-v10", "character": values})))
            db.execute("PRAGMA user_version=6")
        loaded = CharacterStore(self.path, self.catalog).load(character.id)
        self.assertEqual(loaded, character)
        self.assertEqual(loaded.pilot_details, PilotDetails())
        self.assertEqual(combat_snapshot(loaded, self.catalog)[1]["fixed_1"]["condition"].last_roll, 19)

    def test_zaber_fang_migration_moves_killer_saber_upgrades_flags_and_roll(self):
        for version in (1, 6):
            with self.subTest(version=version):
                character = acquire_zoid(new_character(self.catalog), "Zaber Fang", self.catalog)
                character = switch_zoid(character, character.owned_zoids[-1].id, catalog=self.catalog)
                character = set_upgrades(character, Upgrades(speed=2, damage=(0, 0, 0, 2), to_hit=(0, 0, 0, 3)), self.catalog)
                with patch("zoids_app.combat_controller.random.randint", return_value=16):
                    character = weapon_action(character, "fixed_4", "use", catalog=self.catalog).character
                values = asdict(character)
                values.pop("pilot_details")
                values["build"]["upgrades"]["damage"] = [0, 0, 2, 0]
                values["build"]["upgrades"]["to_hit"] = [0, 0, 3, 0]
                values["build"]["fixed_active"] = [False, False, True, False]
                for owned in values["owned_zoids"]:
                    if owned["base_zoid"] == "zoids:zaber_fang":
                        owned["forms"][0]["fixed_active"] = [False, False, True, False]
                        owned["weapons"] = [w for w in owned["weapons"] if not w["weapon_id"].endswith(":laser_machine_gun")]
                if version == 1:
                    for key in ("owned_zoids", "active_zoid_id", "inventory", "archived_content"):
                        values.pop(key)
                with closing(sqlite3.connect(self.path)) as db, db:
                    db.execute("DELETE FROM characters")
                    db.execute("INSERT INTO characters(id,name,payload) VALUES(?,?,?)", (character.id, character.name,
                        json.dumps({"save_version": version, "data_version": "transport-split-v10", "character": values})))
                    db.execute(f"PRAGMA user_version={version}")
                loaded = CharacterStore(self.path, self.catalog).load(character.id)
                self.assertEqual(loaded.build.upgrades.damage, (0, 0, 0, 2))
                self.assertEqual(loaded.build.upgrades.to_hit, (0, 0, 0, 3))
                self.assertEqual(loaded.build.upgrades.speed, 2)
                self.assertEqual(loaded.build.fixed_active, (False, False, False, True))
                _, weapons = combat_snapshot(loaded, self.catalog)
                self.assertEqual(weapons["fixed_3"]["weapon"]["name"], "Laser Machine Gun")
                self.assertIsNone(weapons["fixed_3"]["condition"].last_roll)
                self.assertEqual(weapons["fixed_4"]["condition"].last_roll, 16 if version == 6 else None)
                self.assertEqual(CharacterStore(self.path, self.catalog).load(character.id), loaded)
                with closing(sqlite3.connect(self.path)) as db:
                    self.assertEqual(db.execute("PRAGMA user_version").fetchone()[0], SAVE_VERSION)
