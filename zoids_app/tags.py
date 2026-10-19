"""Case-insensitive tag matching without changing source tag spellings."""
import re


def weapon_tags(text):
    tags = set()
    for part in re.split(r"[,.;]", text or ""):
        part = part.strip().casefold()
        # Recognize legacy missing commas after the weapon class for matching.
        match = re.fullmatch(r"(melee|ranged)\s+(.+)", part)
        if match:
            tags.update(match.groups())
        elif part:
            tags.add(part)
    return tags
