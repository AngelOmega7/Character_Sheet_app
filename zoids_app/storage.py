"""Versioned transactional SQLite saves; no calculated totals are persisted."""
from contextlib import closing
from dataclasses import asdict, replace
from datetime import datetime, timezone
import json
from pathlib import Path
import sqlite3
from uuid import uuid4

from .catalog import Catalog
from .characters import Character, FixedWeaponCondition, FormLoadout, Material, OwnedEquipment, OwnedZoid, PilotDetails, StoredFuzor, WeaponUpgrade, adopt_legacy_character, migrate_equipment_inventory, restore_roster_selection, validate_character
from .combat import RuleError, WeaponCondition
from .stats import CharacterBuild, Upgrades

SAVE_VERSION = 10
EXPORT_FORMAT = "zoids-character-export"
EXPORT_FORMAT_VERSION = 1


def _upgrades(values):
    values = dict(values)
    for key in ("damage", "to_hit"):
        values[key] = tuple(values[key])
    return Upgrades(**values)


def _build(values):
    values = dict(values)
    values["upgrades"] = _upgrades(values["upgrades"])
    for key in ("abilities", "inactive_abilities", "equipment", "equipment_active", "fixed_active"):
        values[key] = tuple(values[key])
    return CharacterBuild(**values)


def _swap_last_fixed_slots(values):
    return (values[0], values[1], values[3], values[2])


def _owned(values, depth=0):
    if depth > 1:
        raise RuleError("Nested FUZOR component history is not supported")
    values = dict(values)
    if values.get("fusion_components") is not None:
        values["fusion_components"] = tuple(_owned(component, depth + 1) for component in values["fusion_components"])
    values["frame"] = _upgrades(values["frame"])
    values["weapons"] = tuple(WeaponUpgrade(**w) for w in values["weapons"])
    values["weapon_conditions"] = tuple(FixedWeaponCondition(w["weapon_id"], WeaponCondition(**w["condition"]))
                                        for w in values.get("weapon_conditions", []))
    forms = []
    for form in values["forms"]:
        form = dict(form)
        for key in ("equipment", "equipment_active", "fixed_active"):
            form[key] = tuple(form[key])
        form["equipment_ids"] = tuple(form.get("equipment_ids", (None,) * 4))
        if form.get("build_parts") is not None:
            form["build_parts"] = tuple(form["build_parts"])
        forms.append(FormLoadout(**form))
    values["forms"] = tuple(forms)
    return OwnedZoid(**values)


