"""Frame pricing, attack bonuses, and migration of real ownership histories."""
from contextlib import closing
from dataclasses import asdict, replace
import json
from pathlib import Path
import sqlite3
import tempfile
import unittest

from zoids_app.catalog import Catalog
from zoids_app.characters import acquire_zoid, set_upgrades, switch_zoid
from zoids_app.combat import RuleError
from zoids_app.commerce import change_upgrade
from zoids_app.stats import CharacterBuild, Upgrades, calculate_stats
from zoids_app.storage import CharacterStore, SAVE_VERSION
from test_support import established_character


class FrameUpgradeTests(unittest.TestCase):
    def setUp(self):
        self.catalog = Catalog()

    def test_progressive_prices_limits_refunds_and_rejected_weapon_tracks(self):
        original = replace(established_character(self.catalog), gold=1000000)
        for track in ("speed", "reaction", "defense", "capacity", "accuracy", "armor"):
            with self.subTest(track=track):
                c = original
                for rank in range(1, 8 if track in ("defense", "accuracy") else 6):
                    old_gold = c.gold
                    c = change_upgrade(c, track, 1, catalog=self.catalog)
                    self.assertEqual(old_gold - c.gold, 5000 * rank + (20000 if track == "armor" else 0))
                    self.assertEqual(getattr(c.build.upgrades, track), rank)
                if track not in ("defense", "accuracy"):
                    with self.assertRaises(RuleError):
                        change_upgrade(c, track, 1, catalog=self.catalog)
                while getattr(c.build.upgrades, track):
                    c = change_upgrade(c, track, -1, catalog=self.catalog)
                self.assertEqual(c.gold, original.gold)
                with self.assertRaises(RuleError):
                    change_upgrade(c, track, -1, catalog=self.catalog)
        for track in ("damage", "to_hit"):
            with self.assertRaises(RuleError):
                change_upgrade(original, track, 1, 0, self.catalog)
        with self.assertRaises(RuleError):
            change_upgrade(replace(original, gold=24999), "armor", 1, catalog=self.catalog)
        for points in (-1, True, 1.5):
            with self.assertRaises(RuleError):
                Upgrades(accuracy=points)

    def test_armor_and_accuracy_are_flat_after_percentage_bonuses(self):
        build = CharacterBuild("Saberlion", pilot_level=20, abilities=("Small Expert",),
                               equipment=("Particle Cannon", None, None, None),
                               organoid_enabled=True, organoid_color="Black", organoid_level=10)
        before = calculate_stats(build, self.catalog)
        after = calculate_stats(replace(build, upgrades=Upgrades(accuracy=9, armor=3)), self.catalog)
        self.assertEqual(after["current"]["armor"], before["current"]["armor"] + 3)
        for a, b in zip(after["weapons"], before["weapons"]):
            self.assertEqual(a["to_hit"] - b["to_hit"], 9 if b["base_damage"] is not None else 0)
            self.assertEqual(a["damage_bonus"], b["damage_bonus"])
            self.assertEqual(a["damage_upgrade"], 0)

    def legacy_character(self):
        c = acquire_zoid(established_character(self.catalog), "Liger Zero", self.catalog)
        owner = c.owned_zoids[-1].id
        c = acquire_zoid(c, "Zero Jager (CAU)", self.catalog, host_id=owner)
        c = switch_zoid(c, owner, catalog=self.catalog)
        c = set_upgrades(c, Upgrades(speed=2, damage=(2, 0, 3, 0), to_hit=(1, 0, 2, 0)), self.catalog)
        c = switch_zoid(c, owner, "zoids:zero_jager_cau", self.catalog)
        c = set_upgrades(c, replace(c.build.upgrades, damage=(2, 4, 0, 3)), self.catalog)
        values = asdict(c)
        # 2+1 and 3+2 on shared weapons, plus 4 on a Jager-only weapon = 12.
        # The active build repeats those values and must not be counted again.
        inactive = values["owned_zoids"][0]
        inactive["weapons"][0].update(damage=1, to_hit=2)
        return c, values

    def test_v10_database_and_import_convert_once_per_owned_chassis(self):
        original, values = self.legacy_character()
        payload = json.dumps({"save_version": 10, "character": values})
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "characters.sqlite3"
            with closing(sqlite3.connect(path)) as db, db:
                db.execute("CREATE TABLE characters (id TEXT PRIMARY KEY, name TEXT, payload TEXT, updated_at TEXT)")
                db.execute("INSERT INTO characters VALUES (?, ?, ?, ?)", (original.id, original.name, payload, "unchanged"))
                db.execute("PRAGMA user_version = 10")
            store = CharacterStore(path, self.catalog)
            loaded = store.load(original.id)
            self.assertEqual(loaded.build.upgrades.accuracy, 12)
            self.assertEqual(loaded.build.upgrades.speed, 2)
            self.assertEqual(loaded.gold, original.gold)
            self.assertEqual(loaded.current_health, original.current_health)
            self.assertEqual(loaded.owned_zoids[0].frame.accuracy, 3)
            for owned in loaded.owned_zoids:
                self.assertTrue(all(w.damage == w.to_hit == 0 for w in owned.weapons))
            base = switch_zoid(loaded, loaded.active_zoid_id, "zoids:liger_zero", self.catalog)
            self.assertEqual(base.build.upgrades.accuracy, 12)
            self.assertEqual(store.save(loaded), loaded)
            self.assertEqual(CharacterStore(path, self.catalog).load(original.id), loaded)
            imported = store.import_character(payload)
            self.assertEqual(imported.build.upgrades.accuracy, 12)
            self.assertEqual(store.import_character(store.export_character(imported.id)).build.upgrades.accuracy, 12)
            with closing(sqlite3.connect(path)) as db:
                self.assertEqual(db.execute("PRAGMA user_version").fetchone()[0], SAVE_VERSION)

    def test_consumed_components_and_stored_fuzors_convert_independently(self):
        c = acquire_zoid(established_character(self.catalog), "2-Arm Lizard", self.catalog)
        fuzor = c.owned_zoids[-1]
        component = acquire_zoid(established_character(self.catalog), "Leo Blaze", self.catalog).owned_zoids[-1]
        values = asdict(c)
        nested = asdict(component)
        key = self.catalog.find("zoids", "Leo Blaze")["fixed_weapon_ids"][0]
        nested["weapons"] = [{"weapon_id": key, "damage": 2, "to_hit": 3}]
        values["owned_zoids"][-1]["fusion_components"] = [nested]
        key = self.catalog.find("zoids", "2-Arm Lizard")["fixed_weapon_ids"][0]
        values["stored_fuzors"] = [{"id": "stored-fuzor", "zoid": fuzor.base_zoid,
                                    "frame": asdict(Upgrades(speed=1)),
                                    "weapons": [{"weapon_id": key, "damage": 4, "to_hit": 3}]}]
        with tempfile.TemporaryDirectory() as directory:
            store = CharacterStore(Path(directory) / "characters.sqlite3", self.catalog)
            loaded = store.import_character(json.dumps({"save_version": 10, "character": values}))
            self.assertEqual(loaded.owned_zoids[-1].fusion_components[0].frame.accuracy, 5)
            self.assertEqual(loaded.stored_fuzors[0].frame.accuracy, 7)
            self.assertEqual(loaded.stored_fuzors[0].frame.speed, 1)
            self.assertEqual(store.load(loaded.id), loaded)

    def test_invalid_legacy_points_roll_back_database_migration(self):
        original, values = self.legacy_character()
        values["owned_zoids"][0]["weapons"][0]["damage"] = -1
        payload = json.dumps({"save_version": 10, "character": values})
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "characters.sqlite3"
            with closing(sqlite3.connect(path)) as db, db:
                db.execute("CREATE TABLE characters (id TEXT PRIMARY KEY, name TEXT, payload TEXT, updated_at TEXT)")
                db.execute("INSERT INTO characters VALUES (?, ?, ?, ?)", (original.id, original.name, payload, "unchanged"))
                db.execute("PRAGMA user_version = 10")
            with self.assertRaises(RuleError):
                CharacterStore(path, self.catalog)
            with closing(sqlite3.connect(path)) as db:
                self.assertEqual(db.execute("PRAGMA user_version").fetchone()[0], 10)
                self.assertEqual(db.execute("SELECT payload FROM characters").fetchone()[0], payload)
