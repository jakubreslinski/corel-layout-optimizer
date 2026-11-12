"""PySide6 desktop application for the Corel layout optimizer."""

from __future__ import annotations

import sys
from pathlib import Path

from PySide6.QtCore import QProcess, Qt
from PySide6.QtGui import QIntValidator
from PySide6.QtWidgets import (QAbstractItemView, QApplication, QDialog,
                               QDialogButtonBox, QFormLayout, QHBoxLayout,
                               QHeaderView,
                               QLabel, QLineEdit, QMainWindow, QMessageBox,
                               QProgressBar, QPushButton, QSpinBox, QSplitter, QTreeWidget,
                               QTreeWidgetItem,
                               QVBoxLayout, QWidget)

from services.coreldraw_export import export_layout
from services.coreldraw_reader import add_object_spacing
from services.orders import clear_work_files, load_database, save_database, write_order
from ui.database_dialogs import ComboDialog, PartsDialog, SelectionForm
from ui.results import ResultsDialog
from ui.text_generator import TextGeneratorDialog


class ItemDialog(QDialog):
    """Small PySide6 replacement for the legacy item/text-generator dialogs."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("New print (PySide6)")
        form = QFormLayout(self)
        self.item_name = QLineEdit()
        self.category = QLineEdit("Other")
        self.item_width, self.item_height = QSpinBox(), QSpinBox()
        self.item_width.setRange(1, 10000); self.item_width.setValue(100)
        self.item_height.setRange(1, 10000); self.item_height.setValue(100)
        self.source_file = QLineEdit()
        for label, widget in (("Name", self.item_name), ("Category", self.category),
                              ("Width (mm)", self.item_width), ("Height (mm)", self.item_height),
                              ("CDR file", self.source_file)):
            form.addRow(label, widget)
        buttons = QDialogButtonBox(QDialogButtonBox.StandardButton.Ok |
                                   QDialogButtonBox.StandardButton.Cancel)
        form.addRow(buttons)
        buttons.accepted.connect(self.accept); buttons.rejected.connect(self.reject)

    def value(self) -> dict:
        width, height = add_object_spacing(self.item_width.value(), self.item_height.value())
        return {"nazwa": self.item_name.text().strip(), "typ": self.category.text().strip() or "Other",
                "w": width, "h": height,
                "plik": self.source_file.text().strip()}


class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Print Layout Manager — PySide6")
        self.resize(1050, 800)
        self.database = load_database()
        self.basket: dict[tuple[str, str], dict] = {}
        self.process: QProcess | None = None
        self.status_label = QLabel("Ready — select prints from the database.")
        self.progress = QProgressBar()
        self.progress.setRange(0, 1)
        self.progress.setValue(0)
        self.search = QLineEdit()
        self.search.setPlaceholderText("Search prints…")
        self.roll_width = QSpinBox(); self.roll_width.setRange(1, 100000); self.roll_width.setValue(443)
        self.tree = QTreeWidget(); self.tree.setHeaderLabels(["Print database", "Add"])
        self.tree.setAlternatingRowColors(True)
        self.tree.setMinimumHeight(360)
        self.tree.setStyleSheet("QTreeWidget::item { padding: 6px 2px; }")
        self.tree.header().setSectionResizeMode(0, QHeaderView.ResizeMode.Stretch)
        self.tree.header().setSectionResizeMode(1, QHeaderView.ResizeMode.ResizeToContents)
        self.tree.setColumnWidth(1, 90)
        self.tree.itemClicked.connect(self.add_tree_item_from_click)
        self.tree.itemDoubleClicked.connect(self.add_tree_item)
        self.basket_table = QTreeWidget()
        self.basket_table.setHeaderLabels(["Name", "Category", "Dimensions", "Quantity", "Actions"])
        self.basket_table.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        self.basket_table.setAlternatingRowColors(True)
        self.basket_table.setMinimumHeight(240)
        basket_header = self.basket_table.header()
        basket_header.setSectionResizeMode(0, QHeaderView.ResizeMode.Stretch)
        basket_header.setSectionResizeMode(1, QHeaderView.ResizeMode.Stretch)
        basket_header.setSectionResizeMode(2, QHeaderView.ResizeMode.ResizeToContents)
        basket_header.setSectionResizeMode(3, QHeaderView.ResizeMode.ResizeToContents)
        basket_header.setSectionResizeMode(4, QHeaderView.ResizeMode.ResizeToContents)
        basket_header.setMinimumSectionSize(120)
        self.build_ui()
        self.refresh_tree()

    def build_ui(self) -> None:
        add = QPushButton("+ New product from CorelDRAW"); add.clicked.connect(self.add_item_from_corel)
        parts = QPushButton("Split product into parts"); parts.clicked.connect(self.add_parts)
        combo = QPushButton("Create combo"); combo.clicked.connect(self.add_combo)
        text = QPushButton("🔤 Generator napisów"); text.clicked.connect(self.add_texts)
        top = QHBoxLayout()
        top.addWidget(self.search); top.addWidget(add); top.addWidget(parts); top.addWidget(combo); top.addWidget(text)
        top.addWidget(QLabel("Roll width:")); top.addWidget(self.roll_width)
        self.search.textChanged.connect(self.refresh_tree)
        remove = QPushButton("Remove selected"); remove.clicked.connect(self.remove_selected)
        self.run_button = QPushButton("Run layout (in background)")
        self.run_button.clicked.connect(self.run_optimizer)
        export = QPushButton("🌟 Send final order to CorelDRAW")
        export.clicked.connect(self.export_corel)
        splitter = QSplitter(Qt.Orientation.Vertical)
        upper = QWidget(); upper_layout = QVBoxLayout(upper)
        upper_layout.addWidget(QLabel("Database — click + or double-click to add to basket")); upper_layout.addWidget(self.tree)
        lower = QWidget(); lower_layout = QVBoxLayout(lower)
        lower_layout.addWidget(QLabel("Items to lay out (basket)")); lower_layout.addWidget(self.basket_table)
        lower_layout.addWidget(self.status_label)
        lower_layout.addWidget(remove)
        splitter.addWidget(upper); splitter.addWidget(lower)
        splitter.setStretchFactor(0, 3)
        splitter.setStretchFactor(1, 2)
        root = QWidget(); layout = QVBoxLayout(root)
        layout.addLayout(top); layout.addWidget(splitter)
        layout.addWidget(self.progress)
        layout.addWidget(self.run_button); layout.addWidget(export)
        self.setCentralWidget(root)

    def refresh_tree(self) -> None:
        self.tree.clear()
        needle = self.search.text().casefold()
        categories: dict[tuple[str, ...], QTreeWidgetItem] = {}
        for item in sorted(self.database, key=self._item_sort_key):
            if needle and needle not in item.get("nazwa", "").casefold():
                continue
            parts = self._category_parts(item.get("typ", "Uncategorized"))
            parent: QTreeWidgetItem | None = None
            for level in range(1, len(parts) + 1):
                path = tuple(parts[:level])
                category = categories.get(path)
                if category is None:
                    category = QTreeWidgetItem([parts[-1] if level == len(parts) else parts[level - 1]])
                    if parent is None:
                        self.tree.addTopLevelItem(category)
                    else:
                        parent.addChild(category)
                    categories[path] = category
                parent = category
            child = QTreeWidgetItem([
                f"{item.get('nazwa', 'unnamed')} ({item.get('w', 0)}×{item.get('h', 0)} mm)",
                "+ Add",
            ])
            child.setData(0, Qt.ItemDataRole.UserRole, item)
            parent.addChild(child)
        self._sort_tree(self.tree)
        if needle:
            self.tree.expandAll()
        else:
            self.tree.collapseAll()

    def add_tree_item(self, item: QTreeWidgetItem, column: int | None = None) -> None:
        if column == 1:
            return
        value = item.data(0, Qt.ItemDataRole.UserRole)
        if value:
            key = (value.get("nazwa", ""), value.get("typ", "unknown"))
            if key in self.basket: self.basket[key]["quantity"] += 1
            else: self.basket[key] = {"item": value, "quantity": 1}
            self.refresh_basket()
            self.status_label.setText(
                f"Selected: {value.get('nazwa', 'unnamed')} "
                f"(quantity {self.basket[key]['quantity']})"
            )

    def add_tree_item_from_click(self, item: QTreeWidgetItem, column: int) -> None:
        if column == 1:
            self.add_tree_item(item)

    def refresh_basket(self) -> None:
        vertical_scroll = self.basket_table.verticalScrollBar().value()
        horizontal_scroll = self.basket_table.horizontalScrollBar().value()
        current_item = self.basket_table.currentItem()
        current_key = (
            current_item.data(0, Qt.ItemDataRole.UserRole)
            if current_item is not None
            else None
        )
        self.basket_table.blockSignals(True)
        self.basket_table.clear()
        self.basket_table.setHeaderLabels(["Name", "Category", "Dimensions", "Quantity", "Actions"])
        categories: dict[tuple[str, ...], QTreeWidgetItem] = {}
        for key, value in sorted(self.basket.items(), key=lambda entry: self._item_sort_key(entry[1]["item"])):
            item = value["item"]
            parts = self._category_parts(item.get("typ", "Uncategorized"))
            parent: QTreeWidgetItem | None = None
            for level in range(1, len(parts) + 1):
                path = tuple(parts[:level])
                category = categories.get(path)
                if category is None:
                    category = QTreeWidgetItem([parts[level - 1]])
                    if parent is None:
                        self.basket_table.addTopLevelItem(category)
                    else:
                        parent.addChild(category)
                    categories[path] = category
                parent = category
            child = QTreeWidgetItem([
                item.get("nazwa", ""),
                item.get("typ", ""),
                f'{item.get("w", 0)}×{item.get("h", 0)} mm',
                "",
            ])
            child.setData(0, Qt.ItemDataRole.UserRole, key)
            parent.addChild(child)
        self._sort_tree(self.basket_table)
        self.basket_table.expandAll()

        for key, value in sorted(self.basket.items(), key=lambda entry: self._item_sort_key(entry[1]["item"])):
            child = self._find_basket_item(key)
            if child is None:
                continue
            quantity_input = QLineEdit(str(value["quantity"]))
            quantity_input.setValidator(QIntValidator(1, 100000, quantity_input))
            quantity_input.setToolTip("Type any quantity from 1 to 100000")
            quantity_input.setMinimumWidth(80)
            quantity_input.editingFinished.connect(
                lambda item_key=key, field=quantity_input: self.quantity_text_changed(
                    item_key, field
                )
            )
            self.basket_table.setItemWidget(child, 3, quantity_input)

            actions = QWidget()
            actions_layout = QHBoxLayout(actions)
            actions_layout.setContentsMargins(2, 0, 2, 0)
            add_one = QPushButton("+1")
            subtract_one = QPushButton("−1")
            add_one.setToolTip("Add one copy")
            subtract_one.setToolTip("Remove one copy")
            add_one.clicked.connect(lambda checked=False, item_key=key: self.change_quantity(item_key, 1))
            subtract_one.clicked.connect(
                lambda checked=False, item_key=key: self.change_quantity(item_key, -1)
            )
            actions_layout.addWidget(add_one)
            actions_layout.addWidget(subtract_one)
            self.basket_table.setItemWidget(child, 4, actions)
        if current_key is not None:
            restored_item = self._find_basket_item(current_key)
            if restored_item is not None:
                self.basket_table.setCurrentItem(restored_item)
        self.basket_table.verticalScrollBar().setValue(vertical_scroll)
        self.basket_table.horizontalScrollBar().setValue(horizontal_scroll)
        self.basket_table.blockSignals(False)

    def _find_basket_item(self, key: tuple[str, str]) -> QTreeWidgetItem | None:
        def find(parent: QTreeWidgetItem) -> QTreeWidgetItem | None:
            for index in range(parent.childCount()):
                child = parent.child(index)
                if child.data(0, Qt.ItemDataRole.UserRole) == key:
                    return child
                result = find(child)
                if result is not None:
                    return result
            return None

        for index in range(self.basket_table.topLevelItemCount()):
            result = find(self.basket_table.topLevelItem(index))
            if result is not None:
                return result
        return None

    @classmethod
    def _item_sort_key(cls, item: dict) -> tuple[tuple[str, ...], str]:
        categories = tuple(part.casefold() for part in cls._category_parts(item.get("typ", "")))
        return categories, str(item.get("nazwa", "")).casefold()

    @staticmethod
    def _sort_tree(tree: QTreeWidget) -> None:
        roots = [tree.takeTopLevelItem(0) for _ in range(tree.topLevelItemCount())]
        for root in sorted(roots, key=lambda node: node.text(0).casefold()):
            tree.addTopLevelItem(root)

            def sort_children(node: QTreeWidgetItem) -> None:
                children = node.takeChildren()
                for child in sorted(children, key=lambda child: child.text(0).casefold()):
                    node.addChild(child)
                    sort_children(child)

            sort_children(root)
    @staticmethod
    def _category_parts(category: object) -> list[str]:
        parts = [part.strip() for part in str(category).split("/") if part.strip()]
        return parts or ["Uncategorized"]

    def quantity_text_changed(self, key: tuple[str, str], field: QLineEdit) -> None:
        try:
            quantity = int(field.text())
        except ValueError:
            field.setText(str(self.basket[key]["quantity"]))
            return
        self.set_quantity(key, quantity)

    def set_quantity(self, key: tuple[str, str], quantity: int) -> None:
        if key not in self.basket:
            return
        self.basket[key]["quantity"] = max(1, min(100000, quantity))
        self.status_label.setText(
            f"Quantity updated: {self.basket[key]['item'].get('nazwa', 'unnamed')} "
            f"({self.basket[key]['quantity']})"
        )

    def change_quantity(self, key: tuple[str, str], amount: int) -> None:
        if key not in self.basket:
            return
        new_quantity = self.basket[key]["quantity"] + amount
        if new_quantity < 1:
            self.basket.pop(key)
            self.status_label.setText("Item removed from the basket.")
            self.refresh_basket()
            return
        self.set_quantity(key, new_quantity)
        self.refresh_basket()

    def remove_selected(self) -> None:
        item = self.basket_table.currentItem()
        if item:
            key = item.data(0, Qt.ItemDataRole.UserRole)
            if key is None:
                return
            self.basket.pop(key, None); self.refresh_basket()
            self.status_label.setText("Selected item removed from the basket.")

    def add_item(self) -> None:
        dialog = ItemDialog(self)
        if dialog.exec() and dialog.value()["nazwa"]:
            self.database.append(dialog.value()); save_database(self.database); self.refresh_tree()

    def add_to_basket_directly(self, value: dict) -> None:
        """Adds an item directly to the basket and refreshes the view."""
        key = (value.get("nazwa", ""), value.get("typ", "unknown"))
        if key in self.basket:
            self.basket[key]["quantity"] += 1
        else:
            self.basket[key] = {"item": value, "quantity": 1}
        self.refresh_basket()
        
    def add_texts(self) -> None:
        dialog = TextGeneratorDialog(self)
        if dialog.exec():
            try:
                values = dialog.values()
            except ValueError as exc:
                QMessageBox.warning(self, "Generator napisów", str(exc))
                return
            self.database.extend(values)
            save_database(self.database)
            self.refresh_tree()
            
            for item in values:
                self.add_to_basket_directly(item)
                                            
            self.status_label.setText(
                "Napisy zmierzone." if not values else "Wygenerowane napisy zapisano w bazie."
            )

    def add_item_from_corel(self) -> None:
        dialog = SelectionForm("New product from CorelDRAW", self)
        if dialog.exec():
            self.database.append(dialog.value())
            save_database(self.database)
            self.refresh_tree()
            self.status_label.setText("Product saved to the database.")

    def add_parts(self) -> None:
        if not self.database:
            QMessageBox.information(self, "Parts", "Add a parent product first.")
            return
        dialog = PartsDialog(self.database, self)
        if dialog.exec():
            self.database.extend(dialog.values())
            save_database(self.database)
            self.refresh_tree()
            self.status_label.setText("Product parts saved to the database.")

    def add_combo(self) -> None:
        if not self.database:
            QMessageBox.information(self, "Combo", "Add products first.")
            return
        dialog = ComboDialog(self.database, self)
        if dialog.exec():
            self.database.append(dialog.value())
            save_database(self.database)
            self.refresh_tree()
            self.status_label.setText("Combo saved to the database.")

    def run_optimizer(self) -> None:
        if not self.basket:
            QMessageBox.information(self, "Basket", "Add at least one print.")
            return
        clear_work_files()
        self.status_label.setText("Algorithm is running — please wait for the results.")
        self.progress.setRange(0, 0)
        self.run_button.setEnabled(False)
        items = [value["item"] for value in self.basket.values() for _ in range(value["quantity"])]
        order = write_order(self.roll_width.value(), items)
        self.process = QProcess(self)
        self.process.finished.connect(lambda: self.show_results(order))
        self.process.start(sys.executable, ["main.py", order])

    def show_results(self, order: str) -> None:
        self.progress.setRange(0, 1)
        self.progress.setValue(0)
        self.run_button.setEnabled(True)
        if self.process and self.process.exitCode() != 0:
            error_details = bytes(self.process.readAllStandardError()).decode('utf-8', errors='ignore').strip()
            if not error_details:
                error_details = bytes(self.process.readAllStandardOutput()).decode('utf-8', errors='ignore').strip()
            if not error_details:
                error_details = f"Kod błędu procesu: {self.process.exitCode()}"

            self.status_label.setText("Optimization failed.")
            
            msg_box = QMessageBox(self)
            msg_box.setIcon(QMessageBox.Icon.Critical)
            msg_box.setWindowTitle("Błąd optymalizacji")
            msg_box.setText("Proces optymalizacji zakończył się błędem:")
            msg_box.setDetailedText(error_details)
            msg_box.exec()
            return
            
        self.status_label.setText("Optimization finished — choose a layout to save.")
        
        ResultsDialog(self, order, self.roll_width.value()).exec()

    def export_corel(self) -> None:
        path = str(Path(__file__).resolve().parent / "data" / "accepted_layouts" / "final_production_layout.json")
        if not Path(path).exists():
            QMessageBox.warning(self, "File missing", "Save the final production layout first.")
            return
        try:
            QMessageBox.information(self, "CorelDRAW", f"Imported {export_layout(path)} items.")
        except Exception as exc:
            QMessageBox.critical(self, "CorelDRAW", str(exc))


def main() -> int:
    app = QApplication(sys.argv)
    window = MainWindow(); window.show()
    return app.exec()


if __name__ == "__main__":
    raise SystemExit(main())
