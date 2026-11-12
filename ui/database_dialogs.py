"""Dialogs for creating products, components, and combos."""

from __future__ import annotations

from typing import Any, Callable

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QComboBox,
    QDialog,
    QDialogButtonBox,
    QFormLayout,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QMessageBox,
    QPushButton,
    QSpinBox,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
)

from services.coreldraw_reader import (
    CorelDrawReaderError,
    CorelSelection,
    add_object_spacing,
    read_active_selection,
    save_selection_to_file,
)


def _selection_row(selection: CorelSelection) -> str:
    source = selection.source_path or "(brak zapisanej ścieżki dokumentu)"
    width, height = add_object_spacing(selection.width_mm, selection.height_mm)
    return f"{width:.2f} × {height:.2f} mm\n{source}"


class SelectionForm(QDialog):
    def __init__(self, title: str, parent=None):
        super().__init__(parent)
        self.setWindowTitle(title)
        self.selection: CorelSelection | None = None
        self.name = QLineEdit()
        self.category = QLineEdit("Nadruk")
        self.preview = QLabel("Nie odczytano zaznaczenia.")
        self.preview.setWordWrap(True)
        scan = QPushButton("Pobierz zaznaczenie z CorelDRAW")
        scan.clicked.connect(self.scan)
        form = QFormLayout()
        form.addRow("Nazwa:", self.name)
        form.addRow("Kategoria drzewa:", self.category)
        form.addRow("Dane z CorelDRAW:", self.preview)
        form.addRow("", scan)
        buttons = QDialogButtonBox(QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel)
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)
        layout = QVBoxLayout(self)
        layout.addLayout(form)
        layout.addWidget(buttons)

    def scan(self) -> None:
        try:
            self.selection = read_active_selection()
            self.preview.setText(_selection_row(self.selection))
        except CorelDrawReaderError as exc:
            QMessageBox.critical(self, "CorelDRAW", str(exc))

    def accept(self) -> None:
        if not self.name.text().strip():
            QMessageBox.warning(self, "Produkt", "Podaj nazwę.")
            return
        if self.selection is None:
            QMessageBox.warning(self, "Produkt", "Najpierw pobierz zaznaczenie z CorelDRAW.")
            return
            
        try:
            self.saved_path = save_selection_to_file(self.name.text().strip())
        except Exception as exc:
            QMessageBox.critical(self, "Błąd zapisu", str(exc))
            return
            
        super().accept()

    def value(self) -> dict[str, Any]:
        assert self.selection is not None
        width, height = add_object_spacing(self.selection.width_mm, self.selection.height_mm)
        return {
            "nazwa": self.name.text().strip(),
            "typ": self.category.text().strip() or "Nadruk",
            "w": width,
            "h": height,
            "plik": getattr(self, "saved_path", self.selection.source_path), # <--- UŻYCIE NOWEJ ŚCIEŻKI
        }


class PartsDialog(QDialog):
    def __init__(self, database: list[dict[str, Any]], parent=None):
        super().__init__(parent)
        self.setWindowTitle("Dodaj części produktu")
        self.database = database
        self.rows: list[dict[str, Any] | None] = []
        self.parent_product = QComboBox()
        self.parent_product.addItems([str(item.get("nazwa", "")) for item in database if item.get("nazwa")])
        self.count = QSpinBox()
        self.count.setRange(1, 100)
        self.count.valueChanged.connect(self.build_rows)
        self.table = QTableWidget(0, 4)
        self.table.setHorizontalHeaderLabels(["Nazwa części", "Status", "W (mm)", "H (mm)"])
        self.build_rows(1)
        add = QPushButton("Pobierz zaznaczenie dla wybranej części")
        add.clicked.connect(self.scan_current)
        buttons = QDialogButtonBox(QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel)
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)
        form = QFormLayout()
        form.addRow("Produkt nadrzędny:", self.parent_product)
        form.addRow("Liczba części:", self.count)
        layout = QVBoxLayout(self)
        layout.addLayout(form)
        layout.addWidget(self.table)
        layout.addWidget(add)
        layout.addWidget(buttons)

    def build_rows(self, count: int) -> None:
        old = self.rows
        self.rows = [old[index] if index < len(old) else None for index in range(count)]
        self.table.setRowCount(count)
        for index in range(count):
            name = QLineEdit()
            name.setPlaceholderText(f"Część {index + 1}")
            self.table.setCellWidget(index, 0, name)
            self.table.setItem(index, 1, QTableWidgetItem("Nie zeskanowano"))
            self.table.setItem(index, 2, QTableWidgetItem(""))
            self.table.setItem(index, 3, QTableWidgetItem(""))
            if self.rows[index]:
                self._show_row(index)

    def scan_current(self) -> None:
        row = self.table.currentRow()
        if row < 0:
            QMessageBox.warning(self, "Część", "Wybierz wiersz części.")
            return
            
        name = self.table.cellWidget(row, 0).text().strip()
        if not name:
            QMessageBox.warning(self, "Część", "Najpierw wpisz nazwę dla tej części (żeby poprawnie nazwać plik).")
            return
            
        parent = self.parent_product.currentText().strip()
        file_base_name = f"{parent}_{name}"
            
        try:
            selection = read_active_selection()
            saved_path = save_selection_to_file(file_base_name)
            self.rows[row] = {"selection": selection, "saved_path": saved_path}
            self._show_row(row)
        except CorelDrawReaderError as exc:
            QMessageBox.critical(self, "CorelDRAW", str(exc))

    def _show_row(self, row: int) -> None:
        selection = self.rows[row]["selection"]
        width, height = add_object_spacing(selection.width_mm, selection.height_mm)
        self.table.item(row, 1).setText("Zeskanowano")
        self.table.item(row, 2).setText(f"{width:.2f}")
        self.table.item(row, 3).setText(f"{height:.2f}")

    def accept(self) -> None:
        parent = self.parent_product.currentText().strip()
        if not parent or any(row is None for row in self.rows):
            QMessageBox.warning(self, "Części", "Zeskanuj każdą część i wybierz produkt nadrzędny.")
            return
        names = [self.table.cellWidget(row, 0).text().strip() for row in range(self.table.rowCount())]
        if any(not name for name in names):
            QMessageBox.warning(self, "Części", "Każda część musi mieć nazwę.")
            return
        super().accept()

    def values(self) -> list[dict[str, Any]]:
        parent = self.parent_product.currentText().strip()
        result = []
        for row in range(self.table.rowCount()):
            row_data = self.rows[row]
            if not row_data or "selection" not in row_data:
                continue
                
            selection = row_data["selection"]
            saved_path = row_data.get("saved_path", selection.source_path)
            width, height = add_object_spacing(selection.width_mm, selection.height_mm)
            
            result.append({
                "nazwa": self.table.cellWidget(row, 0).text().strip(),
                "typ": next((item.get("typ", "Nadruk") for item in self.database if item.get("nazwa") == parent), "Nadruk"),
                "w": width,
                "h": height,
                "plik": saved_path,
                "czesc_z": parent,
            })
        return result


