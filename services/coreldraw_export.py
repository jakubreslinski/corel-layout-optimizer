"""CorelDRAW export service. COM is imported only when export is requested."""

import os
from pathlib import Path

from integrations.coreldraw import connect


def export_layout(
    path: str | os.PathLike[str] = (
        Path(__file__).resolve().parents[1]
        / "data"
        / "accepted_layouts"
        / "final_production_layout.json"
    ),
) -> int:
    import json
    with open(path, encoding="utf-8") as stream:
        data = json.load(stream)
    corel = connect()
    corel.Visible = True
    document = corel.CreateDocument()
    document.Unit = 3
    document.ActivePage.SizeWidth = float(data["szerokosc_maszyny"])
    document.ActivePage.SizeHeight = float(data["wysokosc_rolki"])
    options = corel.CreateStructImportOptions()
    imported = 0
    for element in data["elementy"]:
        source = element.get("plik")
        if not source or not os.path.exists(source):
            continue
        document.ActiveLayer.Import(source, 0, options)
        selection = corel.ActiveSelection
        if element.get("obrocony", False):
            selection.Rotate(90)
        selection.CenterX = float(element["x"]) + float(element["w"]) / 2.0
        selection.CenterY = float(element["y"]) + float(element["h"]) / 2.0
        imported += 1
    return imported
