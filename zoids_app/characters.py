"""Pilot-owned Zoids, acquired CAU forms, and persistent upgrade identities."""
from dataclasses import dataclass, field, replace
from uuid import uuid4

from .catalog import Catalog
from .abilities import AbilityLoadout, activate_ability, deactivate_ability, learn_ability, validate_loadout
from .combat import RuleError, WeaponCondition
from .equipment import SLOT_COLUMNS, eligible_equipment
from .stats import CharacterBuild, Upgrades, calculate_stats


@dataclass(frozen=True)
class FormLoadout:
    zoid: str
    equipment: tuple[str | None, ...] = (None,) * 4
    equipment_active: tuple[bool, ...] = (False,) * 4
    fixed_active: tuple[bool, ...] = (False,) * 4
    equipment_ids: tuple[str | None, ...] = (None,) * 4


@dataclass(frozen=True)
class OwnedEquipment:
    id: str
    armament: str
    condition: WeaponCondition = field(default_factory=WeaponCondition)


@dataclass(frozen=True)
class FixedWeaponCondition:
    weapon_id: str
    condition: WeaponCondition = field(default_factory=WeaponCondition)


def fixed_weapon_identity(record, index):
    """Share base weapons across forms; utility equipment has a form/slot identity."""
    return record["fixed_weapon_ids"][index] or f"{record['id']}:fixed_{index + 1}"


@dataclass(frozen=True)
class WeaponUpgrade:
    weapon_id: str
    damage: int = 0
    to_hit: int = 0


@dataclass(frozen=True)
class OwnedZoid:
    id: str
    base_zoid: str
    forms: tuple[FormLoadout, ...]
    active_form: str
    frame: Upgrades
    weapons: tuple[WeaponUpgrade, ...]
    current_health: int
    shield_adjustment: int = 0
    defense_up: int = 0
    defense_down: int = 0
    weapon_conditions: tuple[FixedWeaponCondition, ...] = ()


@dataclass(frozen=True)
class PilotDetails:
    """Player-managed sheet fields; they never feed automated Zoid rules."""
    physical: int = 0
    social: int = 0
    personality: str = ""
    inventory_notes: str = ""
    database_notes: str = ""
    feats: tuple[str | None, ...] = ()


@dataclass(frozen=True)
class Character:
    id: str
    name: str
    build: CharacterBuild
    current_health: int
    gold: int = 0
    owned_zoids: tuple[OwnedZoid, ...] = ()
    active_zoid_id: str = ""
    archived_content: tuple[dict, ...] = ()
    inventory: tuple[OwnedEquipment, ...] = ()
    pilot_details: PilotDetails = field(default_factory=PilotDetails)


def _nonnegative(value, name):
    if type(value) is not int or value < 0:
        raise RuleError(f"{name} must be a nonnegative integer")


def _validate_build(build, catalog):
    equipment = []
    for slot, item in zip(SLOT_COLUMNS, build.equipment):
        record = catalog.find("armaments", item) if item else None
        if record and record not in eligible_equipment(build.zoid, slot, catalog):
            raise RuleError(f"{record['name']} cannot be equipped in {slot}")
        equipment.append(record["id"] if record else None)
    build = replace(build, zoid=catalog.find("zoids", build.zoid)["id"], equipment=tuple(equipment),
                    abilities=tuple(catalog.find("abilities", a)["id"] if a else None for a in build.abilities),
                    inactive_abilities=tuple(catalog.find("abilities", a)["id"] for a in build.inactive_abilities))
    calculate_stats(build, catalog)
    return build


def _loadout(build, equipment_ids=(None,) * 4):
    return FormLoadout(build.zoid, build.equipment, build.equipment_active, build.fixed_active, equipment_ids)


