"""An established pilot fixture for tests that are not testing character creation."""
from dataclasses import replace
from zoids_app.characters import acquire_zoid, new_character, validate_character


def established_character(catalog=None):
    character = acquire_zoid(new_character(catalog), "Saberlion", catalog)
    # Established combat fixtures explicitly start charged; new-pilot defaults
    # are exercised separately by the acquisition/energy tests.
    return validate_character(replace(character, gold=0, starter_pending=False,
                                      current_energy=20,
                                      build=replace(character.build, organoid_color="Black")), catalog)
