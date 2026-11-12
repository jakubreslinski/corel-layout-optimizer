"""Create optimized ItemStack groups from layout items."""

from __future__ import annotations

from typing import Iterable

from .utilities import Item, ItemStack

_MAX_SUBSET_SEARCH_NODES = 100_000


def create_item_stacks(
    items: Iterable[Item],
    max_width: float = 443,
    min_width_ratio: float = 0.85,
    mix_categories: int = 0,
    epsilon: float = 0.1,
    prefer_higher: bool = False,
    dfs_acceptance_ratio: float = 0.95,
) -> list[Item | ItemStack]:
    """Create stacks, optionally mixing compatible consecutive products."""
    if max_width <= 0:
        raise ValueError("max_width must be positive.")
    if not 0 < min_width_ratio <= 1:
        raise ValueError("min_width_ratio must be greater than 0 and at most 1.")
    if mix_categories < 0:
        raise ValueError("mix_categories must not be negative.")
    if not 0 <= epsilon <= 1:
        raise ValueError("epsilon must be between 0 and 1.")
    if not 0 < dfs_acceptance_ratio <= 1:
        raise ValueError("dfs_acceptance_ratio must be greater than 0 and at most 1.")

    sorted_items = list(items)
    if mix_categories == 0:
        return create_item_stacks_without_mixing(
            sorted_items, max_width, min_width_ratio
        )
    return create_item_stacks_with_mixing(
        sorted_items,
        max_width,
        min_width_ratio,
        mix_categories,
        epsilon,
        prefer_higher,
        dfs_acceptance_ratio,
    )

def create_item_stacks_without_mixing(
    items: Iterable[Item],
    max_width: float,
    min_width_ratio: float,
) -> list[Item | ItemStack]:
    """Create stacks from consecutive items with the same ID."""
    result: list[Item | ItemStack] = []
    index = 0

    sorted_items = list(items)
    while index < len(sorted_items):
        group_end = index + 1
        while group_end < len(sorted_items) and sorted_items[group_end].id == sorted_items[index].id:
            group_end += 1

        group = sorted_items[index:group_end]
        candidate = _build_uniform_stack(group, max_width, min_width_ratio)
        result.extend(candidate if candidate is not None else group)

        
        index = group_end

    return result

def create_item_stacks_with_mixing(
    items: Iterable[Item],
    max_width: float,
    min_width_ratio: float,
    mix_categories: int,
    epsilon: float,
    prefer_higher: bool,
    dfs_acceptance_ratio: float,
) -> list[Item | ItemStack]:
    """Create stacks from consecutive category-compatible products."""
    result: list[Item | ItemStack] = []
    items = list(items)
    index = 0

    while index < len(items):
        group: list[Item] = []
        locked_height_range: tuple[float, float] | None = None
        while index < len(items):
            candidate = items[index]
            if group and not all(
                _categories_can_mix(item.typ, candidate.typ, mix_categories)
                for item in group
            ):
                break

            if locked_height_range is None:
                if group and candidate.id != group[0].id:
                    orientations = _establish_mixed_orientation(
                        group, candidate, epsilon, prefer_higher
                    )
                    if orientations is None:
                        break
                    group = [
                        item._replace(flip=flip)
                        for item, flip in zip(group, orientations[:-1])
                    ]
                    candidate = candidate._replace(flip=orientations[-1])
                    heights = [
                        item.width if item.flip else item.height
                        for item in [*group, candidate]
                    ]
                    locked_height_range = (min(heights), max(heights))
            else:
                candidate_flip = _match_locked_height(
                    candidate, locked_height_range, epsilon
                )
                if candidate_flip is None:
                    break
                candidate = candidate._replace(flip=candidate_flip)
                candidate_height = (
                    candidate.width if candidate.flip else candidate.height
                )
                locked_height_range = (
                    min(locked_height_range[0], candidate_height),
                    max(locked_height_range[1], candidate_height),
                )

            group.append(candidate)
            index += 1

        while group:
            stack, selected_indices = _build_mixed_stack(
                group,
                max_width,
                min_width_ratio,
                dfs_acceptance_ratio,
            )
            if stack is None:
                result.append(group.pop(0))
            else:
                result.append(stack)
                group = [
                    item
                    for index, item in enumerate(group)
                    if index not in selected_indices
                ]

    return result

