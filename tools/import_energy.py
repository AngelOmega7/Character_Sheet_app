"""Apply owner-reviewed energy spreadsheets to generated catalogs and companion."""
import hashlib
import json
import re
from copy import deepcopy

from tools.audit_energy import ROOT, audit, normalize, workbook_rows


def apply_energy_options(tables):
    """Owner-defined abilities and equipment, reapplied on every data import."""
    abilities = tables["abilities"]["records"]
    original = next(r for r in abilities if r["id"] == "abilities:economized_shooting")
    for rank in range(1, 5):
        identity = "abilities:economized_shooting" + (f"_{rank}" if rank > 1 else "")
        record = next((r for r in abilities if r["id"] == identity), None)
        if record is None:
            record = deepcopy(original)
            record["id"] = identity
            record["source"] = {"owner_defined": True}
            record.pop("corrections", None)
            abilities.append(record)
        record["name"] = record["fields"]["name"] = "Economized Shooting" + (f" {rank}" if rank > 1 else "")
        record["rank"] = rank
        record["ranged_energy_cost_reduction"] = rank * 2
        record["fields"]["description"] = f"While active, reduce the Energy Cost of weapons with the Ranged tag by {rank * 2}, to a minimum of 0."
        record.pop("heat_capacity_bonus", None)
        record.pop("energy_redesign_pending", None)
        if rank == 1:
            record["legacy_names"] = ["Economized Shooting 1"]
        else:
            record.pop("legacy_names", None)
    demolitionist = next(r for r in tables["feats"]["records"] if r["id"] == "feats:demolitionist")
    demolitionist["fields"]["description"] = "Once per Rest, you may completely fill your Zoid's Energy."
    demolitionist["handling"] = "player_managed"
    demolitionist.pop("vent_heat", None)
    demolitionist.pop("energy_redesign_pending", None)
    armaments = tables["armaments"]
    for name, stat, amount in (("Physics Reinforcer Unit", "maximum_health_bonus", 100),
                              ("Energy Reinforcer Unit", "maximum_energy_bonus", 20)):
        identity = "armaments:" + name.lower().replace(" ", "_")
        record = next((r for r in armaments["records"] if r["id"] == identity), None)
        if record is None:
            record = {"id": identity, "name": name, "kind": "record", "source": {"owner_defined": True},
                      "fields": {key: None for key in armaments["columns"]}, "dynamic_fields": {}}
            armaments["records"].append(record)
        label = "health" if stat == "maximum_health_bonus" else "Energy"
        record["fields"].update(name=name, effect=f"Increases a Zoid's maximum {label} by {amount}.",
                                weight=3, activation="Passive")
        record.update(assist_eligible=True, energy_cost=0)
        record[stat] = amount
    identity = "armaments:energy_container"
    record = next((r for r in armaments["records"] if r["id"] == identity), None)
    if record is None:
        record = {"id": identity, "name": "Energy Container", "kind": "record", "source": {"owner_defined": True},
                  "fields": {key: None for key in armaments["columns"]}, "dynamic_fields": {}}
        armaments["records"].append(record)
    record["fields"].update(name="Energy Container", effect="Restores 20 Energy when activated, up to the Zoid's maximum Energy.",
                            weight=10, activation="Active")
    record.update(assist_eligible=True, energy_cost=0, energy_restore=20)


