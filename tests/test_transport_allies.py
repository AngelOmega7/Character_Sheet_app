from contextlib import closing
from dataclasses import asdict, replace
import json
from pathlib import Path
import sqlite3
import tempfile
import unittest

from zoids_app.catalog import Catalog
from zoids_app.characters import acquire_zoid, new_character, validate_character
from zoids_app.combat import RuleError
from zoids_app.storage import CharacterStore, SAVE_VERSION
from zoids_app.transport import load_ally, load_zoid, select_transport, unload_ally


class TransportAllyTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.catalog = Catalog()

    def test_allies_and_owned_zoids_share_capacity(self):
        c = acquire_zoid(new_character(), "Command Wolf", self.catalog)
        c = select_transport(c, "Gustav", self.catalog)
        c = load_ally(c, self.catalog)
        c = load_zoid(c, c.active_zoid_id, catalog=self.catalog)
        self.assertEqual(c.loaded_allies, (1,))
        with self.assertRaises(RuleError):
            load_ally(c, self.catalog)
        c = load_zoid(c, c.active_zoid_id, False, self.catalog)
        c = load_ally(c, self.catalog)
        self.assertEqual(c.loaded_allies, (1, 2))
        with self.assertRaises(RuleError):
            load_zoid(c, c.active_zoid_id, catalog=self.catalog)
        self.assertEqual(validate_character(c, self.catalog), c)

    def test_unloading_keeps_other_names_and_reuses_free_number(self):
        c = select_transport(new_character(), "Gustav", self.catalog)
        c = load_ally(load_ally(c, self.catalog), self.catalog)
        c = unload_ally(c, 1, self.catalog)
        self.assertEqual(c.loaded_allies, (2,))
        self.assertEqual(load_ally(c, self.catalog).loaded_allies, (2, 1))
        with self.assertRaises(RuleError):
            unload_ally(c, 1, self.catalog)

    def test_transport_selection_clears_allies_only_when_changed(self):
        with self.assertRaises(RuleError):
            load_ally(new_character(), self.catalog)
        c = load_ally(select_transport(new_character(), "Gustav", self.catalog), self.catalog)
        self.assertEqual(select_transport(c, "Gustav", self.catalog).loaded_allies, (1,))
        self.assertEqual(select_transport(c, "Hover Cargo", self.catalog).loaded_allies, ())
        self.assertEqual(select_transport(c, None, self.catalog).loaded_allies, ())

    def test_invalid_saved_placeholders_are_rejected(self):
        c = select_transport(new_character(), "Gustav", self.catalog)
        for allies in ((0,), (-1,), (True,), ("1",), (1, 1), (1, 2, 3)):
            with self.subTest(allies=allies), self.assertRaises(RuleError):
                validate_character(replace(c, loaded_allies=allies), self.catalog)

    def test_save_export_import_and_version_14_migration(self):
        c = load_ally(select_transport(new_character(), "Gustav", self.catalog), self.catalog)
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "save.db"
            store = CharacterStore(path, self.catalog)
            c = store.save(c)
            self.assertEqual(store.load(c.id), c)
            imported = store.import_character(store.export_character(c.id))
            self.assertEqual(imported.loaded_allies, (1,))
            old = asdict(replace(c, loaded_allies=()))
            old.pop("loaded_allies")
            with closing(sqlite3.connect(path)) as db, db:
                db.execute("DELETE FROM characters")
                db.execute("INSERT INTO characters(id, name, payload) VALUES (?, ?, ?)",
                    (c.id, c.name, json.dumps({"save_version": 14, "character": old})))
                db.execute("PRAGMA user_version = 14")
            store = CharacterStore(path, self.catalog)
            self.assertEqual(store.load(c.id).loaded_allies, ())
            with closing(sqlite3.connect(path)) as db:
                self.assertEqual(db.execute("PRAGMA user_version").fetchone()[0], SAVE_VERSION)
