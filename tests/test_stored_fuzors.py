"""Retain sold FUZOR identities/upgrades without bypassing rebuild recipes."""
from dataclasses import replace
import json
from pathlib import Path
import tempfile
import unittest

from zoids_app.catalog import Catalog
from zoids_app.characters import acquire_zoid, new_character, set_upgrades, validate_character
from zoids_app.combat import RuleError
from zoids_app.commerce import purchase_zoid, quote_purchase, sell_zoid, set_known_design
from zoids_app.stats import Upgrades
from zoids_app.storage import CharacterStore
from zoids_app.transport import load_zoid, select_transport


class StoredFuzorTests(unittest.TestCase):
    def setUp(self):
        self.catalog = Catalog()

    def fused(self):
        c = replace(new_character(self.catalog), starter_pending=False)
        for name in ("Leo Blaze", "Unenlagia"):
            c = acquire_zoid(c, name, self.catalog)
        c = set_known_design(c, "2-Arm Lizard", catalog=self.catalog)
        c = self.buy(c)
        return set_upgrades(c, Upgrades(speed=3, reaction=2, defense=1, capacity=4,
                                       damage=(2, 0, 0, 0), to_hit=(3, 0, 0, 0)), self.catalog)

    def buy(self, c, stored=None, **kwargs):
        quote = quote_purchase(c, "2-Arm Lizard", stored_fuzor_id=stored, catalog=self.catalog)
        return purchase_zoid(c, quote, catalog=self.catalog, **kwargs)

    def test_retained_identity_and_all_upgrades_survive_export_import_and_rebuild(self):
        fused = self.fused()
        identity = fused.active_zoid_id
        sold = sell_zoid(fused, identity, self.catalog, retain_fuzor=True)
        self.assertEqual([s.id for s in sold.stored_fuzors], [identity])
        self.assertNotIn(identity, {o.id for o in sold.owned_zoids})
        component_ids = {o.id for o in sold.owned_zoids}
        with tempfile.TemporaryDirectory() as directory:
            store = CharacterStore(Path(directory) / "stored.sqlite3", self.catalog)
            store.save(sold)
            imported = store.import_character(store.export_character(sold.id))
            for c in (store.load(sold.id), store.load(imported.id)):
                rebuilt = self.buy(c, identity)
                self.assertEqual(rebuilt.active_zoid_id, identity)
                self.assertEqual(rebuilt.build.upgrades, fused.build.upgrades)
                self.assertEqual(rebuilt.stored_fuzors, ())
                self.assertEqual(len(rebuilt.owned_zoids), 1)
                self.assertEqual({o.id for o in rebuilt.owned_zoids[0].fusion_components}, component_ids)
                self.assertEqual(rebuilt.gold, sold.gold)
                self.assertEqual(sell_zoid(rebuilt, identity, self.catalog, retain_fuzor=True).stored_fuzors,
                                 sold.stored_fuzors)

    def test_retention_is_optional_and_fresh_build_does_not_use_saved_upgrades(self):
        fused = self.fused()
        discarded = sell_zoid(fused, fused.active_zoid_id, self.catalog)
        self.assertEqual(discarded.stored_fuzors, ())
        self.assertEqual(self.buy(discarded).build.upgrades, Upgrades())
        kept = sell_zoid(fused, fused.active_zoid_id, self.catalog, retain_fuzor=True)
        fresh = self.buy(kept)
        self.assertNotEqual(fresh.active_zoid_id, fused.active_zoid_id)
        self.assertEqual(fresh.build.upgrades, Upgrades())
        self.assertEqual(fresh.stored_fuzors, kept.stored_fuzors)
        with self.assertRaises(RuleError):
            sell_zoid(kept, kept.active_zoid_id, self.catalog, retain_fuzor=True)

    def test_multiple_retained_copies_remain_independent(self):
        first = self.fused()
        sold = sell_zoid(first, first.active_zoid_id, self.catalog, retain_fuzor=True)
        second = set_upgrades(self.buy(sold), Upgrades(speed=1, damage=(4, 0, 0, 0)), self.catalog)
        sold = sell_zoid(second, second.active_zoid_id, self.catalog, retain_fuzor=True)
        self.assertEqual(len(sold.stored_fuzors), 2)
        rebuilt = self.buy(sold, first.active_zoid_id)
        self.assertEqual(rebuilt.build.upgrades, first.build.upgrades)
        self.assertEqual([s.id for s in rebuilt.stored_fuzors], [second.active_zoid_id])
        sold = sell_zoid(rebuilt, rebuilt.active_zoid_id, self.catalog, retain_fuzor=True)
        rebuilt = self.buy(sold, second.active_zoid_id)
        self.assertEqual(rebuilt.build.upgrades, second.build.upgrades)
        self.assertEqual([s.id for s in rebuilt.stored_fuzors], [first.active_zoid_id])

    def test_rebuild_requires_components_and_rejects_wrong_spent_or_stale_entry(self):
        fused = self.fused()
        identity = fused.active_zoid_id
        sold = sell_zoid(fused, identity, self.catalog, retain_fuzor=True)
        missing = sell_zoid(sold, sold.owned_zoids[-1].id, self.catalog)
        with self.assertRaises(RuleError):
            self.buy(missing, identity)
        with self.assertRaises(RuleError):
            quote_purchase(sold, "Griffin", stored_fuzor_id=identity, catalog=self.catalog)
        quote = quote_purchase(sold, "2-Arm Lizard", stored_fuzor_id=identity, catalog=self.catalog)
        changed = replace(sold, stored_fuzors=(replace(sold.stored_fuzors[0], frame=Upgrades(speed=5)),))
        with self.assertRaises(RuleError):
            purchase_zoid(changed, quote, catalog=self.catalog)
        rebuilt = purchase_zoid(sold, quote, catalog=self.catalog)
        with self.assertRaises(RuleError):
            purchase_zoid(rebuilt, quote, override=True, catalog=self.catalog)

    def test_stored_identities_cannot_be_owned_loaded_or_duplicated(self):
        fused = self.fused()
        sold = sell_zoid(fused, fused.active_zoid_id, self.catalog, retain_fuzor=True)
        stored = sold.stored_fuzors[0]
        with self.assertRaises(RuleError):
            validate_character(replace(fused, stored_fuzors=(stored,)), self.catalog)
        with self.assertRaises(RuleError):
            validate_character(replace(sold, stored_fuzors=(stored, stored)), self.catalog)
        with self.assertRaises(RuleError):
            validate_character(replace(sold, stored_fuzors=(replace(stored, zoid="zoids:leo_blaze"),)), self.catalog)
        with self.assertRaises(RuleError):
            load_zoid(select_transport(sold, "Whale King", self.catalog), stored.id, catalog=self.catalog)

    def test_v9_import_and_empty_roster_with_stored_override_fuzor(self):
        fused = self.fused()
        with tempfile.TemporaryDirectory() as directory:
            store = CharacterStore(Path(directory) / "legacy.sqlite3", self.catalog)
            store.save(fused)
            document = json.loads(store.export_character(fused.id))
            document["save_version"] = 9
            del document["character"]["stored_fuzors"]
            migrated = store.import_character(json.dumps(document))
            self.assertEqual(migrated.stored_fuzors, ())
            self.assertEqual(migrated.owned_zoids, fused.owned_zoids)
            # A retained override build can leave the pilot with no playable chassis.
            c = replace(new_character(self.catalog), starter_pending=False)
            c = self.buy(c, override=True)
            c = set_upgrades(c, Upgrades(speed=2), self.catalog)
            identity = c.active_zoid_id
            sold = sell_zoid(c, identity, self.catalog, retain_fuzor=True)
            self.assertEqual(sold.owned_zoids, ())
            store.save(sold)
            loaded = store.load(sold.id)
            self.assertEqual(loaded, sold)
            rebuilt = self.buy(loaded, identity, override=True)
            self.assertEqual(rebuilt.active_zoid_id, identity)
            self.assertEqual(rebuilt.build.upgrades.speed, 2)
            self.assertEqual(rebuilt.owned_zoids[0].fusion_components, ())
