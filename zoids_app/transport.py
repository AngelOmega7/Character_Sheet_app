"""Transport selection and physical-chassis cargo tracking."""
from dataclasses import replace

from .catalog import Catalog
from .combat import RuleError

SIZES = ("Small", "Medium", "Large", "Large Large", "Extra Large")


def validate_cargo(character, catalog):
    if not isinstance(character.loaded_allies, tuple) or any(type(n) is not int or n < 1 for n in character.loaded_allies):
        raise RuleError("Ally placeholders must have positive whole numbers")
    if len(set(character.loaded_allies)) != len(character.loaded_allies):
        raise RuleError("An ally placeholder cannot be loaded twice")
    if len(set(character.loaded_zoids)) != len(character.loaded_zoids):
        raise RuleError("A Zoid cannot be loaded twice")
    if not character.transport:
        if character.loaded_zoids or character.loaded_allies:
            raise RuleError("Select a Transport before loading Zoids")
        return
    transport = catalog.find("transports", character.transport)
    if len(character.loaded_zoids) + len(character.loaded_allies) > transport["hangar_capacity"]:
        raise RuleError("Transport hangar capacity exceeded")
    owners = {o.id: o for o in character.owned_zoids}
    for identity in character.loaded_zoids:
        if identity not in owners:
            raise RuleError("Only owned Zoids can be loaded")
        size = catalog.find("zoids", owners[identity].active_form)["fields"]["size"].strip()
        if size not in SIZES or SIZES.index(size) > SIZES.index(transport["hangar_size"]):
            raise RuleError(f"This Zoid is too large for {transport['name']}")


def select_transport(character, transport, catalog=None):
    catalog = catalog or Catalog()
    selected = catalog.find("transports", transport)["id"] if transport else None
    changed = selected != character.transport
    return replace(character, transport=selected, loaded_zoids=() if changed else character.loaded_zoids,
                   loaded_allies=() if changed else character.loaded_allies)


def load_zoid(character, identity, loaded=True, catalog=None):
    catalog = catalog or Catalog()
    ids = tuple(i for i in character.loaded_zoids if i != identity)
    if loaded:
        ids += (identity,)
    result = replace(character, loaded_zoids=ids)
    validate_cargo(result, catalog)
    return result


def load_ally(character, catalog=None):
    """Reserve one bay for another player's Zoid, using the first free ally number."""
    catalog = catalog or Catalog()
    number = 1
    while number in character.loaded_allies:
        number += 1
    result = replace(character, loaded_allies=(*character.loaded_allies, number))
    validate_cargo(result, catalog)
    return result


def unload_ally(character, number, catalog=None):
    catalog = catalog or Catalog()
    if type(number) is not int or number not in character.loaded_allies:
        raise RuleError("Select a loaded ally placeholder")
    result = replace(character, loaded_allies=tuple(n for n in character.loaded_allies if n != number))
    validate_cargo(result, catalog)
    return result
