from __future__ import annotations

import random
from PySide6.QtCore import QRectF, Qt
from PySide6.QtGui import QColor, QPen, QBrush, QFont
from PySide6.QtWidgets import QGraphicsScene, QGraphicsView


class LayoutView(QGraphicsView):
    """A scalable preview of the layout JSON contract."""

    def show_layout(self, data: dict) -> None:
        scene = QGraphicsScene(self)
        width = float(data.get("szerokosc_maszyny", 1))
        height = float(data.get("wysokosc_rolki", 1))
        scale = min(1.0, 700.0 / max(width, 1))
        scene.setSceneRect(0, 0, width * scale + 20, height * scale + 20)
        scene.addRect(10, 10, width * scale, height * scale,
                      QPen(QColor("#333333")), QBrush(QColor("#f5f5f5")))
        colors: dict[str, QColor] = {}
        for item in data.get("elementy", []):
            key = item.get("typ", "unknown").split("/")[0].split("_")[0]
            colors.setdefault(key, QColor.fromHsv(random.randint(0, 359), 100, 220))
            rect = QRectF(10 + float(item.get("x", 0)) * scale,
                          10 + float(item.get("y", 0)) * scale,
                          float(item.get("w", 0)) * scale,
                          float(item.get("h", 0)) * scale)
            scene.addRect(rect, QPen(QColor("#555555")), QBrush(colors[key]))
            label = str(item.get("nazwa") or item.get("id") or "unnamed")
            text = scene.addSimpleText(label, QFont("Arial", 8))
            text.setBrush(QBrush(QColor("#111111")))
            text.setPos(rect.left() + 3, rect.top() + 3)
        self.setScene(scene)
        self.fitInView(scene.sceneRect(), Qt.AspectRatioMode.KeepAspectRatio)
