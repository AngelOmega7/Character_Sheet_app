"""First offline Flet character editor. Game rules remain outside the UI."""
from dataclasses import replace
import os
from pathlib import Path
import sqlite3

import flet as ft

from .catalog import Catalog
from .characters import (PilotDetails, acquire_equipment, acquire_zoid, assign_pilot_ability, available_equipment,
                         delete_equipment, equip_owned_equipment, equipment_assignments, learn_pilot_ability,
                         new_character, return_equipment_to_inventory, switch_zoid, validate_character)
from .attacks import calculate_attack
from .combat import RepairConfirmationRequired, RuleError
from .combat_controller import combat_snapshot, repair_character_health, rest_active_loadout, rolls_damage, weapon_action
from .commerce import change_upgrade, detach_cau, purchase_zoid, quote_purchase, recipe, recipe_parts, sell_zoid, set_known_design, set_material
from .transport import load_zoid, select_transport
from .equipment import SLOT_COLUMNS, equipment_template_name, resolved_equipment_name
from .stats import Upgrades
from .storage import CharacterStore
from .tags import weapon_tags

ASSETS_DIR = Path(__file__).resolve().parents[1] / "assets"
MAX_IMPORT_BYTES = 5 * 1024 * 1024


def export_filename(name, character_id):
    """Use a filesystem-safe default while keeping the save identifiable."""
    cleaned = "".join("_" if char in '<>:"/\\|?*' or ord(char) < 32 else char for char in str(name)).strip().rstrip(".")
    return f"{cleaned[:80] or 'character'}-{character_id[:8]}.json"


def option(key, text):
    return ft.DropdownOption(key=key, text=text)


def searchable_dropdown(**kwargs):
    """Native case-insensitive filtering with the full scrollable menu retained."""
    return ft.Dropdown(editable=True, enable_filter=True, enable_search=True, menu_height=300,
                       helper_text="Type to filter, or open the list and scroll.",
                       on_text_change=lambda e: None, **kwargs)


def selected_entry(dropdown):
    """Typing a query must not submit a stale previously selected entry."""
    selected = next((o for o in dropdown.options if o.key == dropdown.value), None)
    if dropdown.text is not None and (selected is None or dropdown.text != selected.text):
        raise RuleError("Select a matching entry from the dropdown list before continuing")
    return dropdown.value


def card(title, controls):
    return ft.Container(content=ft.Column([ft.Text(title, size=20, weight=ft.FontWeight.BOLD), *controls], spacing=14),
                        padding=20, bgcolor="#172333", border_radius=12)