def _build_uniform_stack(
    group: list[Item],
    max_width: float,
    min_width_ratio: float,
) -> list[Item | ItemStack] | None:
    candidates: list[tuple[float, bool, float]] = []
    for flip in (False, True):
        width = group[0].height if flip else group[0].width
        height = group[0].width if flip else group[0].height
        if width <= 0 or height <= 0:
            continue
        stack_size = min(len(group), int(max_width // width))
        stack_width = stack_size * width
        if stack_size >= 2 and stack_width / max_width >= min_width_ratio:
            candidates.append((stack_width, flip, height))
    if not candidates:
        return None

    stack_width, flip, height = max(candidates, key=lambda candidate: (candidate[0], not candidate[1]))
    stack_size = int(stack_width // (group[0].height if flip else group[0].width))
    stacks: list[Item | ItemStack] = [
        ItemStack(
            id=_stack_id(group[start:start + stack_size]),
            ids=tuple(item.id for item in group[start:start + stack_size]),
            width=stack_width,
            height=height,
            flips=(flip,) * stack_size,
        )
        for start in range(0, len(group) - stack_size + 1, stack_size)
    ]
    stacks.extend(group[len(stacks) * stack_size:])
    return stacks or None

def _find_best_subset(
    group: list[Item],
    max_width: float,
    min_width_ratio: float,
    dfs_acceptance_ratio: float,
) -> list[int] | None:
    """
    Finds the combination of item indices that maximizes stack width 
    within the [max_width * min_width_ratio, max_width] range.
    """
    min_width = max_width * min_width_ratio
    acceptance_width = max(min_width, max_width * dfs_acceptance_ratio)
    best_indices: list[int] = []
    best_width = 0.0
    accepted = False
    visited_nodes = 0

    # Pre-calculate widths based on current flips
    widths = [item.height if item.flip else item.width for item in group]
    remaining_widths = [0.0] * (len(widths) + 1)
    for index in range(len(widths) - 1, -1, -1):
        remaining_widths[index] = remaining_widths[index + 1] + widths[index]

    def dfs(index: int, current_indices: list[int], current_width: float):
        nonlocal best_indices, best_width, accepted, visited_nodes
        visited_nodes += 1
        if visited_nodes > _MAX_SUBSET_SEARCH_NODES:
            return
        
        # If valid, see if it's the tightest fit we've found so far
        if current_width > best_width and current_width <= max_width:
            if (len(current_indices) >= 2
                    and current_width >= min_width):

                best_width = current_width
                best_indices = list(current_indices)
                if current_width >= acceptance_width:
                    accepted = True
                    return

        if accepted:
            return

        # Stop exploring if we ran out of items or exceeded max_width
        if index >= len(group) or current_width >= max_width:
            return
        if current_width + remaining_widths[index] < min_width:
            return

        # Path 1: INCLUDE the current item (if it fits)
        if current_width + widths[index] <= max_width:
            current_indices.append(index)
            dfs(index + 1, current_indices, current_width + widths[index])
            current_indices.pop() # Backtrack
            if accepted:
                return

        # Path 2: SKIP the current item
        dfs(index + 1, current_indices, current_width)
        if accepted:
            return

    dfs(0, [], 0.0)
    return best_indices if best_indices else None

def _build_mixed_stack(
    group: list[Item],
    max_width: float,
    min_width_ratio: float,
    dfs_acceptance_ratio: float,
) -> tuple[ItemStack | None, list[int]]:
    selected_indices = _find_best_subset(
        group, max_width, min_width_ratio, dfs_acceptance_ratio
    )
    if selected_indices is None:
        return None, []

    selected = [group[index] for index in selected_indices]
    orientations = tuple(item.flip for item in selected)
    heights = tuple(
        item.width if flip else item.height
        for item, flip in zip(selected, orientations)
    )
    widths = tuple(
        item.height if flip else item.width
        for item, flip in zip(selected, orientations)
    )
    stack_width = sum(widths)
    stack_height = max(heights)
    return (
        ItemStack(
            id=_stack_id(selected),
            ids=tuple(item.id for item in selected),
            width=stack_width,
            height=stack_height,
            flips=orientations,
        ),
        selected_indices,
    )


def _stack_id(items: list[Item]) -> str:
    """Create a stable ID for a stack from its member IDs."""
    return "stack:" + "|".join(item.id for item in items)

def _establish_mixed_orientation(
    group: list[Item],
    candidate: Item,
    epsilon: float,
    prefer_higher: bool,
) -> tuple[bool, ...] | None:
    """Choose orientations when the first different ID enters the group."""
    products = [*group, candidate]
    best: tuple[float, float, tuple[bool, ...]] | None = None

    for group_flip in (False, True):
        for candidate_flip in (False, True):
            orientations = (group_flip,) * len(group) + (candidate_flip,)
            heights = tuple(
                item.width if flip else item.height
                for item, flip in zip(products, orientations)
            )
            target_height = max(heights) if prefer_higher else min(heights)
            spread = max(heights) - min(heights)
            relative_spread = spread / max(heights)
            if relative_spread > epsilon:
                continue
            score = (
                target_height if prefer_higher else -target_height,
                -relative_spread,
                orientations,
            )
            if best is None or score[:2] > best[:2]:
                best = score

    return None if best is None else best[2]

def _match_locked_height(
    candidate: Item,
    height_range: tuple[float, float],
    epsilon: float,
) -> bool | None:
    """Return the candidate orientation if it fits the locked height range."""
    candidate_options = (
        (False, candidate.height),
        (True, candidate.width),
    )
    best: tuple[float, bool] | None = None
    for flip, height in candidate_options:
        new_min = min(height_range[0], height)
        new_max = max(height_range[1], height)
        relative_spread = (new_max - new_min) / new_max
        if relative_spread <= epsilon:
            distance = min(abs(height - height_range[0]), abs(height - height_range[1]))
            if best is None or distance < best[0]:
                best = (distance, flip)
    return None if best is None else best[1]

def _categories_can_mix(
    first: str,
    second: str,
    mix_categories: int,
) -> bool:
    """Return whether two category paths are within the mixing depth."""
    if mix_categories == 0:
        return first == second

    first_parts = [part.strip() for part in first.split("/") if part.strip()]
    second_parts = [part.strip() for part in second.split("/") if part.strip()]
    shared_parts = 0
    for first_part, second_part in zip(first_parts, second_parts):
        if first_part != second_part:
            break
        shared_parts += 1

    return max(len(first_parts), len(second_parts)) - shared_parts <= mix_categories
