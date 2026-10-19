"""Inspect a local XLSX without evaluating formulas or accessing the network."""
import argparse
import collections
import json
from pathlib import Path
import re
import xml.etree.ElementTree as ET
from zipfile import ZipFile
import posixpath

NS = {"m": "http://schemas.openxmlformats.org/spreadsheetml/2006/main"}
REL = "{http://schemas.openxmlformats.org/officeDocument/2006/relationships}id"


def inspect(source, output):
    output.mkdir(parents=True, exist_ok=True)
    with ZipFile(source) as archive:
        def xml(path):
            return ET.fromstring(archive.read(path))

        strings = []
        if "xl/sharedStrings.xml" in archive.namelist():
            strings = ["".join(item.itertext()) for item in xml("xl/sharedStrings.xml")]
        workbook = xml("xl/workbook.xml")
        relationships = {
            item.attrib["Id"]: item.attrib["Target"]
            for item in xml("xl/_rels/workbook.xml.rels")
        }
        report = {"source": source.name, "sheets": [], "named_ranges": [], "tables": []}
        for item in workbook.findall("m:definedNames/m:definedName", NS):
            report["named_ranges"].append({**item.attrib, "expression": item.text})
        for path in archive.namelist():
            if path.startswith("xl/tables/") and path.endswith(".xml"):
                table = xml(path)
                report["tables"].append({**table.attrib, "columns": [c.attrib for c in table.findall("m:tableColumns/m:tableColumn", NS)]})
        for sheet in workbook.findall("m:sheets/m:sheet", NS):
            target = relationships[sheet.attrib[REL]]
            path = target.lstrip("/") if target.startswith("/") else posixpath.normpath("xl/" + target)
            root = xml(path)
            cells = []
            for cell in root.findall("m:sheetData/m:row/m:c", NS):
                value = cell.find("m:v", NS)
                value = value.text if value is not None else None
                kind = cell.get("t", "n")
                if kind == "s" and value is not None:
                    value = strings[int(value)]
                elif kind == "inlineStr":
                    value = "".join(t.text or "" for t in cell.findall("m:is//m:t", NS))
                elif kind == "b" and value is not None:
                    value = value == "1"
                formula = cell.find("m:f", NS)
                entry = {"address": cell.get("r"), "type": kind, "value": value, "style": cell.get("s")}
                if formula is not None:
                    entry["formula"] = formula.text
                    entry["formula_attributes"] = formula.attrib
                if value is not None or formula is not None:
                    cells.append(entry)
            validations = []
            for item in root.findall("m:dataValidations/m:dataValidation", NS):
                validations.append({**item.attrib, "expressions": [child.text for child in item]})
            report["sheets"].append({
                "name": sheet.get("name"), "state": sheet.get("state", "visible"),
                "cells": cells, "validations": validations,
                "merged_ranges": [m.get("ref") for m in root.findall("m:mergeCells/m:mergeCell", NS)],
            })
    (output / "workbook_inventory.json").write_text(json.dumps(report, indent=2, ensure_ascii=False), encoding="utf-8")
    formulas = [{"sheet": s["name"], **c} for s in report["sheets"] for c in s["cells"] if "formula" in c]
    (output / "formulas.json").write_text(json.dumps(formulas, indent=2, ensure_ascii=False), encoding="utf-8")
    functions = collections.Counter(f.upper() for c in formulas for f in re.findall(r"([A-Za-z_][A-Za-z_0-9.]*)\s*\(", c["formula"] or ""))
    lines = ["# Workbook inventory", "", "Generated from a local XLSX export. Values are cached source values, not recalculated results.", "", "| Sheet | Populated cells | Formula cells | Validation rules |", "|---|---:|---:|---:|"]
    for sheet in report["sheets"]:
        lines.append(f'| {sheet["name"]} | {len(sheet["cells"])} | {sum("formula" in c for c in sheet["cells"])} | {len(sheet["validations"])} |')
    lines += ["", f"Total formula cells: {len(formulas)}", "", "## Formula function tokens", "", "Counts are lexical, including formulas embedded in compatibility-wrapper strings.", ""]
    lines += [f"- `{name}`: {count}" for name, count in functions.most_common()]
    lines += ["", "## Export limitations", "", "- Shared formula followers retain their shared-formula metadata; their expressions are not expanded by this tool.", "- Google-specific formulas may be compatibility wrappers. Verify their original semantics before translation.", "- Checkbox formatting, validation rules, scripts, buttons, and images may not survive XLSX export completely.", "- Non-formula cells are candidates for inputs or reference data, not automatically editable fields.", "- Numeric values retain their XML text to avoid precision loss; normalization is a later conversion step."]
    (output / "inventory.md").write_text("\n".join(lines) + "\n", encoding="utf-8")
    print("Wrote", output / "inventory.md")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("workbook", type=Path)
    parser.add_argument("output", type=Path)
    args = parser.parse_args()
    inspect(args.workbook, args.output)