def _project(pilot_build, owned, form, catalog):
    """Adapt owned upgrades into the calculator's four positional weapon slots."""
    identities = catalog.find("zoids", form.zoid)["fixed_weapon_ids"]
    upgrades = {w.weapon_id: w for w in owned.weapons}
    points = [upgrades.get(key, WeaponUpgrade(key)) for key in identities]
    return replace(pilot_build, zoid=form.zoid, equipment=form.equipment,
                   equipment_active=form.equipment_active, fixed_active=form.fixed_active,
                   upgrades=replace(owned.frame, damage=tuple(w.damage for w in points),
                                    to_hit=tuple(w.to_hit for w in points)),
                   shield_adjustment=owned.shield_adjustment,
                   defense_up=owned.defense_up, defense_down=owned.defense_down)


def _capture(character, owned, catalog):
    """Flush active calculator inputs back into the owned chassis and form."""
    build = character.build
    identities = catalog.find("zoids", build.zoid)["fixed_weapon_ids"]
    weapons = {w.weapon_id: w for w in owned.weapons}
    for key, damage, hit in zip(identities, build.upgrades.damage, build.upgrades.to_hit):
        if key is None:
            if damage or hit:
                raise RuleError("Empty and utility slots cannot receive weapon upgrades")
        else:
            weapons[key] = WeaponUpgrade(key, damage, hit)
    return replace(owned, forms=tuple(_loadout(build, f.equipment_ids) if f.zoid == build.zoid else f for f in owned.forms),
                   frame=replace(build.upgrades, damage=(0,) * 4, to_hit=(0,) * 4),
                   weapons=tuple(weapons.values()), current_health=character.current_health,
                   shield_adjustment=build.shield_adjustment, defense_up=build.defense_up, defense_down=build.defense_down)


