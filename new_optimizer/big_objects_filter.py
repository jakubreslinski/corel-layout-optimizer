"""Split items into width-filling and remaining groups."""

from __future__ import annotations

from typing import Iterable

from .utilities import Item


def split_big_objects(
    items: Iterable[Item],
    max_width: float = 443.0,
    min_width_ratio: float = 0.9,
) -> tuple[list[Item], list[Item]]:
    """Split items by whether one dimension fills the target width.

    An item is considered big when its larger dimension is at least
    ``max_width * min_width_ratio``. Big items are oriented so their larger
    dimension is their width. Both returned lists preserve input order.
    """
    if max_width <= 0:
        raise ValueError("max_width must be positive.")
    if not 0 < min_width_ratio <= 1:
        raise ValueError("min_width_ratio must be greater than 0 and at most 1.")

    big_objects: list[Item] = []
    remaining_objects: list[Item] = []
    minimum_width = max_width * min_width_ratio

    for item in items:
        if max(item.width, item.height) < minimum_width:
            remaining_objects.append(item)
            continue

        big_objects.append(
            item._replace(flip=item.height > item.width)
        )

    return big_objects, remaining_objects