def apply_energy(output=None, companion=True):
    output = output or ROOT / "zoids_app/data"
    report = audit(output)
    assert not report["unknown_zoids"], report["unknown_zoids"]
    proposals = {
        "zoids:great_zaber": (35, 4, [0, 10, 10, 1, 7, 6, None, None]),
        "zoids:buster_fury": (40, 5, [20, 25, 5, 3, None, None, None, None]),
    }
    matched = {e["id"]: e for e in report["matched"]}
    tables = {name: json.loads((output / f"{name}.json").read_text())
              for name in ("zoids", "transports", "armaments", "abilities", "feats")}
    apply_energy_options(tables)
    moves = []
    for name in ("zoids", "transports"):
        for record in tables[name]["records"]:
            if record["kind"] != "record":
                continue
            if record["id"] in proposals:
                energy, recharge, costs = proposals[record["id"]]
                source = "Owner-approved proposal"
            else:
                entry = matched[record["id"]]
                energy, recharge, costs = entry["energy"], entry["recharge"], [None] * 8
                for weapon in entry["weapons"]:
                    assert len(weapon["app_slots"]) == 1 and weapon["cost"] is not None, (entry["name"], weapon)
                    slot = weapon["app_slots"][0]
                    assert costs[slot - 1] is None
                    costs[slot - 1] = weapon["cost"]
                    if slot != weapon["source_slot"]:
                        moves.append(f"- {entry['name']}: {weapon['name']} — source E{weapon['source_slot']} → app E{slot}.")
                for slot, weapon in enumerate(entry["app_slots"]):
                    if record["id"] == "zoids:zero_x_cau" and slot == 4:
                        costs[slot] = 3
                    assert not weapon or costs[slot] is not None, (entry["name"], slot, weapon)
                source = "Energy_Addition.ods (matched by weapon name)"
            record.update(energy=energy, energy_recharge=recharge, energy_costs=costs, energy_source=source)
            if record["id"] == "zoids:great_zaber":
                record["zoid_equipment_mounts"] = {"armaments:zoid_equipment_slot_2": ["left"]}
    generic = {normalize(row[0]): int(row[1]) if row[1] else 0 for row in workbook_rows("Generic_Energy.ods")}
    generic.update(acidblade=3, concentrateacidblade=5, acidneutralizerunit=0, emphardenedcircuits=0)
    used = set()
    for record in tables["armaments"]["records"]:
        if record["kind"] == "record":
            key = normalize(record["name"])
            assert key in generic, record["name"]
            record["energy_cost"] = generic[key]
            used.add(key)
    unknown = set(generic) - used - {"assist"}
    assert not unknown, unknown
    for name, table in tables.items():
        removed = {key for key in table["columns"] if "heat" in key}
        pairs = [(key, header) for key, header in zip(table["columns"], table["source_headers"]) if key not in removed]
        table["columns"], table["source_headers"] = map(list, zip(*pairs))
        for record in table["records"]:
            for key in removed:
                record["fields"].pop(key, None)
                record["dynamic_fields"].pop(key, None)
            # Historical correction records remain provenance, not active rules.
        (output / f"{name}.json").write_text(json.dumps(table, indent=2, ensure_ascii=False) + "\n")
    manifest_path = output / "manifest.json"
    manifest = json.loads(manifest_path.read_text())
    manifest["data_version"] = "energy-v17"
    for name, table in tables.items():
        manifest["datasets"][name]["records"] = len(table["records"])
        manifest["datasets"][name]["selectable"] = sum(r["kind"] == "record" for r in table["records"])
    manifest["energy_sources"] = {p.name: hashlib.sha256(p.read_bytes()).hexdigest()
                                  for p in (ROOT / "docs/Energy_Addition.ods", ROOT / "docs/Generic_Energy.ods")}
    manifest_path.write_text(json.dumps(manifest, indent=2) + "\n")
    if companion:
        update_companion(tables)
    report_path = ROOT / "docs/generated/energy-mapping.md"
    report_path.write_text("# Energy mapping audit\n\nAll named Zoid and generic equipment entries are represented. Physics Reinforcer Unit (+100 maximum health) and Energy Reinforcer Unit (+20 maximum Energy) are passive equipment, each weight 3 and zero energy cost. Energy Container is active equipment, weight 10, zero energy cost; activation restores 20 Energy capped at maximum.\n\n"
        "Names were normalized for punctuation, source descriptions, and documented spelling variants. Zoid aliases: Command Wolf Town → UC; Strum Fury → Sturm Fury; Redler BoostC → BC; Dragon Nest → Dragoon Nest.\n\n"
        "## Existing app positions retained\n\n" + "\n".join(moves) + "\n\n"
        "## Owner-approved additions\n\n"
        "Great Zaber: energy 35, recharge 4; E1–E8 costs: 0, 10, 10, 1, 7, 6, —, —.\n\n"
        "Buster Fury: energy 40, recharge 5; E1–E8 costs: 20, 25, 5, 3, —, —, —, —.\n\n"
        "Additional approved costs: Zero X Stealth Generator 3; Acid Blade 3; Concentrate Acid Blade 5; Acid Neutralizer Unit 0; EMP Hardened Circuits 0.\n\n"
        "Generic spreadsheet blanks are explicit zero cost, as approved. Zoid-specific templates use the Zoid's cost, not the generic similarly named item's cost.\n")


def update_companion(tables):
    path = ROOT / "ZOIDS_Companion.txt"
    text = path.read_text()
    zoids = [r for r in tables["zoids"]["records"] if r["kind"] == "record"]
    bases = sum(r["id"] == r["ownership_base_id"] for r in zoids)
    text = re.sub(r"\d+ Zoids: \d+ base entries and \d+ CAU forms; plus 4 transport Zoids\.",
                  f"{len(zoids)} Zoids: {bases} base entries and {len(zoids) - bases} CAU forms; plus 4 transport Zoids.", text)
    text = text.replace("are retained. Heat is shown wherever explicitly recorded.",
                        "are retained. Energy recharges at Start Turn, capped at total energy.")
    text = re.sub(r" *\| Heat: \d+", "", text)
    records = {r["name"]: r for name in ("zoids", "transports") for r in tables[name]["records"]}
    current, section, lines = None, None, []
    for line in text.splitlines():
        header = re.match(r"\[[^]]+\] (.+)", line)
        if header:
            current = records[header[1]]
            section = None
        if line.startswith("  Energy:") or line.startswith("     Energy cost:"):
            continue
        lines.append(line)
        if current and line.startswith("  Health:"):
            lines.append(f"  Energy: {current['energy']} | Energy recharge: {current['energy_recharge']}")
        if line == "FIXED WEAPONS & SYSTEMS":
            section = 0
        elif line == "REMOVABLE EQUIPMENT SLOTS":
            section = 4
        elif line == "PURCHASE & BUILD REFERENCE":
            section = None
        slot = re.match(r"  ([1-4])\. ", line)
        if current and section is not None and slot:
            cost = current["energy_costs"][section + int(slot[1]) - 1]
            if cost is not None:
                lines.append(f"     Energy cost: {cost}")
    path.write_text("\n".join(lines) + "\n")


if __name__ == "__main__":
    apply_energy()
