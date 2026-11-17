from dataclasses import replace
import re
import unittest

from tools.update_concealment import revise_concealment
from zoids_app.catalog import Catalog
from zoids_app.characters import acquire_zoid, new_character, validate_character
from zoids_app.combat_controller import start_turn
from zoids_app.stats import CharacterBuild, Upgrades, calculate_stats


class OrganoidAndConcealmentTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.catalog = Catalog()

    def test_mental_adds_to_ept_only_while_organoid_is_active(self):
        for color in ("White", "Red", "Blue", "Black"):
            for mental in (0, 7):
                with self.subTest(color=color, mental=mental):
                    build = CharacterBuild("Command Wolf", mental=mental, organoid_color=color,
                                           organoid_level=10, upgrades=Upgrades(ept=2))
                    baseline = calculate_stats(build, self.catalog)
                    active = calculate_stats(replace(build, organoid_enabled=True), self.catalog)
                    self.assertEqual(baseline["energy_recharge"], self.catalog.find("zoids", "Command Wolf")["energy_recharge"] + 2)
                    self.assertEqual(active["energy_recharge"], baseline["energy_recharge"] + mental)

    def test_start_turn_uses_mental_bonus_and_still_caps_at_maximum(self):
        c = acquire_zoid(new_character(), "Command Wolf", self.catalog)
        c = validate_character(replace(c, current_energy=0, build=replace(c.build,
            mental=7, organoid_color="Red", organoid_level=10, organoid_enabled=True,
            upgrades=Upgrades(ept=2))), self.catalog)
        stats = calculate_stats(c.build, self.catalog)
        self.assertEqual(start_turn(c, self.catalog).character.current_energy, stats["energy_recharge"])
        nearly_full = replace(c, current_energy=stats["energy"] - 1)
        self.assertEqual(start_turn(nearly_full, self.catalog).character.current_energy, stats["energy"])

    def test_all_smoke_and_invisibility_effects_use_targeting_rule(self):
        descriptions = []
        for dataset in ("zoids", "transports", "armaments"):
            for record in self.catalog.tables[dataset]["records"]:
                for key, text in record["fields"].items():
                    if key and key.startswith("effect") and isinstance(text, str) and re.search(r"smoke|invisib", text, re.I):
                        descriptions.append(text)
                        with self.subTest(record=record["name"], field=key):
                            self.assertNotRegex(text.casefold(), r"disadva[n]?tage")
                            self.assertIn("cannot be targeted by attacks, but can still be hit by AoE attacks", text)
                            self.assertEqual(revise_concealment(text), text)
        self.assertEqual(len(descriptions), 19)

    def test_fixed_and_dynamic_effects_resolve_and_unrelated_disadvantage_is_preserved(self):
        build = CharacterBuild("Shadow Fox", equipment=(None, None, None, "armaments:zoid_equipment_slot_4"))
        stats = calculate_stats(build, self.catalog)
        for index in (1, 7):
            self.assertIn("cannot be targeted by attacks", stats["weapons"][index]["effect"])
        text = "Launch sound waves. Opponents become disoriented and have disadvantage on attack rolls."
        self.assertEqual(revise_concealment(text), text)
        self.assertIn("Lasts six turns", self.catalog.find("armaments", "Enhanced Optical Camouflage")["fields"]["effect"])
