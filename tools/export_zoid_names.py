"""Explicitly refresh the names-only owner worksheet after catalog changes."""
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from zoids_app.catalog import Catalog


def export():
    catalog = Catalog()
    names = sorted({r["name"] for dataset in ("zoids", "transports")
                    for r in catalog.tables[dataset]["records"] if r["kind"] == "record"}, key=str.casefold)
    path = ROOT / "assets/ZoidNames.txt"
    path.write_text("\n".join(names) + "\n", encoding="utf-8", newline="\n")
    print(f"Wrote {len(names)} names to {path}")


if __name__ == "__main__":
    export()
