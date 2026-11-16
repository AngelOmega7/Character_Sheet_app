"""Extract offline base pictures from the source workbook (requires Pillow)."""
from io import BytesIO
from pathlib import Path
import posixpath
import xml.etree.ElementTree as ET
from zipfile import ZipFile

from PIL import Image

from zoids_app.catalog import Catalog

ROOT = Path(__file__).resolve().parents[1]
NS = {
    "m": "http://schemas.openxmlformats.org/spreadsheetml/2006/main",
    "d": "http://schemas.openxmlformats.org/drawingml/2006/spreadsheetDrawing",
    "a": "http://schemas.openxmlformats.org/drawingml/2006/main",
}
REL = "{http://schemas.openxmlformats.org/officeDocument/2006/relationships}"


def extract(source=ROOT / "source/character_sheet.xlsx", assets=ROOT / "assets"):
    catalog = Catalog()
    with ZipFile(source) as archive:
        def xml(path):
            return ET.fromstring(archive.read(path))

        def relationships(path):
            directory, name = posixpath.split(path)
            return {r.get("Id"): posixpath.normpath(posixpath.join(directory, r.get("Target")))
                    for r in xml(f"{directory}/_rels/{name}.rels") if r.get("TargetMode") != "External"}

        workbook = "xl/workbook.xml"
        sheet = next(s for s in xml(workbook).findall("m:sheets/m:sheet", NS) if s.get("name") == "Zoid List")
        sheet_path = relationships(workbook)[sheet.get(REL + "id")]
        sheet_xml = xml(sheet_path)
        strings = ["".join(s.itertext()) for s in xml("xl/sharedStrings.xml")]
        header = next(c for c in sheet_xml.findall("m:sheetData/m:row/m:c", NS)
                      if c.get("t") == "s" and strings[int(c.find("m:v", NS).text)] == "Zoid Picture Base")
        column = 0
        for letter in header.get("r").rstrip("0123456789"):
            column = column * 26 + ord(letter) - ord("A") + 1
        drawing = sheet_xml.find("m:drawing", NS)
        drawing_path = relationships(sheet_path)[drawing.get(REL + "id")]
        media = relationships(drawing_path)
        pictures = {}
        for anchor in xml(drawing_path):
            origin = anchor.find("d:from", NS)
            blip = anchor.find(".//a:blip", NS)
            if origin is not None and blip is not None and int(origin.find("d:col", NS).text) == column - 1:
                # The last picture is topmost when workbook drawings overlap.
                pictures[int(origin.find("d:row", NS).text) + 1] = media[blip.get(REL + "embed")]
        count = 0
        for dataset in ("zoids", "transports"):
            destination = assets / dataset
            destination.mkdir(parents=True, exist_ok=True)
            for record in catalog.tables[dataset]["records"]:
                if record["id"] == "zoids:great_zaber":
                    continue  # The app shares Proto Zaber's image.
                image_path = pictures[record["source"]["row"]]
                with Image.open(BytesIO(archive.read(image_path))) as image:
                    image.convert("RGBA").save(destination / f"{record['id'].split(':', 1)[1]}.png", optimize=True)
                count += 1
        print(f"Extracted {count} base pictures to {assets}")


if __name__ == "__main__":
    extract()
