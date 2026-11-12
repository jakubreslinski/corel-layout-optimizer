"""Reusable helpers for experimenting with print-layout algorithms in notebooks."""

from __future__ import annotations

import json
import random
import time
from pathlib import Path
from typing import Any, Callable, Iterable

from rectpack import SORT_NONE, newPacker

Algorithm = Callable[[list[dict[str, Any]], int], tuple[float, Any]]
MAX_MACHINE_WIDTH = 443


def project_root() -> Path:
    return Path(__file__).resolve().parents[1]


def load_json(path: str | Path) -> dict[str, Any]:
    with Path(path).open(encoding="utf-8") as stream:
        return json.load(stream)


def load_training_layout(path: str | Path) -> tuple[int, list[dict[str, Any]]]:
    """Load one accepted layout as a valid optimizer input collection."""
    data = load_json(path)
    items = []
    for index, element in enumerate(data.get("elementy", []), start=1):
        items.append(
            {
                "id": f"{element.get('id', 'item')} [training {index}]",
                "nazwa": element.get("id", f"item-{index}"),
                "typ": element.get("typ", "unknown"),
                "w": float(element.get("w", 0)),
                "h": float(element.get("h", 0)),
                "plik": element.get("plik", ""),
            }
        )
    return int(data.get("szerokosc_maszyny", 443)), items


def load_database(path: str | Path | None = None) -> list[dict[str, Any]]:
    return load_json(path or project_root() / "data" / "print_database.json")


def normalize_items(items: Iterable[dict[str, Any]]) -> list[dict[str, Any]]:
    """Copy items and guarantee unique IDs required by rectpack."""
    normalized = []
    for index, item in enumerate(items, start=1):
        copy = dict(item)
        copy["id"] = f"{copy.get('id') or copy.get('nazwa') or 'item'} [{index}]"
        copy["w"] = float(copy.get("w", 0))
        copy["h"] = float(copy.get("h", 0))
        if copy["w"] <= 0 or copy["h"] <= 0:
            raise ValueError(f"Item {copy['id']!r} must have positive width and height.")
        normalized.append(copy)
    return normalized


def pack_sequence(
    items: list[dict[str, Any]],
    machine_width: int,
    order: Iterable[int],
    rotations: dict[int, bool] | None = None,
    pack_algo: Any | None = None,
) -> tuple[float, Any]:
    rotations = rotations or {}
    packer_options: dict[str, Any] = {"sort_algo": SORT_NONE, "rotation": False}
    if pack_algo is not None:
        packer_options["pack_algo"] = pack_algo
    packer = newPacker(**packer_options)
    packer.add_bin(machine_width, 9_999_999)
    for index in order:
        item = items[index]
        rotated = rotations.get(index, False)
        width, height = (item["h"], item["w"]) if rotated else (item["w"], item["h"])
        packer.add_rect(width, height, item["id"])
    packer.pack()
    rectangles = packer.rect_list()
    height = max((y + h for _, x, y, w, h, item_id in rectangles), default=0)
    return height, packer


def _fit_rotation(item: dict[str, Any], machine_width: int) -> bool:
    if item["w"] <= machine_width:
        return False
    if item["h"] <= machine_width:
        return True
    return False


from experiments.notebooks.area_decreasing import area_decreasing
from experiments.notebooks.first_fit_decreasing import first_fit_decreasing
from experiments.notebooks.genetic_baseline import genetic_baseline
from experiments.notebooks.max_rects import max_rects
from experiments.notebooks.random_search import random_search


def _algorithm_map(
    genetic_population: int,
    genetic_generations: int,
    random_attempts: int,
) -> dict[str, Algorithm]:
    return {
        "Genetic baseline": lambda items, width: genetic_baseline(
            items, width, genetic_population, genetic_generations
        ),
        "First-fit decreasing": first_fit_decreasing,
        "Area decreasing": area_decreasing,
        "MaxRects": max_rects,
        "Random search": lambda items, width: random_search(
            items, width, random_attempts
        ),
    }


