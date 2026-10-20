"""Transport selection and physical-chassis cargo tracking."""
from dataclasses import replace

from .catalog import Catalog
from .combat import RuleError

SIZES = ("Small", "Medium", "Large", "Large Large", "Extra Large")


def validate_cargo(character, catalog):
    if len(set(character.loaded_zoids)) != len(character.loaded_zoids):
        raise RuleError("A Zoid cannot be loaded twice")
    if not character.transport:
        if character.loaded_zoids:
            raise RuleError("Select a Transport before loading Zoids")
        return
    transport = catalog.find("transports", character.transport)
    if len(character.loaded_zoids) > transport["hangar_capacity"]:
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
    return replace(character, transport=selected, loaded_zoids=() if selected != character.transport else character.loaded_zoids)


def load_zoid(character, identity, loaded=True, catalog=None):
    catalog = catalog or Catalog()
    ids = tuple(i for i in character.loaded_zoids if i != identity)
    if loaded:
        ids += (identity,)
    result = replace(character, loaded_zoids=ids)
    validate_cargo(result, catalog)
    return result
