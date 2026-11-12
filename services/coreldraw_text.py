"""CorelDRAW text measurement and scaling calculations."""

from __future__ import annotations

from dataclasses import dataclass

from integrations.coreldraw import connect
from services.coreldraw_reader import CorelDrawReaderError, _to_mm


@dataclass(frozen=True)
class MeasuredText:
    text: str
    width_mm: float
    height_mm: float


def _set_text_style(shape: object, font_name: str, font_size_mm: float) -> None:
    # CorelDRAW exposes formatting on the text story/range, not reliably on
    # the dynamic Text dispatch object returned by pywin32.
    story = shape.Text.Story
    story.Font = font_name
    story.Size = font_size_mm


def measure_texts(
    lines: list[str], font_name: str, reference_text: str = "O"
) -> tuple[list[MeasuredText], MeasuredText]:
    """Measure lines with CorelDRAW's text engine and remove temporary shapes."""
    clean_lines = [line.strip() for line in lines if line.strip()]
    if not clean_lines:
        raise CorelDrawReaderError("Wpisz co najmniej jeden napis.")
    if not font_name.strip():
        raise CorelDrawReaderError("Podaj czcionkę.")
    if not reference_text.strip():
        raise CorelDrawReaderError("Podaj tekst referencyjny, np. O.")
    try:
        corel = connect()
        document = corel.ActiveDocument
        layer = document.ActivePage.ActiveLayer
        temporary = []
        # A nominal size is sufficient because only each shape's measured bounds
        # are used; the final requested height is applied after measurement.
        for line in [reference_text.strip(), *clean_lines]:
            shape = layer.CreateArtisticText(0, 0, line)
            _set_text_style(shape, font_name.strip(), 100.0)
            temporary.append(shape)
        unit = document.Unit
        reference_shape, *line_shapes = temporary
        reference = MeasuredText(
            reference_text.strip(),
            round(_to_mm(float(reference_shape.SizeWidth), unit), 2),
            round(_to_mm(float(reference_shape.SizeHeight), unit), 2),
        )
        measured = [
            MeasuredText(
                line,
                round(_to_mm(float(shape.SizeWidth), unit), 2),
                round(_to_mm(float(shape.SizeHeight), unit), 2),
            )
            for line, shape in zip(clean_lines, line_shapes)
        ]
        return measured, reference
    except CorelDrawReaderError:
        raise
    except Exception as exc:
        raise CorelDrawReaderError(f"Nie udało się zmierzyć napisów w CorelDRAW: {exc}") from exc
    finally:
        for shape in locals().get("temporary", []):
            try:
                shape.Delete()
            except Exception:
                pass


def scale_measured_texts(
    measured: list[MeasuredText],
    reference: MeasuredText,
    target_height_mm: float,
    width_limit_mm: float,
    width_mode: str,
) -> list[MeasuredText]:
    """Normalize height from a reference line, then apply flat/percentage narrowing."""
    if target_height_mm <= 0:
        raise ValueError("Wysokość musi być większa od zera.")
    if width_limit_mm <= 0:
        raise ValueError("Maksymalna szerokość musi być większa od zera.")
    height_factor = target_height_mm / reference.height_mm
    normalized = [
        MeasuredText(item.text, item.width_mm * height_factor, target_height_mm * item.height_mm / reference.height_mm)
        for item in measured
    ]
    widest = max(item.width_mm for item in normalized)
    if width_mode == "percentage":
        factor = min(1.0, width_limit_mm / widest)
        return [MeasuredText(item.text, item.width_mm * factor, item.height_mm) for item in normalized]
    if width_mode != "flat":
        raise ValueError(f"Nieznany tryb zwężania: {width_mode}")
    return [
        MeasuredText(item.text, min(item.width_mm, width_limit_mm), item.height_mm)
        for item in normalized
    ]