def validate_character(character, catalog=None):
    """Validate every owned form and synchronize the active build without healing."""
    catalog = catalog or Catalog()
    if not isinstance(character.id, str) or not character.id.strip():
        raise RuleError("Character ID is required")
    if not isinstance(character.name, str) or not character.name.strip():
        raise RuleError("Enter a character name")
    if len(character.name.strip()) > 100:
        raise RuleError("Character name must be at most 100 characters")
    _nonnegative(character.current_health, "current_health")
    _nonnegative(character.gold, "gold")
    details = character.pilot_details
    if not isinstance(details, PilotDetails):
        raise RuleError("Pilot details must be a valid tracking record")
    for name in ("physical", "social"):
        if type(getattr(details, name)) is not int:
            raise RuleError(f"{name.title()} must be a whole number")
    for name in ("personality", "inventory_notes", "database_notes"):
        if not isinstance(getattr(details, name), str):
            raise RuleError(f"{name} must be text")
    if len(details.feats) > 7:
        raise RuleError("At most seven feat slots are supported")
    feats = []
    for entry in details.feats:
        if entry is None:
            feats.append(None)
            continue
        record = catalog.find("feats", entry)
        if record["kind"] == "placeholder":
            feats.append(None)
        elif record["kind"] == "record":
            feats.append(record["id"])
        else:
            raise RuleError("Choose a feat from the reference catalog")
    while feats and feats[-1] is None:
        feats.pop()
    character = replace(character, pilot_details=replace(details, feats=tuple(feats)))
    # Selected Organoid settings must remain valid even while deactivated.
    if character.build.organoid_color not in ("White", "Red", "Blue", "Black"):
        raise RuleError("Choose a White, Red, Blue, or Black Organoid")
    if type(character.build.organoid_level) is not int or not 0 <= character.build.organoid_level <= 40:
        raise RuleError("Organoid level must be a whole number from 0 to 40")
    catalog.find("organoids", str(character.build.organoid_level))
    inventory = []
    copies = {}
    for item in character.inventory:
        if not isinstance(item.id, str) or not item.id.strip() or item.id in copies:
            raise RuleError("Each equipment copy must have a unique inventory ID")
        record = catalog.find("armaments", item.armament)
        if record["kind"] not in {"record", "dynamic"}:
            raise RuleError("Only actual equipment can be acquired")
        if not isinstance(item.condition, WeaponCondition):
            raise RuleError("Inventory equipment must have a valid weapon condition")
        item = replace(item, armament=record["id"])
        copies[item.id] = item
        inventory.append(item)
    character = replace(character, inventory=tuple(inventory))
    if not character.owned_zoids:
        build = character.build
        if character.active_zoid_id or build.zoid:
            raise RuleError("A pilot with no owned Zoids cannot have an active Zoid")
        if any(build.equipment) or any(build.equipment_active) or any(build.fixed_active) or build.upgrades != Upgrades():
            raise RuleError("A pilot with no owned Zoids cannot have an active loadout")
        catalog.find(build.pilot_style.lower(), str(build.pilot_level))
        abilities = tuple(catalog.find("abilities", a)["id"] if a else None for a in build.abilities)
        inactive = tuple(catalog.find("abilities", a)["id"] for a in build.inactive_abilities)
        validate_loadout(AbilityLoadout(abilities, inactive), catalog)
        return replace(character, name=character.name.strip(), build=replace(build, abilities=abilities, inactive_abilities=inactive))
    build = _validate_build(character.build, catalog)
    character = replace(character, name=character.name.strip(), build=build)
    seen_ids, seen_bases, roster = set(), set(), []
    assigned_chassis = {}
    for owned in character.owned_zoids:
        base = catalog.find("zoids", owned.base_zoid)
        if base["ownership_base_id"] != base["id"]:
            raise RuleError("CAU forms must belong to their base Zoid")
        if not isinstance(owned.id, str) or not owned.id or owned.id in seen_ids or base["id"] in seen_bases:
            raise RuleError("Each base Zoid can be owned only once, with a unique instance ID")
        seen_ids.add(owned.id)
        seen_bases.add(base["id"])
        for name in ("current_health", "shield_adjustment", "defense_up", "defense_down"):
            _nonnegative(getattr(owned, name), name)
        if any(owned.frame.damage) or any(owned.frame.to_hit):
            raise RuleError("Frame upgrades cannot contain weapon-slot upgrades")
        form_ids = [f.zoid for f in owned.forms]
        if len(set(form_ids)) != len(form_ids) or base["id"] not in form_ids or owned.active_form not in form_ids:
            raise RuleError("Owned forms must be unique and include the base and selected form")
        valid_weapons = set()
        valid_conditions = set()
        for form in owned.forms:
            record = catalog.find("zoids", form.zoid)
            if record["id"] != form.zoid or record["ownership_base_id"] != base["id"]:
                raise RuleError("CAU form does not belong to this owned Zoid")
            valid_weapons.update(k for k in record["fixed_weapon_ids"] if k)
            valid_conditions.update(fixed_weapon_identity(record, i) for i, column in enumerate((13, 19, 30, 41))
                                    if catalog.column(record, column))
        if len({w.weapon_id for w in owned.weapons}) != len(owned.weapons):
            raise RuleError("Duplicate weapon upgrade identity")
        for weapon in owned.weapons:
            if weapon.weapon_id not in valid_weapons:
                raise RuleError("Weapon upgrades reference an unowned form or unknown weapon")
            Upgrades(damage=(weapon.damage, 0, 0, 0), to_hit=(weapon.to_hit, 0, 0, 0))
        if len({w.weapon_id for w in owned.weapon_conditions}) != len(owned.weapon_conditions):
            raise RuleError("Duplicate fixed-weapon condition identity")
        for weapon in owned.weapon_conditions:
            if weapon.weapon_id not in valid_conditions or not isinstance(weapon.condition, WeaponCondition):
                raise RuleError("Fixed-weapon condition must reference an acquired form's weapon")
        forms = tuple(_loadout(_validate_build(_project(build, owned, f, catalog), catalog), f.equipment_ids) for f in owned.forms)
        owned = replace(owned, base_zoid=base["id"], forms=forms)
        if owned.id == character.active_zoid_id:
            if owned.active_form != build.zoid:
                raise RuleError("Use the owned-Zoid switch action to select a different Zoid or form")
            owned = _capture(character, owned, catalog)
        for form in owned.forms:
            if len(form.equipment_ids) != 4:
                raise RuleError("Four inventory-copy references are required for each form")
            form_copies = set()
            for armament, copy_id in zip(form.equipment, form.equipment_ids):
                if armament is None and copy_id is None:
                    continue
                if copy_id not in copies or copies[copy_id].armament != armament:
                    raise RuleError("Equipped items must reference matching owned inventory copies")
                if copy_id in form_copies:
                    raise RuleError("One equipment copy cannot occupy multiple slots in the same form")
                form_copies.add(copy_id)
                if copy_id in assigned_chassis and assigned_chassis[copy_id] != owned.id:
                    raise RuleError("One equipment copy cannot be assigned to different owned Zoids")
                assigned_chassis[copy_id] = owned.id
        roster.append(owned)
    if character.active_zoid_id not in seen_ids:
        raise RuleError("Select an owned Zoid")
    return replace(character, owned_zoids=tuple(roster))


