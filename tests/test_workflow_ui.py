import asyncio
from pathlib import Path
import tempfile
from types import SimpleNamespace
import unittest

try:
    import flet as ft
except ImportError:
    ft = None

from zoids_app.catalog import Catalog
from zoids_app.storage import CharacterStore
from test_ui import PageStub


class WindowStub:
    prevent_close = False
    closed = False

    async def destroy(self):
        self.closed = True


class WindowPage(PageStub):
    def __init__(self):
        self.window = WindowStub()
        self.scheduled = None

    def run_task(self, function):
        self.scheduled = function


@unittest.skipIf(ft is None, "Install Flet to run UI interaction tests")
class WorkflowUITests(unittest.TestCase):
    def setUp(self):
        from zoids_app.ui import CharacterEditor
        self.directory = tempfile.TemporaryDirectory()
        self.addCleanup(self.directory.cleanup)
        self.catalog = Catalog()
        self.store = CharacterStore(Path(self.directory.name) / "test.sqlite3", self.catalog)
        self.page = WindowPage()
        self.editor = CharacterEditor(self.page, self.store, self.catalog)

    def starter(self):
        self.editor.acquisition.value = "zoids:saberlion"
        self.editor.obtain()
        self.assertEqual(self.page.dialog.title.value, "Confirm purchase")
        self.page.dialog.actions[-1].on_click(None)

    def test_starter_pages_stats_and_draft_fields_survive_navigation(self):
        editor = self.editor
        self.assertEqual(editor.character.gold, 10000)
        self.assertTrue(editor.organoid_enabled.disabled)
        self.assertNotIn("zoids:zero_empire_cau", {o.key for o in editor.acquisition.options})
        self.starter()
        self.assertEqual(editor.character.gold, 4000)
        self.assertFalse(editor.character.starter_pending)
        editor.name.value = "Pilot A"
        editor.switch_page("Pilot")
        self.assertEqual(editor.character.name, "Pilot A")
        editor.database_notes.value = "Keep these notes"
        for page in ("Overview", "Combat", "Upgrades", "Pilot", "Transport"):
            editor.switch_page(page)
            self.assertEqual(editor.character.pilot_details.database_notes, "Keep these notes")
            title = editor.body.controls[0].content.controls[0].value
            self.assertEqual(title, "Transport" if page == "Transport" else "Calculated stats")
        editor.switch_page("Overview")
        self.assertTrue(any(isinstance(c, ft.Text) and "Required level:" in c.value for c in editor.page_cards["Overview"][2].content.controls))

    def test_purchase_confirmation_cancel_override_and_material_editing(self):
        self.starter()
        editor = self.editor
        editor.material_name.value = "Zoid Core H1"
        editor.material_quantity.value = "2"
        editor.update_material()
        editor.design_to_add.value = "zoids:godos"
        editor.update_known()
        editor.gold_input.value = "10000"
        editor.apply_profile()
        editor.acquisition.value = "zoids:godos"
        before = editor.character
        editor.obtain()
        self.page.dialog.actions[0].on_click(None)
        self.assertEqual(editor.character, before)
        editor.obtain()
        self.page.dialog.actions[-1].on_click(None)
        self.assertEqual(editor.character.gold, 0)
        self.assertEqual(editor.character.materials[0].quantity, 1)
        editor.acquisition.value = "zoids:saberlion"
        editor.obtain()
        self.assertEqual(self.page.dialog.title.value, "GM Override confirmation")
        self.page.dialog.actions[-1].on_click(None)
        self.assertEqual(len(editor.character.owned_zoids), 3)
        self.assertEqual(editor.character.gold, 0)

    def test_save_discard_cancel_and_failed_save_on_close(self):
        editor = self.editor
        editor.name.value = "Saved before closing"
        editor.changed()
        asyncio.run(editor.window_event(SimpleNamespace(type=ft.WindowEventType.CLOSE)))
        self.page.dialog.actions[0].on_click(None)
        self.assertFalse(self.page.window.closed)
        self.assertTrue(editor.dirty)
        asyncio.run(editor.window_event(SimpleNamespace(type=ft.WindowEventType.CLOSE)))
        self.page.dialog.actions[-1].on_click(None)
        self.assertEqual(self.store.load(editor.character.id).name, "Saved before closing")
        asyncio.run(self.page.scheduled())
        self.assertTrue(self.page.window.closed)
        self.page.window.closed = False
        self.page.scheduled = None
        editor.name.value = ""
        editor.changed()
        asyncio.run(editor.window_event(SimpleNamespace(type=ft.WindowEventType.CLOSE)))
        self.page.dialog.actions[-1].on_click(None)
        self.assertIsNone(self.page.scheduled)
        self.assertFalse(self.page.window.closed)
        asyncio.run(editor.window_event(SimpleNamespace(type=ft.WindowEventType.CLOSE)))
        self.page.dialog.actions[1].on_click(None)
        asyncio.run(self.page.scheduled())
        self.assertTrue(self.page.window.closed)

    def test_save_before_switching_saved_characters_keeps_requested_selection(self):
        editor = self.editor
        editor.name.value = "First"
        editor.save()
        first = editor.character.id
        editor.new()
        editor.name.value = "Second"
        editor.save()
        second = editor.character.id
        editor.name.value = "Second edited"
        editor.changed()
        editor.saved.value = first
        editor.open_saved()
        self.page.dialog.actions[-1].on_click(None)
        self.assertEqual(self.store.load(second).name, "Second edited")
        self.assertEqual(editor.character.id, first)
        self.assertEqual(editor.saved.value, first)

    def test_utility_cards_have_activation_without_dice_and_transport_loads(self):
        self.starter()
        editor = self.editor
        editor.acquisition.value = "zoids:liger_zero"
        editor.obtain()
        self.page.dialog.actions[-1].on_click(None)
        self.assertNotIn("fixed_2", editor.roll_boxes)
        self.assertIn("fixed_1", editor.roll_boxes)
        combat_cards = editor.page_cards["Combat"][1].controls
        self.assertEqual(len(combat_cards), 3)  # Three occupied fixed slots; no empty cards.
        for card in combat_cards:
            title = card.content.controls[0].value
            checkboxes = [c for c in card.content.controls if isinstance(c, ft.Checkbox)]
            self.assertEqual(len(checkboxes), 1 if "Ion Boosters" in title else 0)
        editor.transport_picker.value = "transports:hover_cargo"
        editor.change_transport(SimpleNamespace(control=editor.transport_picker))
        editor.load_cargo(editor.character.active_zoid_id)
        self.assertEqual(len(editor.character.loaded_zoids), 1)
        editor.transport_picker.value = "transports:gustav"
        editor.change_transport(SimpleNamespace(control=editor.transport_picker))
        self.assertEqual(editor.character.loaded_zoids, ())
        editor.load_cargo(editor.character.active_zoid_id)
        self.assertEqual(editor.character.loaded_zoids, ())  # Liger is too large.