class CharacterEditor:
    def __init__(self, page, store, catalog, file_picker=None):
        self.page, self.store, self.catalog = page, store, catalog
        self.file_picker = file_picker
        self.character = new_character(catalog)
        self.dirty = False
        self.attack_bands = {}
        self.view = "Overview"
        self.navigation = ft.Row(wrap=True)
        self.status = ft.Text("New character — save when ready.", color="#8CD9C8")
        self.body = ft.Column(spacing=18)
        self.saved = ft.Dropdown(label="Saved characters")
        self.delete_saved_button = ft.Button("Delete saved character", on_click=self.delete_saved)
        self.export_saved_button = ft.Button("Export selected", on_click=self.export_saved)
        self.import_saved_button = ft.Button("Import character", on_click=self.import_saved)
        self.page.add(ft.Column([
            ft.Row([ft.Image(src="icon.png", width=48, height=48, fit=ft.BoxFit.CONTAIN,
                             semantics_label="Zoids app icon"),
                    ft.Text("ZOIDS / PILOT HANGAR", size=28, weight=ft.FontWeight.BOLD, expand=True)]),
            ft.Text("Offline character manager · local saves", color="#AAC0D6"),
            ft.ResponsiveRow([ft.Container(self.saved, col={"xs": 12, "md": 10}),
                              ft.Container(ft.Button("Open", on_click=self.open_saved), col={"xs": 12, "md": 2})]),
            ft.Row([ft.Button("New character", on_click=self.new), ft.Button("Save character", on_click=self.save),
                    self.export_saved_button, self.import_saved_button, self.delete_saved_button], wrap=True),
            self.status, self.navigation, self.body,
            ft.Text(f"Save file: {store.path}", size=12, selectable=True, color="#AAC0D6"),
        ], spacing=16))
        self.refresh_saved()
        self.render()
        if hasattr(page, "window"):
            page.window.prevent_close = True
            page.window.on_event = self.window_event

    async def window_event(self, event):
        if event.type == ft.WindowEventType.CLOSE:
            self.confirm_switch(lambda: self.page.run_task(self.finish_close))

    async def finish_close(self):
        await self.page.window.destroy()

    def switch_page(self, name):
        try:
            candidate = self.profile_candidate()
            self.dirty = self.dirty or candidate != self.character
            self.character = candidate
            self.view = name
            self.render()
        except RuleError as exc:
            self.message(str(exc), True)

    def message(self, text, error=False):
        self.status.value = text
        self.status.color = "#FFB4AB" if error else "#8CD9C8"
        self.page.update()

    def changed(self, event=None):
        self.dirty = True
        self.message("Unsaved changes. Apply details to refresh stats, or Save character.")

    def refresh_saved(self):
        records = self.store.list_characters()
        self.saved.options = [option(r["id"], f"{r['name']} · {r['id'][:8]}") for r in records]
        self.saved.disabled = not records
        self.delete_saved_button.disabled = not records
        self.export_saved_button.disabled = not records or self.file_picker is None
        self.import_saved_button.disabled = self.file_picker is None
        if not records:
            self.saved.value = None
        if records and self.saved.value not in {r["id"] for r in records}:
            self.saved.value = records[0]["id"]

    def delete_saved(self, event=None):
        selected = self.saved.value
        try:
            record = next((r for r in self.store.list_characters() if r["id"] == selected), None)
            if record is None:
                raise RuleError("Select a saved character to delete")

            def confirm(event):
                self.page.pop_dialog()
                try:
                    self.store.delete(selected)
                    self.refresh_saved()
                    if self.character.id == selected:
                        self.character = new_character(self.catalog)
                        self.dirty = False
                        self.attack_bands.clear()
                        self.view = "Overview"
                        self.render()
                    self.message(f"Deleted saved character {record['name']}.")
                except (RuleError, OSError, sqlite3.Error) as exc:
                    self.message(str(exc), True)

            warning = f"Permanently delete {record['name']} ({selected[:8]}) and all of its saved state? This cannot be undone."
            if self.character.id == selected:
                warning += " Unsaved edits to this character will also be discarded."
            self.page.show_dialog(ft.AlertDialog(modal=True, scrollable=True, title=ft.Text("Delete saved character?"),
                content=ft.Text(warning), actions=[ft.TextButton("Cancel", on_click=lambda e: self.page.pop_dialog()),
                                                  ft.TextButton("Delete permanently", on_click=confirm)]))
        except (RuleError, OSError, sqlite3.Error) as exc:
            self.message(str(exc), True)

    async def export_saved(self, event=None):
        if self.file_picker is None:
            self.message("File export is unavailable in this environment.", True)
            return
        selected = self.saved.value
        try:
            record = next((r for r in self.store.list_characters() if r["id"] == selected), None)
            if record is None:
                raise RuleError("Select a saved character to export")
            text = self.store.export_character(selected)
            path = await self.file_picker.save_file(
                dialog_title="Export saved character",
                file_name=export_filename(record["name"], selected),
                file_type=ft.FilePickerFileType.CUSTOM,
                allowed_extensions=["json"],
                src_bytes=text.encode("utf-8"))
            if path:
                self.message(f"Exported saved character {record['name']} to {path}.")
            else:
                self.message("Export canceled.")
        except (RuleError, OSError, sqlite3.Error) as exc:
            self.message(str(exc), True)

    async def import_saved(self, event=None):
        if self.file_picker is None:
            self.message("File import is unavailable in this environment.", True)
            return
        try:
            files = await self.file_picker.pick_files(
                dialog_title="Import saved character", file_type=ft.FilePickerFileType.CUSTOM,
                allowed_extensions=["json"], allow_multiple=False, with_data=True)
            if not files:
                self.message("Import canceled.")
                return
            selected = files[0]
            data = selected.bytes
            if data is None and selected.path:
                path = Path(selected.path)
                if path.stat().st_size > MAX_IMPORT_BYTES:
                    raise RuleError("The import file is too large")
                data = path.read_bytes()
            if data is None:
                raise RuleError("The selected import file could not be read")
            if len(data) > MAX_IMPORT_BYTES:
                raise RuleError("The import file is too large")
            try:
                text = data.decode("utf-8-sig")
            except UnicodeDecodeError as exc:
                raise RuleError("The import file must be UTF-8 JSON") from exc
            imported = self.store.import_character(text)
            self.refresh_saved()
            self.saved.value = imported.id
            self.message(f"Imported {imported.name} as a saved character. Select Open to play it.")
        except (RuleError, OSError, sqlite3.Error) as exc:
            self.message(str(exc), True)

    def confirm_switch(self, action):
        if not self.dirty:
            action()
            return

        def discard(event):
            self.page.pop_dialog()
            action()

        def save_first(event):
            self.page.pop_dialog()
            if self.save():
                action()

        self.page.show_dialog(ft.AlertDialog(
            modal=True, title=ft.Text("Unsaved changes"),
            content=ft.Text("Save the current character before continuing?"),
            actions=[ft.TextButton("Keep editing", on_click=lambda e: self.page.pop_dialog()),
                     ft.TextButton("Discard changes", on_click=discard),
                     ft.TextButton("Save", on_click=save_first)]))

    def new(self, event=None):
        def action():
            self.character = new_character(self.catalog)
            self.dirty = False
            self.view = "Overview"
            self.render()
            self.message("New character — save when ready.")
        self.confirm_switch(action)

    def open_saved(self, event=None):
        if not self.saved.value:
            self.message("No saved character selected.", True)
            return
        selected = self.saved.value

        def action():
            try:
                character = self.store.load(selected)
                self.character = character
                self.saved.value = selected
                self.dirty = False
                self.render()
                self.message(f"Loaded {character.name}.")
            except (RuleError, OSError, sqlite3.Error) as exc:
                self.message(str(exc), True)
        self.confirm_switch(action)

    def profile_candidate(self):
        try:
            level, mental = int(self.level.value), int(self.mental.value)
        except (ValueError, TypeError) as exc:
            raise RuleError("Pilot level and Mental must be whole numbers") from exc
        if not 1 <= level <= 100:
            raise RuleError("Pilot level must be from 1 to 100")
        try:
            physical, social = int(self.physical.value), int(self.social.value)
        except (ValueError, TypeError) as exc:
            raise RuleError("Physical and Social must be whole numbers") from exc
        details = PilotDetails(physical=physical, social=social, personality=self.personality.value,
            inventory_notes=self.inventory_notes.value, database_notes=self.database_notes.value,
            feats=tuple(control.value or None for control in self.feat_slots))
        upgrades = self.character.build.upgrades
        try:
            organoid_level = int(self.organoid_level.value)
        except (ValueError, TypeError) as exc:
            raise RuleError("Organoid level must be a whole number from 0 to 40") from exc
        try:
            health, shields, gold = (int(control.value) for control in (self.health_input, self.shield_damage_input, self.gold_input))
        except (ValueError, TypeError) as exc:
            raise RuleError("Current health, shield damage, and gold must be nonnegative whole numbers") from exc
        build = replace(self.character.build, pilot_level=level, mental=mental,
                        pilot_style=self.style.value, upgrades=upgrades,
                        organoid_color=self.organoid_color.value, organoid_level=organoid_level,
                        organoid_enabled=self.organoid_enabled.value, shield_adjustment=shields)
        return validate_character(replace(self.character, name=self.name.value, build=build, current_health=health,
                                          gold=gold, pilot_details=details, transport_notes=self.transport_notes.value), self.catalog)

    def change_feat(self, slot, value):
        try:
            if type(slot) is not int or not 0 <= slot < 7:
                raise RuleError("Choose a feat slot from 1 to 7")
            self.feat_slots[slot].value = value or ""
            self.character = self.profile_candidate()
            self.dirty = True
            self.render()
            self.message("Feat tracking updated. Effects are handled at the table. Unsaved changes.")
        except RuleError as exc:
            if type(slot) is int and 0 <= slot < 7:
                feats = self.character.pilot_details.feats
                self.feat_slots[slot].value = (feats[slot] if slot < len(feats) else None) or ""
            self.message(str(exc), True)

    def feat_panel(self, character):
        records = sorted([r for r in self.catalog.tables["feats"]["records"] if r["kind"] == "record"], key=lambda r: r["name"])
        self.feat_slots, self.feat_descriptions = [], []
        controls = [ft.Text("Seven tracking slots, matching the pilot sheet. Feat effects and eligibility are handled by players at the table.", size=13)]
        feats = character.pilot_details.feats
        for slot in range(7):
            selected = feats[slot] if slot < len(feats) else None
            dropdown = ft.Dropdown(label=f"Feat {slot + 1}", value=selected or "", menu_height=300,
                options=[option("", "Empty"), *[option(r["id"], r["name"]) for r in records]],
                on_select=lambda e, i=slot: self.change_feat(i, e.control.value))
            description = self.catalog.find("feats", selected)["fields"]["description"] if selected else ""
            text = ft.Text(description or "", size=12, selectable=True, visible=bool(selected))
            self.feat_slots.append(dropdown)
            self.feat_descriptions.append(text)
            controls.extend([dropdown, text])
        return card("Pilot feats · player-managed", controls)

    def apply_resources(self, event=None):
        try:
            self.character = self.profile_candidate()
            self.dirty = True
            self.render()
            self.message("Combat resources recorded. Unsaved changes.")
        except RuleError as exc:
            self.message(str(exc), True)

    def commit_combat(self, result):
        self.character = result.character
        self.dirty = True
        self.render()
        self.message(result.message + " Unsaved changes.")

    def weapon_action(self, slot, action, *, confirmed=False, expected=None):
        try:
            candidate = self.profile_candidate()
            if expected is not None and candidate != expected:
                self.message("State changed since the repair quote. Click Repair again for a fresh quote.", True)
                return
            self.commit_combat(weapon_action(candidate, slot, action, confirmed=confirmed, catalog=self.catalog))
        except RepairConfirmationRequired as exc:
            quote = candidate

            def confirm(event):
                self.page.pop_dialog()
                self.weapon_action(slot, "repair", confirmed=True, expected=quote)

            self.page.show_dialog(ft.AlertDialog(modal=True, scrollable=True, title=ft.Text("Confirm weapon repair"),
                content=ft.Text(str(exc)), actions=[
                    ft.TextButton("Cancel", on_click=lambda e: self.page.pop_dialog()),
                    ft.TextButton("Repair anyway", on_click=confirm)]))
        except RuleError as exc:
            self.message(str(exc), True)

    def rest(self, event=None):
        try:
            self.commit_combat(rest_active_loadout(self.profile_candidate(), self.catalog))
        except RuleError as exc:
            self.message(str(exc), True)

    def repair_health(self, event=None):
        try:
            try:
                text = self.health_repair_points.value.strip()
                points = int(text) if text else None
            except (ValueError, TypeError) as exc:
                raise RuleError("Repair points must be a nonnegative whole number, or blank for full repair") from exc
            self.commit_combat(repair_character_health(self.profile_candidate(), points, self.catalog))
        except RuleError as exc:
            self.message(str(exc), True)

    def change_attack_range(self, identity, value):
        try:
            if value not in ("close", "normal", "long"):
                raise RuleError("Choose Close, Normal, or Long Range")
            candidate = self.profile_candidate()
            changed = candidate != self.character
            self.character = candidate
            self.dirty = self.dirty or changed
            self.attack_bands[identity] = value
            self.render()
            self.message("Attack preview updated. No use or heat added." + (" Unsaved changes." if self.dirty else ""))
        except RuleError as exc:
            self.message(str(exc), True)

    def resource_panel(self, character, stats):
        self.health_input = ft.TextField(label="Current health", value=str(character.current_health),
            keyboard_type=ft.KeyboardType.NUMBER, on_change=self.changed, disabled=stats is None)
        self.shield_damage_input = ft.TextField(label="Shield damage taken", value=str(character.build.shield_adjustment),
            keyboard_type=ft.KeyboardType.NUMBER, on_change=self.changed, disabled=stats is None)
        self.gold_input = ft.TextField(label="Pilot gold", value=str(character.gold),
            keyboard_type=ft.KeyboardType.NUMBER, on_change=self.changed)
        self.health_repair_points = ft.TextField(label="Health repair points (blank = full)", value="",
            keyboard_type=ft.KeyboardType.NUMBER, disabled=stats is None)
        text = (f"Health {character.current_health} / {stats['pilot']['health']} · "
                f"Shields {max(0, stats['shields'])} / {max(0, stats['shields'] + character.build.shield_adjustment)}") if stats else "Select an owned Zoid for combat."
        return card("Combat resources", [ft.Text(text, size=16),
            self.health_input, self.shield_damage_input,
            ft.Button("Apply resources", on_click=self.apply_resources),
            self.health_repair_points,
            ft.Row([ft.Button("Repair health · 10g/point", on_click=self.repair_health, disabled=stats is None),
                    ft.Button("Rest active loadout", on_click=self.rest, disabled=stats is None)], wrap=True),
            ft.Text("Rest clears heat in the current eight-slot loadout, without healing or repairing. Use rolls one d20 and records the use; apply the attack modifier and resolve effects at the table. Save character to keep combat changes and last rolls.", size=12)])

    def learn_selected_ability(self, event=None):
        if not self.ability_to_learn.value:
            self.message("Choose an ability or higher rank to learn.", True)
            return
        try:
            record = self.catalog.find("abilities", selected_entry(self.ability_to_learn))
            candidate = self.profile_candidate()
            self.character = learn_pilot_ability(candidate, record["id"], self.catalog)
            self.dirty = True
            self.render()
            self.message(f"Learned {record['name']}. New families are inactive; higher ranks replace the owned rank. Unsaved changes.")
        except RuleError as exc:
            self.message(str(exc), True)

    def change_ability_slot(self, slot, value):
        try:
            candidate = self.profile_candidate()
            self.character = assign_pilot_ability(candidate, slot, value or None, self.catalog)
            self.dirty = True
            self.render()
            self.message("Ability loadout updated. Unsaved changes.")
        except RuleError as exc:
            # Restore the displayed selection without erasing unrelated draft fields.
            if type(slot) is int and 0 <= slot < 6:
                active = self.character.build.abilities
                self.ability_slots[slot].value = (active[slot] if slot < len(active) else None) or ""
            self.message(str(exc), True)

    def apply_organoid(self, event=None):
        try:
            if self.organoid_color.value == "None":
                self.organoid_enabled.value = False
            self.character = self.profile_candidate()
            self.dirty = True
            self.render()
            self.message("Organoid settings applied. Current health preserved. Unsaved changes.")
        except RuleError as exc:
            build = self.character.build
            self.organoid_color.value = build.organoid_color
            self.organoid_level.value = str(build.organoid_level)
            self.organoid_enabled.value = build.organoid_enabled
            self.message(str(exc), True)

    def ability_panel(self, build):
        records = self.catalog.tables["abilities"]["records"]
        owned = [self.catalog.find("abilities", a) for a in (*build.abilities, *build.inactive_abilities) if a]
        ranks = {r["family"]: r["rank"] for r in owned}
        learnable = sorted([r for r in records if r["kind"] == "record" and r["rank"] > ranks.get(r["family"], 0)],
                           key=lambda r: (r["family"], r["rank"]))
        self.ability_description = ft.Text("Choose an ability to read its effect.", size=13, selectable=True)

        def describe(event):
            record = self.catalog.find("abilities", event.control.value)
            self.ability_description.value = record["fields"]["description"] or "No description."
            self.page.update()

        self.ability_to_learn = searchable_dropdown(label="Learn ability / upgrade rank",
            options=[option(r["id"], r["name"]) for r in learnable], on_select=describe, disabled=not learnable)
        inactive = sorted([self.catalog.find("abilities", a) for a in build.inactive_abilities], key=lambda r: r["name"].casefold())
        self.ability_slots = []
        slot_controls = []
        for slot in range(6):
            selected = build.abilities[slot] if slot < len(build.abilities) else None
            current = self.catalog.find("abilities", selected) if selected else None
            choices = ([option(current["id"], current["name"])] if current else []) + [option(r["id"], r["name"]) for r in inactive]
            dropdown = ft.Dropdown(label=f"Active ability {slot + 1}", value=selected or "", menu_height=300,
                options=[option("", "Empty / deactivate"), *choices],
                on_select=lambda e, i=slot: self.change_ability_slot(i, e.control.value))
            self.ability_slots.append(dropdown)
            slot_controls.append(dropdown)
            if current:
                handling = "Player-managed. " if current.get("handling") == "player_managed" else ""
                slot_controls.append(ft.Text(handling + (current["fields"]["description"] or ""), size=12, selectable=True))
        return card("Abilities", [
            ft.Text("Six active slots; one active size ability. Replacing a slot returns its ability to inactive ownership. Higher ranks permanently replace lower ranks.", size=13),
            self.ability_to_learn, self.ability_description,
            ft.Button("Learn / upgrade", on_click=self.learn_selected_ability, disabled=not learnable),
            *slot_controls,
            ft.Text(f"Owned inactive ({len(inactive)})", weight=ft.FontWeight.BOLD),
            *[ft.Text(f"{r['name']} — {r['fields']['description'] or ''}", size=12, selectable=True) for r in inactive],
            ft.Text("No inactive abilities yet." if not inactive else "Select an inactive ability in an active slot to activate it.", size=12),
            ft.Text("Weapon-card attack previews include range/health-dependent bonuses. Player-managed effects remain descriptive.", size=12, color="#AAC0D6"),
        ])

    def select_owned(self, owned_id, form_id=None):
        try:
            candidate = self.profile_candidate()
            self.character = switch_zoid(candidate, owned_id, form_id, self.catalog)
            self.dirty = True
            self.render()
            self.message("Switched owned Zoid/form. Upgrades and loadouts preserved. Unsaved changes.")
        except RuleError as exc:
            self.owned_select.value = self.character.active_zoid_id
            self.form_select.value = self.character.build.zoid
            self.message(str(exc), True)

    def obtain(self, event=None):
        if not self.acquisition.value:
            self.message("Select a Zoid or CAU form to obtain.", True)
            return
        try:
            candidate = self.profile_candidate()
            record = self.catalog.find("zoids", selected_entry(self.acquisition))
            quote = quote_purchase(candidate, record["id"], host_id=self.purchase_host.value or None,
                base_id=self.purchase_base.value or None,
                blox_ids=tuple(control.value or None for control in self.purchase_blox.controls),
                stored_fuzor_id=self.purchase_stored_fuzor.value if self.purchase_stored_fuzor.value not in (None, "new") else None,
                starter=candidate.starter_pending, catalog=self.catalog)
            override = bool(quote.issues)
            materials = ", ".join(f"{count} × {name}" for name, count in quote.materials) or "None"
            text = (record["name"] + "\n" + "\n".join(quote.issues) + "\n\nGM Override grants this build without spending gold, materials, or component/base Zoids.") if override else f"Purchase {record['name']} for {quote.cost:,}g?\nMaterials: {materials}"
            if quote.host_id:
                text += "\nHost: " + self.owner_label(next(o for o in candidate.owned_zoids if o.id == quote.host_id))
            if not override and quote.base_id:
                text += f"\nConsumes base Zoid instance {quote.base_id[:8]}; upgrades are lost and removable equipment is returned to inventory."
            if not override and quote.blox_ids:
                owners = {o.id: o for o in candidate.owned_zoids}
                text += "\nConsumes BLOX components:\n" + "\n".join(self.owner_label(owners[i]) for i in quote.blox_ids)
                text += "\nComponent upgrades, health, and weapon conditions are preserved for recovery when this FUZOR is sold. Removable equipment returns to inventory."
            if quote.predecessor:
                text += "\nReplaces predecessor CAU: " + self.catalog.find("zoids", quote.predecessor)["name"]
            if quote.stored_fuzor:
                text += f"\nRebuild stored FUZOR {quote.stored_fuzor.id[:8]} with its retained frame and weapon upgrades. This stored entry will be used up."
            def confirm(event):
                self.page.pop_dialog()
                try:
                    latest = self.profile_candidate()
                    if latest != candidate:
                        raise RuleError("Character changed; request a fresh purchase quote")
                    self.character = purchase_zoid(latest, quote, override=override, catalog=self.catalog)
                    self.dirty = True
                    self.render()
                    self.message(f"Obtained {record['name']}. Unsaved changes.")
                except RuleError as exc:
                    self.message(str(exc), True)
            self.page.show_dialog(ft.AlertDialog(modal=True, scrollable=True, title=ft.Text("GM Override confirmation" if override else "Confirm purchase"),
                content=ft.Text(text), actions=[ft.TextButton("Cancel", on_click=lambda e: self.page.pop_dialog()),
                                               ft.TextButton("GM Override" if override else "Purchase", on_click=confirm)]))
        except RuleError as exc:
            self.message(str(exc), True)

    def apply_profile(self, event=None):
        try:
            self.character = self.profile_candidate()
            self.dirty = True
            self.render()
            self.message("Pilot details applied. Unsaved changes.")
        except RuleError as exc:
            self.message(str(exc), True)

    def save(self, event=None):
        try:
            candidate = self.profile_candidate()
            self.character = self.store.save(candidate)
            self.dirty = False
            self.refresh_saved()
            self.saved.value = self.character.id
            self.render()
            self.message(f"Saved {self.character.name} locally.")
            return True
        except (RuleError, OSError, sqlite3.Error) as exc:
            self.message(str(exc), True)
            return False

    def change_equipment(self, slot, value):
        try:
            candidate = self.profile_candidate()
            self.character = equip_owned_equipment(candidate, slot, value or None, self.catalog)
            self.dirty = True
            self.render()
            self.message("Equipment updated. Unsaved changes.")
        except RuleError as exc:
            if slot in self.equipment_dropdowns:
                owner = next((o for o in self.character.owned_zoids if o.id == self.character.active_zoid_id), None)
                form = next((f for f in owner.forms if f.zoid == self.character.build.zoid), None) if owner else None
                copy_id = form.equipment_ids[list(SLOT_COLUMNS).index(slot)] if form else None
                self.equipment_dropdowns[slot].value = copy_id or ""
                self.equipment_dropdowns[slot].text = self.inventory_labels.get(copy_id, "Empty / unequip")
            self.message(str(exc), True)

    def obtain_equipment(self, event=None):
        if not self.equipment_to_acquire.value:
            self.message("Choose equipment to acquire.", True)
            return
        try:
            try:
                quantity = int(self.equipment_quantity.value)
            except (ValueError, TypeError) as exc:
                raise RuleError("Equipment quantity must be a positive whole number") from exc
            candidate = self.profile_candidate()
            selected = selected_entry(self.equipment_to_acquire)
            armament = self.acquisition_armaments.get(selected, selected)
            self.character = acquire_equipment(candidate, armament, quantity, self.catalog)
            self.dirty = True
            self.render()
            self.message(f"Added {quantity} equipment copy/copies to inventory. Unsaved changes.")
        except RuleError as exc:
            self.message(str(exc), True)

    def return_equipment(self, copy_id):
        try:
            candidate = self.profile_candidate()
            self.character = return_equipment_to_inventory(candidate, copy_id, self.catalog)
            self.dirty = True
            self.render()
            self.message("Equipment returned to inventory from all saved forms. Unsaved changes.")
        except RuleError as exc:
            self.message(str(exc), True)

    def delete_equipment_copy(self, copy_id):
        try:
            candidate = self.profile_candidate()
            item = next((i for i in candidate.inventory if i.id == copy_id), None)
            if item is None:
                raise RuleError("This pilot does not own that equipment copy")
            if copy_id in equipment_assignments(candidate):
                raise RuleError("Return this copy to inventory from all forms before deleting it")
            label = self.inventory_labels.get(copy_id, self.catalog.find("armaments", item.armament)["name"])

            def confirm(event):
                self.page.pop_dialog()
                try:
                    latest = self.profile_candidate()
                    self.character = delete_equipment(latest, copy_id, self.catalog)
                    self.dirty = True
                    self.render()
                    self.message(f"Deleted {label} from pilot inventory. Unsaved changes.")
                except RuleError as exc:
                    self.message(str(exc), True)

            warning = f"Permanently delete {label} from this pilot's inventory? This cannot be undone."
            if item.condition.heat or item.condition.broken:
                warning += f" Its stored heat ({item.condition.heat}) and condition will also be discarded."
            self.page.show_dialog(ft.AlertDialog(modal=True, scrollable=True, title=ft.Text("Delete equipment copy?"),
                content=ft.Text(warning), actions=[ft.TextButton("Cancel", on_click=lambda e: self.page.pop_dialog()),
                                                  ft.TextButton("Delete copy", on_click=confirm)]))
        except RuleError as exc:
            self.message(str(exc), True)

    def equipment_name(self, item, character, assignments):
        """Resolve Zoid-specific copies against their Zoid, not a generic slot name."""
        record = self.catalog.find("armaments", item.armament)
        if record["kind"] != "dynamic":
            return record["name"]
        forms = [form for _, form, _ in assignments.get(item.id, [])]
        if not forms and character.build.zoid:
            forms = [character.build.zoid]
        names = []
        for form in forms:
            name = resolved_equipment_name(record, form, self.catalog)
            if name != record["name"] and name not in names:
                names.append(name)
        return " / ".join(names) or record["name"]

    def equipment_acquisition_options(self, character):
        """List static gear plus Zoid-specific templates under their real names."""
        records = [r for r in self.catalog.tables["armaments"]["records"] if r["kind"] in {"record", "dynamic"}]
        self.acquisition_armaments = {}
        options = [option(r["id"], r["name"]) for r in records if r["kind"] == "record"]
        sources = {}
        for owned in character.owned_zoids:
            for form in owned.forms:
                zoid = self.catalog.find("zoids", form.zoid)
                for record in records:
                    if record["kind"] != "dynamic":
                        continue
                    name = resolved_equipment_name(record, zoid, self.catalog)
                    if name == record["name"]:
                        continue
                    key = (record["id"], name)
                    sources.setdefault(key, [])
                    if zoid["name"] not in sources[key]:
                        sources[key].append(zoid["name"])
        for (record_id, name), names in sources.items():
            key = f"dynamic|{record_id}|{name}"
            self.acquisition_armaments[key] = record_id
            template = self.catalog.find("armaments", record_id)
            options.append(option(key, f"{name} · {equipment_template_name(template)} ({', '.join(names)})"))
        return sorted(options, key=lambda o: o.text.casefold())

    def inventory_panel(self, character):
        self.equipment_to_acquire = searchable_dropdown(label="Acquire equipment",
                                                        options=self.equipment_acquisition_options(character))
        self.equipment_quantity = ft.TextField(label="Quantity", value="1", keyboard_type=ft.KeyboardType.NUMBER)
        assignments = equipment_assignments(character)
        ordinals, self.inventory_labels, rows = {}, {}, []
        for item in character.inventory:
            name = self.equipment_name(item, character, assignments)
            ordinals[item.armament] = ordinals.get(item.armament, 0) + 1
            label = f"{name} · copy {ordinals[item.armament]}"
            self.inventory_labels[item.id] = label
            mounts = assignments.get(item.id, [])
            locations = [f"{self.catalog.find('zoids', form)['name']} / {slot.title()}" for _, form, slot in mounts]
            rows.append(ft.Column([ft.Text(label, weight=ft.FontWeight.BOLD),
                ft.Text("Assigned: " + "; ".join(locations) if mounts else "In inventory — unattached", size=12),
                ft.Text(f"Stored heat: {item.condition.heat} · {'BROKEN — attach to repair' if item.condition.broken else 'Intact'}", size=12),
                ft.Button("Return to inventory (all forms)", visible=bool(mounts),
                          on_click=lambda e, copy_id=item.id: self.return_equipment(copy_id)),
                ft.Button("Delete copy", visible=not mounts,
                          on_click=lambda e, copy_id=item.id: self.delete_equipment_copy(copy_id)),
                ft.Text("Return this copy from all forms before deleting it.", visible=bool(mounts), size=12)]))
        loose = sum(item.id not in assignments for item in character.inventory)
        return card("Pilot equipment inventory", [
            ft.Text(f"{len(character.inventory)} owned copies · {loose} unattached", size=13),
            self.equipment_to_acquire, self.equipment_quantity,
            ft.Button("Acquire equipment", on_click=self.obtain_equipment),
            ft.Text("Record equipment acquired in play; no gold is charged. Copies can be reused across CAU forms of the same Zoid, but never assigned to different Zoids or two slots in one form. Zoid-specific entries resolve against the Zoid they are equipped to.", size=12),
            *rows,
        ])

    def activate(self, index, value, fixed=False):
        try:
            candidate = self.profile_candidate()
            field = "fixed_active" if fixed else "equipment_active"
            flags = list(getattr(candidate.build, field))
            flags[index] = value
            self.character = validate_character(replace(candidate, build=replace(candidate.build, **{field: tuple(flags)})), self.catalog)
            self.dirty = True
            self.render()
            self.message("Activation updated. Unsaved changes.")
        except RuleError as exc:
            self.message(str(exc), True)

    def purchase_selection(self, event=None):
        if not self.acquisition.value:
            return
        r = self.catalog.find("zoids", self.acquisition.value)
        data = recipe(self.catalog, r["id"])
        cau = r["id"] != r["ownership_base_id"]
        hosts = [o for o in self.character.owned_zoids if o.base_zoid == r["ownership_base_id"]
                 and not any(f.zoid == r["id"] for f in o.forms)] if cau else []
        self.purchase_host.options = [option(o.id, self.owner_label(o)) for o in hosts]
        self.purchase_host.value = self.character.active_zoid_id if any(o.id == self.character.active_zoid_id for o in hosts) else (hosts[0].id if len(hosts) == 1 else None)
        self.purchase_host.disabled = not cau
        candidates = [o for o in self.character.owned_zoids if o.base_zoid == data["base_zoid"] and len(o.forms) == 1]
        if cau and data["base_zoid"] == r["ownership_base_id"]:
            candidates = []
        self.purchase_base.options = [option(o.id, self.owner_label(o)) for o in candidates]
        self.purchase_base.value = candidates[0].id if len(candidates) == 1 else None
        self.purchase_base.disabled = not candidates
        stored = [s for s in self.character.stored_fuzors if s.zoid == r["id"]]
        self.purchase_stored_fuzor.options = [option("new", "New FUZOR — no retained upgrades"),
            *[option(s.id, f"{s.id[:8]} · Frame {s.frame.speed}/{s.frame.reaction}/{s.frame.defense}/{s.frame.capacity}"
                     f" · Weapon points {sum(w.damage + w.to_hit for w in s.weapons)}") for s in stored]]
        self.purchase_stored_fuzor.value = "new"
        self.purchase_stored_fuzor.visible = bool(stored)
        self.purchase_blox.controls = []
        for index, component in enumerate(data.get("blox", []), 1):
            candidates = [o for o in self.character.owned_zoids if o.base_zoid == component and len(o.forms) == 1]
            name = self.catalog.find("zoids", component)["name"]
            self.purchase_blox.controls.append(ft.Dropdown(label=f"BLOX {index}: {name} instance to consume",
                options=[option(o.id, self.owner_label(o)) for o in candidates],
                value=candidates[0].id if len(candidates) == 1 else None, disabled=not candidates))
        base_name = self.catalog.find("zoids", data["base_zoid"])["name"] if data["base_zoid"] else "None"
        self.purchase_details.value = f"Cost: {data['cost']:,}g · Core: {data['core'] or 'None'} · Parts: {data['parts'] or 'None'} · Base/prerequisite: {base_name}"
        if data.get("blox"):
            self.purchase_details.value += "\nFUZOR components: " + ", ".join(self.catalog.find("zoids", identity)["name"] for identity in data["blox"])
        self.page.update()

    def owner_label(self, owner):
        return f"{self.catalog.find('zoids', owner.base_zoid)['name']} · {owner.id[:8]}"

    def detach_selected_cau(self, event=None):
        try:
            candidate = self.profile_candidate()
            owner = next(o for o in candidate.owned_zoids if o.id == candidate.active_zoid_id)
            form = next(f for f in owner.forms if f.zoid == candidate.build.zoid)
            result = detach_cau(candidate, owner.id, form.zoid, self.catalog)
            parts = form.build_parts if form.build_parts is not None else recipe_parts(self.catalog, form.zoid)
            def confirm(event):
                self.page.pop_dialog()
                try:
                    latest = self.profile_candidate()
                    if latest != candidate or detach_cau(latest, owner.id, form.zoid, self.catalog) != result:
                        raise RuleError("State changed; request a fresh detachment quote")
                    self.character = result
                    self.dirty = True
                    self.render()
                    self.message("CAU detached; refund and Parts returned. Unsaved changes.")
                except RuleError as exc:
                    self.message(str(exc), True)
            self.page.show_dialog(ft.AlertDialog(modal=True, scrollable=True, title=ft.Text("Detach CAU permanently?"),
                content=ft.Text(f"Refund: {result.gold - candidate.gold:,}g. Return Parts: {', '.join(parts) or 'None'}. Form-specific upgrades are lost; removable equipment returns to inventory."),
                actions=[ft.TextButton("Cancel", on_click=lambda e: self.page.pop_dialog()), ft.TextButton("Detach", on_click=confirm)]))
        except (RuleError, StopIteration) as exc:
            self.message(str(exc) or "Select an owned CAU first", True)

    def sell_selected_zoid(self, event=None):
        try:
            candidate = self.profile_candidate()
            owner = next((o for o in candidate.owned_zoids if o.id == candidate.active_zoid_id), None)
            if owner is None:
                raise RuleError("Select an owned Zoid to sell")
            result = sell_zoid(candidate, owner.id, self.catalog)
            refund = result.gold - candidate.gold
            lines = [f"{self.catalog.find('zoids', f.zoid)['name']}: {recipe(self.catalog, f.zoid)['cost']:,}g" for f in owner.forms]
            restored = [o for o in result.owned_zoids if o.id not in {existing.id for existing in candidate.owned_zoids}]
            is_fuzor = self.catalog.find("zoids", owner.base_zoid).get("is_fuzor", False)
            retain = ft.Checkbox(label="Keep FUZOR identity and upgrades for rebuilding", value=False)

            def confirm(event):
                self.page.pop_dialog()
                try:
                    latest = self.profile_candidate()
                    if latest != candidate or sell_zoid(latest, owner.id, self.catalog) != result:
                        raise RuleError("State changed; request a fresh sale quote")
                    self.character = sell_zoid(latest, owner.id, self.catalog, retain_fuzor=bool(retain.value))
                    self.dirty = True
                    self.render()
                    self.message(f"Zoid and its CAUs sold for {refund:,}g. "
                                 + (f"Recovered {len(restored)} component Zoids. " if restored else "")
                                 + ("FUZOR identity and upgrades retained. " if retain.value else "") + "Unsaved changes.")
                except RuleError as exc:
                    self.message(str(exc), True)

            text = (f"Sell {self.owner_label(owner)} and all its currently owned CAUs?\n\n" + "\n".join(lines)
                    + f"\n\n75% refund: {refund:,}g.\n"
                    + ("The FUZOR leaves the hangar. Its identity and upgrades are discarded unless you select the keep option below. " if is_fuzor else
                       "The chassis, CAUs, and their upgrades will be removed. ")
                    + "Removable equipment stays in inventory, and the chassis is unloaded from Transport.")
            if restored:
                text += "\n\nRecovered components:\n" + "\n".join(self.owner_label(o) for o in restored)
                text += ("\nOriginal identities, upgrades, health, and fixed-weapon conditions will be restored."
                         if owner.fusion_components is not None else
                         "\nThis older FUZOR has no component history: fresh, unupgraded recipe copies will be returned.")
                text += " Equipment stays in inventory; recovered Zoids are not loaded into Transport."
            self.page.show_dialog(ft.AlertDialog(modal=True, scrollable=True, title=ft.Text("Confirm Zoid sale"),
                content=ft.Column([ft.Text(text), retain], tight=True) if is_fuzor else ft.Text(text),
                actions=[ft.TextButton("Cancel", on_click=lambda e: self.page.pop_dialog()),
                                               ft.TextButton("Sell Zoid and CAUs", on_click=confirm)]))
        except RuleError as exc:
            self.message(str(exc), True)

    def adjust_upgrade(self, field, delta, slot=None):
        try:
            candidate = self.profile_candidate()
            result = change_upgrade(candidate, field, delta, slot, self.catalog)
            difference = candidate.gold - result.gold
            self.character = result
            self.dirty = True
            self.render()
            self.message((f"Spent {difference:,}g." if difference >= 0 else f"Refunded {-difference:,}g.") + " Unsaved changes.")
        except RuleError as exc:
            self.message(str(exc), True)

    def upgrade_counter(self, label, value, field, slot=None, disabled=False):
        control = ft.TextField(label=label, value=str(value), read_only=True, width=100, disabled=disabled)
        base = 5000 if slot is None else 10000
        widget = ft.Column([ft.Row([
            ft.IconButton(icon=ft.Icons.REMOVE, disabled=disabled or value == 0, tooltip=f"Refund {base * value:,}g",
                          on_click=lambda e: self.adjust_upgrade(field, -1, slot)), control,
            ft.IconButton(icon=ft.Icons.ADD, disabled=disabled or value == 5, tooltip=f"Buy next point for {base * (value + 1):,}g",
                          on_click=lambda e: self.adjust_upgrade(field, 1, slot)),
        ], wrap=True), ft.Text(f"Next: {base * (value + 1):,}g" if value < 5 else "Maximum 5", size=12)])
        return control, widget

    def update_material(self, event=None, *, name=None, quantity=None):
        try:
            name = name or self.material_name.text or self.material_name.value
            if quantity is None:
                try:
                    quantity = int(self.material_quantity.value)
                except (ValueError, TypeError) as exc:
                    raise RuleError("Enter a nonnegative whole quantity") from exc
            self.character = set_material(self.profile_candidate(), name, quantity, self.catalog)
            self.dirty = True
            self.render()
            self.message("General inventory updated. Unsaved changes.")
        except RuleError as exc:
            self.message(str(exc), True)

    def update_known(self, event=None, *, identity=None, known=True):
        try:
            identity = identity or selected_entry(self.design_to_add)
            if not identity:
                raise RuleError("Select a Zoid design")
            self.character = set_known_design(self.profile_candidate(), identity, known, self.catalog)
            self.dirty = True
            self.render()
            self.message("Zi Database updated. Unsaved changes.")
        except RuleError as exc:
            self.message(str(exc), True)

    def purchasing_inventory_panels(self, character):
        names = {r["fields"][key] for r in self.catalog.tables["purchases"]["records"] for key in ("core", "parts") if r["fields"][key]}
        names.update(i.name for i in character.materials)
        self.material_name = searchable_dropdown(label="General item (or type a custom name)", options=[option(n, n) for n in sorted(names)])
        self.material_quantity = ft.TextField(label="Quantity (0 removes item)", value="1", keyboard_type=ft.KeyboardType.NUMBER)
        inventory = card("General inventory", [self.material_name, self.material_quantity,
            ft.Button("Set quantity", on_click=self.update_material),
            *[ft.Row([ft.Text(f"{i.name} × {i.quantity}", expand=True),
                      ft.TextButton("Remove", on_click=lambda e, n=i.name: self.update_material(name=n, quantity=0))]) for i in character.materials]])
        self.design_to_add = searchable_dropdown(label="Known Zoid design", options=[option(r["id"], r["name"]) for r in sorted(self.catalog.tables["zoids"]["records"], key=lambda r: r["name"])])
        database = card("Zi Database", [self.design_to_add, ft.Button("Add known design", on_click=self.update_known),
            *[ft.Row([ft.Text(self.catalog.find("zoids", identity)["name"], expand=True),
                      ft.TextButton("Remove", on_click=lambda e, i=identity: self.update_known(identity=i, known=False))]) for identity in character.known_zoids]])
        return inventory, database

    def change_transport(self, event):
        try:
            self.character = select_transport(self.profile_candidate(), event.control.value or None, self.catalog)
            self.dirty = True
            self.render()
            self.message("Transport changed; cargo unloaded. Owned Zoids are retained. Unsaved changes.")
        except RuleError as exc:
            self.message(str(exc), True)

    def load_cargo(self, identity, loaded=True):
        try:
            self.character = load_zoid(self.profile_candidate(), identity, loaded, self.catalog)
            self.dirty = True
            self.render()
            self.message("Transport cargo updated. Unsaved changes.")
        except RuleError as exc:
            self.message(str(exc), True)

    def transport_panels(self, character):
        transports = [self.catalog.find("transports", n) for n in ("Gustav", "Hover Cargo", "Dragoon Nest", "Whale King")]
        self.transport_picker = ft.Dropdown(label="Transport type", value=character.transport or "",
            options=[option("", "None"), *[option(r["id"], r["name"]) for r in transports]], on_select=self.change_transport)
        r = self.catalog.find("transports", character.transport) if character.transport else None
        stats = [ft.Text(f"{key.title()}: {r['fields'][key]}") for key in ("health", "armor", "defense", "speed", "reaction", "range")] if r else []
        if r:
            stats.extend([ft.Text(f"Shield: {(self.catalog.column(r, 24) or 0) + (self.catalog.column(r, 35) or 0)}"),
                          ft.Text(f"Hangar Capacity: {r['hangar_capacity']} · Hangar Size: {r['hangar_size']}")])
        self.transport_section = card("Transport", [self.transport_picker, *stats,
            ft.Text("GM-managed selection. Changing Transport unloads all cargo. Each owned chassis occupies one bay; its CAUs stay with it.", size=12)])
        owned, loaded = [], []
        for owner in character.owned_zoids:
            record = self.catalog.find("zoids", owner.active_form)
            label = f"{self.owner_label(owner)} · {record['name']} · {record['fields']['size']}"
            owned.append(ft.Row([ft.Text(label, expand=True), ft.Button("Load", disabled=not r or owner.id in character.loaded_zoids,
                on_click=lambda e, i=owner.id: self.load_cargo(i))]))
            if owner.id in character.loaded_zoids:
                loaded.append(ft.Row([ft.Text(label, expand=True), ft.Button("Unload", on_click=lambda e, i=owner.id: self.load_cargo(i, False))]))
        self.transport_notes = ft.TextField(label="Transport notes", value=character.transport_notes,
            multiline=True, min_lines=3, max_lines=10, on_change=self.changed)
        return [self.transport_section, card("All owned Zoids", owned),
                card(f"Loaded Zoids · {len(loaded)} / {r['hangar_capacity'] if r else 0}", loaded),
                card("Transport Notes", [self.transport_notes])]

    def render(self):
        character, build = self.character, self.character.build
        stats, combat_weapons = combat_snapshot(character, self.catalog) if character.owned_zoids else (None, {})
        resources = self.resource_panel(character, stats)
        transport_cards = self.transport_panels(character)
        general_inventory, database = self.purchasing_inventory_panels(character)
        self.name = ft.TextField(label="Pilot / character name", value=character.name, on_change=self.changed)
        self.style = ft.Dropdown(label="Pilot style", value=build.pilot_style,
                                options=[option(s, s.title() if s != "NPC" else s) for s in ("FIGHTER", "TANK", "SCOUT", "ALMIGHTY", "NPC")], on_select=self.changed)
        self.level = ft.TextField(label="Pilot level (1–100)", value=str(build.pilot_level), on_change=self.changed,
                                  keyboard_type=ft.KeyboardType.NUMBER)
        self.mental = ft.TextField(label="Mental", value=str(build.mental), on_change=self.changed,
                                   keyboard_type=ft.KeyboardType.NUMBER)
        details = character.pilot_details
        self.physical = ft.TextField(label="Physical · tracking", value=str(details.physical), on_change=self.changed,
                                    keyboard_type=ft.KeyboardType.NUMBER)
        self.social = ft.TextField(label="Social · tracking", value=str(details.social), on_change=self.changed,
                                  keyboard_type=ft.KeyboardType.NUMBER)
        self.personality = ft.TextField(label="Personality", value=details.personality, on_change=self.changed,
                                       multiline=True, min_lines=1, max_lines=3)
        self.inventory_notes = ft.TextField(label="General inventory / cargo notes", value=details.inventory_notes,
                                           on_change=self.changed, multiline=True, min_lines=3, max_lines=8)
        self.database_notes = ft.TextField(label="Zi Database / campaign notes", value=details.database_notes,
                                          on_change=self.changed, multiline=True, min_lines=3, max_lines=8)
        profile = card("Pilot", [self.name, self.style,
                        ft.ResponsiveRow([ft.Container(self.level, col=6), ft.Container(self.mental, col=6)]),
                        ft.ResponsiveRow([ft.Container(self.physical, col=6), ft.Container(self.social, col=6)]),
                         ft.Button("Apply pilot details", on_click=self.apply_profile)])
        pilot_notes = card("Pilot notes · tracking", [self.gold_input, self.personality, self.inventory_notes, self.database_notes,
            ft.Text("These notes and Physical/Social are player-managed. Equipment copies are tracked separately in the equipment inventory.", size=12)])
        feats = self.feat_panel(character)
        self.organoid_color = ft.Dropdown(label="Organoid color", value=build.organoid_color,
            options=[option(color, color) for color in ("None", "White", "Red", "Blue", "Black")], on_select=self.apply_organoid)
        self.organoid_level = ft.Dropdown(label="Organoid level (0–40)", value=str(build.organoid_level), menu_height=300,
            options=[option(str(level), str(level)) for level in range(41)], on_select=self.apply_organoid)
        self.organoid_enabled = ft.Checkbox(label="Organoid activated", value=build.organoid_enabled,
            disabled=build.organoid_color == "None", on_change=self.apply_organoid)
        self.organoid_level.disabled = build.organoid_color == "None"
        organoid = card("Organoid", [self.organoid_color, self.organoid_level, self.organoid_enabled,
            ft.Text("Bonuses apply only while activated. Only White generates shields, using Organoid level. These pilot-wide settings follow Zoid and CAU switches; current health is preserved.", size=12)])
        abilities = self.ability_panel(build)
        active = next((o for o in character.owned_zoids if o.id == character.active_zoid_id), None)
        self.owned_select = ft.Dropdown(label="Owned Zoid", value=active.id if active else None, menu_height=300, disabled=active is None,
            options=[option(o.id, self.owner_label(o)) for o in character.owned_zoids],
            on_select=lambda e: self.select_owned(e.control.value))
        self.form_select = ft.Dropdown(label="Obtained form", value=build.zoid or None, menu_height=300, disabled=active is None,
            options=[option(f.zoid, self.catalog.find("zoids", f.zoid)["name"]) for f in (active.forms if active else ())],
            on_select=lambda e: self.select_owned(active.id, e.control.value))
        owned_bases = {o.base_zoid for o in character.owned_zoids}
        obtainable = sorted([r for r in self.catalog.tables["zoids"]["records"]
            if (r["ownership_base_id"] == r["id"] or any(o.base_zoid == r["ownership_base_id"] and all(f.zoid != r["id"] for f in o.forms) for o in character.owned_zoids))
            and (not character.starter_pending or (r["ownership_base_id"] == r["id"] and recipe(self.catalog, r["id"])["cost"] <= 10000
                                                   and not recipe(self.catalog, r["id"])["base_zoid"]
                                                   and not recipe(self.catalog, r["id"]).get("blox")))],
            key=lambda r: r["name"])
        self.acquisition = searchable_dropdown(label="Purchase starting Zoid" if character.starter_pending else "Purchase Zoid / CAU form",
            options=[option(r["id"], f"{r['name']} · {recipe(self.catalog, r['id'])['cost']:,}g") for r in obtainable],
            disabled=not obtainable, on_select=self.purchase_selection)
        self.purchase_host = ft.Dropdown(label="CAU host instance", options=[], disabled=True)
        self.purchase_base = ft.Dropdown(label="Base Zoid instance to consume", options=[], disabled=True)
        self.purchase_blox = ft.Column([])
        self.purchase_stored_fuzor = ft.Dropdown(label="Rebuild stored FUZOR (frame: speed/reaction/defense/capacity)",
            options=[option("new", "New FUZOR — no retained upgrades")], value="new", visible=False)
        self.purchase_details = ft.Text("Select a design to view its recipe.", size=13)
        roster = card("Owned-Zoid hangar", [self.owned_select, self.form_select,
            ft.Text(f"{len(character.owned_zoids)} owned Zoid(s) · {len(active.forms) if active else 0} form(s) for this chassis", size=12),
            ft.Text(f"Required level: {self.catalog.find('zoids', build.zoid)['fields']['required_level']} · Type: {self.catalog.find('zoids', build.zoid)['fields'].get('type', 'Unknown')}" if active else "No active Zoid"),
            ft.Text("Starter: non-CAU, up to 10,000g, no Base Zoid or BLOX component requirement. Core, Parts, and Zi Database requirements are waived." if character.starter_pending else "Multiple copies are allowed. Select specific host/base/component instances when needed.", size=12),
            ft.Text(f"{len(character.stored_fuzors)} stored FUZOR rebuild(s). Select a matching design to reuse its identity and upgrades.",
                    size=12, visible=bool(character.stored_fuzors)),
            self.acquisition, self.purchase_details, self.purchase_host, self.purchase_base, self.purchase_blox, self.purchase_stored_fuzor,
            ft.Button("Review purchase", on_click=self.obtain, disabled=not obtainable),
            ft.Button("Detach selected CAU", disabled=not active or build.zoid == active.base_zoid, on_click=self.detach_selected_cau),
            ft.Button("Sell selected Zoid + CAUs", disabled=not active, on_click=self.sell_selected_zoid)])
        self.frame_fields, frame_widgets = {}, []
        for key in ("speed", "reaction", "defense", "capacity"):
            control, widget = self.upgrade_counter(key.title(), getattr(build.upgrades, key), key, disabled=not active)
            self.frame_fields[key] = control
            frame_widgets.append(ft.Container(widget, col={"xs": 12, "md": 6}))
        self.damage_fields, self.hit_fields = [], []
        upgrade_controls = [ft.Text("Points 0–5. Chassis tiers cost 5,000g × new rank; weapon tiers cost 10,000g × new rank. Minus refunds the full removed tier cost. Frame/shared-weapon upgrades follow the host across forms.", size=12),
            ft.ResponsiveRow(frame_widgets)]
        identities = self.catalog.find("zoids", build.zoid)["fixed_weapon_ids"] if active else (None,) * 4
        base_identities = self.catalog.find("zoids", active.base_zoid)["fixed_weapon_ids"] if active else ()
        for index, key in enumerate(identities):
            damage_field, damage_widget = self.upgrade_counter("Damage", build.upgrades.damage[index], "damage", index, key is None)
            hit_field, hit_widget = self.upgrade_counter("To-hit", build.upgrades.to_hit[index], "to_hit", index, key is None)
            self.damage_fields.append(damage_field)
            self.hit_fields.append(hit_field)
            if key:
                shared = "Shared with matching base weapon" if key in base_identities else "This form's weapon"
                upgrade_controls.extend([ft.Text(f"{index + 1}. {stats['weapons'][index]['name']} · {shared}", size=13),
                    ft.ResponsiveRow([ft.Container(damage_widget, col={"xs": 12, "md": 6}), ft.Container(hit_widget, col={"xs": 12, "md": 6})])])
        upgrades_card = card("Chassis & weapon upgrades", upgrade_controls)
        upgrades_card.visible = active is not None
        inventory_card = self.inventory_panel(character)
        equipment_controls = [ft.Text("Only compatible owned copies are listed. Unequipping clears this form's assignment; use Return to inventory to free a copy from all forms.", size=12)]
        self.equipment_dropdowns = {}
        active_form = next((f for f in active.forms if f.zoid == build.zoid), None) if active else None
        zoid_record = self.catalog.find("zoids", build.zoid) if active else None
        for index, (slot, column) in enumerate(SLOT_COLUMNS.items()):
            choices = available_equipment(character, slot, self.catalog) if active else ()
            slot_type = (self.catalog.column(zoid_record, column) or "No slot") if active else "No active Zoid"
            dropdown = searchable_dropdown(label=f"{index + 5}. {slot.title()} · {slot_type}",
                                   value=(active_form.equipment_ids[index] if active_form else None) or "",
                                   options=[option("", "Empty / unequip"), *[option(item.id, self.inventory_labels[item.id]) for item in choices]],
                                   disabled=not choices and not build.equipment[index],
                                   on_select=lambda e, s=slot: self.change_equipment(s, e.control.value))
            self.equipment_dropdowns[slot] = dropdown
            equipment_controls.extend([dropdown, ft.Checkbox(label="Activated (passive bonuses apply automatically)",
                value=build.equipment_active[index], disabled=not build.equipment[index],
                on_change=lambda e, i=index: self.activate(i, e.control.value))])
        equipment_card = card("Removable equipment", equipment_controls)
        equipment_card.visible = active is not None
        stat_values = {"Max health": stats["pilot"]["health"], "Armor": stats["current"]["armor"],
                       "Defense": stats["current"]["defense"], "Speed": stats["current"]["speed"],
                       "Reaction": stats["current"]["reaction"], "Range (m)": stats["current"]["range"],
                       "Shields remaining": max(0, stats["shields"]), "Carry": f"{stats['carry_load']} / {stats['carry_capacity']}"} if stats else {}
        tiles = [ft.Container(ft.Column([ft.Text(label, size=12, color="#AAC0D6"), ft.Text(str(value), size=24)]),
                              padding=12, bgcolor="#213349", border_radius=8, col={"xs": 6, "md": 3})
                 for label, value in stat_values.items()]
        notes = []
        if not stats:
            notes.append("No playable Zoid is currently owned. Obtain a Zoid to start a new loadout.")
        if stats and stats["underleveled"]:
            notes.append("Under required Zoid level: speed and reaction penalties apply.")
        if stats and stats["overloaded"]:
            notes.append("Over carry capacity: speed, reaction, and fixed attack penalties apply.")
        summary = card("Calculated stats", [ft.ResponsiveRow(tiles), *[ft.Text(note, color="#FFD08A") for note in notes]])
        weapon_cards = []
        self.attack_previews, self.range_controls = {}, {}
        self.roll_boxes = {}
        for index, weapon in enumerate(stats["weapons"] if stats else []):
            if not weapon["name"]:
                continue
            controls = [ft.Text(weapon["damage_type"] or "Utility / empty", color="#AAC0D6"),
                        ft.Text(weapon["effect"] or ("No effect text recorded." if weapon["name"] else "No equipment in this slot."), size=13)]
            slot = weapon["slot"]
            target = combat_weapons.get(slot)
            if target:
                condition = target["condition"]
                roll_box = ft.Container(content=ft.Column([
                    ft.Text("Last d20", size=12, color="#AAC0D6"),
                    ft.Text(str(condition.last_roll) if condition.last_roll is not None else "—",
                            size=32, weight=ft.FontWeight.BOLD, selectable=True),
                ], spacing=4), padding=12, width=110, bgcolor="#213349", border_radius=8,
                    tooltip="Unmodified d20 result from this weapon's last successful use.")
                if rolls_damage(weapon):
                    self.roll_boxes[slot] = roll_box
                    controls.append(roll_box)
                controls.extend([ft.Text(f"Heat: {condition.heat} / {weapon['maximum_heat'] if weapon['maximum_heat'] is not None else 'unrated'}"),
                    ft.Text("BROKEN — repair required" if condition.broken else "Ready", color="#FFB4AB" if condition.broken else "#8CD9C8")])
                if rolls_damage(weapon):
                    tags = weapon_tags(weapon["damage_type"])
                    ranged = "ranged" in tags and "melee" not in tags
                    band = self.attack_bands.get(target["identity"], "normal")
                    if ranged:
                        half_range = stats["current"]["range"] / 2
                        bands = ("close", "normal", "long") if half_range > 60 else ("close", "long")
                        if band not in bands:
                            band = "close"
                        range_control = ft.Dropdown(label="Attack range", value=band,
                            options=[option(value, value.title()) for value in bands],
                            on_select=lambda e, key=target["identity"]: self.change_attack_range(key, e.control.value))
                        self.range_controls[slot] = range_control
                        controls.append(range_control)
                        range_text = f"Close ≤60m; Normal >60m to {half_range}m; Long beyond both." if half_range > 60 else "Close ≤60m; Long >60m. No Normal band for this maximum range."
                        controls.append(ft.Text(f"{range_text} Maximum range: {stats['current']['range']}m.", size=12))
                    try:
                        preview = calculate_attack(build, slot, current_health=character.current_health,
                                                   range_band=band if ranged else None, catalog=self.catalog)
                        self.attack_previews[slot] = preview
                        controls.append(ft.Text(f"Attack preview · To-hit {preview['to_hit']:+} · Damage {preview['damage']}", weight=ft.FontWeight.BOLD))
                        if preview["sniper_bonus"] or preview["comeback_percent"]:
                            controls.append(ft.Text(f"Sniper +{preview['sniper_bonus']} · Comeback +{preview['comeback_percent'] * 100}%", size=12))
                    except RuleError as exc:
                        controls.append(ft.Text(f"Preview: {exc}", color="#FFD08A"))
                controls.append(ft.Row([
                    ft.Button("Use", disabled=condition.broken, on_click=lambda e, s=slot: self.weapon_action(s, "use")),
                    ft.Button("Vent", on_click=lambda e, s=slot: self.weapon_action(s, "vent")),
                    ft.Button("Repair · 10,000g", disabled=not condition.broken, on_click=lambda e, s=slot: self.weapon_action(s, "repair")),
                ], wrap=True))
            if not rolls_damage(weapon):
                controls.append(ft.Checkbox(label="Activated (passive is automatic)",
                    value=build.fixed_active[index] if index < 4 else build.equipment_active[index - 4],
                    on_change=lambda e, i=index: self.activate(i if i < 4 else i - 4, e.control.value, i < 4)))
            weapon_card = card(f"{index + 1}. {weapon['name'] or 'Empty'}", controls)
            weapon_card.col = {"xs": 12, "md": 6}
            weapon_cards.append(weapon_card)
        self.page_cards = {"Overview": [profile, organoid, roster], "Combat": [resources, ft.ResponsiveRow(weapon_cards)],
            "Upgrades": [upgrades_card, inventory_card, equipment_card],
            "Pilot": [abilities, feats, pilot_notes, general_inventory, database], "Transport": transport_cards}
        self.navigation.controls = [ft.Button(name, bgcolor="#213349" if name == self.view else None,
            on_click=lambda e, n=name: self.switch_page(n)) for name in self.page_cards]
        self.body.controls = ([] if self.view == "Transport" else [summary]) + self.page_cards[self.view]
        self.page.update()


async def main(page: ft.Page):
    page.title = "Zoids — Pilot Hangar"
    if page.platform == ft.PagePlatform.WINDOWS:
        page.window.icon = str(ASSETS_DIR / "icon.ico")
    page.theme_mode = ft.ThemeMode.DARK
    page.bgcolor = "#0D1622"
    page.padding = 20
    page.scroll = ft.ScrollMode.AUTO
    try:
        override = os.environ.get("ZOIDS_SAVE_DIR")
        if override:
            directory = Path(override)
        else:
            paths = ft.StoragePaths()
            page.services.append(paths)
            directory = Path(await paths.get_application_support_directory()) / "zoids-character-app"
        picker = ft.FilePicker()
        page.services.append(picker)
        catalog = Catalog()
        CharacterEditor(page, CharacterStore(directory / "characters.sqlite3", catalog), catalog, file_picker=picker)
    except (RuleError, OSError, sqlite3.Error) as exc:
        page.add(ft.Text(f"Unable to open local saves: {exc}", color="#FFB4AB"))
