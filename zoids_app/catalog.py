"""Local reference catalogs. Spreadsheet column numbers are provenance only."""
import json
from pathlib import Path

from .combat import RuleError


class Catalog:
    def __init__(self, directory=None):
        directory = Path(directory) if directory else Path(__file__).parent / "data"
        manifest = json.loads((directory / "manifest.json").read_text(encoding="utf-8"))
        self.tables = {name: json.loads((directory / f"{name}.json").read_text(encoding="utf-8")) for name in manifest["datasets"]}
        self.by_id = {r["id"]: r for table in self.tables.values() for r in table["records"]}

    def find(self, dataset, name_or_id):
        for record in self.tables[dataset]["records"]:
            if record["id"] == name_or_id or record["name"] == name_or_id:
                return record
        raise RuleError(f"Unknown {dataset} entry: {name_or_id}")

    def column(self, record, index):
        dataset = record["id"].split(":", 1)[0]
        key = self.tables[dataset]["columns"][index - 1]
        if key in record["dynamic_fields"]:
            raise RuleError(f"Dynamic field needs character context: {record['id']}.{key}")
        return record["fields"][key]
