import unittest

from tools.convert_reference_data import DICE_DAMAGE, flatten_damage
from zoids_app.catalog import Catalog


class DamageConversionTests(unittest.TestCase):
    def test_numeric_damage_variants(self):
        for source, expected in (("18d10", 180), ("18D10 explosive", 180), (" 12D10 ", 120), ("3 d 12", 36), ("Shoots three bursts of 3D10 ", 30)):
            with self.subTest(source=source):
                self.assertEqual(flatten_damage(source, numeric=True), expected)

    def test_prose_retains_damage_type_and_shot_count(self):
        self.assertEqual(flatten_damage("Shoots three bursts of 3D10 piercing"), "Shoots three bursts of 30 piercing")
        self.assertEqual(flatten_damage("5D8 piercing and 2d6 energy"), "40 piercing and 12 energy")

    def test_existing_flat_values_are_unchanged(self):
        for value in (180, None, "180", "A shield blocks 200 damage"):
            self.assertEqual(flatten_damage(value, numeric=True), value)

    def test_ambiguous_numeric_fields_are_not_silently_collapsed(self):
        with self.assertRaises(ValueError):
            flatten_damage("2d6 + 3d10", numeric=True)

    def test_live_weapon_catalogs_contain_no_legacy_dice_terms(self):
        catalog = Catalog()
        for dataset in ("zoids", "armaments"):
            for record in catalog.tables[dataset]["records"]:
                for field, value in record["fields"].items():
                    with self.subTest(record=record["id"], field=field):
                        if isinstance(value, str) and not value.startswith(("http://", "https://")):
                            self.assertIsNone(DICE_DAMAGE.search(value))
        notes = catalog.find("zoids", "Shadow Fox")["damage_notes"]
        self.assertIn("Shoots three bursts of 30", notes.values())


if __name__ == "__main__":
    unittest.main()