def adopt_legacy_character(character, catalog=None):
    """Migrate a v1 active build into one owned base plus its active CAU if any."""
    catalog = catalog or Catalog()
    build = _validate_build(character.build, catalog)
    record = catalog.find("zoids", build.zoid)
    base = record["ownership_base_id"]
    forms = (FormLoadout(base),) if base != build.zoid else ()
    owned = OwnedZoid(str(uuid4()), base, (*forms, _loadout(build)), build.zoid,
                      Upgrades(), (), character.current_health)
    character = replace(character, build=build, owned_zoids=(owned,), active_zoid_id=owned.id)
    return validate_character(migrate_equipment_inventory(character, catalog), catalog)


def new_character(catalog=None):
    catalog = catalog or Catalog()
    build = CharacterBuild("zoids:saberlion")
    return adopt_legacy_character(Character(str(uuid4()), "New pilot", build,
                                           calculate_stats(build, catalog)["pilot"]["health"]), catalog)


def acquire_zoid(character, zoid, catalog=None):
    """Obtain a base Zoid or one CAU form; acquisition does not switch pilots."""
    catalog = catalog or Catalog()
    character = validate_character(character, catalog)
    record = catalog.find("zoids", zoid)
    base = record["ownership_base_id"]
    existing = next((o for o in character.owned_zoids if o.base_zoid == base), None)
    if record["id"] != base:
        if existing is None:
            raise RuleError("Obtain the base Zoid before obtaining a CAU form")
        if any(f.zoid == record["id"] for f in existing.forms):
            raise RuleError("This CAU form is already owned")
        updated = replace(existing, forms=(*existing.forms, FormLoadout(record["id"])))
        roster = tuple(updated if o.id == existing.id else o for o in character.owned_zoids)
    else:
        if existing:
            raise RuleError("This base Zoid is already owned")
        fresh_build = replace(character.build, zoid=base, equipment=(None,) * 4,
                              equipment_active=(False,) * 4, fixed_active=(False,) * 4,
                              upgrades=Upgrades(), shield_adjustment=0, defense_up=0, defense_down=0)
        health = calculate_stats(fresh_build, catalog)["pilot"]["health"]
        owned = OwnedZoid(str(uuid4()), base, (FormLoadout(base),), base, Upgrades(), (), health)
        roster = (*character.owned_zoids, owned)
    if not character.owned_zoids:
        return validate_character(replace(character, owned_zoids=roster, active_zoid_id=owned.id,
                                          build=fresh_build, current_health=health), catalog)
    return validate_character(replace(character, owned_zoids=roster), catalog)


def switch_zoid(character, owned_id, form_id=None, catalog=None):
    """Switch without dropping upgrades, form loadouts, or each chassis's health."""
    catalog = catalog or Catalog()
    character = validate_character(character, catalog)
    owned = next((o for o in character.owned_zoids if o.id == owned_id), None)
    if owned is None:
        raise RuleError("This pilot does not own that Zoid")
    form_id = form_id or owned.active_form
    form = next((f for f in owned.forms if f.zoid == form_id), None)
    if form is None:
        raise RuleError("This CAU form has not been obtained")
    owned = replace(owned, active_form=form_id)
    roster = tuple(owned if o.id == owned.id else o for o in character.owned_zoids)
    build = _project(character.build, owned, form, catalog)
    return validate_character(replace(character, build=build, current_health=owned.current_health,
                                      owned_zoids=roster, active_zoid_id=owned.id), catalog)


