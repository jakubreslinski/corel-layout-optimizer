"""Data types and input utilities for the stack-building algorithm."""

from __future__ import annotations

from typing import Any, Iterable, Mapping, NamedTuple


class Item(NamedTuple):
    """The minimum data needed to evolve one rectangle placement."""

    id: str
    width: float
    height: float
    flip: bool
    typ: str


class ItemStack(NamedTuple):
    """A horizontal group represented by member IDs and orientations."""

    id: str
    ids: tuple[str, ...]
    width: float
    height: float
    flips: tuple[bool, ...]
    flip: bool = False


class UnpackedItems(list[Item]):
    """List result carrying the optimized gene grouping for final repacking."""

    def __init__(
        self,
        items: Iterable[Item],
        source_genes: tuple[Item | ItemStack, ...],
    ) -> None:
        super().__init__(items)
        self.source_genes = source_genes


def unpack_gene(
    gene: Item | ItemStack,
    items_by_id: Mapping[str, Item] | None = None,
) -> list[Item]:
    """Expand one gene into its individual items."""
    if isinstance(gene, Item):
        return [gene]

    if items_by_id is None:
        raise ValueError("items_by_id is required to unpack an ItemStack.")
    if len(gene.ids) != len(gene.flips):
        raise ValueError("ItemStack ids and flips must have the same length.")

    unpacked = []
    for item_id, flip in zip(gene.ids, gene.flips):
        try:
            item = items_by_id[item_id]
        except KeyError as error:
            raise ValueError(f"No source Item found for ItemStack member {item_id!r}.") from error
        unpacked.append(item._replace(flip=flip ^ gene.flip))
    return unpacked


def unpack_genes(
    genes: Iterable[Item | ItemStack],
    items_by_id: Mapping[str, Item] | None = None,
) -> list[Item]:
    """Expand all genes into individual items in gene and stack order."""
    return [
        item
        for gene in genes
        for item in unpack_gene(gene, items_by_id)
    ]


def compact_rectangles(items: Iterable[dict[str, Any]]) -> list[Item]:
    """Convert layout items to compact genetic-algorithm chromosomes."""
    rectangles = []
    for index, item in enumerate(items, start=1):
        width = float(item.get("w", 0))
        height = float(item.get("h", 0))
        if width <= 0 or height <= 0:
            raise ValueError(
                f"Rectangle {index} must have positive width and height."
            )

        source_id = item.get("id") or item.get("nazwa") or "rectangle"
        rectangles.append(
            Item(
                id=f"{source_id} [{index}]",
                width=width,
                height=height,
                flip=False,
                typ=str(item.get("typ", "unknown")),
            )
        )
    return rectangles


def sort_items(items: Iterable[Item]) -> list[Item]:
    """Return items sorted by type and then ID."""
    return sorted(
        items,
        key=lambda item: (item.typ.casefold(), item.id.casefold()),
    )
