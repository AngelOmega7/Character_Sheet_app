"""Headless interaction tests; skipped when only the standard-library core is installed."""
import asyncio
from dataclasses import replace
import json
from pathlib import Path
from types import SimpleNamespace
import tempfile
import unittest
from unittest.mock import patch

try:
    import flet
except ImportError:
    flet = None

from zoids_app.catalog import Catalog
from zoids_app.characters import acquire_zoid, restore_roster_selection, switch_zoid
from zoids_app.combat_controller import combat_snapshot
from zoids_app.stats import calculate_stats
from zoids_app.storage import CharacterStore, EXPORT_FORMAT
from test_support import established_character


class PageStub:
    def add(self, *controls):
        self.controls = controls

    def update(self):
        pass

    def show_dialog(self, dialog):
        self.dialog = dialog

    def pop_dialog(self):
        self.dialog = None


class PickerStub:
    def __init__(self):
        self.save_kwargs = None
        self.save_result = "/tmp/exported-character.json"
        self.pick_kwargs = None
        self.pick_result = []

    async def save_file(self, **kwargs):
        self.save_kwargs = kwargs
        return self.save_result

    async def pick_files(self, **kwargs):
        self.pick_kwargs = kwargs
        return self.pick_result


@unittest.skipIf(flet is None, "Install requirements.txt to run Flet interaction tests")
class EditorTests(unittest.TestCase):
    def setUp(self):
        from zoids_app.ui import CharacterEditor
        self.directory = tempfile.TemporaryDirectory()
        self.addCleanup(self.directory.cleanup)
        catalog = Catalog()
        self.store = CharacterStore(Path(self.directory.name) / "characters.sqlite3", catalog)
        self.page = PageStub()
        self.picker = PickerStub()
        self.editor = CharacterEditor(self.page, self.store, catalog, file_picker=self.picker)
        self.editor.character = established_character(catalog)
        self.editor.render()

    def test_create_equip_activate_save_and_reopen(self):
        editor = self.editor
        editor.name.value = "Test pilot"
        editor.level.value = "20"
        self.acquire_item("Particle Cannon")
        editor.change_equipment("left", editor.character.inventory[-1].id)
        editor.activate(1, True)
        editor.save()
        saved_id = editor.character.id
        self.assertFalse(editor.dirty)
        editor.new()
        self.assertNotEqual(editor.character.id, saved_id)
        editor.saved.value = saved_id
        editor.open_saved()
        self.assertEqual(editor.character.name, "Test pilot")
        self.assertEqual(editor.character.build.pilot_level, 20)
        self.assertEqual(editor.character.build.equipment[1], "armaments:particle_cannon")
        self.assertTrue(editor.character.build.equipment_active[1])

    def test_export_selected_saved_character_to_json(self):
        editor = self.editor
        editor.name.value = "Export Pilot"
        editor.save()
        asyncio.run(editor.export_saved())
        kwargs = self.picker.save_kwargs
        self.assertIsNotNone(kwargs)
        self.assertEqual(kwargs["file_name"], f"Export Pilot-{editor.character.id[:8]}.json")
        self.assertEqual(kwargs["allowed_extensions"], ["json"])
        document = json.loads(kwargs["src_bytes"].decode("utf-8"))
        self.assertEqual(document["format"], EXPORT_FORMAT)
        self.assertEqual(document["character"]["id"], editor.character.id)
        self.assertIn("Exported saved character Export Pilot", editor.status.value)

    def test_export_cancel_does_not_change_state(self):
        editor = self.editor
        editor.save()
        before = editor.character
        self.picker.save_result = None
        asyncio.run(editor.export_saved())
        self.assertEqual(editor.character, before)
        self.assertEqual(editor.status.value, "Export canceled.")

    def test_import_saved_character_adds_copy_without_changing_open_draft(self):
        editor = self.editor
        editor.name.value = "Import Pilot"
        editor.save()
        saved = editor.character
        editor.name.value = "Unsaved editor change"
        editor.dirty = True
        exported = self.store.export_character(saved.id)
        self.picker.pick_result = [SimpleNamespace(bytes=exported.encode("utf-8"), path=None, name="pilot.json")]
        asyncio.run(editor.import_saved())
        self.assertEqual(self.picker.pick_kwargs["allowed_extensions"], ["json"])
        self.assertTrue(self.picker.pick_kwargs["with_data"])
        records = self.store.list_characters()
        self.assertEqual(len(records), 2)
        imported_id = next(r["id"] for r in records if r["id"] != saved.id)
        self.assertEqual(editor.saved.value, imported_id)
        self.assertEqual(self.store.load(imported_id).name, "Import Pilot")
        self.assertEqual(editor.character, saved)
        self.assertTrue(editor.dirty)
        self.assertEqual(editor.name.value, "Unsaved editor change")
        self.assertIn("Imported Import Pilot", editor.status.value)

    def test_import_reads_file_path_when_bytes_are_not_returned(self):
        editor = self.editor
        editor.save()
        saved = editor.character
        path = Path(self.directory.name) / "portable.json"
        path.write_text(self.store.export_character(saved.id), encoding="utf-8")
        self.picker.pick_result = [SimpleNamespace(bytes=None, path=str(path), name=path.name)]
        asyncio.run(editor.import_saved())
        self.assertEqual(len(self.store.list_characters()), 2)

    def test_invalid_import_reports_error_without_saving_or_switching(self):
        editor = self.editor
        editor.save()
        before = editor.character
        self.picker.pick_result = [SimpleNamespace(bytes=b"not json", path=None, name="broken.json")]
        asyncio.run(editor.import_saved())
        self.assertEqual(self.store.list_characters()[0]["id"], before.id)
        self.assertEqual(len(self.store.list_characters()), 1)
        self.assertEqual(editor.character, before)
        self.assertIn("not valid character JSON", editor.status.value)

    def test_invalid_profile_cannot_overwrite_saved_character(self):
        editor = self.editor
        editor.save()
        original = editor.character
        editor.level.value = "not a level"
        editor.save()
        self.assertEqual(editor.character, original)
        self.assertEqual(self.store.load(original.id), original)
        self.assertIn("whole numbers", editor.status.value)

    def test_owned_chassis_switch_preserves_equipment_and_upgrades(self):
        editor = self.editor
        self.acquire_item("Particle Cannon")
        editor.change_equipment("left", editor.character.inventory[-1].id)
        original_id = editor.character.active_zoid_id
        health = editor.character.current_health
        editor.gold_input.value = "15000"
        editor.adjust_upgrade("speed", 1)
        editor.adjust_upgrade("speed", 1)
        editor.acquisition.value = "zoids:shield_liger"
        self.confirm_purchase()
        self.assertEqual(editor.character.build.equipment, (None,) * 4)
        self.assertEqual(editor.character.build.upgrades.speed, 0)
        editor.select_owned(original_id)
        self.assertEqual(editor.character.build.equipment[1], "armaments:particle_cannon")
        self.assertEqual(editor.character.build.upgrades.speed, 2)
        self.assertEqual(editor.character.current_health, health)

    def test_roster_selectors_only_offer_owned_zoids_and_forms(self):
        editor = self.editor
        self.assertEqual(len(editor.owned_select.options), 1)
        self.assertEqual(len(editor.form_select.options), 1)
        self.assertNotIn("zoids:zero_jager_cau", {o.key for o in editor.acquisition.options})
        editor.acquisition.value = "zoids:liger_zero"
        self.confirm_purchase()
        self.assertEqual(len(editor.owned_select.options), 2)
        self.assertEqual(len(editor.form_select.options), 1)
        self.assertIn("zoids:zero_jager_cau", {o.key for o in editor.acquisition.options})
        editor.gold_input.value = "60000"
        for _ in range(3):
            editor.adjust_upgrade("damage", 1, 2)
        editor.acquisition.value = "zoids:zero_jager_cau"
        self.confirm_purchase()
        self.assertEqual(len(editor.owned_select.options), 2)
        self.assertEqual(len(editor.form_select.options), 2)
        self.assertEqual(editor.damage_fields[3].value, "3")
        editor.save()
        loaded = self.store.load(editor.character.id)
        self.assertEqual(loaded.build.upgrades.damage[3], 3)

    def test_unsaved_switch_can_be_cancelled(self):
        editor = self.editor
        original = editor.character
        editor.name.value = "Unsaved name"
        editor.changed()
        editor.new()
        self.assertEqual(editor.character, original)
        self.assertIsNotNone(self.page.dialog)
        self.page.dialog.actions[0].on_click(None)
        self.assertEqual(editor.name.value, "Unsaved name")

    def test_fuzor_recipe_selects_component_instances_and_confirms_consumption(self):
        editor = self.editor
        c = editor.character
        for name in ("Leo Blaze", "Leo Blaze", "Unenlagia"):
            c = acquire_zoid(c, name, editor.catalog)
        first, chosen, other = c.owned_zoids[-3:]
        editor.character = replace(c, known_zoids=(*c.known_zoids, "zoids:2_arm_lizard"))
        editor.render()
        editor.acquisition.value = "zoids:2_arm_lizard"
        editor.purchase_selection()
        self.assertIn("Cost: 0g", editor.purchase_details.value)
        self.assertEqual(len(editor.purchase_blox.controls), 2)
        self.assertIsNone(editor.purchase_blox.controls[0].value)
        self.assertEqual(editor.purchase_blox.controls[1].value, other.id)
        editor.purchase_blox.controls[0].value = chosen.id
        editor.obtain()
        self.assertEqual(self.page.dialog.title.value, "Confirm purchase")
        self.assertIn(chosen.id[:8], self.page.dialog.content.value)
        self.assertIn("preserved for recovery", self.page.dialog.content.value)
        self.page.dialog.actions[-1].on_click(None)
        self.assertEqual(editor.character.build.zoid, "zoids:2_arm_lizard")
        self.assertIn(first.id, {o.id for o in editor.character.owned_zoids})
        self.assertNotIn(chosen.id, {o.id for o in editor.character.owned_zoids})
        self.assertEqual(editor.character.gold, c.gold)
        fused = editor.character
        editor.sell_selected_zoid()
        self.assertIn("Original identities, upgrades, health", self.page.dialog.content.controls[0].value)
        self.assertIn(chosen.id[:8], self.page.dialog.content.controls[0].value)
        self.page.dialog.actions[0].on_click(None)
        self.assertEqual(editor.character, fused)
        editor.sell_selected_zoid()
        self.page.dialog.actions[-1].on_click(None)
        self.assertEqual({o.id for o in editor.character.owned_zoids}, {o.id for o in c.owned_zoids})
        self.assertEqual(editor.character.gold, c.gold)

    def test_starter_picker_includes_base_blox_but_not_free_fuzors(self):
        from zoids_app.characters import new_character
        editor = self.editor
        editor.character = new_character(editor.catalog)
        editor.render()
        offered = {option.key for option in editor.acquisition.options}
        self.assertIn("zoids:leo_blaze", offered)
        self.assertNotIn("zoids:2_arm_lizard", offered)
        self.assertNotIn("zoids:gojulox", offered)

    def test_keep_sold_fuzor_checkbox_and_select_retained_rebuild(self):
        from zoids_app.characters import set_upgrades
        from zoids_app.stats import Upgrades
        editor = self.editor
        c = acquire_zoid(editor.character, "2-Arm Lizard", editor.catalog)
        identity = c.owned_zoids[-1].id
        c = switch_zoid(c, identity, catalog=editor.catalog)
        c = set_upgrades(c, Upgrades(speed=3, damage=(2, 0, 0, 0)), editor.catalog)
        editor.character = replace(c, known_zoids=(*c.known_zoids, "zoids:2_arm_lizard"))
        editor.render()
        editor.sell_selected_zoid()
        keep = self.page.dialog.content.controls[1]
        self.assertFalse(keep.value)
        keep.value = True
        self.page.dialog.actions[0].on_click(None)
        self.assertEqual(editor.character.stored_fuzors, ())
        editor.sell_selected_zoid()
        self.page.dialog.content.controls[1].value = True
        self.page.dialog.actions[-1].on_click(None)
        self.assertEqual([s.id for s in editor.character.stored_fuzors], [identity])
        editor.acquisition.value = "zoids:2_arm_lizard"
        editor.purchase_selection()
        self.assertTrue(editor.purchase_stored_fuzor.visible)
        self.assertEqual(editor.purchase_stored_fuzor.value, "new")
        editor.purchase_stored_fuzor.value = identity
        editor.obtain()
        self.assertIn("retained frame and weapon upgrades", self.page.dialog.content.value)
        self.page.dialog.actions[-1].on_click(None)
        self.assertEqual(editor.character.active_zoid_id, identity)
        self.assertEqual(editor.character.build.upgrades, c.build.upgrades)
        self.assertEqual(editor.character.stored_fuzors, ())
        editor.save()
        self.assertEqual(self.store.load(editor.character.id), editor.character)

    def test_transport_section_and_empty_roster_after_retirement(self):
        editor = self.editor
        editor.character = restore_roster_selection(replace(editor.character, owned_zoids=()), editor.catalog)
        editor.render()
        self.assertTrue(editor.owned_select.disabled)
        names = {o.text for o in editor.acquisition.options}
        self.assertTrue(any(name.startswith("Leo Blaze ·") for name in names))
        self.assertFalse(names & {"Zero Phoenix", "Gustav", "Hover Cargo", "Whale King"})
        self.assertTrue({"None", "Hover Cargo", "Gustav", "Whale King", "Dragoon Nest"} <= {o.text for o in editor.transport_picker.options})
        editor.save()
        self.assertEqual(self.store.load(editor.character.id).owned_zoids, ())
        editor.acquisition.value = "zoids:liger_zero"
        self.confirm_purchase()
        self.assertEqual(editor.character.build.zoid, "zoids:liger_zero")

    def learn(self, name):
        self.editor.ability_to_learn.value = self.editor.catalog.find("abilities", name)["id"]
        self.editor.learn_selected_ability()

    def confirm_purchase(self):
        self.editor.obtain()
        self.assertIsNotNone(self.page.dialog)
        self.page.dialog.actions[-1].on_click(None)

    def acquire_item(self, name, quantity=1):
        self.editor.equipment_to_acquire.value = self.editor.catalog.find("armaments", name)["id"]
        self.editor.equipment_quantity.value = str(quantity)
        self.editor.obtain_equipment()

    def test_learn_upgrade_displace_and_deactivate_abilities(self):
        editor = self.editor
        baseline = calculate_stats(editor.character.build, editor.catalog)
        self.learn("Fleet Footed")
        self.assertEqual(editor.character.build.inactive_abilities, ("abilities:fleet_footed",))
        self.assertEqual(calculate_stats(editor.character.build, editor.catalog), baseline)
        editor.change_ability_slot(5, "abilities:fleet_footed")
        self.assertEqual(len(editor.character.build.abilities), 6)
        self.assertEqual(calculate_stats(editor.character.build, editor.catalog)["current"]["speed"], baseline["current"]["speed"] + 50)
        self.learn("Fleet Footed 2")
        self.assertEqual(editor.character.build.abilities[5], "abilities:fleet_footed_2")
        self.assertNotIn("abilities:fleet_footed", {o.key for o in editor.ability_to_learn.options})
        self.assertNotIn("abilities:fleet_footed_2", {o.key for o in editor.ability_to_learn.options})
        self.learn("Sniper 4")
        editor.change_ability_slot(5, "abilities:sniper_4")
        self.assertIn("abilities:fleet_footed_2", editor.character.build.inactive_abilities)
        editor.change_ability_slot(5, "")
        self.assertIsNone(editor.character.build.abilities[5])
        self.assertEqual(set(editor.character.build.inactive_abilities), {"abilities:sniper_4", "abilities:fleet_footed_2"})
        self.assertEqual(calculate_stats(editor.character.build, editor.catalog), baseline)

    def test_remove_inactive_ability_preserves_other_abilities_and_saves(self):
        editor = self.editor
        self.learn("Weapon Breaker 1")
        self.learn("Fleet Footed")
        editor.change_ability_slot(0, "abilities:fleet_footed")
        editor.remove_inactive_ability("Weapon Breaker 1")
        self.assertEqual(editor.character.build.inactive_abilities, ())
        self.assertEqual(editor.character.build.abilities[0], "abilities:fleet_footed")
        self.assertIn("abilities:weapon_breaker_1", {o.key for o in editor.ability_to_learn.options})
        self.assertTrue(editor.dirty)
        before = editor.character
        editor.remove_inactive_ability("Fleet Footed")
        self.assertEqual(editor.character, before)
        editor.save()
        self.assertEqual(self.store.load(editor.character.id).build.inactive_abilities, ())
        self.learn("Weapon Breaker 1")
        self.assertIn("abilities:weapon_breaker_1", editor.character.build.inactive_abilities)

    def test_second_size_ability_rejected_without_losing_owned_abilities(self):
        editor = self.editor
        self.learn("Small Expert")
        self.learn("Medium Expert")
        editor.change_ability_slot(0, "abilities:small_expert")
        before = editor.character
        editor.ability_slots[1].value = "abilities:medium_expert"
        editor.change_ability_slot(1, "abilities:medium_expert")
        self.assertEqual(editor.character, before)
        self.assertEqual(editor.ability_slots[1].value, "")
        self.assertIn("one size", editor.status.value)
        editor.change_ability_slot(0, "abilities:medium_expert")
        self.assertEqual(editor.character.build.abilities[0], "abilities:medium_expert")
        self.assertIn("abilities:small_expert", editor.character.build.inactive_abilities)

    def test_learning_options_description_and_rejected_unowned_activation(self):
        editor = self.editor
        self.assertEqual(sum("blox" in o.key for o in editor.ability_to_learn.options), 5)
        editor.ability_to_learn.value = "abilities:comeback"
        editor.ability_to_learn.on_select(SimpleNamespace(control=editor.ability_to_learn))
        self.assertIn("20%", editor.ability_description.value)
        before = editor.character
        editor.change_ability_slot(0, "abilities:comeback")
        self.assertEqual(editor.character, before)
        self.assertIn("owned and inactive", editor.status.value)
        self.learn("Fleet Footed 2")
        before = editor.character
        self.learn("Fleet Footed")
        self.assertEqual(editor.character, before)
        self.assertIn("downgraded", editor.status.value)

    def test_organoid_controls_apply_each_color_without_healing(self):
        editor = self.editor
        editor.character = replace(editor.character, current_health=17)
        editor.render()
        baseline = calculate_stats(editor.character.build, editor.catalog)
        for color in ("White", "Red", "Blue", "Black"):
            for level in (0, 40):
                with self.subTest(color=color, level=level):
                    editor.organoid_enabled.value = False
                    editor.organoid_color.value = color
                    editor.organoid_level.value = str(level)
                    editor.apply_organoid()
                    self.assertEqual(calculate_stats(editor.character.build, editor.catalog), baseline)
                    editor.organoid_enabled.value = True
                    editor.apply_organoid()
                    expected_shield = editor.catalog.column(editor.catalog.find("organoids", str(level)), 22) if color == "White" else 0
                    self.assertEqual(calculate_stats(editor.character.build, editor.catalog)["shields"], expected_shield)
                    self.assertEqual(editor.character.current_health, 17)
                    editor.organoid_enabled.value = False
                    editor.apply_organoid()
                    self.assertEqual(calculate_stats(editor.character.build, editor.catalog), baseline)

    def test_invalid_organoid_settings_leave_state_and_saved_record_unchanged(self):
        editor = self.editor
        editor.save()
        original = editor.character
        for value in ("41", "-1", "1.5", ""):
            editor.organoid_level.value = value
            editor.apply_organoid()
            self.assertEqual(editor.character, original)
            self.assertEqual(editor.organoid_level.value, str(original.build.organoid_level))
        editor.organoid_color.value = "Green"
        editor.save()
        self.assertEqual(self.store.load(original.id), original)
        self.assertEqual(editor.character, original)

    def test_pilot_abilities_and_organoid_survive_zoid_form_switch_and_reload(self):
        editor = self.editor
        self.learn("Small Expert")
        editor.change_ability_slot(0, "abilities:small_expert")
        self.learn("Sniper 4")
        editor.organoid_color.value = "White"
        editor.organoid_level.value = "5"
        editor.organoid_enabled.value = True
        editor.apply_organoid()
        saber_id = editor.character.active_zoid_id
        editor.acquisition.value = "zoids:liger_zero"
        self.confirm_purchase()
        liger_id = editor.character.active_zoid_id
        editor.acquisition.value = "zoids:zero_jager_cau"
        self.confirm_purchase()
        editor.select_owned(saber_id)
        editor.select_owned(liger_id)
        self.assertEqual(editor.character.build.zoid, "zoids:zero_jager_cau")
        editor.save()
        saved = editor.character
        editor.new()
        editor.store = CharacterStore(self.store.path, editor.catalog)
        editor.saved.value = saved.id
        editor.open_saved()
        self.assertEqual(editor.character, saved)
        self.assertEqual(editor.ability_slots[0].value, "abilities:small_expert")
        self.assertIn("abilities:sniper_4", editor.character.build.inactive_abilities)
        self.assertEqual((editor.organoid_color.value, editor.organoid_level.value, editor.organoid_enabled.value), ("White", "5", True))

    def test_pilot_controls_work_without_owned_zoids(self):
        editor = self.editor
        editor.character = restore_roster_selection(replace(editor.character, owned_zoids=()), editor.catalog)
        editor.render()
        self.learn("Fleet Footed")
        editor.change_ability_slot(0, "abilities:fleet_footed")
        editor.organoid_color.value = "White"
        editor.organoid_level.value = "40"
        editor.organoid_enabled.value = True
        editor.apply_organoid()
        editor.save()
        self.assertEqual(editor.character.owned_zoids, ())
        self.assertEqual(self.store.load(editor.character.id), editor.character)
        editor.acquisition.value = "zoids:liger_zero"
        self.confirm_purchase()
        self.assertEqual(editor.character.build.abilities, ("abilities:fleet_footed",))
        self.assertEqual(editor.character.build.organoid_level, 40)
        self.assertTrue(editor.character.build.organoid_enabled)

    def test_searchable_menus_preserve_options_and_typing_does_not_acquire(self):
        editor = self.editor
        for dropdown in (editor.acquisition, editor.ability_to_learn, editor.equipment_to_acquire,
                         *editor.equipment_dropdowns.values()):
            self.assertTrue(dropdown.editable)
            self.assertTrue(dropdown.enable_filter)
            self.assertTrue(dropdown.enable_search)
            self.assertEqual(dropdown.menu_height, 300)
        before = editor.character
        original_options = tuple(o.key for o in editor.acquisition.options)
        editor.acquisition.value = "zoids:liger_zero"
        editor.acquisition.text = "no matching zoid"
        editor.acquisition.on_text_change(SimpleNamespace(control=editor.acquisition))
        editor.obtain()
        self.assertEqual(editor.character, before)
        self.assertEqual(tuple(o.key for o in editor.acquisition.options), original_options)
        editor.ability_to_learn.value = "abilities:comeback"
        editor.ability_to_learn.text = "fleet"
        editor.learn_selected_ability()
        self.assertEqual(editor.character, before)
        editor.equipment_to_acquire.value = "armaments:particle_cannon"
        editor.equipment_to_acquire.text = "shield"
        editor.obtain_equipment()
        self.assertEqual(editor.character, before)
        # Choosing the displayed entry after searching commits its stable ID.
        editor.equipment_to_acquire.text = "Particle Cannon"
        editor.obtain_equipment()
        self.assertEqual(len(editor.character.inventory), 1)

    def test_equipment_inventory_lists_only_available_copies_and_returns_them(self):
        editor = self.editor
        editor.change_equipment("left", "armaments:particle_cannon")
        self.assertIsNone(editor.character.build.equipment[1])
        self.acquire_item("Particle Cannon", 2)
        first, second = editor.character.inventory
        editor.change_equipment("left", first.id)
        self.assertNotIn(first.id, {o.key for o in editor.equipment_dropdowns["right"].options})
        self.assertIn(second.id, {o.key for o in editor.equipment_dropdowns["right"].options})
        self.assertNotIn(second.id, {o.key for o in editor.equipment_dropdowns["back"].options})
        editor.change_equipment("right", second.id)
        editor.return_equipment(first.id)
        self.assertIsNone(editor.character.build.equipment[1])
        self.assertEqual(editor.character.build.equipment[2], "armaments:particle_cannon")
        self.assertIn(first.id, {o.key for o in editor.equipment_dropdowns["left"].options})
        editor.save()
        saved = editor.character
        editor.new()
        editor.saved.value = saved.id
        editor.open_saved()
        self.assertEqual(editor.character.inventory, saved.inventory)
        self.assertEqual(editor.equipment_dropdowns["right"].value, second.id)

    def test_invalid_equipment_quantity_does_not_change_inventory(self):
        editor = self.editor
        before = editor.character
        for quantity in ("0", "-1", "1.5", ""):
            editor.equipment_to_acquire.value = "armaments:particle_cannon"
            editor.equipment_quantity.value = quantity
            editor.obtain_equipment()
            self.assertEqual(editor.character, before)

    def test_delete_unattached_equipment_copy_requires_confirmation_and_saves(self):
        editor = self.editor
        self.acquire_item("Particle Cannon", 2)
        first, second = editor.character.inventory
        editor.change_equipment("left", first.id)
        editor.delete_equipment_copy(first.id)
        self.assertIn("Return this copy", editor.status.value)
        self.assertEqual(editor.character.inventory, (first, second))
        editor.delete_equipment_copy(second.id)
        self.assertIsNotNone(self.page.dialog)
        self.assertIn("Permanently delete", self.page.dialog.content.value)
        self.page.dialog.actions[0].on_click(None)
        self.assertEqual(editor.character.inventory, (first, second))
        editor.delete_equipment_copy(second.id)
        self.page.dialog.actions[-1].on_click(None)
        self.assertEqual(editor.character.inventory, (first,))
        self.assertNotIn(second.id, {o.key for o in editor.equipment_dropdowns["right"].options})
        self.assertTrue(editor.dirty)
        editor.save()
        saved = editor.character
        editor.new()
        editor.saved.value = saved.id
        editor.open_saved()
        self.assertEqual(editor.character.inventory, saved.inventory)

    def test_zoid_specific_equipment_is_listed_under_its_real_name(self):
        editor = self.editor
        editor.character = acquire_zoid(editor.character, "Command Wolf", editor.catalog)
        wolf = next(o for o in editor.character.owned_zoids if o.base_zoid == "zoids:command_wolf")
        editor.character = switch_zoid(editor.character, wolf.id, catalog=editor.catalog)
        editor.render()
        choices = [o for o in editor.equipment_to_acquire.options if "Double Beam Cannon" in o.text]
        self.assertEqual(len(choices), 1)
        self.assertIn("Command Wolf", choices[0].text)
        self.assertIn("Zoid equipment slot 5", choices[0].text)
        self.assertNotIn("ZOS", choices[0].text)
        editor.equipment_to_acquire.value = choices[0].key
        editor.equipment_to_acquire.text = choices[0].text
        editor.obtain_equipment()
        copy = editor.character.inventory[-1]
        self.assertEqual(copy.armament, "armaments:zoid_equipment_slot_1")
        self.assertEqual(editor.inventory_labels[copy.id], "Double Beam Cannon · copy 1")
        editor.change_equipment("left", copy.id)
        self.assertEqual(editor.character.build.equipment[1], "armaments:zoid_equipment_slot_1")
        self.assertEqual(editor.inventory_labels[copy.id], "Double Beam Cannon · copy 1")

    def combat_pilot(self, health=27, gold=20000):
        self.acquire_item("Particle Cannon")
        self.editor.change_equipment("left", self.editor.character.inventory[0].id)
        self.editor.health_input.value = str(health)
        self.editor.gold_input.value = str(gold)
        self.editor.shield_damage_input.value = "9"
        self.editor.apply_resources()
        return self.editor

    def test_combat_resource_inputs_and_attack_range_preview_do_not_fire(self):
        editor = self.combat_pilot()
        self.learn("Sniper 4")
        editor.change_ability_slot(0, "abilities:sniper_4")
        self.learn("Comeback")
        editor.change_ability_slot(1, "abilities:comeback")
        normal = editor.attack_previews["left"]
        target = combat_snapshot(editor.character, editor.catalog)[1]["left"]
        editor.change_attack_range(target["identity"], "long")
        self.assertEqual(editor.attack_previews["left"]["to_hit"], normal["to_hit"] + 4)
        self.assertEqual(editor.attack_previews["left"]["damage"], 78)
        self.assertEqual(editor.character.inventory[0].condition.heat, 0)
        self.assertNotIn("fixed_1", editor.range_controls)  # Melee has no range selector.
        editor.health_input.value = "28"
        editor.apply_resources()
        self.assertEqual(editor.attack_previews["left"]["damage"], 65)
        before = editor.character
        editor.gold_input.value = "-1"
        editor.apply_resources()
        self.assertEqual(editor.character, before)

    def test_use_vent_rest_and_save_preserve_broken_status(self):
        editor = self.combat_pilot()
        for _ in range(4):
            editor.weapon_action("left", "use")
        self.assertTrue(editor.character.inventory[0].condition.broken)
        self.assertEqual(editor.character.inventory[0].condition.heat, 4)
        before = editor.character
        editor.weapon_action("left", "use")
        self.assertEqual(editor.character, before)
        editor.weapon_action("left", "vent")
        self.assertEqual(editor.character.inventory[0].condition.heat, 3)
        editor.rest()
        self.assertEqual(editor.character.inventory[0].condition.heat, 0)
        self.assertTrue(editor.character.inventory[0].condition.broken)
        self.assertEqual((editor.character.current_health, editor.character.gold, editor.character.build.shield_adjustment), (27, 20000, 9))
        editor.save()
        self.assertEqual(self.store.load(editor.character.id), editor.character)

    def test_weapon_repair_cancel_stale_quote_and_confirmed_payment(self):
        editor = self.combat_pilot(health=20, gold=10100)
        for _ in range(4):
            editor.weapon_action("left", "use")
        before = editor.character
        editor.weapon_action("left", "repair")
        self.assertEqual(editor.character, before)
        self.assertIn("10,000", self.page.dialog.content.value)
        self.page.dialog.actions[0].on_click(None)
        self.assertEqual(editor.character, before)
        editor.weapon_action("left", "repair")
        editor.gold_input.value = "10101"
        self.page.dialog.actions[1].on_click(None)
        self.assertEqual(editor.character, before)
        self.assertIn("fresh quote", editor.status.value)
        editor.weapon_action("left", "repair")
        confirm = self.page.dialog.actions[1].on_click
        confirm(None)
        self.assertEqual(editor.character.gold, 101)
        self.assertEqual(editor.character.current_health, 20)
        self.assertFalse(editor.character.inventory[0].condition.broken)
        self.assertEqual(editor.character.inventory[0].condition.heat, 0)
        confirm(None)
        self.assertEqual(editor.character.gold, 101)

    def test_health_repair_ui_charges_actual_points_and_preserves_other_resources(self):
        editor = self.combat_pilot(health=100, gold=200)
        editor.weapon_action("left", "use")
        editor.health_repair_points.value = "5"
        editor.repair_health()
        self.assertEqual((editor.character.current_health, editor.character.gold), (105, 150))
        self.assertEqual(editor.character.inventory[0].condition.heat, 1)
        self.assertEqual(editor.character.build.shield_adjustment, 9)
        before = editor.character
        editor.repair_health()  # Blank/full repair is unaffordable.
        self.assertEqual(editor.character, before)

    def test_weapon_roll_boxes_update_only_on_use_and_survive_reload(self):
        editor = self.combat_pilot()

        def displayed(slot):
            return editor.roll_boxes[slot].content.controls[1].value

        self.assertEqual(displayed("left"), "—")
        with patch("zoids_app.combat_controller.random.randint", side_effect=[20, 1]) as roll:
            editor.weapon_action("left", "use")
            self.assertEqual(displayed("left"), "20")
            self.assertEqual(editor.character.inventory[0].condition.heat, 1)
            editor.weapon_action("fixed_1", "use")
            self.assertEqual(displayed("fixed_1"), "1")
            self.assertEqual(displayed("left"), "20")
            target = combat_snapshot(editor.character, editor.catalog)[1]["left"]
            editor.change_attack_range(target["identity"], "long")
            editor.weapon_action("left", "vent")
            editor.rest()
            editor.render()
            editor.save()
            saved_id = editor.character.id
            editor.new()
            editor.saved.value = saved_id
            editor.open_saved()
            self.assertEqual(displayed("left"), "20")
            self.assertEqual(displayed("fixed_1"), "1")
            self.assertEqual(roll.call_count, 2)

    def test_pilot_details_and_feat_tracking_survive_save_and_reload(self):
        editor = self.editor
        baseline = calculate_stats(editor.character.build, editor.catalog)
        editor.physical.value = "2"
        editor.social.value = "1"
        editor.personality.value = "Outspoken"
        editor.inventory_notes.value = "Spare parts × 3\nRations"
        editor.database_notes.value = "Ruins explored"
        editor.change_feat(0, "feats:phalanx_fire")
        editor.change_feat(6, "feats:demolitionist")
        self.assertEqual(calculate_stats(editor.character.build, editor.catalog), baseline)
        self.assertIn("advantage", editor.feat_descriptions[0].value)
        self.assertIn("vent", editor.feat_descriptions[6].value)
        editor.organoid_color.value = "White"
        editor.apply_organoid()
        self.assertEqual(editor.personality.value, "Outspoken")
        editor.acquisition.value = "zoids:liger_zero"
        self.confirm_purchase()
        editor.save()
        saved = editor.character
        editor.new()
        editor.saved.value = saved.id
        editor.open_saved()
        self.assertEqual(editor.character, saved)
        self.assertEqual((editor.physical.value, editor.social.value, editor.personality.value), ("2", "1", "Outspoken"))
        self.assertEqual(editor.inventory_notes.value, "Spare parts × 3\nRations")
        self.assertEqual(editor.database_notes.value, "Ruins explored")
        self.assertEqual(editor.feat_slots[6].value, "feats:demolitionist")
        editor.change_feat(6, "")
        self.assertNotIn("feats:demolitionist", editor.character.pilot_details.feats)

    def test_invalid_pilot_details_or_feat_does_not_overwrite_state(self):
        editor = self.editor
        editor.save()
        before = editor.character
        editor.physical.value = "two"
        editor.apply_profile()
        self.assertEqual(editor.character, before)
        editor.physical.value = "2"
        editor.change_feat(0, "feats:unknown")
        self.assertEqual(editor.character, before)
        self.assertEqual(editor.feat_slots[0].value, "")
        self.assertEqual(self.store.load(before.id), before)
