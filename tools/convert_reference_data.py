"""Build offline reference JSON from the audited workbook inventory (no network)."""
import hashlib
import json
from pathlib import Path
import re
from decimal import Decimal

ROOT = Path(__file__).resolve().parents[1]
DICE_DAMAGE = re.compile(r"\b(\d+)\s*[dD]\s*(\d+)\b")


def flatten_damage(text, numeric=False):
    """Multiply legacy dice terms; preserve surrounding prose in descriptions.

    A damage field with prose and exactly one dice term becomes a number.
    Multiple terms in a numeric field require an explicit rule, not a guess.
    """
    if not isinstance(text, str):
        return text
    matches = list(DICE_DAMAGE.finditer(text))
    if not matches:
        return text
    if numeric:
        if len(matches) != 1:
            raise ValueError(f"Ambiguous multi-term damage field: {text!r}")
        return int(matches[0][1]) * int(matches[0][2])
    return DICE_DAMAGE.sub(lambda match: str(int(match[1]) * int(match[2])), text)


def clean_weapon_tags(text):
    """Apply owner-approved tag cleanup, preserving unrelated tags and order."""
    if not isinstance(text, str):
        return text
    tags = []
    for part in re.split(r"[,.;]", text):
        # Split legacy missing separators after the attack class.
        parts = re.sub(r"^(Melee|Ranged)\s+", r"\1,", part.strip(), flags=re.I).split(",")
        for tag in parts:
            tag = tag.strip()
            key = tag.casefold()
            if not key or key in {"slashing", "bludgeon"}:
                continue
            if key == "anti-ait":
                tag = "Anti-Air"
            elif key in {"freeze", "electric", "electrical", "lighting"}:
                tag = "Electrical"
            if tag.casefold() not in {existing.casefold() for existing in tags}:
                tags.append(tag)
    return ", ".join(tags)


def slug(value):
    return re.sub(r"[^a-z0-9]+", "_", str(value).lower()).strip("_")


def column(index):
    result = ""
    while index:
        index, remainder = divmod(index - 1, 26)
        result = chr(65 + remainder) + result
    return result


def value(cell):
    raw = cell.get("value")
    if raw is None or cell.get("type") != "n":
        return raw
    number = Decimal(raw)
    return int(number) if number == number.to_integral_value() else float(number)