class CharacterStore:
    def __init__(self, path, catalog=None):
        self.path = Path(path)
        self.catalog = catalog or Catalog()
        self.path.parent.mkdir(parents=True, exist_ok=True)
        with closing(sqlite3.connect(self.path)) as db, db:
            version = db.execute("PRAGMA user_version").fetchone()[0]
            if version not in (*range(SAVE_VERSION), SAVE_VERSION):
                raise RuleError(f"Unsupported save database version: {version}")
            db.execute("""CREATE TABLE IF NOT EXISTS characters (
                id TEXT PRIMARY KEY, name TEXT NOT NULL, payload TEXT NOT NULL,
                updated_at TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%fZ','now'))
            )""")
            if version < SAVE_VERSION:
                # All rows migrate in one transaction. A corrupt row rolls back
                # every update and leaves the old schema version intact.
                for character_id, payload in db.execute("SELECT id, payload FROM characters").fetchall():
                    character = self._decode(payload, character_id, allow_legacy=True)
                    db.execute("UPDATE characters SET payload=? WHERE id=?", (self._encode(character), character_id))
            db.execute(f"PRAGMA user_version = {SAVE_VERSION}")

    def list_characters(self):
        with closing(sqlite3.connect(self.path)) as db:
            db.row_factory = sqlite3.Row
            return [dict(row) for row in db.execute(
                "SELECT id, name, updated_at FROM characters ORDER BY updated_at DESC, id")]

    def export_character(self, character_id):
        """Return one saved character as a portable, versioned JSON document."""
        character = self.load(character_id)
        return json.dumps({
            "format": EXPORT_FORMAT,
            "format_version": EXPORT_FORMAT_VERSION,
            "exported_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
            "save_version": SAVE_VERSION,
            "data_version": self.catalog.manifest["data_version"],
            "character": asdict(character),
        }, ensure_ascii=False, indent=2) + "\n"

    def import_character(self, text):
        """Validate an export/raw payload and save it without overwriting an existing ID."""
        try:
            document = json.loads(text)
        except (TypeError, json.JSONDecodeError) as exc:
            raise RuleError("The import file is not valid character JSON") from exc
        if not isinstance(document, dict):
            raise RuleError("The import file must contain a character document")
        if "format" in document or "format_version" in document:
            if document.get("format") != EXPORT_FORMAT:
                raise RuleError("The import file is not a Zoids character export")
            if type(document.get("format_version")) is not int or document["format_version"] != EXPORT_FORMAT_VERSION:
                raise RuleError("This character export uses an unsupported format version")
        values = document.get("character")
        if not isinstance(values, dict) or not isinstance(values.get("id"), str) or not values["id"]:
            raise RuleError("The import file does not contain a valid character")
        payload = json.dumps({"save_version": document.get("save_version"),
                              "data_version": document.get("data_version", ""),
                              "character": values}, ensure_ascii=False)
        character = self._decode(payload, values["id"], allow_legacy=True)
        if any(record["id"] == character.id for record in self.list_characters()):
            character = replace(character, id=str(uuid4()))
        return self.save(character)

    def _encode(self, character):
        manifest = self.catalog.manifest
        return json.dumps({"save_version": SAVE_VERSION, "data_version": manifest["data_version"],
                           "character": asdict(character)}, ensure_ascii=False)

    def save(self, character):
        character = validate_character(character, self.catalog)
        payload = self._encode(character)
        with closing(sqlite3.connect(self.path)) as db, db:
            db.execute("""INSERT INTO characters (id, name, payload) VALUES (?, ?, ?)
                ON CONFLICT(id) DO UPDATE SET name=excluded.name, payload=excluded.payload,
                updated_at=strftime('%Y-%m-%dT%H:%M:%fZ','now')""",
                       (character.id, character.name, payload))
        return character

    def load(self, character_id):
        with closing(sqlite3.connect(self.path)) as db:
            row = db.execute("SELECT payload FROM characters WHERE id=?", (character_id,)).fetchone()
        if row is None:
            raise RuleError("Saved character was not found")
        return self._decode(row[0], character_id)

    def delete(self, character_id):
        """Delete exactly one saved character, without affecting other saves."""
        with closing(sqlite3.connect(self.path)) as db, db:
            result = db.execute("DELETE FROM characters WHERE id=?", (character_id,))
            if result.rowcount != 1:
                raise RuleError("Saved character was not found")

    def _decode(self, text, character_id, allow_legacy=False):
        try:
            payload = json.loads(text)
            version = payload["save_version"]
            if type(version) is not int or version not in (range(1, SAVE_VERSION + 1) if allow_legacy else (SAVE_VERSION,)):
                raise RuleError("This character uses an unsupported save version")
            values = dict(payload["character"])
            details = dict(values.get("pilot_details", {}))
            details["feats"] = tuple(details.get("feats", ()))
            values["pilot_details"] = PilotDetails(**details)
            values["materials"] = tuple(Material(**i) for i in values.get("materials", []))
            values["known_zoids"] = tuple(values.get("known_zoids", []))
            values["loaded_zoids"] = tuple(values.get("loaded_zoids", []))
            values["stored_fuzors"] = tuple(StoredFuzor(i["id"], i["zoid"], _upgrades(i["frame"]),
                tuple(WeaponUpgrade(**w) for w in i["weapons"])) for i in values.get("stored_fuzors", []))
            archived = list(values.get("archived_content", []))
            removed_active = False
            if version < 3:
                removed = {key: r for r in self.catalog.tables["zoids"]["excluded_rows"]
                           if "id" in r for key in (r["id"], r["name"])}
                for transport in self.catalog.tables["transports"]["records"]:
                    original_id = transport["legacy_zoid_id"]
                    if original_id in removed:
                        for alias in transport.get("legacy_names", []):
                            removed[alias] = removed[original_id]
                retired_abilities = {key for r in self.catalog.tables["abilities"]["excluded_rows"]
                                     if "id" in r for key in (r["id"], r["name"])}
                build = dict(values["build"])
                for field in ("abilities", "inactive_abilities"):
                    kept = []
                    for index, ability in enumerate(build[field]):
                        if ability in retired_abilities:
                            archived.append({"kind": "ability", "reason": "Retired ability", "record": ability,
                                             "previous_list": field, "previous_slot": index})
                            if field == "abilities":
                                kept.append(None)
                        else:
                            kept.append(ability)
                    build[field] = kept
                values["build"] = build
                if version == 1:
                    if build["zoid"] in removed:
                        archived.append({"kind": "legacy_zoid", "reason": removed[build["zoid"]]["reason"],
                                         "record": {"build": payload["character"]["build"], "current_health": values["current_health"]}})
                        removed_active = True
                else:
                    roster = []
                    for owned in values["owned_zoids"]:
                        if owned["base_zoid"] in removed:
                            archived.append({"kind": "owned_zoid", "reason": removed[owned["base_zoid"]]["reason"], "record": owned})
                            removed_active = removed_active or owned["id"] == values["active_zoid_id"]
                        else:
                            roster.append(owned)
                    values["owned_zoids"] = roster
            values["archived_content"] = tuple(archived)
            values["inventory"] = tuple(OwnedEquipment(i["id"], i["armament"], WeaponCondition(**i.get("condition", {})))
                                        for i in values["inventory"]) if version >= 4 else ()
            values["build"] = _build(values["build"])
            if version >= 2:
                values["owned_zoids"] = tuple(_owned(o) for o in values["owned_zoids"])
                if values["owned_zoids"] and not values["active_zoid_id"]:
                    raise RuleError("Saved pilot has no active owned Zoid")
                if version < 7:
                    values["owned_zoids"] = tuple(replace(o, forms=tuple(
                        replace(f, fixed_active=_swap_last_fixed_slots(f.fixed_active)) if f.zoid == "zoids:zaber_fang" else f
                        for f in o.forms)) for o in values["owned_zoids"])
            elif values["build"].zoid in ("Zaber Fang", "zoids:zaber_fang"):
                build = values["build"]
                values["build"] = replace(build, fixed_active=_swap_last_fixed_slots(build.fixed_active),
                    upgrades=replace(build.upgrades, damage=_swap_last_fixed_slots(build.upgrades.damage),
                                     to_hit=_swap_last_fixed_slots(build.upgrades.to_hit)))
            character = Character(**values)
            if character.id != character_id:
                raise RuleError("Saved character ID does not match its database entry")
            if removed_active:
                character = restore_roster_selection(character, self.catalog)
            elif version == 1:
                from .workflow_migration import prepare_legacy_build
                character = replace(character, build=prepare_legacy_build(character.build, self.catalog))
                character = adopt_legacy_character(character, self.catalog)
            elif version < 7 and character.build.zoid == "zoids:zaber_fang":
                # Persistent upgrade/condition identities already belong to Killer
                # Saber; reproject them into its new slot before capture can run.
                character = restore_roster_selection(character, self.catalog)
            if version < 4 and (version != 1 or removed_active):
                character = migrate_equipment_inventory(character, self.catalog)
            if version < 8 and version != 1:
                from .workflow_migration import migrate_workflow
                character = migrate_workflow(character, self.catalog)
            from .workflow_migration import migrate_expanded_caus
            character = migrate_expanded_caus(character, self.catalog)
            return validate_character(character, self.catalog)
        except (KeyError, TypeError, ValueError, AttributeError) as exc:
            raise RuleError(f"Cannot load character: {exc}") from exc
