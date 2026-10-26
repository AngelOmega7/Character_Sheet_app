from dataclasses import replace
import unittest

from zoids_app.attacks import range_band_for_distance
from zoids_app.catalog import Catalog
from zoids_app.combat import RuleError
from zoids_app.equipment import eligible_equipment, equip_item, equipment_template_name, resolved_equipment_name
from zoids_app.stats import CharacterBuild, calculate_stats
from zoids_app.tags import weapon_tags


class EquipmentRuleTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.catalog = Catalog()

    def test_fixed_shields_use_their_own_activation(self):
        for name, slot, hp in (("Shield Liger", 1, 150), ("Shield Liger DCS", 2, 150)):
            build = CharacterBuild(name, pilot_level=100)
            self.assertEqual(calculate_stats(build, self.catalog)["shields"], 0)
            for activated in range(4):
                flags = tuple(i == activated for i in range(4))
                result = calculate_stats(replace(build, fixed_active=flags), self.catalog)
                self.assertEqual(result["shields"], hp if activated == slot else 0)

    def test_fixed_removable_and_organoid_shields_stack_once(self):
        build = CharacterBuild("Shield Liger", pilot_level=100,
                               fixed_active=(True, True, True, True),
                               equipment=("E-Shield Generator",) * 4,
                               equipment_active=(True,) * 4,
                               organoid_enabled=True, organoid_color="White", organoid_level=5,
                               abilities=("Shield Master",))
        white = self.catalog.column(self.catalog.find("organoids", "5"), 22)
        self.assertEqual(calculate_stats(build, self.catalog)["shields"], 150 + 800 + white + 25)

    def test_only_white_generates_shields_using_organoid_level(self):
        for color in ("White", "Red", "Blue", "Black"):
            for level in (0, 5, 40):
                expected = self.catalog.column(self.catalog.find("organoids", str(level)), 22) if color == "White" else 0
                for pilot_level in (1, 100):
                    build = CharacterBuild("Saberlion", pilot_level=pilot_level, organoid_enabled=True,
                                           organoid_color=color, organoid_level=level)
                    self.assertEqual(calculate_stats(build, self.catalog)["shields"], expected)
                    self.assertEqual(calculate_stats(replace(build, organoid_enabled=False), self.catalog)["shields"], 0)

    def test_range_boundaries_and_short_ranges(self):
        for distance, maximum, expected in ((0, 500, "close"), (60, 500, "close"),
                                            (60.1, 500, "normal"), (250, 500, "normal"),
                                            (250.1, 500, "long"), (50, 100, "close"),
                                            (60, 100, "close"), (61, 100, "long"),
                                            (60, 120, "close"), (61, 120, "long")):
            self.assertEqual(range_band_for_distance(distance, maximum), expected)
        for distance, maximum in ((-1, 500), (0, 0)):
            with self.assertRaises(RuleError):
                range_band_for_distance(distance, maximum)

    def test_assist_eligibility_tracks_source_heading(self):
        heading = self.catalog.find("armaments", "ASSIST")["source"]["row"]
        items = self.catalog.tables["armaments"]["records"]
        expected = {r["id"] for r in items if r["source"]["row"] > heading and r["kind"] in {"record", "dynamic"}}
        self.assertEqual({r["id"] for r in eligible_equipment("Saberlion", "back", self.catalog)}, expected)
        self.assertEqual({r["id"] for r in eligible_equipment("Saberlion", "left", self.catalog)},
                         {r["id"] for r in items if r["kind"] in {"record", "dynamic"}})

    def test_equipping_validates_slot_and_resets_activation(self):
        build = CharacterBuild("Saberlion", equipment_active=(True,) * 4)
        for item in ("Particle Cannon", "Zoid equipment slot 1", "ASSIST", "WEAPONS"):
            with self.assertRaises(RuleError):
                equip_item(build, "back", item, self.catalog)
        equipped = equip_item(build, "back", "E-Shield Generator", self.catalog)
        self.assertEqual(equipped.equipment[0], "armaments:e_shield_generator")
        self.assertFalse(equipped.equipment_active[0])
        for item in ("Particle Cannon", "Zoid equipment slot 1", "E-Shield Generator"):
            self.assertIsNotNone(equip_item(build, "left", item, self.catalog).equipment[1])
        self.assertIsNone(equip_item(equipped, "back", None, self.catalog).equipment[0])
        with self.assertRaises(RuleError):
            equip_item(build, "unknown", None, self.catalog)

    def test_zoid_specific_equipment_names_resolve_for_their_zoid(self):
        for zoid in ("Command Wolf", "Zaber Fang", "Zaber Fang RS"):
            with self.subTest(zoid=zoid):
                self.assertEqual(resolved_equipment_name("armaments:zoid_equipment_slot_1", zoid, self.catalog),
                                 "Double Beam Cannon")
        self.assertEqual(resolved_equipment_name("armaments:zoid_equipment_slot_4", "Shadow Fox", self.catalog),
                         "Optical Camouflage")
        self.assertEqual(resolved_equipment_name("armaments:zoid_equipment_slot_1", "Saberlion", self.catalog),
                         "Zoid equipment slot 5")
        self.assertEqual(resolved_equipment_name("armaments:particle_cannon", "Command Wolf", self.catalog),
                         "Particle Cannon")

    def test_generic_equipment_templates_display_as_slots_five_through_eight(self):
        for source_slot in range(1, 5):
            record = self.catalog.find("armaments", f"armaments:zoid_equipment_slot_{source_slot}")
            with self.subTest(source_slot=source_slot):
                self.assertEqual(equipment_template_name(record), f"Zoid equipment slot {source_slot + 4}")

    def test_command_wolf_rifle_tags_and_demolitionist_tracking(self):
        zoid = self.catalog.find("zoids", "Command Wolf IS")
        tags = weapon_tags(self.catalog.column(zoid, 33))
        self.assertTrue({"ranged", "bullet"} <= tags)
        self.assertNotIn("piercing", tags)
        self.assertEqual(self.catalog.find("feats", "Demolitionist")["handling"], "player_managed")
