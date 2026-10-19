"""Versioned transactional SQLite saves; no calculated totals are persisted."""
from contextlib import closing
from dataclasses import asdict, replace
import json
from pathlib import Path
import sqlite3

from .catalog import Catalog
from .characters import Character, FixedWeaponCondition, FormLoadout, OwnedEquipment, OwnedZoid, PilotDetails, WeaponUpgrade, adopt_legacy_character, migrate_equipment_inventory, restore_roster_selection, validate_character
from .combat import RuleError, WeaponCondition
from .stats import CharacterBuild, Upgrades

SAVE_VERSION = 7


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


def _owned(values):
    values = dict(values)
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
            if version not in (0, 1, 2, 3, 4, 5, 6, SAVE_VERSION):
                raise RuleError(f"Unsupported save database version: {version}")
            db.execute("""CREATE TABLE IF NOT EXISTS characters (
                id TEXT PRIMARY KEY, name TEXT NOT NULL, payload TEXT NOT NULL,
                updated_at TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%fZ','now'))
            )""")
            if version in (0, 1, 2, 3, 4, 5, 6):
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

    def _encode(self, character):
        manifest = json.loads((Path(__file__).parent / "data/manifest.json").read_text(encoding="utf-8"))
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

    def _decode(self, text, character_id, allow_legacy=False):
        try:
            payload = json.loads(text)
            version = payload["save_version"]
            if type(version) is not int or version not in ((1, 2, 3, 4, 5, 6, SAVE_VERSION) if allow_legacy else (SAVE_VERSION,)):
                raise RuleError("This character uses an unsupported save version")
            values = dict(payload["character"])
            details = dict(values.get("pilot_details", {}))
            details["feats"] = tuple(details.get("feats", ()))
            values["pilot_details"] = PilotDetails(**details)
            archived = list(values.get("archived_content", []))
            removed_active = False
            if version < 3:
                removed = {key: r for r in self.catalog.tables["zoids"]["excluded_rows"]
                           if "id" in r for key in (r["id"], r["name"])}
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
                character = adopt_legacy_character(character, self.catalog)
            elif version < 7 and character.build.zoid == "zoids:zaber_fang":
                # Persistent upgrade/condition identities already belong to Killer
                # Saber; reproject them into its new slot before capture can run.
                character = restore_roster_selection(character, self.catalog)
            if version < 4 and (version != 1 or removed_active):
                character = migrate_equipment_inventory(character, self.catalog)
            return validate_character(character, self.catalog)
        except (KeyError, TypeError, ValueError, AttributeError) as exc:
            raise RuleError(f"Cannot load character: {exc}") from exc
