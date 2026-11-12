"""Utilities and stack-building algorithm for the new optimizer."""

from .big_objects_filter import split_big_objects
from .benchmark import (
    compare_genetic_packers,
    compare_genetic_packers_batch,
    run_genetic_algorithm,
    run_genetic_algorithm_auto,
)
from .skyline_packer import SkylinePacker, pack_rectangles
from .create_item_stacks import (
    create_item_stacks,
    create_item_stacks_with_mixing,
    create_item_stacks_without_mixing,
)
from .fitness import gene_dimensions
from .genetic_algorithm import (
    DEFAULT_STACK_OPTIONS,
    Gene,
    StackOption,
    genetic_algorithm,
)
from .stackless_skyline_packer import StacklessSkylinePacker, pack_genes
from .utilities import (
    Item,
    ItemStack,
    UnpackedItems,
    compact_rectangles,
    unpack_gene as expand_gene,
    sort_items,
    unpack_gene,
    unpack_genes,
)

__all__ = [
    "Item",
    "ItemStack",
    "UnpackedItems",
    "compact_rectangles",
    "expand_gene",
    "create_item_stacks",
    "create_item_stacks_with_mixing",
    "create_item_stacks_without_mixing",
    "Gene",
    "StackOption",
    "DEFAULT_STACK_OPTIONS",
    "gene_dimensions",
    "genetic_algorithm",
    "run_genetic_algorithm",
    "run_genetic_algorithm_auto",
    "compare_genetic_packers",
    "compare_genetic_packers_batch",
    "SkylinePacker",
    "pack_rectangles",
    "StacklessSkylinePacker",
    "pack_genes",
    "split_big_objects",
    "sort_items",
    "unpack_gene",
    "unpack_genes",
]
