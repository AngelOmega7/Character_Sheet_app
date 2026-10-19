from dataclasses import replace
import unittest

from zoids_app.catalog import Catalog
from zoids_app.characters import acquire_equipment, acquire_zoid, equip_owned_equipment, new_character, set_upgrades, switch_zoid, validate_character
from zoids_app.combat import RuleError
from zoids_app.stats import Upgrades, calculate_stats
from tools.convert_reference_data import CAU_BASES


class RosterTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.catalog = Catalog()

    def family(self, base="Liger Zero", forms=("Zero Jager (CAU)", "Zero Panzer (CAU)")):
        character = acquire_zoid(new_character(self.catalog), base, self.catalog)
        owned = character.owned_zoids[-1]
        for form in forms:
            character = acquire_zoid(character, form, self.catalog)
        return switch_zoid(character, owned.id, catalog=self.catalog)

    def form(self, character, name):
        return switch_zoid(character, character.active_zoid_id, self.catalog.find("zoids", name)["id"], self.catalog)

    def test_shared_claw_upgrades_follow_weapon_across_slots_both_directions(self):
        character = self.family()
        character = set_upgrades(character, Upgrades(speed=2, capacity=3, damage=(1, 0, 4, 0), to_hit=(2, 0, 3, 0)), self.catalog)
        jager = self.form(character, "Zero Jager (CAU)")
        self.assertEqual(jager.build.upgrades.damage, (1, 0, 0, 4))
        self.assertEqual(jager.build.upgrades.to_hit, (2, 0, 0, 3))
        self.assertEqual(jager.build.upgrades.speed, 2)
        jager = set_upgrades(jager, replace(jager.build.upgrades, damage=(1, 2, 0, 5), defense=4), self.catalog)
        base = self.form(jager, "Liger Zero")
        self.assertEqual(base.build.upgrades.damage, (1, 0, 5, 0))
        self.assertEqual(base.build.upgrades.defense, 4)
        panzer = self.form(base, "Zero Panzer (CAU)")
        self.assertEqual(panzer.build.upgrades.damage, (0, 0, 0, 5))
        self.assertEqual(panzer.build.upgrades.capacity, 3)
        self.assertEqual(self.form(panzer, "Zero Jager (CAU)").build.upgrades.damage, (1, 2, 0, 5))

    def test_newly_acquired_form_inherits_existing_shared_upgrades(self):
        character = self.family(forms=())
        character = set_upgrades(character, Upgrades(speed=3, damage=(0, 0, 2, 0)), self.catalog)
        character = acquire_zoid(character, "Zero X (CAU)", self.catalog)
        form = self.form(character, "Zero X (CAU)")
        self.assertEqual(form.build.upgrades.speed, 3)
        self.assertEqual(form.build.upgrades.damage, (0, 0, 0, 2))

    def test_other_families_share_by_identity_and_not_position(self):
        for base, form, source, target in (("Konig Wolf", "Konig Wolf DSR (CAU)", 2, 3),
                                           ("Berserk Fury", "Sturm Fury (CAU)", 3, 2),
                                           ("Berserk Fury", "Berserk Fury Z (CAU)", 3, 2)):
            with self.subTest(form=form):
                character = self.family(base, (form,))
                damage = tuple(3 if i == source else 0 for i in range(4))
                character = set_upgrades(character, Upgrades(damage=damage), self.catalog)
                transformed = self.form(character, form)
                self.assertEqual(transformed.build.upgrades.damage[target], 3)
                self.assertEqual(sum(transformed.build.upgrades.damage), 3)

    def test_same_named_weapon_on_other_owned_zoid_does_not_share(self):
        character = self.family()
        character = set_upgrades(character, Upgrades(damage=(0, 0, 4, 0)), self.catalog)
        liger_id = character.active_zoid_id
        character = acquire_zoid(character, "Berserk Fury", self.catalog)
        character = switch_zoid(character, character.owned_zoids[-1].id, catalog=self.catalog)
        self.assertEqual(character.build.upgrades.damage, (0,) * 4)
        character = set_upgrades(character, Upgrades(damage=(0, 0, 0, 1)), self.catalog)
        self.assertEqual(switch_zoid(character, liger_id, catalog=self.catalog).build.upgrades.damage[2], 4)

    def test_loadouts_activation_and_chassis_resources_survive_switching(self):
        character = self.family()
        character = acquire_equipment(character, "Particle Cannon", catalog=self.catalog)
        character = equip_owned_equipment(character, "left", character.inventory[-1].id, self.catalog)
        build = character.build
        character = replace(character, current_health=42, build=replace(build, equipment_active=(False, True, False, False),
                             fixed_active=(True, False, False, False), shield_adjustment=25))
        jager = self.form(character, "Zero Jager (CAU)")
        self.assertEqual(jager.current_health, 42)
        self.assertEqual(jager.build.equipment, (None,) * 4)
        self.assertEqual(jager.build.shield_adjustment, 25)
        jager = acquire_equipment(jager, "Extension Armor", catalog=self.catalog)
        jager = equip_owned_equipment(jager, "right", jager.inventory[-1].id, self.catalog)
        original = self.form(jager, "Liger Zero")
        self.assertEqual(original.build.equipment[1], "armaments:particle_cannon")
        self.assertTrue(original.build.equipment_active[1])
        self.assertTrue(original.build.fixed_active[0])
        self.assertEqual(self.form(original, "Zero Jager (CAU)").build.equipment[2], "armaments:extension_armor")
        other = switch_zoid(original, original.owned_zoids[0].id, catalog=self.catalog)
        self.assertNotEqual(other.current_health, 42)
        restored = switch_zoid(other, original.active_zoid_id, catalog=self.catalog)
        self.assertEqual((restored.current_health, restored.build.shield_adjustment), (42, 25))

    def test_unowned_duplicate_and_wrong_family_selections_are_rejected(self):
        character = new_character(self.catalog)
        for name in ("Saberlion", "Zero Jager (CAU)"):
            with self.assertRaises(RuleError):
                acquire_zoid(character, name, self.catalog)
        with self.assertRaises(RuleError):
            switch_zoid(character, "unknown", catalog=self.catalog)
        with self.assertRaises(RuleError):
            switch_zoid(character, character.active_zoid_id, "zoids:zero_jager_cau", self.catalog)
        with self.assertRaises(RuleError):
            validate_character(replace(character, build=replace(character.build, zoid="Liger Zero")), self.catalog)
        character = self.family()
        with self.assertRaises(RuleError):
            acquire_zoid(character, "Zero Jager (CAU)", self.catalog)

    def test_all_cau_mappings_and_standardized_weapon_names(self):
        actual = {r["name"]: self.catalog.find("zoids", r["ownership_base_id"])["name"]
                  for r in self.catalog.tables["zoids"]["records"] if "(CAU)" in r["name"]}
        self.assertEqual(actual, CAU_BASES)
        for record in self.catalog.tables["zoids"]["records"]:
            for column in (13, 19, 30, 41, 47, 54, 61, 66):
                name = self.catalog.column(record, column)
                if name and name.strip().rstrip(":").strip().casefold() in {"strike laster claw", "strike laser claw", "strike laser claws"}:
                    self.assertEqual(name, "Strike Laser Claw")
        base = self.catalog.find("zoids", "Liger Zero")
        self.assertEqual(base["corrections"]["weapon_3_30"]["original"], "Strike Laster Claw:")

    def test_blox_and_transports_cannot_be_acquired_as_normal_zoids(self):
        for name in ("Leo Blaze", "Zero Phoenix", "Gustav", "Hover Cargo", "Whale King"):
            with self.subTest(name=name), self.assertRaises(RuleError):
                acquire_zoid(new_character(self.catalog), name, self.catalog)

    def test_utilities_cannot_receive_weapon_upgrades(self):
        character = self.family()
        with self.assertRaises(RuleError):
            set_upgrades(character, Upgrades(damage=(0, 1, 0, 0)), self.catalog)

    def test_shared_points_change_damage_without_replacing_form_base_damage(self):
        character = self.family(forms=("Zero Empire (CAU)",))
        character = set_upgrades(character, Upgrades(damage=(0, 0, 2, 0)), self.catalog)
        empire = self.form(character, "Zero Empire (CAU)")
        result = calculate_stats(empire.build, self.catalog)["weapons"][2]
        self.assertEqual(result["base_damage"], 210)
        self.assertEqual(result["damage_upgrade"], 40)
