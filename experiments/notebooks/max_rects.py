"""MaxRects layout algorithm."""

from typing import Any

from rectpack import MaxRectsBssf

from experiments.notebooks.layout_lab_utils import (
    MAX_MACHINE_WIDTH,
    _fit_rotation,
    pack_sequence,
)


def max_rects(
    items: list[dict[str, Any]],
    machine_width: int = MAX_MACHINE_WIDTH,
) -> tuple[float, Any]:
    """Pack rectangles with MaxRects Best Short Side Fit."""
    if machine_width > MAX_MACHINE_WIDTH:
        raise ValueError(
            f"MaxRects supports a maximum machine width of "
            f"{MAX_MACHINE_WIDTH} mm."
        )
    order = sorted(
        range(len(items)),
        key=lambda index: items[index]["w"] * items[index]["h"],
        reverse=True,
    )
    rotations = {
        index: _fit_rotation(items[index], machine_width)
        for index in order
    }
    return pack_sequence(
        items,
        machine_width,
        order,
        rotations,
        pack_algo=MaxRectsBssf,
    )
