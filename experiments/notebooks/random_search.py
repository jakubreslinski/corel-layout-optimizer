"""Random-search layout algorithm."""

import random
from typing import Any

from experiments.notebooks.layout_lab_utils import pack_sequence


def random_search(
    items: list[dict[str, Any]],
    machine_width: int,
    attempts: int = 100,
    seed: int = 42,
) -> tuple[float, Any]:
    """Try random item orders and rotations, returning the shortest layout."""
    if attempts < 1:
        raise ValueError("attempts must be at least 1")

    rng = random.Random(seed)
    best_height = float("inf")
    best_packer = None
    indices = list(range(len(items)))
    for _ in range(attempts):
        rng.shuffle(indices)
        rotations = {
            index: bool(rng.getrandbits(1))
            for index in indices
        }
        height, packer = pack_sequence(
            items,
            machine_width,
            indices,
            rotations,
        )
        if height < best_height:
            best_height, best_packer = height, packer
    return best_height, best_packer
