from dataclasses import replace
from decimal import Decimal
import json
from pathlib import Path
import unittest

from zoids_app.catalog import Catalog
from zoids_app.combat import RuleError
from zoids_app.stats import CharacterBuild, Upgrades, calculate_stats, sheet_round, sheet_roundup


class StatsTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.catalog = Catalog()
        cls.example = CharacterBuild("Saberlion", mental=3, abilities=("Lion Type 1",))

    def calc(self, **changes):
        return calculate_stats(replace(self.example, **changes), self.catalog)

    def test_original_workbook_snapshot_parity(self):
        fixture = json.loads((Path(__file__).parent / "fixtures/saberlion_snapshot.json").read_text())
        build = CharacterBuild(**fixture["build"], upgrades=Upgrades(**fixture["upgrades"]))
        actual = calculate_stats(build, self.catalog)
        for key, expected in fixture["expected"].items():
            with self.subTest(key=key):
                if key == "weapon_to_hit":
                    self.assertEqual([w["to_hit"] for w in actual["weapons"]], expected)
                else:
                    self.assertEqual(actual[key], expected)
        self.assertEqual(actual["weapons"][0]["damage_bonus"], 20)

    def test_spreadsheet_rounding_ties_and_away_from_zero(self):
        self.assertEqual(sheet_round("2.5"), 3)
        self.assertEqual(sheet_round("-2.5"), -3)
        self.assertEqual(sheet_roundup("-2.01"), -3)
        self.assertEqual(sheet_roundup("2.01"), 3)

    def test_multiple_ranks_of_a_type_ability_are_rejected(self):
        with self.assertRaises(RuleError):
            self.calc(abilities=("Lion Type 1", "Lion Type 2"))
        self.assertEqual(self.calc(abilities=("Lion Type 2",))["effective_level"], 11)

    def test_single_size_bonus_applies(self):
        result = self.calc(abilities=("Lion Type 1", "Small Expert"))
        self.assertEqual(result["pilot"]["health"], 153)
        self.assertEqual(result["pilot"]["range"], 675)

    def test_size_percentage_applies_to_all_weapon_slots_before_flat_upgrades(self):
        result = self.calc(abilities=("Lion Type 1", "Small Expert"), equipment=("Particle Cannon", None, None, None), upgrades=Upgrades(to_hit=(2, 0, 0, 0)))
        self.assertEqual(result["weapons"][0]["to_hit"], 25)  # ROUND(17 * 1.35) + 2
        self.assertEqual(result["weapons"][4]["to_hit"], 22)  # ROUND(16 * 1.35)

    def test_size_categories_match_exactly_and_support_explicit_lists(self):
        for ability in ("Extra Large Expert", "Large Large Expert", "Large Large Over Expert"):
            with self.subTest(ability=ability):
                result = self.calc(zoid="Liger Zero", pilot_level=15, abilities=(ability,))
                self.assertEqual(result["size_bonus"], 0)
        self.assertEqual(self.calc(zoid="Liger Zero", pilot_level=15, abilities=("Large Expert",))["size_bonus"], Decimal("0.1"))
        self.assertEqual(self.calc(abilities=("Medium Under Expert 4",))["size_bonus"], Decimal("0.25"))
        self.assertEqual(self.calc(abilities=(), inactive_abilities=("Small Expert 4",))["size_bonus"], 0)

    def test_multiple_active_size_families_rejected_even_when_only_one_matches(self):
        with self.assertRaises(RuleError):
            self.calc(abilities=("Small Expert", "Medium Expert"))

    def test_underlevel_penalty_does_not_penalize_weapon_hit(self):
        result = self.calc(abilities=())
        self.assertTrue(result["underleveled"])
        self.assertEqual(result["base"]["speed"], 153)
        self.assertEqual(result["base"]["reaction"], 11)
        self.assertEqual(result["weapons"][0]["base_to_hit"], 17)

    def test_capacity_boundary_and_overload(self):
        exact = self.calc(equipment=("Particle Cannon", None, None, None))
        self.assertEqual(exact["carry_load"], 20)
        self.assertFalse(exact["overloaded"])
        overloaded = self.calc(equipment=("Particle Cannon", "Extension Armor", None, None))
        self.assertTrue(overloaded["overloaded"])
        self.assertEqual(overloaded["base"]["speed"], 153)
        self.assertEqual(overloaded["weapons"][0]["base_to_hit"], 11)
        self.assertEqual(overloaded["weapons"][4]["base_to_hit"], 16)

    def test_frame_upgrade_units_and_order(self):
        result = self.calc(abilities=(), upgrades=Upgrades(speed=2, reaction=2, defense=2, capacity=2))
        self.assertEqual(result["base"]["speed"], 213)
        self.assertEqual(result["base"]["reaction"], 13)
        self.assertEqual(result["base"]["defense"], 18)
        self.assertEqual(result["carry_capacity"], 40)

    def test_fixed_hit_upgrade_adds_flat_final_bonus(self):
        result = self.calc(upgrades=Upgrades(to_hit=(2, 0, 0, 0)))
        self.assertEqual(result["weapons"][0]["base_to_hit"], 19)
        self.assertEqual(result["weapons"][0]["to_hit"], 23)

    def test_hit_upgrades_are_slot_specific_and_do_not_affect_removable_weapons(self):
        equipment = ("Particle Cannon",) * 4
        baseline = self.calc(equipment=equipment)
        upgraded = self.calc(equipment=equipment, upgrades=Upgrades(to_hit=(1, 2, 3, 4)))
        self.assertTrue(upgraded["overloaded"])
        for i, (before, after) in enumerate(zip(baseline["weapons"], upgraded["weapons"])):
            with self.subTest(slot=i + 1):
                expected_bonus = i + 1 if i < 4 else 0
                self.assertEqual(after["to_hit"] - before["to_hit"], expected_bonus)
                self.assertEqual(after["base_to_hit"] - before["base_to_hit"], expected_bonus)
                self.assertEqual(after["damage_bonus"], before["damage_bonus"])

    def test_hit_upgrades_stack_with_pilot_equipment_and_skill_bonuses(self):
        changes = dict(
            pilot_level=20, abilities=("Lion Type 1", "Melee Expert"),
            equipment=("Ion Projector", None, None, None),
            equipment_active=(True, False, False, False),
        )
        baseline = self.calc(**changes)
        upgraded = self.calc(**changes, upgrades=Upgrades(to_hit=(5, 0, 0, 0)))
        self.assertEqual(upgraded["weapons"][0]["to_hit"], baseline["weapons"][0]["to_hit"] + 5)

    def test_upgrade_inputs_cannot_extend_to_removable_slots(self):
        with self.assertRaises(RuleError):
            Upgrades(to_hit=(1, 1, 1, 1, 1))
        with self.assertRaises(RuleError):
            Upgrades(damage=(1, 1, 1, 1, 1))

    def test_passive_equipment_and_base_defense_skill(self):
        result = self.calc(equipment=("Extension Armor", None, None, None), abilities=("Lion Type 1", "Iron Defense"))
        self.assertEqual(result["current"]["armor"], 26)
        self.assertEqual(result["current"]["defense"], 18)

    def test_only_activated_thruster_adds_reaction(self):
        equipment = ("Thruster", "Thruster", None, None)
        inactive = self.calc(equipment=equipment)
        active = self.calc(equipment=equipment, equipment_active=(True, False, False, False))
        self.assertEqual(inactive["current"]["reaction"], 24)
        self.assertEqual(active["current"]["reaction"], 34)
        both = self.calc(equipment=equipment, equipment_active=(True, True, False, False))
        self.assertEqual(both["current"]["reaction"], 44)

    def test_passive_chest_armor_does_not_enable_inactive_thruster(self):
        result = self.calc(equipment=("Thruster", None, None, "Extension Armor"))
        self.assertEqual(result["current"]["armor"], 26)
        self.assertEqual(result["current"]["defense"], 13)
        self.assertEqual(result["current"]["reaction"], 24)

    def test_each_equipment_bonus_uses_its_own_activation(self):
        # Controlled reference items exercise every bonus field independently.
        catalog = Catalog()
        for name, activation in (("Extension Armor", "Passive"), ("Thruster", "Active")):
            fields = catalog.find("armaments", name)["fields"]
            fields.update(activation=activation, weight=0, armor=2, defense=3,
                          reaction_bonus=4, speed_bonus=5, range_bonus=6,
                          to_hit_bonus=7, shields=8)
        base = calculate_stats(self.example, catalog)
        for slot in range(4):
            equipment = [None] * 4
            equipment[slot] = "Thruster"
            active = [False] * 4
            active[slot] = True
            off = calculate_stats(replace(self.example, equipment=tuple(equipment)), catalog)
            on = calculate_stats(replace(self.example, equipment=tuple(equipment), equipment_active=tuple(active)), catalog)
            equipment[slot] = "Extension Armor"
            passive = calculate_stats(replace(self.example, equipment=tuple(equipment)), catalog)
            for result in (on, passive):
                for stat, bonus in (("armor", 2), ("defense", 3), ("reaction", 4), ("speed", 5), ("range", 6)):
                    self.assertEqual(result["current"][stat], base["current"][stat] + bonus)
                    self.assertEqual(off["current"][stat], base["current"][stat])
                self.assertEqual(result["shields"], 8)
                self.assertEqual(result["weapons"][0]["to_hit"], base["weapons"][0]["to_hit"] + 7)
            self.assertEqual(off["shields"], 0)
            self.assertEqual(off["weapons"][0]["to_hit"], base["weapons"][0]["to_hit"])

    def test_equipment_activation_does_not_drop_ability_reaction_bonus(self):
        baseline = self.calc(abilities=("Lion Type 1", "Honed"), equipment=("Thruster", None, None, None))
        active = self.calc(abilities=("Lion Type 1", "Honed"), equipment=("Thruster", None, None, None), equipment_active=(True, False, False, False))
        self.assertEqual(active["current"]["reaction"], baseline["current"]["reaction"] + 10)

    def test_active_shields(self):
        off = self.calc(equipment=("E-Shield Generator", None, None, None))
        on = self.calc(equipment=("E-Shield Generator", None, None, None), equipment_active=(True, False, False, False))
        self.assertEqual((off["shields"], on["shields"]), (0, 200))

    def test_organoid_percentages_and_damage_rounding(self):
        result = self.calc(organoid_enabled=True, upgrades=Upgrades(damage=(1, 0, 0, 0)))
        self.assertEqual(result["pilot"]["health"], 145)
        self.assertEqual(result["pilot"]["speed"], 260)
        self.assertEqual(result["pilot"]["range"], 630)
        self.assertEqual(result["weapons"][0]["damage_bonus"], 23)
        self.assertEqual(result["weapons"][0]["to_hit"], 22)

    def test_organoid_hit_percentage_applies_to_all_eight_slots_when_active(self):
        result = self.calc(equipment=("Particle Cannon",) * 4, organoid_enabled=True, organoid_level=5, organoid_color="Black")
        # Overloaded fixed bases: 11, 8, 0, 10. Removable bases: 16.
        # Pilot 25% + Black level 5 Organoid 25% => multiplier 1.5.
        self.assertEqual([w["to_hit"] for w in result["weapons"]], [17, 12, 0, 15, 24, 24, 24, 24])

    def test_organoid_hit_stacks_with_size_before_flat_fixed_upgrades(self):
        result = self.calc(abilities=("Lion Type 1", "Small Expert"), organoid_enabled=True, organoid_color="Black", organoid_level=5, upgrades=Upgrades(to_hit=(2, 0, 0, 0)))
        # ROUND(17 * (1 + .25 + .10 + .25)) + 2 = 29
        self.assertEqual(result["weapons"][0]["to_hit"], 29)

    def test_disabling_organoid_removes_all_bonuses_for_every_color(self):
        base = replace(self.example, equipment=("Particle Cannon", None, None, None), fixed_active=(False, False, False, True), upgrades=Upgrades(damage=(1, 0, 0, 0), to_hit=(2, 0, 0, 0)))
        baseline = calculate_stats(base, self.catalog)
        for color in ("White", "Red", "Blue", "Black"):
            with self.subTest(color=color):
                enabled = replace(base, organoid_enabled=True, organoid_color=color, organoid_level=20)
                active = calculate_stats(enabled, self.catalog)
                for stat in ("health", "armor", "speed", "range"):
                    self.assertGreater(active["pilot"][stat], baseline["pilot"][stat])
                if color == "White":
                    self.assertGreater(active["shields"], baseline["shields"])
                else:
                    self.assertEqual(active["shields"], baseline["shields"])
                for slot in (0, 4):
                    self.assertGreater(active["weapons"][slot]["to_hit"], baseline["weapons"][slot]["to_hit"])
                    self.assertGreater(active["weapons"][slot]["damage_bonus"], baseline["weapons"][slot]["damage_bonus"])
                disabled = calculate_stats(replace(enabled, organoid_enabled=False), self.catalog)
                self.assertEqual(disabled, baseline)

    def test_liger_booster_uses_current_zoid_speed_not_cached_saberlion(self):
        result = self.calc(zoid="Liger Zero", pilot_level=15, abilities=(), fixed_active=(False, True, False, False))
        self.assertEqual(result["pilot"]["speed"], 307)
        self.assertEqual(result["current"]["speed"], 614)

    def test_dynamic_equipment_rebinds_to_selected_zoid(self):
        result = self.calc(zoid="Lightning Saix", pilot_level=100, abilities=(), equipment=("armaments:zoid_equipment_slot_1", None, None, None))
        self.assertEqual(result["weapons"][1]["base_damage"], 110)
        self.assertEqual(result["weapons"][1]["name"], "Pulse Laser Gun:")
        self.assertEqual(result["carry_load"], 0)

    def test_legacy_dice_damage_is_numeric_and_accepts_bonuses(self):
        result = self.calc(zoid="Ultra Phalanx", pilot_level=100, abilities=())
        self.assertEqual(result["weapons"][2]["base_damage"], 180)
        self.assertEqual(result["weapons"][3]["base_damage"], 300)
        self.assertEqual(result["weapons"][2]["damage_bonus"], 0)
        self.assertFalse(result["warnings"])
        upgraded = self.calc(zoid="Ultra Phalanx", pilot_level=100, abilities=(), upgrades=Upgrades(damage=(0, 0, 1, 0)), organoid_enabled=True, organoid_color="White")
        self.assertEqual(upgraded["weapons"][2]["damage_bonus"], 22)

    def test_dynamic_equipment_inherits_flat_damage(self):
        result = self.calc(zoid="Zaber Fang", pilot_level=100, abilities=(), equipment=("armaments:zoid_equipment_slot_1", None, None, None))
        self.assertEqual(result["weapons"][4]["base_damage"], 120)
        self.assertFalse(result["warnings"])
        bursts = self.calc(zoid="Shadow Fox", pilot_level=100, abilities=(), equipment=("armaments:zoid_equipment_slot_1", None, None, None))
        self.assertEqual(bursts["weapons"][2]["base_damage"], 30)
        self.assertEqual(bursts["weapons"][2]["damage_note"], "Shoots three bursts of 30")

    def test_all_zoids_and_pilot_styles_calculate(self):
        for z in self.catalog.tables["zoids"]["records"]:
            for style in ("TANK", "FIGHTER", "SCOUT", "ALMIGHTY"):
                with self.subTest(zoid=z["name"], style=style):
                    result = self.calc(zoid=z["id"], pilot_style=style, pilot_level=100, abilities=())
                    self.assertGreater(result["pilot"]["health"], 0)

    def test_all_organoid_colors_at_boundaries(self):
        for color in ("White", "Red", "Blue", "Black"):
            for level in (0, 40):
                with self.subTest(color=color, level=level):
                    result = self.calc(organoid_enabled=True, organoid_color=color, organoid_level=level)
                    self.assertGreaterEqual(result["pilot"]["health"], 144)

    def test_invalid_builds_and_lookup_ranges(self):
        for changes in ({"pilot_level": 100, "abilities": ("Lion Type 1",)}, {"pilot_style": "other"}, {"organoid_enabled": True, "organoid_level": 41}, {"equipment": ("WEAPONS", None, None, None)}):
            with self.assertRaises(RuleError):
                self.calc(**changes)
        with self.assertRaises(RuleError):
            Upgrades(speed=6)


class CatalogTests(unittest.TestCase):
    def test_catalog_counts_unique_ids_and_source_provenance(self):
        catalog = Catalog()
        for table in catalog.tables.values():
            ids = [r["id"] for r in table["records"]]
            self.assertEqual(len(ids), len(set(ids)))
            for r in table["records"]:
                self.assertGreater(r["source"]["row"], 1)
        self.assertEqual(len(catalog.tables["zoids"]["records"]), 134)
        self.assertEqual(len(catalog.tables["organoids"]["records"]), 41)

    def test_formula_constants_and_unresolved_dynamic_fields(self):
        catalog = Catalog()
        self.assertEqual(catalog.column(catalog.find("fighter", "1"), 2), 0.5)
        with self.assertRaises(RuleError):
            catalog.column(catalog.find("zoids", "Liger Zero"), 25)
        self.assertEqual(catalog.column(catalog.find("abilities", "Medium Under Expert 4"), 5), 0.25)


if __name__ == "__main__":
    unittest.main()
