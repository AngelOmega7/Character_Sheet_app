from contextlib import closing
from dataclasses import asdict
import json
from pathlib import Path
import sqlite3
import tempfile
import unittest

from zoids_app.catalog import Catalog
from zoids_app.characters import acquire_zoid, new_character
from zoids_app.combat import RuleError
from zoids_app.storage import CharacterStore, SAVE_VERSION
from test_support import established_character as new_character


class RetirementTests(unittest.TestCase):
    def setUp(self):
        self.catalog = Catalog()
        self.directory = tempfile.TemporaryDirectory()
        self.addCleanup(self.directory.cleanup)
        self.path = Path(self.directory.name) / "characters.sqlite3"

    def test_blox_zoids_and_five_abilities_are_restored(self):
        zoids = self.catalog.tables["zoids"]
        self.assertEqual(len(zoids["records"]), 154)
        self.assertEqual(sum(r["fields"]["type"].strip().casefold() == "blox" for r in zoids["records"]), 14)
        for name, expected in (("Buster Eagle", "Flying"), ("Fire Phoenix", "Flying"),
                               ("Jet Falcon", "Flying"), ("Zero Falcon", "Liger"), ("Zero Phoenix", "Liger")):
            self.assertEqual(self.catalog.find("zoids", name)["fields"]["type"], expected)
        retired = [r for r in zoids["excluded_rows"] if r["reason"] == "Owner retired BLOX Zoids"]
        self.assertEqual(retired, [])
        for name in ("BLOXType 1", "BLOX Type 2", "BLOX Type 3", "BLOX Type 4", "BLOX Type 5"):
            self.assertEqual(self.catalog.find("abilities", name)["eligible_types"], ["BLOX"])
        self.assertEqual(sum(r["kind"] == "record" for r in self.catalog.tables["abilities"]["records"]), 165)

    def test_transports_have_separate_reference_catalog_and_provenance(self):
        records = self.catalog.tables["transports"]["records"]
        self.assertEqual({r["name"] for r in records}, {"Hover Cargo", "Gustav", "Whale King", "Dragoon Nest"})
        for record in records:
            with self.assertRaises(RuleError):
                self.catalog.find("zoids", record["name"])
            self.assertTrue(record["id"].startswith("transports:"))
            self.assertEqual(record["source"]["sheet"], "Zoid List")
            self.assertEqual(self.catalog.column(record, 1), record["fields"]["name"])
            self.assertNotIn("ownership_base_id", record)

    def old_pilot(self, removed_id, survivor=False):
        character = new_character(self.catalog)
        if survivor:
            character = acquire_zoid(character, "Liger Zero", self.catalog)
        values = asdict(character)
        values.pop("archived_content")
        values["gold"] = 1234
        values["current_health"] = 17
        values["build"]["zoid"] = removed_id
        values["build"]["abilities"] = ["abilities:wimp", "abilities:sniper_4"]
        values["build"]["inactive_abilities"] = ["abilities:slowpoke"]
        values["build"]["upgrades"]["speed"] = 3
        owned = values["owned_zoids"][0]
        owned["base_zoid"] = removed_id
        owned["active_form"] = removed_id
        owned["forms"][0]["zoid"] = removed_id
        owned["forms"][0]["equipment"] = [None, "armaments:particle_cannon", None, None]
        owned["current_health"] = 17
        owned["frame"]["speed"] = 3
        owned["weapons"] = [{"weapon_id": removed_id + ":weapon:legacy_claw", "damage": 4, "to_hit": 2}]
        return values

    def write_old(self, values, version):
        with closing(sqlite3.connect(self.path)) as db, db:
            db.execute("CREATE TABLE characters(id TEXT PRIMARY KEY,name TEXT NOT NULL,payload TEXT NOT NULL,updated_at TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%fZ','now')))")
            db.execute("INSERT INTO characters VALUES(?,?,?,?)", (values["id"], values["name"],
                json.dumps({"save_version": version, "data_version": "owned-zoids-v9", "character": values}), "2026-01-01"))
            db.execute(f"PRAGMA user_version={version}")

    def test_v2_retirement_preserves_archive_and_selects_surviving_zoid(self):
        old = self.old_pilot("zoids:hover_cargo", survivor=True)
        removed = old["owned_zoids"][0]
        self.write_old(old, 2)
        store = CharacterStore(self.path, self.catalog)
        loaded = store.load(old["id"])
        self.assertEqual(loaded.build.zoid, "zoids:liger_zero")
        self.assertEqual(len(loaded.owned_zoids), 1)
        self.assertEqual(loaded.gold, 1234)
        self.assertEqual(loaded.build.abilities, (None, "abilities:sniper_4"))
        self.assertEqual(loaded.build.inactive_abilities, ())
        archived = next(a for a in loaded.archived_content if a["kind"] == "owned_zoid")
        self.assertEqual(archived["record"], json.loads(json.dumps(removed)))
        self.assertEqual(loaded.build.upgrades.speed, 0)
        store.save(loaded)
        self.assertEqual(store.load(loaded.id), loaded)

    def test_transport_only_pilot_can_save_and_obtain_a_playable_zoid(self):
        old = self.old_pilot("zoids:gustav")
        self.write_old(old, 2)
        store = CharacterStore(self.path, self.catalog)
        loaded = store.load(old["id"])
        self.assertEqual(loaded.owned_zoids, ())
        self.assertEqual(loaded.active_zoid_id, "")
        self.assertEqual(loaded.build.zoid, "")
        self.assertEqual(loaded.gold, 1234)
        self.assertTrue(any(a["reason"] == "Moved to Transport catalog" for a in loaded.archived_content))
        store.save(loaded)
        self.assertEqual(CharacterStore(self.path, self.catalog).load(loaded.id), loaded)
        acquired = acquire_zoid(loaded, "Liger Zero", self.catalog)
        self.assertEqual(acquired.build.zoid, "zoids:liger_zero")
        self.assertEqual(len(acquired.owned_zoids), 1)
        self.assertEqual(acquired.archived_content, loaded.archived_content)
        self.assertEqual(acquired.build.upgrades.speed, 0)

    def test_v1_retired_zoid_migrates_without_granting_a_replacement(self):
        old = self.old_pilot("zoids:hover_cargo")
        old.pop("owned_zoids")
        old.pop("active_zoid_id")
        self.write_old(old, 1)
        loaded = CharacterStore(self.path, self.catalog).load(old["id"])
        self.assertEqual(loaded.owned_zoids, ())
        archived = next(a for a in loaded.archived_content if a["kind"] == "legacy_zoid")
        self.assertEqual(archived["record"]["build"], json.loads(json.dumps(old["build"])))
        self.assertEqual(archived["record"]["current_health"], 17)
        with closing(sqlite3.connect(self.path)) as db:
            self.assertEqual(db.execute("PRAGMA user_version").fetchone()[0], SAVE_VERSION)
