from __future__ import annotations

import json
from pathlib import Path

from PySide6.QtWidgets import (QDialog, QHBoxLayout, QLabel, QMessageBox,
                               QPushButton, QTabWidget, QVBoxLayout, QWidget)

from services.orders import accept_layout
from .preview import LayoutView

RUNTIME_PATH = Path(__file__).resolve().parents[1] / "runtime"


class ResultsDialog(QDialog):
    def __init__(self, parent, order_path: str, width: int):
        super().__init__(parent)
        self.setWindowTitle("Choose the best strategy")
        self.resize(1100, 750)
        self.roll_width = width
        self.tabs = QTabWidget()
        self.result_paths: list[Path] = []
        self.save_button = QPushButton("Save as final")
        controls = QHBoxLayout()
        controls.addWidget(self.save_button)
        layout = QVBoxLayout(self)
        layout.addWidget(self.tabs)
        layout.addLayout(controls)
        self.save_button.clicked.connect(self.save_selected)
        self.order_path = order_path
        self.load_tabs()

    def load_tabs(self) -> None:
        self.tabs.clear()
        self.result_paths.clear()
        for index in (1, 2):
            path = RUNTIME_PATH / f"Optimal_{index}.json"
            if not path.exists():
                continue
            try:
                with path.open(encoding="utf-8") as stream:
                    data = json.load(stream)
                title = data.get("nazwa_strategii", f"Strategy #{index}")
                page = QWidget()
                row = QHBoxLayout(page)
                panel = QVBoxLayout()
                panel.addWidget(QLabel(f"Optimized (height {self._height(path)} mm)"))
                view = LayoutView()
                with path.open(encoding="utf-8") as stream:
                    view.show_layout(json.load(stream))
                panel.addWidget(view)
                row.addLayout(panel)
                self.tabs.addTab(page, f"{'🥇' if index == 1 else '🥈'} {title}")
                self.result_paths.append(path)
            except (OSError, ValueError) as exc:
                QMessageBox.warning(self, "Results error", str(exc))

    @staticmethod
    def _height(path: Path) -> str:
        if not path.exists():
            return "-"
        try:
            with path.open(encoding="utf-8") as stream:
                return str(json.load(stream).get("wysokosc_rolki", "-"))
        except (OSError, ValueError):
            return "-"

    def save_selected(self) -> None:
        selected_index = self.tabs.currentIndex()
        if selected_index < 0 or selected_index >= len(self.result_paths):
            QMessageBox.warning(self, "File missing", "No optimized layout is available.")
            return
        filename = self.result_paths[selected_index]
        if not filename.exists():
            QMessageBox.warning(self, "File missing", f"{filename.name} was not found")
            return
        accept_layout(filename)
        QMessageBox.information(self, "Done", "Saved data/accepted_layouts/final_production_layout.json")
        self.accept()
