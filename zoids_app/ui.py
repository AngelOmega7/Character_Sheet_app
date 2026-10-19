"""First offline Flet character editor. Game rules remain outside the UI."""
from dataclasses import replace
import os
from pathlib import Path
import sqlite3

import flet as ft

from .catalog import Catalog
from .characters import (PilotDetails, acquire_equipment, acquire_zoid, assign_pilot_ability, available_equipment,
                         equip_owned_equipment, equipment_assignments, learn_pilot_ability,
                         new_character, return_equipment_to_inventory, switch_zoid, validate_character)
from .attacks import calculate_attack
from .combat import RepairConfirmationRequired, RuleError
from .combat_controller import combat_snapshot, repair_character_health, rest_active_loadout, weapon_action
from .equipment import SLOT_COLUMNS
from .stats import Upgrades
from .storage import CharacterStore
from .tags import weapon_tags

ASSETS_DIR = Path(__file__).resolve().parents[1] / "assets"


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
    def __init__(self, page, store, catalog):
        self.page, self.store, self.catalog = page, store, catalog
        self.character = new_character(catalog)
        self.dirty = False
        self.attack_bands = {}
        self.status = ft.Text("New character — save when ready.", color="#8CD9C8")
        self.body = ft.Column(spacing=18)
        self.saved = ft.Dropdown(label="Saved characters")
        self.page.add(ft.Column([
            ft.Row([ft.Image(src="icon.png", width=48, height=48, fit=ft.BoxFit.CONTAIN,
                             semantics_label="Zoids app icon"),
                    ft.Text("ZOIDS / PILOT HANGAR", size=28, weight=ft.FontWeight.BOLD, expand=True)]),
            ft.Text("Offline character manager · local saves", color="#AAC0D6"),
            ft.ResponsiveRow([ft.Container(self.saved, col={"xs": 12, "md": 10}),
                              ft.Container(ft.Button("Open", on_click=self.open_saved), col={"xs": 12, "md": 2})]),
            ft.Row([ft.Button("New character", on_click=self.new), ft.Button("Save character", on_click=self.save)], wrap=True),
            self.status, self.body,
            ft.Text(f"Save file: {store.path}", size=12, selectable=True, color="#AAC0D6"),
        ], spacing=16))
        self.refresh_saved()
        self.render()

    def message(self, text, error=False):
        self.status.value = text
        self.status.color = "#FFB4AB" if error else "#8CD9C8"
        self.page.update()

    def changed(self, event=None):
        self.dirty = True
        self.message("Unsaved changes. Apply details/upgrades to refresh stats, or Save character.")

    def refresh_saved(self):
        records = self.store.list_characters()
        self.saved.options = [option(r["id"], f"{r['name']} · {r['id'][:8]}") for r in records]
        self.saved.disabled = not records
        if records and self.saved.value not in {r["id"] for r in records}:
            self.saved.value = records[0]["id"]

    def confirm_switch(self, action):
        if not self.dirty:
            action()
            return

        def discard(event):
            self.page.pop_dialog()
            action()

        self.page.show_dialog(ft.AlertDialog(
            modal=True, title=ft.Text("Unsaved changes"),
            content=ft.Text("Discard changes and switch characters? Use Save character first to keep them."),
            actions=[ft.TextButton("Keep editing", on_click=lambda e: self.page.pop_dialog()),
                     ft.TextButton("Discard changes", on_click=discard)]))

    def new(self, event=None):
        def action():
            self.character = new_character(self.catalog)
            self.dirty = False
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
        try:
            upgrades = Upgrades(**{key: int(control.value) for key, control in self.frame_fields.items()},
                                damage=tuple(int(c.value) for c in self.damage_fields),
                                to_hit=tuple(int(c.value) for c in self.hit_fields))
        except (ValueError, TypeError) as exc:
            raise RuleError("Upgrade points must be whole numbers from 0 to 5") from exc
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
                                          gold=gold, pilot_details=details), self.catalog)

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

            self.page.show_dialog(ft.AlertDialog(modal=True, title=ft.Text("Confirm weapon repair"),
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
            self.health_input, self.shield_damage_input, self.gold_input,
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
            candidate = acquire_zoid(candidate, record["id"], self.catalog)
            owned = next(o for o in candidate.owned_zoids if o.base_zoid == record["ownership_base_id"])
            self.character = switch_zoid(candidate, owned.id, record["id"], self.catalog)
            self.dirty = True
            self.render()
            self.message(f"Obtained {record['name']}. Unsaved changes.")
        except RuleError as exc:
            self.message(str(exc), True)

    def apply_profile(self, event=None):
        try:
            self.character = self.profile_candidate()
            self.dirty = True
            self.render()
            self.message("Pilot details and upgrade points applied. Unsaved changes.")
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
        except (RuleError, OSError, sqlite3.Error) as exc:
            self.message(str(exc), True)

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
            self.character = acquire_equipment(candidate, selected_entry(self.equipment_to_acquire), quantity, self.catalog)
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

    def inventory_panel(self, character):
        records = sorted([r for r in self.catalog.tables["armaments"]["records"] if r["kind"] in {"record", "dynamic"}],
                         key=lambda r: r["name"].casefold())
        self.equipment_to_acquire = searchable_dropdown(label="Acquire equipment", options=[option(r["id"], r["name"]) for r in records])
        self.equipment_quantity = ft.TextField(label="Quantity", value="1", keyboard_type=ft.KeyboardType.NUMBER)
        assignments = equipment_assignments(character)
        ordinals, self.inventory_labels, rows = {}, {}, []
        for item in character.inventory:
            name = self.catalog.find("armaments", item.armament)["name"]
            ordinals[item.armament] = ordinals.get(item.armament, 0) + 1
            label = f"{name} · copy {ordinals[item.armament]}"
            self.inventory_labels[item.id] = label
            mounts = assignments.get(item.id, [])
            locations = [f"{self.catalog.find('zoids', form)['name']} / {slot.title()}" for _, form, slot in mounts]
            rows.append(ft.Column([ft.Text(label, weight=ft.FontWeight.BOLD),
                ft.Text("Assigned: " + "; ".join(locations) if mounts else "In inventory — unattached", size=12),
                ft.Text(f"Stored heat: {item.condition.heat} · {'BROKEN — attach to repair' if item.condition.broken else 'Intact'}", size=12),
                ft.Button("Return to inventory (all forms)", visible=bool(mounts),
                          on_click=lambda e, copy_id=item.id: self.return_equipment(copy_id))]))
        loose = sum(item.id not in assignments for item in character.inventory)
        return card("Pilot equipment inventory", [
            ft.Text(f"{len(character.inventory)} owned copies · {loose} unattached", size=13),
            self.equipment_to_acquire, self.equipment_quantity,
            ft.Button("Acquire equipment", on_click=self.obtain_equipment),
            ft.Text("Record equipment acquired in play; no gold is charged. Copies can be reused across CAU forms of the same Zoid, but never assigned to different Zoids or two slots in one form.", size=12),
            *rows,
        ])

    def activate(self, index, value, fixed=False):
        try:
            candidate = self.profile_candidate()
            field = "fixed_active" if fixed else "equipment_active"
            flags = list(getattr(candidate.build, field))
            flags[index] = value
            self.character = replace(candidate, build=replace(candidate.build, **{field: tuple(flags)}))
            self.dirty = True
            self.render()
            self.message("Activation updated. Unsaved changes.")
        except RuleError as exc:
            self.message(str(exc), True)

    def render(self):
        character, build = self.character, self.character.build
        stats, combat_weapons = combat_snapshot(character, self.catalog) if character.owned_zoids else (None, {})
        resources = self.resource_panel(character, stats)
        self.name = ft.TextField(label="Pilot / character name", value=character.name, on_change=self.changed)
        self.style = ft.Dropdown(label="Pilot style", value=build.pilot_style,
                                options=[option(s, s.title()) for s in ("FIGHTER", "TANK", "SCOUT", "ALMIGHTY")], on_select=self.changed)
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
        pilot_notes = card("Pilot notes · tracking", [self.personality, self.inventory_notes, self.database_notes,
            ft.Text("These notes and Physical/Social are player-managed. Equipment copies are tracked separately in the equipment inventory.", size=12)])
        feats = self.feat_panel(character)
        self.organoid_color = ft.Dropdown(label="Organoid color", value=build.organoid_color,
            options=[option(color, color) for color in ("White", "Red", "Blue", "Black")], on_select=self.apply_organoid)
        self.organoid_level = ft.Dropdown(label="Organoid level (0–40)", value=str(build.organoid_level), menu_height=300,
            options=[option(str(level), str(level)) for level in range(41)], on_select=self.apply_organoid)
        self.organoid_enabled = ft.Checkbox(label="Organoid activated", value=build.organoid_enabled, on_change=self.apply_organoid)
        organoid = card("Organoid", [self.organoid_color, self.organoid_level, self.organoid_enabled,
            ft.Text("Bonuses apply only while activated. Only White generates shields, using Organoid level. These pilot-wide settings follow Zoid and CAU switches; current health is preserved.", size=12)])
        abilities = self.ability_panel(build)
        active = next((o for o in character.owned_zoids if o.id == character.active_zoid_id), None)
        self.owned_select = ft.Dropdown(label="Owned Zoid", value=active.id if active else None, menu_height=300, disabled=active is None,
            options=[option(o.id, self.catalog.find("zoids", o.base_zoid)["name"]) for o in character.owned_zoids],
            on_select=lambda e: self.select_owned(e.control.value))
        self.form_select = ft.Dropdown(label="Obtained form", value=build.zoid or None, menu_height=300, disabled=active is None,
            options=[option(f.zoid, self.catalog.find("zoids", f.zoid)["name"]) for f in (active.forms if active else ())],
            on_select=lambda e: self.select_owned(active.id, e.control.value))
        owned_bases = {o.base_zoid for o in character.owned_zoids}
        owned_forms = {f.zoid for o in character.owned_zoids for f in o.forms}
        obtainable = sorted([r for r in self.catalog.tables["zoids"]["records"]
            if r["id"] not in owned_forms and (r["ownership_base_id"] == r["id"] or r["ownership_base_id"] in owned_bases)],
            key=lambda r: r["name"])
        self.acquisition = searchable_dropdown(label="Obtain a Zoid / CAU form",
                                      options=[option(r["id"], r["name"]) for r in obtainable], disabled=not obtainable)
        roster = card("Owned-Zoid hangar", [self.owned_select, self.form_select,
            ft.Text(f"{len(character.owned_zoids)} owned Zoid(s) · {len(active.forms) if active else 0} form(s) for this chassis", size=12),
            ft.Text("Switching preserves each chassis and form. Obtain a base before its CAU forms.", size=12),
            self.acquisition, ft.Button("Obtain & select", on_click=self.obtain, disabled=not obtainable),
            ft.Text("Record acquisitions from play; no gold is charged. Each base Zoid can be owned once.", size=12)])
        self.frame_fields = {key: ft.TextField(label=f"{key.title()} points", value=str(getattr(build.upgrades, key)),
            on_change=self.changed, keyboard_type=ft.KeyboardType.NUMBER) for key in ("speed", "reaction", "defense", "capacity")}
        self.damage_fields, self.hit_fields = [], []
        upgrade_controls = [ft.Text("Record upgrade points (0–5). Frame upgrades apply to every obtained form of this chassis. No purchase cost is charged.", size=12),
            ft.ResponsiveRow([ft.Container(c, col=6) for c in self.frame_fields.values()])]
        identities = self.catalog.find("zoids", build.zoid)["fixed_weapon_ids"] if active else (None,) * 4
        base_identities = self.catalog.find("zoids", active.base_zoid)["fixed_weapon_ids"] if active else ()
        for index, key in enumerate(identities):
            damage_field = ft.TextField(label="Damage points", value=str(build.upgrades.damage[index]),
                on_change=self.changed, disabled=key is None, keyboard_type=ft.KeyboardType.NUMBER)
            hit_field = ft.TextField(label="To-hit points", value=str(build.upgrades.to_hit[index]),
                on_change=self.changed, disabled=key is None, keyboard_type=ft.KeyboardType.NUMBER)
            self.damage_fields.append(damage_field)
            self.hit_fields.append(hit_field)
            if key:
                shared = "Shared with matching base weapon" if key in base_identities else "This form's weapon"
                upgrade_controls.extend([ft.Text(f"{index + 1}. {stats['weapons'][index]['name']} · {shared}", size=13),
                    ft.ResponsiveRow([ft.Container(damage_field, col=6), ft.Container(hit_field, col=6)])])
        upgrade_controls.append(ft.Button("Apply upgrades", on_click=self.apply_profile))
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
                self.roll_boxes[slot] = roll_box
                controls.append(roll_box)
                controls.extend([ft.Text(f"Heat: {condition.heat} / {weapon['maximum_heat'] if weapon['maximum_heat'] is not None else 'unrated'}"),
                    ft.Text("BROKEN — repair required" if condition.broken else "Ready", color="#FFB4AB" if condition.broken else "#8CD9C8")])
                if weapon["base_damage"] is not None:
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
            if index < 4:
                controls.append(ft.Checkbox(label="Activated", value=build.fixed_active[index],
                    disabled=not weapon["name"], on_change=lambda e, i=index: self.activate(i, e.control.value, True)))
            weapon_card = card(f"{index + 1}. {weapon['name'] or 'Empty'}", controls)
            weapon_card.col = {"xs": 12, "md": 6}
            weapon_cards.append(weapon_card)
        self.transport_section = card("Transport", [
            ft.Text("Transport Zoids carry other Zoids and store unused collected Zoids. Transport gameplay will be implemented later.", size=13),
            *[ft.Text(r["name"], size=16) for r in sorted(self.catalog.tables["transports"]["records"], key=lambda r: r["name"])],
            ft.Text("Reference only — not selectable as a normal Zoid.", size=12, color="#AAC0D6"),
        ])
        self.body.controls = [ft.ResponsiveRow([
            ft.Column([profile, pilot_notes, organoid, roster, upgrades_card, inventory_card, equipment_card], col={"xs": 12, "lg": 5}),
            ft.Column([summary, resources, ft.Text("Combat · weapons & equipment", size=22), ft.ResponsiveRow(weapon_cards), abilities, feats, self.transport_section], col={"xs": 12, "lg": 7}),
        ])]
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
        catalog = Catalog()
        CharacterEditor(page, CharacterStore(directory / "characters.sqlite3", catalog), catalog)
    except (RuleError, OSError, sqlite3.Error) as exc:
        page.add(ft.Text(f"Unable to open local saves: {exc}", color="#FFB4AB"))