def build():
    source = ROOT / "docs/generated/workbook_inventory.json"
    inventory = json.loads(source.read_text())
    sheets = {s["name"]: {c["address"]: c for c in s["cells"]} for s in inventory["sheets"]}
    tables = {t["name"]: t for t in inventory["tables"]}
    definitions = [
        ("zoids", "Zoid List", "Zoid_DB"),
        ("armaments", "Armaments", "Armaments"),
        ("abilities", "Zoid Abilities", "Skills"),
        ("feats", "Feats", "Feats"),
        *((style.lower(), "Stats", style) for style in ("TANK", "FIGHTER", "SCOUT", "ALMIGHTY")),
        ("organoids", "Organoid", None),
    ]
    issues = []
    damage_conversions = []
    output = ROOT / "zoids_app/data"
    output.mkdir(exist_ok=True)
    counts = {}
    for dataset, sheet, table_name in definitions:
        cells = sheets[sheet]
        if table_name:
            table = tables[table_name]
            headers = [c["name"] for c in table["columns"]]
            start, end = [int(re.search(r"\d+", address)[0]) for address in table["ref"].split(":")]
        else:
            headers = [cells[f"{column(i)}1"]["value"] for i in range(1, 30)]
            start, end = 1, max(int(re.search(r"\d+", a)[0]) for a in cells)
        keys = []
        for i, header in enumerate(headers, 1):
            key = slug(header)
            if key in keys:
                key += f"_{i}"
            keys.append(key)
        if dataset == "armaments":
            keys = ["name", "damage", "damage_type", "effect", "to_hit", "defense", "armor", "to_hit_bonus", "range_bonus", "reaction_bonus", "speed_bonus", "weight", "activation", "shields", "weapon_class", "heat"]
        elif dataset == "abilities":
            keys = ["name", "description", "bonus_levels", "zoid_sizes", "all_stats_bonus", "armor_bonus", "to_hit_bonus", "speed_bonus", "range_bonus", "reaction_bonus", "damage_bonus", "shield_bonus", "equipment_defense_bonus", "damage_type", "base_defense_bonus"]
        elif dataset == "feats":
            keys = ["name", "description"]
        elif dataset == "zoids":
            keys[:12] = ["name", "base_zoid", "type", "size", "required_level", "health", "armor", "defense", "speed", "reaction", "range", "carry_capacity"]
        records, excluded = [], []
        for row in range(start + 1, end + 1):
            row_cells = [cells.get(f"{column(i)}{row}", {}) for i in range(1, len(keys) + 1)]
            if not any(row_cells):
                excluded.append({"row": row, "reason": "empty"})
                continue
            fields = {key: value(cell) for key, cell in zip(keys, row_cells)}
            first = fields[keys[0]]
            name = str(first).strip() if first is not None else None
            kind = "record"
            if name and re.fullmatch(r"[-\s]+", name):
                kind = "placeholder"
            if dataset == "armaments" and name in ("WEAPONS", "ASSIST"):
                kind = "heading"
            if dataset == "armaments" and row in (3, 4, 5, 6):
                kind = "dynamic"
                name = f"Zoid equipment slot {row - 2}"
            if dataset == "abilities" and name and re.sub(r"\s+\d+$", "", name).casefold().replace("-", " ") in {"wimp", "cross eyed", "slowpoke", "bad armor"}:
                excluded.append({"row": row, "name": name, "reason": "Owner retired this ability family and all ranks"})
                continue
            record = {
                "id": f"{dataset}:{(slug(name) or 'none') if name is not None else 'row_' + str(row)}",
                "name": name, "kind": kind, "source": {"sheet": sheet, "row": row},
                "fields": fields, "dynamic_fields": {},
            }
            for key, cell in zip(keys, row_cells):
                if "formula" not in cell:
                    continue
                expression = cell["formula"]
                if expression is None:
                    shared = cell["formula_attributes"].get("si")
                    expression = next(c["formula"] for c in cells.values() if c.get("formula") and c.get("formula_attributes", {}).get("si") == shared)
                constant = re.fullmatch(r'([+-]?\d+(?:\.\d+)?)(%)?', expression)
                if constant:
                    number = Decimal(constant[1]) / (100 if constant[2] else 1)
                    fields[key] = int(number) if number == number.to_integral_value() else float(number)
                elif expression.startswith('"') and re.fullmatch(r'"[^"]*"', expression):
                    fields[key] = expression[1:-1]
                elif dataset == "abilities" and key == keys[1]:
                    # These description formulas reference local blank/type cells;
                    # preserve provenance and cached text, never evaluate as code.
                    record.setdefault("description_formulas", {})[key] = expression
                else:
                    record["dynamic_fields"][key] = expression
                    fields[key] = None  # Never freeze a character-dependent cached value.
            damage_columns = {15, 21, 32, 43, 49, 55, 62, 67} if dataset == "zoids" else {2} if dataset == "armaments" else set()
            effect_columns = {14, 20, 31, 42, 48, 56, 69} if dataset == "zoids" else {4} if dataset == "armaments" else set()
            for index in sorted(damage_columns | effect_columns):
                key = keys[index - 1]
                original = fields[key]
                converted = flatten_damage(original, numeric=index in damage_columns)
                if converted != original:
                    fields[key] = converted
                    if index in damage_columns and DICE_DAMAGE.fullmatch(original.strip()) is None:
                        record.setdefault("damage_notes", {})[key] = flatten_damage(original).strip()
                    damage_conversions.append({
                        "dataset": dataset, "id": record["id"],
                        "source": f"{sheet}!{column(index)}{row}", "field": key,
                        "original": original, "converted": converted,
                    })
            tag_columns = {16, 22, 33, 44, 50, 58} if dataset == "zoids" else {3} if dataset == "armaments" else set()
            for index in tag_columns:
                key = keys[index - 1]
                original = fields[key]
                if not isinstance(original, str):
                    continue
                cleaned = clean_weapon_tags(original)
                if cleaned != original:
                    fields[key] = cleaned
                    record.setdefault("corrections", {})[key] = {"original": original, "corrected": cleaned, "reason": "Owner-approved tag cleanup"}
                original_source = original
                original = cleaned
                ranged = bool(re.search(r"\bRanged\b", original, re.I)) or (dataset == "armaments" and str(fields["weapon_class"]).strip().casefold() == "ranged")
                if ranged and not re.search(r"\bMelee\b", original, re.I):
                    converted = re.sub(r"\bPiercing\b", "Bullet", original, flags=re.I)
                    if converted != original:
                        if not re.search(r"\bRanged\b", converted, re.I):
                            converted = "Ranged, " + converted
                        fields[key] = converted
                        record.setdefault("corrections", {})[key] = {"original": original_source, "corrected": converted, "reason": "Owner tag cleanup and ranged Piercing to Bullet"}
            records.append(record)
            if dataset == "abilities" and kind == "record":
                # BLOXType 1 is a source spelling inconsistency in the BLOX Type family.
                family_name = name.replace("BLOXType", "BLOX Type")
                match = re.fullmatch(r"(.+?)\s+(\d+)", family_name)
                record["family"] = slug(match[1] if match else family_name)
                record["rank"] = int(match[2]) if match else 1
                expert_families = {"laser_expert", "missile_expert", "particle_expert", "melee_expert", "rifle_expert"}
                if record["family"] in expert_families:
                    original = fields["description"]
                    description = re.sub(r"\s+and gain advantage", "", original, flags=re.I)
                    if record["family"] == "rifle_expert":
                        description = re.sub(r"\bpiercing\b", "Bullet", description, flags=re.I)
                        fields["damage_type"] = "Ranged, Bullet"
                    fields["description"] = description
                    if description != original:
                        record.setdefault("corrections", {})["description"] = {"original": original, "corrected": description, "reason": "Owner removed Expert advantage and renamed ranged Piercing"}
                sizes = fields["zoid_sizes"]
                record["eligible_sizes"] = [s.strip() for s in sizes.split(",")] if isinstance(sizes, str) else []
                if name == "Medium Under Expert 4":
                    record["corrections"] = {"all_stats_bonus": {"original": fields["all_stats_bonus"], "corrected": 0.25, "reason": "Owner confirmed 25%, not 2500%"}}
                    fields["all_stats_bonus"] = 0.25
                if record["family"] == "comeback":
                    percent = 10 + record["rank"] * 10
                    record["corrections"] = {
                        "damage_bonus": {"original": fields["damage_bonus"], "corrected": percent / 100},
                        "description": {"original": fields["description"], "reason": "Owner replaced legacy dice damage with rank-based flat-damage percentages at <=20% health"},
                    }
                    fields["damage_bonus"] = percent / 100
                    fields["description"] = f"While active and current health is 20% or less of maximum health, attacks gain {percent}% damage."
                if record["family"] == "sniper":
                    record["long_range_to_hit_bonus"] = record["rank"]
                if record["family"] == "evasion_master":
                    record["corrections"] = {"description": {"original": fields["description"], "reason": "Owner changed effect to armor per reaction-boosting item"}}
                    fields["description"] = f"While active, each enabled item that boosts Reaction also adds {record['rank']} Armor."
                    record["armor_per_reaction_item"] = record["rank"]
                if record["family"] == "economized_shooting":
                    record["corrections"] = {"description": {"original": fields["description"], "reason": "Owner replaced one-use exception with heat capacity bonus"}}
                    fields["description"] = "While active, increase maximum heat of every heat-rated weapon by 1."
                    record["heat_capacity_bonus"] = 1
                if record["family"] in {"melee_multi_attack", "ranged_multi_attack", "smoke_master", "armor_breaker", "weapon_breaker", "counter_attack"}:
                    record["handling"] = "player_managed"
            if kind != "record":
                issues.append({"dataset": dataset, "id": record["id"], "kind": kind})
            for key, val in fields.items():
                if isinstance(val, str) and val.startswith(("#REF!", "#VALUE!", "#N/A")):
                    issues.append({"dataset": dataset, "id": record["id"], "field": key, "error": val})
        ids = [r["id"] for r in records]
        if len(ids) != len(set(ids)):
            raise ValueError(f"Duplicate normalized IDs in {dataset}")
        data = {"schema_version": 1, "columns": keys, "source_headers": headers, "records": records, "excluded_rows": excluded}
        (output / f"{dataset}.json").write_text(json.dumps(data, indent=2, ensure_ascii=False) + "\n")
        counts[dataset] = dict(records=len(records), selectable=sum(r["kind"] == "record" for r in records), excluded_empty_rows=sum(r["reason"] == "empty" for r in excluded), excluded_retired_rows=sum(r["reason"] != "empty" for r in excluded))
    manifest = {"schema_version": 1, "data_version": "weapon-tags-v7", "source_sha256": hashlib.sha256(source.read_bytes()).hexdigest(), "datasets": counts, "review_items": issues}
    (output / "manifest.json").write_text(json.dumps(manifest, indent=2) + "\n")
    (ROOT / "docs/generated/damage-conversions.json").write_text(json.dumps(damage_conversions, indent=2) + "\n")
    print(json.dumps(counts, indent=2))
    print(f"Converted {len(damage_conversions)} legacy damage fields/descriptions")


if __name__ == "__main__":
    build()
