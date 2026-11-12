"""Fitness calculation for layout candidates."""

from math import sqrt

from rectpack import SORT_NONE, newPacker


def evaluate_layout(
    candidate,
    items,
    machine_width,
    main_weight=0.0,
    sub_weight=0.0,
    line_weight=0.0,
    return_packer=False,
):
    """Pack a candidate and return its fitness and physical height."""
    sequence, rotations = candidate
    packer = newPacker(sort_algo=SORT_NONE, rotation=False)
    packer.add_bin(machine_width, 9_999_999)

    for item_index in sequence:
        item = items[item_index]
        if rotations[item_index]:
            width, height = item["h"], item["w"]
        else:
            width, height = item["w"], item["h"]
        packer.add_rect(width, height, item["id"])
    packer.pack()

    rectangles = packer.rect_list()
    missing_penalty = max(0, len(sequence) - len(rectangles)) * 10_000
    category_penalty = 0.0
    line_penalty = 0.0
    max_height = 0
    item_by_id = {item["id"]: item for item in items}
    main_groups = {}
    sub_groups = {}
    line_edges = []

    calculate_categories = main_weight > 0 or sub_weight > 0
    for _, x, y, width, height, item_id in rectangles:
        top = y + height
        max_height = max(max_height, top)

        if line_weight > 0:
            line_edges.extend((y, top))

        if not calculate_categories:
            continue

        category_parts = _split_category(item_by_id[item_id]["typ"])
        main_category = category_parts[0]
        sub_category = (
            f"{category_parts[0]}/{category_parts[1]}"
            if len(category_parts) > 1
            else item_by_id[item_id]["typ"]
        )
        _add_to_group(main_groups, main_category, x, y, width, top)
        _add_to_group(sub_groups, sub_category, x, y, width, top)

    category_penalty += _group_penalty(main_groups, main_weight)
    category_penalty += _group_penalty(sub_groups, sub_weight)
    if line_edges and line_weight > 0:
        line_edges.sort()
        unique_lines = 1
        previous = line_edges[0]
        for line in line_edges[1:]:
            if line - previous > 6:
                unique_lines += 1
                previous = line
        line_penalty = unique_lines * line_weight

    fitness = max_height + category_penalty + line_penalty + missing_penalty
    if return_packer:
        return fitness, max_height, packer
    return fitness, max_height


def _split_category(category):
    separator = "/" if "/" in category else "_"
    return [part.strip() for part in category.split(separator)]


def _add_to_group(groups, name, x, y, width, top):
    group = groups.setdefault(
        name,
        {"min_x": float("inf"), "max_x": 0, "min_y": float("inf"), "max_y": 0, "area": 0},
    )
    group["min_x"] = min(group["min_x"], x)
    group["max_x"] = max(group["max_x"], x + width)
    group["min_y"] = min(group["min_y"], y)
    group["max_y"] = max(group["max_y"], top)
    group["area"] += width * (top - y)


def _group_penalty(groups, weight):
    if weight <= 0:
        return 0.0
    penalty = 0.0
    for group in groups.values():
        bounding_area = (group["max_x"] - group["min_x"]) * (group["max_y"] - group["min_y"])
        wasted_area = max(0, bounding_area - group["area"])
        penalty += sqrt(wasted_area) / 2 * weight
    return penalty
