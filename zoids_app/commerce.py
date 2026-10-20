"""CSV-backed, atomic build/purchase, upgrade, and CAU-detachment transactions."""
from collections import Counter
from dataclasses import dataclass, replace

from .catalog import Catalog
from .characters import (Material, acquire_zoid, fixed_weapon_identity, restore_roster_selection,
                         set_upgrades, switch_zoid, validate_character)
from .combat import RuleError


def recipe(catalog, zoid):
    identity = catalog.find("zoids", zoid)["id"]
    row = next((r for r in catalog.tables["purchases"]["records"] if r["zoid_id"] == identity), None)
    if row is None:
        raise RuleError("No purchasing recipe is available for this Zoid")
    return row["fields"]


def recipe_parts(catalog, zoid, seen=()):
    record = catalog.find("zoids", zoid)
    if record["id"] in seen:
        raise RuleError("Cyclic CAU recipe")
    data = recipe(catalog, record["id"])
    parts = (data["parts"],) if data["parts"] else ()
    if data["base_zoid"]:
        predecessor = catalog.find("zoids", data["base_zoid"])
        if predecessor["id"] != predecessor["ownership_base_id"] and predecessor["ownership_base_id"] == record["ownership_base_id"]:
            parts += recipe_parts(catalog, predecessor["id"], (*seen, record["id"]))
    return parts


def set_material(character, name, quantity, catalog=None):
    catalog = catalog or Catalog()
    if not isinstance(name, str) or not name.strip() or type(quantity) is not int or quantity < 0:
        raise RuleError("Enter an item name and nonnegative whole quantity")
    name = name.strip()
    items = [i for i in character.materials if i.name.casefold() != name.casefold()]
    if quantity:
        items.append(Material(name, quantity))
    return validate_character(replace(character, materials=tuple(items)), catalog)


def set_known_design(character, zoid, known=True, catalog=None):
    catalog = catalog or Catalog()
    identity = catalog.find("zoids", zoid)["id"]
    entries = tuple(z for z in character.known_zoids if z != identity)
    return validate_character(replace(character, known_zoids=(*entries, identity) if known else entries), catalog)


@dataclass(frozen=True)
class PurchaseQuote:
    zoid: str
    cost: int
    materials: tuple[tuple[str, int], ...]
    host_id: str | None
    base_id: str | None
    predecessor: str | None
    issues: tuple[str, ...]
    starter: bool = False


def quote_purchase(character, zoid, *, host_id=None, base_id=None, starter=False, catalog=None):
    catalog = catalog or Catalog()
    if type(starter) is not bool:
        raise RuleError("Starter flag must be a Boolean")
    character = validate_character(character, catalog)
    record = catalog.find("zoids", zoid)
    data = recipe(catalog, record["id"])
    cau = record["id"] != record["ownership_base_id"]
    if starter:
        if not character.starter_pending or character.owned_zoids or cau or data["cost"] > 10000:
            raise RuleError("Choose a non-CAU starting Zoid costing at most 10,000g")
    elif character.starter_pending:
        raise RuleError("Purchase a starting Zoid first")
    issues, predecessor = [], None
    host = None
    if cau:
        hosts = [o for o in character.owned_zoids if o.base_zoid == record["ownership_base_id"] and (host_id is None or o.id == host_id)]
        if len(hosts) != 1:
            raise RuleError("Select the specific owned host Zoid for this CAU")
        host = hosts[0]
        host_id = host.id
        if any(f.zoid == record["id"] for f in host.forms):
            raise RuleError("This host already owns that CAU")
    else:
        host_id = None
    if character.gold < data["cost"]:
        issues.append(f"Requires {data['cost']:,}g; available {character.gold:,}g")
    required = Counter()
    if not starter:
        required.update(x for x in (data["core"], data["parts"]) if x)
        available = {i.name.casefold(): i.quantity for i in character.materials}
        for name, quantity in required.items():
            if available.get(name.casefold(), 0) < quantity:
                issues.append(f"Missing {quantity} × {name}")
        if record["id"] not in character.known_zoids:
            issues.append("Design is missing from Zi Database")
        base = data["base_zoid"]
        if base and (not host or base != host.base_zoid):
            base_record = catalog.find("zoids", base)
            if host and base_record["ownership_base_id"] == host.base_zoid and base_record["id"] != host.base_zoid:
                predecessor = base
                if not any(f.zoid == base for f in host.forms):
                    issues.append(f"Host requires predecessor CAU: {base_record['name']}")
                base_id = None
            else:
                candidates = [o for o in character.owned_zoids if o.base_zoid == base and len(o.forms) == 1 and (base_id is None or o.id == base_id)]
                if len(candidates) == 1:
                    base_id = candidates[0].id
                else:
                    issues.append(f"Select one owned {base_record['name']} with no acquired CAUs to consume")
        else:
            base_id = None
    else:
        base_id = None
    return PurchaseQuote(record["id"], data["cost"], tuple(required.items()), host_id, base_id, predecessor, tuple(issues), starter)


def _prune_form_state(owner, catalog):
    upgrades, conditions = set(), set()
    for form in owner.forms:
        r = catalog.find("zoids", form.zoid)
        upgrades.update(k for k in r["fixed_weapon_ids"] if k)
        conditions.update(fixed_weapon_identity(r, i) for i, col in enumerate((13, 19, 30, 41)) if catalog.column(r, col))
    return replace(owner, weapons=tuple(w for w in owner.weapons if w.weapon_id in upgrades),
                   weapon_conditions=tuple(w for w in owner.weapon_conditions if w.weapon_id in conditions))


