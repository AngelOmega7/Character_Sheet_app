"""Compare named energy workbook entries with the current catalog (no slot moves)."""
import json
from pathlib import Path
import re
import xml.etree.ElementTree as ET
import zipfile

ROOT = Path(__file__).resolve().parents[1]
NS = {"t": "urn:oasis:names:tc:opendocument:xmlns:table:1.0",
      "x": "urn:oasis:names:tc:opendocument:xmlns:text:1.0"}


def normalize(value):
    value = value.split(":", 1)[0].lower().replace("(cau)", "")
    value = value.replace("paticle", "particle").replace("laster", "laser").replace("claws", "claw")
    value = value.replace("long rang rifle", "long range rifle").replace("anchro", "anchor")
    return re.sub(r"[^a-z0-9]", "", value)


def workbook_rows(filename=None):
    path = next((ROOT / "docs" / name for name in ((filename,) if filename else ("Energy_Additions.ods", "Energy_Addition.ods"))
                 if (ROOT / "docs" / name).exists()))
    with zipfile.ZipFile(path) as archive:
        root = ET.fromstring(archive.read("content.xml"))
    rows = []
    for row in root.findall(".//t:table/t:table-row", NS):
        cells = []
        for cell in row:
            text = " ".join("".join(p.itertext()) for p in cell.findall("x:p", NS)).strip()
            cells.extend([text] * min(30, int(cell.get("{" + NS["t"] + "}number-columns-repeated", "1"))))
        if cells and cells[0] and cells[0] != "Name":
            rows.append(cells)
    return rows


def audit(directory=None):
    directory = directory or ROOT / "zoids_app/data"
    tables = {name: json.loads((directory / f"{name}.json").read_text())
              for name in ("zoids", "transports", "armaments")}
    records = [r for table in ("zoids", "transports") for r in tables[table]["records"]
               if r["kind"] == "record"]
    aliases = {"strumfury": "sturmfury", "commandwolftown": "commandwolfuc", "redlerboostc": "redlerbc",
               "dragonnest": "dragoonnest"}
    by_name = {normalize(r["name"]): r for r in records}
    result = {"matched": [], "unknown_zoids": [], "missing_zoids": []}
    seen = set()
    for row in workbook_rows():
        key = aliases.get(normalize(row[0]), normalize(row[0]))
        record = by_name.get(key)
        if not record:
            result["unknown_zoids"].append(row)
            continue
        seen.add(record["id"])
        table = tables[record["id"].split(":")[0]]
        slots = [record["fields"][table["columns"][i - 1]] for i in (13, 19, 30, 41, 47, 54, 61, 66)]
        entry = {"id": record["id"], "name": record["name"], "energy": int(row[1]),
                 "recharge": int(row[18]), "app_slots": slots, "weapons": []}
        for i in range(8):
            cost, name = row[2 + i * 2:4 + i * 2]
            if not name and not cost:
                continue
            matches = [j + 1 for j, slot in enumerate(slots) if slot and normalize(slot) == normalize(name)]
            armaments = [r["id"] for r in tables["armaments"]["records"] if normalize(r["name"]) == normalize(name)]
            entry["weapons"].append({"source_slot": i + 1, "name": name,
                                     "cost": int(cost) if cost else None,
                                     "app_slots": matches, "armaments": armaments})
        result["matched"].append(entry)
    result["missing_zoids"] = [{"id": r["id"], "name": r["name"]} for r in records if r["id"] not in seen]
    return result


if __name__ == "__main__":
    print(json.dumps(audit(), indent=2))