def set_upgrades(character, upgrades, catalog=None):
    """Assign recorded points (0–5); shared weapon IDs propagate across slots/forms."""
    return validate_character(replace(character, build=replace(character.build, upgrades=upgrades)), catalog)


def learn_pilot_ability(character, ability, catalog=None):
    """Learn inactive or permanently replace an owned lower rank in place."""
    catalog = catalog or Catalog()
    loadout = learn_ability(AbilityLoadout(character.build.abilities, character.build.inactive_abilities), ability, catalog)
    return validate_character(replace(character, build=replace(character.build,
        abilities=loadout.active, inactive_abilities=loadout.inactive)), catalog)


def assign_pilot_ability(character, slot, ability=None, catalog=None):
    """Assign an owned inactive ability, or deactivate a slot without losing it."""
    catalog = catalog or Catalog()
    if type(slot) is not int or not 0 <= slot < 6:
        raise RuleError("Choose an active ability slot from 1 to 6")
    loadout = validate_loadout(AbilityLoadout(character.build.abilities, character.build.inactive_abilities), catalog)
    current = loadout.active[slot] if slot < len(loadout.active) else None
    if ability is None:
        if current is not None:
            loadout = deactivate_ability(loadout, slot, catalog)
    else:
        record = catalog.find("abilities", ability)
        if record["id"] != current:
            loadout = activate_ability(loadout, record["id"], slot, catalog)
    return validate_character(replace(character, build=replace(character.build,
        abilities=loadout.active, inactive_abilities=loadout.inactive)), catalog)


def restore_roster_selection(character, catalog):
    """Reproject a migrated roster, leaving a pilot without Zoids unassigned."""
    if character.owned_zoids:
        owned = next((o for o in character.owned_zoids if o.id == character.active_zoid_id), character.owned_zoids[0])
        form = next((f for f in owned.forms if f.zoid == owned.active_form), None)
        if form is None:
            raise RuleError("Migrated Zoid has no matching selected form")
        return replace(character, active_zoid_id=owned.id, current_health=owned.current_health,
                       build=_project(character.build, owned, form, catalog))
    return replace(character, active_zoid_id="", current_health=0,
                   build=replace(character.build, zoid="", equipment=(None,) * 4,
                                 equipment_active=(False,) * 4, fixed_active=(False,) * 4,
                                  upgrades=Upgrades(), shield_adjustment=0, defense_up=0, defense_down=0))


def migrate_equipment_inventory(character, catalog):
    """Give legacy loadouts the minimum copies needed per owned chassis.

    Alternate forms reuse corresponding copies of a type. Different chassis,
    or repeated occurrences within one form, always receive distinct copies.
    Archived retired content remains untouched.
    """
    inventory, roster = [], []
    for owned in character.owned_zoids:
        shared = {}
        forms = []
        for form in owned.forms:
            occurrences, ids, armaments = {}, [], []
            for reference in form.equipment:
                if reference is None:
                    ids.append(None)
                    armaments.append(None)
                    continue
                record = catalog.find("armaments", reference)
                armament = record["id"]
                occurrence = occurrences.get(armament, 0)
                occurrences[armament] = occurrence + 1
                key = (armament, occurrence)
                if key not in shared:
                    shared[key] = OwnedEquipment(str(uuid4()), armament)
                    inventory.append(shared[key])
                ids.append(shared[key].id)
                armaments.append(armament)
            forms.append(replace(form, equipment=tuple(armaments), equipment_ids=tuple(ids)))
        roster.append(replace(owned, forms=tuple(forms)))
    return replace(character, inventory=tuple(inventory), owned_zoids=tuple(roster))


def equipment_assignments(character):
    """Inventory ID -> saved (owned Zoid ID, form ID, slot) assignments."""
    assignments = {}
    for owned in character.owned_zoids:
        for form in owned.forms:
            for slot, copy_id in zip(SLOT_COLUMNS, form.equipment_ids):
                if copy_id:
                    assignments.setdefault(copy_id, []).append((owned.id, form.zoid, slot))
    return assignments