def benchmark(
    items: list[dict[str, Any]],
    machine_width: int,
    algorithms: dict[str, Algorithm] | None = None,
    genetic_population: int = 30,
    genetic_generations: int = 30,
    random_attempts: int = 100,
) -> list[dict[str, Any]]:
    items = normalize_items(items)
    algorithms = algorithms or _algorithm_map(
        genetic_population, genetic_generations, random_attempts
    )
    results = []
    for name, algorithm in algorithms.items():
        started = time.perf_counter()
        height, packer = algorithm(items, machine_width)
        elapsed = time.perf_counter() - started
        rectangles = packer.rect_list() if packer is not None else []
        used_area = sum(width * height for _, x, y, width, height, item_id in rectangles)
        placed = len(rectangles)
        results.append(
            {
                "algorithm": name,
                "height_mm": round(float(height), 2),
                "used_area_mm2": round(float(used_area), 2),
                "utilization_percent": round(
                    used_area / (machine_width * height) * 100, 2
                ) if height else 0.0,
                "placed": placed,
                "missing": len(items) - placed,
                "seconds": round(elapsed, 3),
                "packer": packer,
                "items": items,
            }
        )
    return sorted(results, key=lambda result: (result["missing"], result["height_mm"]))


def generate_random_orders(
    database: list[dict[str, Any]],
    count: int = 20,
    min_distinct_items: int = 3,
    max_distinct_items: int = 6,
    min_quantity: int = 7,
    max_quantity: int = 13,
    occasional_max_quantity: int = 20,
    high_quantity_probability: float = 0.12,
    widths: tuple[int, ...] = (443,),
    seed: int = 42,
) -> list[dict[str, Any]]:
    """Generate orders from several distinct items in one deepest category.

    Most selected prints receive quantities from ``min_quantity`` to
    ``max_quantity``. A small fraction receive a larger quantity up to
    ``occasional_max_quantity`` to model repeated production runs.
    """
    grouped_by_name: dict[str, dict[str, dict[str, Any]]] = {}
    for item in filter_simple_prints(database):
        category = deepest_category(item)
        name = str(item.get("nazwa", "")).casefold()
        grouped_by_name.setdefault(category, {}).setdefault(name, item)
    grouped = {
        category: list(items_by_name.values())
        for category, items_by_name in grouped_by_name.items()
    }
    groups = [
        (category, items)
        for category, items in grouped.items()
        if len(items) >= min_distinct_items
    ]
    if not groups:
        raise ValueError(
            "The database has no deepest category with enough ordinary prints."
        )
    if min_distinct_items < 1 or max_distinct_items < min_distinct_items:
        raise ValueError("Distinct-item limits are invalid.")
    if min_quantity < 1 or max_quantity < min_quantity:
        raise ValueError("Quantity limits are invalid.")
    if occasional_max_quantity < max_quantity:
        raise ValueError("The occasional maximum must not be below max_quantity.")
    if not 0 <= high_quantity_probability <= 1:
        raise ValueError("high_quantity_probability must be between 0 and 1.")

    rng = random.Random(seed)
    orders = []
    for order_index in range(count):
        category_name, category_items = rng.choice(groups)
        distinct_count = min(
            len(category_items),
            rng.randint(min_distinct_items, max_distinct_items),
        )
        selected = []
        for item in rng.sample(category_items, distinct_count):
            quantity_max = (
                occasional_max_quantity
                if rng.random() < high_quantity_probability
                else max_quantity
            )
            quantity = rng.randint(min_quantity, quantity_max)
            selected.extend(dict(item) for _ in range(quantity))
        orders.append(
            {
                "case_id": f"random-{order_index + 1:04d}",
                "szerokosc_maszyny": rng.choice(widths),
                "elementy": selected,
                "source_category": category_name,
                "distinct_item_count": distinct_count,
            }
        )
    return orders


def _is_simple_print(item: dict[str, Any]) -> bool:
    """Exclude combo and component records from random benchmark generation."""
    name = str(item.get("nazwa", "")).casefold()
    return (
        "combo" not in name
        and "czesc" not in name
        and "część" not in name
        and "sklad_combo" not in item
        and "czesc_z" not in item
    )


def deepest_category(item: dict[str, Any]) -> str:
    """Return the deepest non-empty slash-separated category from an item."""
    parts = [part.strip() for part in str(item.get("typ", "")).split("/") if part.strip()]
    return parts[-1] if parts else "uncategorized"


def filter_simple_prints(database: Iterable[dict[str, Any]]) -> list[dict[str, Any]]:
    """Return ordinary prints only, excluding combos and split components."""
    return [
        item for item in database
        if _is_simple_print(item)
        and float(item.get("w", 0)) > 0
        and float(item.get("h", 0)) > 0
    ]
