"""First-fit decreasing layout algorithm."""

from typing import Any

from experiments.notebooks.layout_lab_utils import _fit_rotation, pack_sequence


def first_fit_decreasing(
    items: list[dict[str, Any]],
    machine_width: int,
) -> tuple[float, Any]:
    """Pack items in descending maximum-side order."""
    order = sorted(
        range(len(items)),
        key=lambda index: max(items[index]["w"], items[index]["h"]),
        reverse=True,
    )
    rotations = {
        index: _fit_rotation(items[index], machine_width)
        for index in order
    }
    return pack_sequence(items, machine_width, order, rotations)