def acquire_equipment(character, armament, quantity=1, catalog=None):
    catalog = catalog or Catalog()
    character = validate_character(character, catalog)
    if type(quantity) is not int or quantity < 1:
        raise RuleError("Equipment quantity must be a positive whole number")
    record = catalog.find("armaments", armament)
    if record["kind"] not in {"record", "dynamic"}:
        raise RuleError("Only actual equipment can be acquired")
    acquired = tuple(OwnedEquipment(str(uuid4()), record["id"]) for _ in range(quantity))
    return replace(character, inventory=(*character.inventory, *acquired))


def available_equipment(character, slot, catalog=None):
    """Eligible copies free for this slot, including same-chassis CAU reuse."""
    catalog = catalog or Catalog()
    if slot not in SLOT_COLUMNS:
        raise RuleError(f"Unknown removable equipment slot: {slot}")
    if not character.owned_zoids:
        return ()
    eligible = {r["id"] for r in eligible_equipment(character.build.zoid, slot, catalog)}
    assignments = equipment_assignments(character)
    return tuple(item for item in character.inventory if item.armament in eligible and all(
        owner == character.active_zoid_id and (form != character.build.zoid or mounted_slot == slot)
        for owner, form, mounted_slot in assignments.get(item.id, [])))


def equip_owned_equipment(character, slot, copy_id=None, catalog=None):
    catalog = catalog or Catalog()
    character = validate_character(character, catalog)
    if not character.owned_zoids:
        raise RuleError("Obtain a Zoid before attaching equipment")
    if slot not in SLOT_COLUMNS:
        raise RuleError(f"Unknown removable equipment slot: {slot}")
    item = next((i for i in character.inventory if i.id == copy_id), None) if copy_id is not None else None
    if copy_id is not None and (item is None or item not in available_equipment(character, slot, catalog)):
        raise RuleError("Choose an owned copy that fits this slot and is not assigned to another Zoid or slot")
    index = list(SLOT_COLUMNS).index(slot)
    owner = next(o for o in character.owned_zoids if o.id == character.active_zoid_id)
    form = next(f for f in owner.forms if f.zoid == character.build.zoid)
    if form.equipment_ids[index] == copy_id:
        return character
    equipment, ids, flags = list(form.equipment), list(form.equipment_ids), list(form.equipment_active)
    equipment[index], ids[index], flags[index] = item.armament if item else None, copy_id, False
    form = replace(form, equipment=tuple(equipment), equipment_ids=tuple(ids), equipment_active=tuple(flags))
    owner = replace(owner, forms=tuple(form if f.zoid == form.zoid else f for f in owner.forms))
    roster = tuple(owner if o.id == owner.id else o for o in character.owned_zoids)
    return validate_character(replace(character, owned_zoids=roster,
        build=replace(character.build, equipment=form.equipment, equipment_active=form.equipment_active)), catalog)


def return_equipment_to_inventory(character, copy_id, catalog=None):
    """Unassign a copy from every saved form, preserving it in pilot inventory."""
    catalog = catalog or Catalog()
    character = validate_character(character, catalog)
    if not any(i.id == copy_id for i in character.inventory):
        raise RuleError("This pilot does not own that equipment copy")
    roster = []
    for owned in character.owned_zoids:
        forms = []
        for form in owned.forms:
            equipment, ids, flags = list(form.equipment), list(form.equipment_ids), list(form.equipment_active)
            for index, item_id in enumerate(ids):
                if item_id == copy_id:
                    equipment[index], ids[index], flags[index] = None, None, False
            forms.append(replace(form, equipment=tuple(equipment), equipment_ids=tuple(ids), equipment_active=tuple(flags)))
        roster.append(replace(owned, forms=tuple(forms)))
    character = restore_roster_selection(replace(character, owned_zoids=tuple(roster)), catalog)
    return validate_character(character, catalog)
