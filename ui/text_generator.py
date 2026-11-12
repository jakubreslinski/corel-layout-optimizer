"""Multi-line CorelDRAW text generator dialog."""

from __future__ import annotations

from html import escape

from PySide6.QtCore import Qt
from PySide6.QtGui import QFontDatabase
from PySide6.QtWidgets import (
    QCheckBox,
    QComboBox,
    QDialog,
    QDialogButtonBox,
    QFormLayout,
    QFrame,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QMessageBox,
    QPushButton,
    QDoubleSpinBox,
    QPlainTextEdit,
    QScrollArea,
    QVBoxLayout,
    QWidget,
)

from services.coreldraw_reader import CorelDrawReaderError, add_object_spacing
from services.coreldraw_text import MeasuredText, measure_texts, scale_measured_texts


class TextGeneratorDialog(QDialog):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Generator napisów z CorelDRAW")
        self.measurements: list[MeasuredText] = []
        self.raw_measurements: list[MeasuredText] = []
        self.result_rows: list[tuple[QLineEdit, QLineEdit]] = []
        self.lines = QPlainTextEdit()
        self.lines.setPlaceholderText("Wpisz każdy napis w osobnej linii")
        self.font = QComboBox()
        self.font.setEditable(True)
        self.font.addItems(sorted(QFontDatabase.families()))
        if self.font.findText("Arial") >= 0:
            self.font.setCurrentText("Arial")
        elif self.font.count():
            self.font.setCurrentText(self.font.itemText(0) if self.font.count() else "")
        else:
            self.font.addItem("Arial")
            self.font.setCurrentText("Arial")
        self.reference = QLineEdit("O")
        self.reference.setToolTip("Tekst używany wyłącznie do ustalenia wysokości referencyjnej.")
        self.target_height = QDoubleSpinBox()
        self.target_height.setRange(0.01, 100000)
        self.target_height.setValue(50)
        self.width_limit = QDoubleSpinBox()
        self.width_limit.setRange(0.01, 100000)
        self.width_limit.setValue(250)
        self.mode = QComboBox()
        self.mode.addItem("Płasko — tylko za długie napisy", "flat")
        self.mode.addItem("Procentowo — wszystkie napisy", "percentage")
        self.category = QLineEdit("Nadruk/Napisy")
        self.save_prints = QCheckBox("Zapisz wygenerowane napisy w bazie nadruków")
        self.results_scroll = QScrollArea()
        self.results_scroll.setWidgetResizable(True)
        self.results_scroll.setFrameShape(QFrame.Shape.NoFrame)
        self.results_container = QWidget()
        self.results_layout = QVBoxLayout(self.results_container)
        self.results_layout.setContentsMargins(4, 4, 4, 4)
        self.results_layout.setSpacing(8)
        self.results_scroll.setWidget(self.results_container)
        test = QPushButton("Testuj — policz wszystkie napisy w CorelDRAW")
        test.clicked.connect(self.test_measurements)
        buttons = QDialogButtonBox(QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel)
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)
        form = QFormLayout()
        form.addRow("Napisy:", self.lines)
        form.addRow("Czcionka:", self.font)
        form.addRow("Napis referencyjny:", self.reference)
        form.addRow("Główna wysokość (mm):", self.target_height)
        form.addRow("Limit szerokości (mm):", self.width_limit)
        form.addRow("Zwężanie:", self.mode)
        form.addRow("Kategoria:", self.category)
        form.addRow("", self.save_prints)
        layout = QVBoxLayout(self)
        layout.addLayout(form)
        layout.addWidget(test)
        layout.addWidget(QLabel("Wyniki po skalowaniu:"))
        layout.addWidget(self.results_scroll)
        layout.addWidget(buttons)
        self.resize(700, 650)

    def test_measurements(self) -> None:
        lines = [line.strip() for line in self.lines.toPlainText().splitlines() if line.strip()]
        try:
            self.raw_measurements, self.reference_measurement = measure_texts(
                lines, self.font.currentText(), self.reference.text()
            )
            self.measurements = self._scaled_measurements()
            self._refresh_results(self.measurements)
        except CorelDrawReaderError as exc:
            QMessageBox.critical(self, "CorelDRAW", str(exc))

    def _scaled_measurements(self) -> list[MeasuredText]:
        return scale_measured_texts(
            self.raw_measurements,
            self.reference_measurement,
            self.target_height.value(),
            self.width_limit.value(),
            self.mode.currentData(),
        )

    def _refresh_results(self, values: list[MeasuredText]) -> None:
        while self.results_layout.count():
            item = self.results_layout.takeAt(0)
            if item.widget() is not None:
                item.widget().deleteLater()
        self.result_rows = []
        normalized_widths = [
            raw.width_mm
            * self.target_height.value()
            / self.reference_measurement.height_mm
            for raw in self.raw_measurements
        ]
        for index, (value, normalized_width) in enumerate(
            zip(values, normalized_widths), start=1
        ):
            card = QFrame()
            card.setFrameShape(QFrame.Shape.StyledPanel)
            card.setStyleSheet(
                "QFrame { padding: 6px; border: 1px solid #555; border-radius: 4px; }"
            )
            card_layout = QVBoxLayout(card)
            card_layout.setSpacing(4)
            width_text = f"{value.width_mm:.2f} mm"
            if normalized_width - value.width_mm > 0.01:
                width_text = (
                    f"<s>{normalized_width:.2f} mm</s> "
                    f"<b>→ {value.width_mm:.2f} mm</b>"
                )
            summary = QLabel(
                f"<b>{index}. {escape(value.text)}</b><br>"
                f"Szerokość: {width_text} &nbsp;|&nbsp; "
                f"Wysokość: <b>{value.height_mm:.2f} mm</b>"
            )
            summary.setTextFormat(Qt.TextFormat.RichText)
            summary.setWordWrap(True)
            card_layout.addWidget(summary)

            fields = QHBoxLayout()
            name = QLineEdit(value.text)
            name.setPlaceholderText("Nazwa zapisu")
            source = QLineEdit()
            source.setPlaceholderText("Ścieżka pliku CDR")
            fields.addWidget(name, 1)
            fields.addWidget(source, 2)
            card_layout.addLayout(fields)
            self.results_layout.addWidget(card)
            self.result_rows.append((name, source))
        self.results_layout.addStretch()

    def accept(self) -> None:
        if not self.raw_measurements or not hasattr(self, "reference_measurement"):
            QMessageBox.warning(self, "Generator", "Najpierw kliknij przycisk testowego pomiaru.")
            return
            
        try:
            self.measurements = self._scaled_measurements()
            
            if self.save_prints.isChecked():
                missing = []
                for row, (name, path) in enumerate(self.result_rows):
                    if not name or not name.text().strip():
                        missing.append(str(row + 1))
                if missing:
                    QMessageBox.warning(self, "Generator", "Podaj nazwy dla wierszy, które chcesz zapisać: " + ", ".join(missing))
                    return

            import time
            from pathlib import Path
            from integrations.coreldraw import connect
            
            corel = connect()
            doc_roboczy = corel.CreateDocument()
            doc_roboczy.Unit = 3
            
            project_root = Path(__file__).resolve().parents[1]
            target_folder = project_root / "Pliki_Zrodlowe"
            target_folder.mkdir(parents=True, exist_ok=True)
            
            for row, item in enumerate(self.measurements):
                name_widget, path_widget = self.result_rows[row]
                nazwa_usera = name_widget.text().strip() if name_widget else item.text.strip()[:30]
                
                if self.save_prints.isChecked():
                    bezpieczna_nazwa = "".join(c for c in nazwa_usera if c.isalnum() or c in " _-").strip()
                    nazwa_pliku = f"{bezpieczna_nazwa}.cdr"
                else:
                    bezpieczna_nazwa = "".join(c for c in nazwa_usera if c.isalnum() or c in " _-").strip()
                    nazwa_pliku = f"__{int(time.time())}_{row}_{bezpieczna_nazwa}.cdr"
                
                sciezka_zapisu = str(target_folder / nazwa_pliku)
                
                txt_obj = doc_roboczy.ActiveLayer.CreateArtisticText(0, 0, item.text)
                txt_obj.Text.Story.Font = self.font.currentText().strip()
                txt_obj.Text.Story.Size = 100.0 
                txt_obj.ConvertToCurves()
                
                txt_obj.SizeWidth = item.width_mm
                txt_obj.SizeHeight = item.height_mm
                
                txt_obj.CreateSelection()
                corel.ActiveSelection.Copy()
                
                doc_temp = corel.CreateDocument()
                doc_temp.ActiveLayer.Paste()
                opcje_zapisu = corel.CreateStructSaveAsOptions()
                doc_temp.SaveAs(sciezka_zapisu, opcje_zapisu)
                doc_temp.Close()
                
                txt_obj.Delete()
                
                if name_widget:
                    name_widget.setText(nazwa_usera)
                if path_widget:
                    path_widget.setText(sciezka_zapisu)
                    
            doc_roboczy.Close()
            super().accept()
            
        except Exception as exc:
            QMessageBox.warning(self, "Błąd Generowania", f"Problem z CorelDRAW: {exc}")

    def values(self) -> list[dict]:
        values = []
        for row, item in enumerate(self.measurements):
            name_widget, path_widget = self.result_rows[row]
            name = name_widget.text().strip() if name_widget else ""
            source = path_widget.text().strip() if path_widget else ""
            
            width, height = add_object_spacing(item.width_mm, item.height_mm)
            
            typ_kategorii = self.category.text().strip()
            if not self.save_prints.isChecked():
                typ_kategorii = f"Tymczasowe_Napisy/{self.font.currentText().strip()}"
                
            values.append({
                "nazwa": name,
                "typ": typ_kategorii,
                "w": width,
                "h": height,
                "plik": source,
                "generator": {
                    "czcionka": self.font.currentText().strip(),
                    "tekst_referencyjny": self.reference.text().strip(),
                    "tryb_zwężania": self.mode.currentData(),
                    "wysokosc_referencyjna_mm": self.target_height.value(),
                },
                "zapisz_w_bazie": self.save_prints.isChecked()
            })
        return values