class ComboDialog(QDialog):
    def __init__(self, database: list[dict[str, Any]], parent=None):
        super().__init__(parent)
        self.setWindowTitle("Utwórz combo")
        self.database = database
        self.selection: CorelSelection | None = None
        self.name = QLineEdit()
        self.category = QLineEdit("Nadruk")
        self.product = QComboBox()
        self.product.addItems([str(item.get("nazwa", "")) for item in database if item.get("nazwa")])
        self.quantity = QSpinBox()
        self.quantity.setRange(1, 100000)
        self.table = QTableWidget(0, 2)
        self.table.setHorizontalHeaderLabels(["Produkt", "Ilość"])
        add = QPushButton("Dodaj składnik")
        add.clicked.connect(self.add_component)
        remove = QPushButton("Usuń zaznaczony składnik")
        remove.clicked.connect(lambda: self.table.removeRow(self.table.currentRow()) if self.table.currentRow() >= 0 else None)
        scan = QPushButton("Pobierz wymiary combo z CorelDRAW")
        scan.clicked.connect(self.scan)
        self.preview = QLabel("Nie odczytano zaznaczenia.")
        buttons = QDialogButtonBox(QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel)
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)
        form = QFormLayout()
        form.addRow("Nazwa combo:", self.name)
        form.addRow("Kategoria drzewa:", self.category)
        form.addRow("Produkt:", self.product)
        form.addRow("Ilość:", self.quantity)
        layout = QVBoxLayout(self)
        layout.addLayout(form)
        layout.addWidget(add)
        layout.addWidget(self.table)
        layout.addWidget(remove)
        layout.addWidget(scan)
        layout.addWidget(self.preview)
        layout.addWidget(buttons)

    def add_component(self) -> None:
        row = self.table.rowCount()
        self.table.insertRow(row)
        self.table.setItem(row, 0, QTableWidgetItem(self.product.currentText()))
        self.table.setItem(row, 1, QTableWidgetItem(str(self.quantity.value())))

    def scan(self) -> None:
        try:
            self.selection = read_active_selection()
            self.preview.setText(_selection_row(self.selection))
        except CorelDrawReaderError as exc:
            QMessageBox.critical(self, "CorelDRAW", str(exc))

    def accept(self) -> None:
        if not self.name.text().strip() or self.table.rowCount() == 0 or self.selection is None:
            QMessageBox.warning(self, "Combo", "Podaj nazwę, dodaj składniki i zeskanuj combo.")
            return
            
        try:
            self.saved_path = save_selection_to_file(self.name.text().strip())
        except Exception as exc:
            QMessageBox.critical(self, "Błąd zapisu", str(exc))
            return
            
        super().accept()

    def value(self) -> dict[str, Any]:
        assert self.selection is not None
        width, height = add_object_spacing(self.selection.width_mm, self.selection.height_mm)
        composition: dict[str, int] = {}
        for row in range(self.table.rowCount()):
            product = self.table.item(row, 0).text()
            quantity = int(self.table.item(row, 1).text())
            if quantity <= 0:
                raise ValueError("Ilość składnika musi być dodatnia.")
            composition[product] = composition.get(product, 0) + quantity
        return {
            "nazwa": self.name.text().strip(),
            "typ": self.category.text().strip() or "Nadruk",
            "w": width,
            "h": height,
            "plik": getattr(self, "saved_path", self.selection.source_path), # <--- UŻYCIE NOWEJ ŚCIEŻKI
            "sklad_combo": composition,
        }
