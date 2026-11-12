"""Read the active CorelDRAW selection without modifying the document."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
import shutil
import sys

from integrations.coreldraw import connect
import re

    
try:
    import win32com
    if hasattr(win32com, '__gen_path__'):
        shutil.rmtree(win32com.__gen_path__, ignore_errors=True)
except Exception:
    pass

sys.modules.pop("win32com.gen_py", None)


class CorelDrawReaderError(RuntimeError):
    """A user-actionable error while reading CorelDRAW."""


OBJECT_SPACING_MM = 3.0


@dataclass(frozen=True)
class CorelSelection:
    width_mm: float
    height_mm: float
    source_path: str


def add_object_spacing(width_mm: float, height_mm: float) -> tuple[float, float]:
    """Return stored object dimensions with the required clearance added."""
    return round(width_mm + OBJECT_SPACING_MM, 2), round(height_mm + OBJECT_SPACING_MM, 2)


def _document_path(document: object) -> str:
    for attribute in ("FullFileName", "FilePath", "FileName"):
        try:
            value = getattr(document, attribute)
        except Exception:
            continue
        if value:
            return str(Path(str(value)))
    return ""


def _to_mm(value: float, unit: object) -> float:
    # CorelDRAW cdrUnit values: pixel=0, inch=1, foot=2, millimeter=3,
    # centimeter=4, meter=5, point=6, pica=7.
    unit_id = int(unit)
    factors = {
        0: 25.4 / 96.0,
        1: 25.4,
        2: 304.8,
        3: 1.0,
        4: 10.0,
        5: 1000.0,
        6: 25.4 / 72.0,
        7: 25.4 / 6.0,
    }
    if unit_id not in factors:
        raise CorelDrawReaderError(f"Nieobsługiwana jednostka CorelDRAW: {unit_id}.")
    return float(value) * factors[unit_id]


def _selection_count(selection: object) -> int:
    try:
        if hasattr(selection, "Shapes"):
            return int(selection.Shapes.Count)
        return int(selection.Count)
    except (AttributeError, TypeError, ValueError):
        return 0


def _active_selection(corel: object, document: object) -> object:
    selections = []
    
    for owner_name, owner in [("corel", corel), ("document", document)]:
        try:
            sel = owner.ActiveSelection
            selections.append(sel)
        except Exception as e:
            continue

    for i, selection in enumerate(selections):
        count = _selection_count(selection)
        if count > 0:
            return selection

    raise CorelDrawReaderError(
        "Nie wykryto zaznaczenia. Zaznacz obiekt w CorelDRAW, "
        "pozostaw dokument otwarty i kliknij przycisk ponownie."
    )


def read_active_selection() -> CorelSelection:
    """Return the active selection dimensions in millimetres."""
    try:
        corel = connect()
        document = corel.ActiveDocument
        selection = _active_selection(corel, document)
        width = _to_mm(float(selection.SizeWidth), document.Unit)
        height = _to_mm(float(selection.SizeHeight), document.Unit)
        if width <= 0 or height <= 0:
            raise CorelDrawReaderError("Zaznaczenie w CorelDRAW ma nieprawidłowe wymiary.")
        return CorelSelection(width, height, _document_path(document))
    except CorelDrawReaderError:
        raise
    except Exception as exc:
        raise CorelDrawReaderError(
            f"Nie udało się odczytać zaznaczenia z CorelDRAW: {exc}"
        ) from exc


def save_selection_to_file(name: str) -> str:
    """Coppies the active selection to a new CorelDRAW document and saves it to a file."""
    try:
        corel = connect()
        document = corel.ActiveDocument
        selection = _active_selection(corel, document)
        
        safe_name = re.sub(r'[^a-zA-Z0-9_\- ]', '', name).strip().replace(' ', '_')
        if not safe_name:
            safe_name = "nadruk"
            
        project_root = Path(__file__).resolve().parents[1]
        target_folder = project_root / "Pliki_Zrodlowe"
        target_folder.mkdir(parents=True, exist_ok=True)
        
        save_path = str(target_folder / f"{safe_name}.cdr")
        
        selection.Copy()
        new_doc = corel.CreateDocument()
        new_doc.ActiveLayer.Paste()
        options = corel.CreateStructSaveAsOptions()
        new_doc.SaveAs(save_path, options)
        new_doc.Close()
        
        return save_path
    except CorelDrawReaderError:
        raise
    except Exception as exc:
        raise CorelDrawReaderError(f"Błąd zapisu oddzielnego pliku cdr: {exc}") from exc