def purchase_zoid(character, quote, *, override=False, catalog=None):
    catalog = catalog or Catalog()
    if type(override) is not bool:
        raise RuleError("GM Override must be explicitly confirmed")
    character = validate_character(character, catalog)
    fresh = quote_purchase(character, quote.zoid, host_id=quote.host_id, base_id=quote.base_id, starter=quote.starter, catalog=catalog)
    if fresh != quote:
        raise RuleError("Purchase requirements changed; request a fresh quote")
    if quote.issues and not override:
        raise RuleError("; ".join(quote.issues))
    if not override:
        consumed = {name.casefold(): count for name, count in quote.materials}
        character = replace(character, gold=character.gold - quote.cost,
            materials=tuple(Material(i.name, i.quantity - consumed.get(i.name.casefold(), 0)) for i in character.materials))
        if quote.base_id:
            character = replace(character, owned_zoids=tuple(o for o in character.owned_zoids if o.id != quote.base_id),
                                loaded_zoids=tuple(i for i in character.loaded_zoids if i != quote.base_id))
            character = restore_roster_selection(character, catalog)
    parts = recipe_parts(catalog, quote.zoid)
    if quote.predecessor and quote.host_id:
        roster = []
        for owner in character.owned_zoids:
            if owner.id == quote.host_id:
                prior = next((f for f in owner.forms if f.zoid == quote.predecessor), None)
                if prior is not None:
                    own_part = recipe(catalog, quote.zoid)["parts"]
                    parts = ((own_part,) if own_part else ()) + (prior.build_parts if prior.build_parts is not None else recipe_parts(catalog, prior.zoid))
                    owner = replace(owner, forms=tuple(f for f in owner.forms if f.zoid != quote.predecessor),
                                    active_form=owner.base_zoid if owner.active_form == quote.predecessor else owner.active_form)
                    owner = _prune_form_state(owner, catalog)
            roster.append(owner)
        character = restore_roster_selection(replace(character, owned_zoids=tuple(roster)), catalog)
    before = {o.id for o in character.owned_zoids}
    character = acquire_zoid(character, quote.zoid, catalog, host_id=quote.host_id)
    owner = next(o for o in character.owned_zoids if o.id == quote.host_id) if quote.host_id else next(o for o in character.owned_zoids if o.id not in before)
    if quote.host_id:
        owner = replace(owner, forms=tuple(replace(f, build_parts=parts) if f.zoid == quote.zoid else f for f in owner.forms))
        character = replace(character, owned_zoids=tuple(owner if o.id == owner.id else o for o in character.owned_zoids))
    character = replace(character, starter_pending=False)
    return switch_zoid(character, owner.id, quote.zoid, catalog)


def detach_cau(character, owner_id, form_id, catalog=None):
    catalog = catalog or Catalog()
    character = validate_character(character, catalog)
    owner = next((o for o in character.owned_zoids if o.id == owner_id), None)
    if owner is None or form_id == owner.base_zoid:
        raise RuleError("Choose an acquired CAU, not the host chassis")
    form = next((f for f in owner.forms if f.zoid == form_id), None)
    if form is None:
        raise RuleError("This CAU is not owned by that host")
    parts = form.build_parts if form.build_parts is not None else recipe_parts(catalog, form_id)
    items = {i.name.casefold(): i for i in character.materials}
    for name in parts:
        key = name.casefold()
        items[key] = Material(items[key].name if key in items else name, items[key].quantity + 1 if key in items else 1)
    owner = _prune_form_state(replace(owner, forms=tuple(f for f in owner.forms if f.zoid != form_id),
        active_form=owner.base_zoid if owner.active_form == form_id else owner.active_form), catalog)
    character = replace(character, gold=character.gold + recipe(catalog, form_id)["cost"] // 2,
        materials=tuple(items.values()), owned_zoids=tuple(owner if o.id == owner_id else o for o in character.owned_zoids))
    return validate_character(restore_roster_selection(character, catalog), catalog)


def change_upgrade(character, field, delta, slot=None, catalog=None):
    catalog = catalog or Catalog()
    character = validate_character(character, catalog)
    if not character.owned_zoids or delta not in (-1, 1) or type(delta) is not int:
        raise RuleError("Select a Zoid and increase or decrease one upgrade point")
    upgrades = character.build.upgrades
    if field in ("speed", "reaction", "defense", "capacity") and slot is None:
        old, base = getattr(upgrades, field), 5000
        updated = replace(upgrades, **{field: old + delta})
    elif field in ("damage", "to_hit") and type(slot) is int and 0 <= slot < 4:
        if not catalog.find("zoids", character.build.zoid)["fixed_weapon_ids"][slot]:
            raise RuleError("Only fixed weapons can receive weapon upgrades")
        points = list(getattr(upgrades, field))
        old, base = points[slot], 10000
        points[slot] += delta
        updated = replace(upgrades, **{field: tuple(points)})
    else:
        raise RuleError("Unknown upgrade track")
    amount = base * (old + 1) if delta > 0 else -base * old
    if amount > character.gold:
        raise RuleError(f"Upgrade costs {amount:,}g; only {character.gold:,}g available")
    return set_upgrades(replace(character, gold=character.gold - amount), updated, catalog)
