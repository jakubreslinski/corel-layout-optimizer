"""Skyline packing that keeps ItemStack members together after expansion."""

from __future__ import annotations

from typing import Hashable, Mapping

from .skyline_packer import SkylinePacker, SkylineRectangle
from .utilities import Item, ItemStack, unpack_gene


class StacklessSkylinePacker(SkylinePacker):
    """Pack every stack as adjacent rectangles on one common baseline."""

    def add_group(
        self,
        rectangles: list[tuple[float, float, Hashable]],
    ) -> None:
        if not rectangles:
            return
        if any(width <= 0 or height <= 0 for width, height, _ in rectangles):
            raise ValueError("Rectangle dimensions must be positive.")
        if any(width > self.width for width, _, _ in rectangles):
            return

        group_width = sum(width for width, _, _ in rectangles)
        group_height = max(height for _, height, _ in rectangles)
        if group_width > self.width:
            return

        best: tuple[float, float, int] | None = None
        for index, (start, _, _) in enumerate(self._skyline):
            if group_width > self._available_width(index, group_width):
                continue
            y = self._height_at(index, group_width)
            candidate = (y, start, index)
            if best is None or candidate < best:
                best = candidate
        if best is None:
            return

        y, x, _ = best
        self._raise_skyline(x, group_width, y + group_height)
        current_x = x
        for width, height, rid in rectangles:
            self._rectangles.append(SkylineRectangle(current_x, y, width, height, rid))
            current_x += width


def pack_genes(
    genes: tuple[Item | ItemStack, ...],
    items_by_id: Mapping[str, Item],
    max_width: float,
) -> StacklessSkylinePacker:
    """Pack genes while preserving each stack's intended horizontal layout."""
    packer = StacklessSkylinePacker(max_width)
    for gene_index, gene in enumerate(genes):
        members = unpack_gene(gene, items_by_id)
        rectangles = [
            (member.height if member.flip else member.width,
             member.width if member.flip else member.height,
             (gene_index, member.id))
            for member in members
        ]
        packer.add_group(rectangles)
    return packer
