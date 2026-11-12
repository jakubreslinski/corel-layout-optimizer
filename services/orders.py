"""JSON persistence and order helpers for the desktop application."""

from __future__ import annotations

import json
import os
import time
from pathlib import Path
from typing import Any


WORK_FILES = (
    "runtime/Optimal_1.json", "runtime/Human_1.json",
    "runtime/Optimal_2.json", "runtime/Human_2.json",
    "runtime/meta_zlecenia.json", "runtime/zlecenie.json",
)
PROJECT_ROOT = Path(__file__).resolve().parents[1]
DATABASE_PATH = PROJECT_ROOT / "data" / "print_database.json"
TRAINING_PATH = PROJECT_ROOT / "data" / "training"
FINAL_LAYOUT_PATH = PROJECT_ROOT / "data" / "accepted_layouts" / "final_production_layout.json"
RUNTIME_PATH = PROJECT_ROOT / "runtime"


def load_database(path: str | os.PathLike[str] = DATABASE_PATH) -> list[dict[str, Any]]:
    file_path = Path(path)
    if not file_path.exists():
        save_database([], file_path)
        return []
    with file_path.open(encoding="utf-8") as stream:
        value = json.load(stream)
    return value if isinstance(value, list) else []


def save_database(items: list[dict[str, Any]], path: str | os.PathLike[str] = DATABASE_PATH) -> None:
    with Path(path).open("w", encoding="utf-8") as stream:
        json.dump(items, stream, ensure_ascii=False, indent=4)


def clear_work_files() -> None:
    RUNTIME_PATH.mkdir(parents=True, exist_ok=True)
    for name in WORK_FILES:
        try:
            (PROJECT_ROOT / name).unlink()
        except FileNotFoundError:
            pass


def write_order(width: int, items: list[dict[str, Any]], path: str = "zlecenie.json") -> str:
    if path == "zlecenie.json":
        path = str(RUNTIME_PATH / path)
    RUNTIME_PATH.mkdir(parents=True, exist_ok=True)
    order = {
        "szerokosc_maszyny": width,
        "kalkuluj_optymalna": True,
        "elementy": items,
    }
    with open(path, "w", encoding="utf-8") as stream:
        json.dump(order, stream, ensure_ascii=False, indent=4)
    return os.path.abspath(path)


def accept_layout(source: str, destination: str | os.PathLike[str] = FINAL_LAYOUT_PATH) -> str:
    destination = Path(destination)
    destination.parent.mkdir(parents=True, exist_ok=True)
    with open(source, encoding="utf-8") as stream:
        data = json.load(stream)
    with open(destination, "w", encoding="utf-8") as stream:
        json.dump(data, stream, ensure_ascii=False, indent=4)
    TRAINING_PATH.mkdir(parents=True, exist_ok=True)
    with (TRAINING_PATH / f"uklad_ai_{int(time.time())}.json").open("w", encoding="utf-8") as stream:
        json.dump(data, stream, ensure_ascii=False, indent=4)
    for name in ("Optimal_1.json", "Optimal_2.json", "Human_1.json",
                 "Human_2.json", "meta_zlecenia.json"):
        try:
            (PROJECT_ROOT / "runtime" / name).unlink()
        except FileNotFoundError:
            pass
    return str(destination)
