"""Fitness calculation for the new genetic layout optimizer."""

from __future__ import annotations

from functools import lru_cache
from typing import TypeAlias

from rectpack import SORT_NONE, newPacker

from .skyline_packer import pack_rectangles
from .stackless_skyline_packer import pack_genes
from .utilities import Item, ItemStack

Gene: TypeAlias = Item | ItemStack


def gene_dimensions(gene: Gene) -> tuple[float, float]:
    """Return the current width and height of a gene."""
    if gene.flip:
        return gene.height, gene.width
    return gene.width, gene.height


@lru_cache(maxsize=100_000)
def _layout_score(genes: tuple[Gene, ...], max_width: float) -> float:
    """Score genes by packed height, penalizing rectangles that do not fit."""
    if max_width <= 0:
        raise ValueError("max_width must be positive.")

    packer = newPacker(sort_algo=SORT_NONE, rotation=False)
    packer.add_bin(max_width, 9_999_999)

    for index, gene in enumerate(genes):
        width, height = gene_dimensions(gene)
        if width <= 0 or height <= 0:
            raise ValueError("Genes must have positive dimensions.")
        packer.add_rect(width, height, index)

    packer.pack()

    rectangles = packer.rect_list()
    max_height = max(
        (y + height for _, _, y, _, height, _ in rectangles),
        default=0.0,
    )
    missing_penalty = (len(genes) - len(rectangles)) * 10_000
    return max_height + missing_penalty


@lru_cache(maxsize=100_000)
def _skyline_layout_score(genes: tuple[Gene, ...], max_width: float) -> float:
    """Score genes with the fast Skyline packer."""
    rectangles = [
        (*gene_dimensions(gene), index)
        for index, gene in enumerate(genes)
    ]
    packer = pack_rectangles(rectangles, max_width)
    packed = packer.rect_list()
    max_height = max((y + height for _, _, y, _, height, _ in packed), default=0.0)
    return max_height + (len(genes) - len(packed)) * 10_000


@lru_cache(maxsize=100_000)
def _stackless_skyline_layout_score(
    genes: tuple[Gene, ...],
    max_width: float,
    source_items: tuple[Item, ...],
) -> float:
    """Score expanded genes while keeping each stack horizontally grouped."""
    items_by_id = {item.id: item for item in source_items}
    packer = pack_genes(genes, items_by_id, max_width)
    packed = packer.rect_list()
    expected = sum(len(gene.ids) if isinstance(gene, ItemStack) else 1 for gene in genes)
    max_height = max((y + height for _, _, y, _, height, _ in packed), default=0.0)
    return max_height + (expected - len(packed)) * 10_000
