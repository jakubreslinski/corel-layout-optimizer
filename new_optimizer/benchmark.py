"""Adapters for running the new optimizer in the benchmark notebook."""

from __future__ import annotations

import time
from typing import Any

from rectpack import SORT_NONE, newPacker

from .genetic_algorithm import StackOption, genetic_algorithm
from .skyline_packer import SkylinePacker
from .stackless_skyline_packer import pack_genes
from .utilities import Item


def run_genetic_algorithm(
    items: list[dict[str, Any]],
    machine_width: int,
    population_size: int = 40,
    generations: int = 80,
    mutation_rate: float = 0.15,
    seed: int | None = None,
    verbose: bool = True,
    packer: str = "skyline",
    stagnation_generations: int = 10,
    elite_count: int = 2,
    crossover_probability: float = 0.7,
    orientation_mutation_rate: float | None = None,
    swap_mutation_rate: float = 0.3,
    stack_options: tuple[StackOption, ...] | None = None,
) -> tuple[float, Any]:
    """Run the optimizer using the notebook benchmark interface.

    The input items must have the normalized unique IDs produced by
    ``notebooks.layout_lab_utils.normalize_items``.
    """
    if machine_width <= 0:
        raise ValueError("machine_width must be positive.")

    genes = [
        Item(
            id=str(item["id"]),
            width=float(item["w"]),
            height=float(item["h"]),
            flip=False,
            typ=str(item.get("typ", "unknown")),
        )
        for item in items
    ]
    if len({item.id for item in genes}) != len(genes):
        raise ValueError("Benchmark items must have unique IDs.")

    result = genetic_algorithm(
        genes,
        machine_width,
        population_size=population_size,
        generations=generations,
        mutation_rate=mutation_rate,
        seed=seed,
        verbose=verbose,
        packer=packer,
        stagnation_generations=stagnation_generations,
        elite_count=elite_count,
        crossover_probability=crossover_probability,
        orientation_mutation_rate=orientation_mutation_rate,
        swap_mutation_rate=swap_mutation_rate,
        stack_options=stack_options,
    )

    repack_started = time.perf_counter()
    source_genes = getattr(result, "source_genes", None)
    if packer == "skyline" and source_genes and any(
        hasattr(gene, "ids") for gene in source_genes
    ):
        result_packer = pack_genes(
            tuple(source_genes),
            {item.id: item for item in result},
            machine_width,
        )
        rectangles = result_packer.rect_list()
        height = max(
            (y + rectangle_height for _, _, y, _, rectangle_height, _ in rectangles),
            default=0.0,
        )
        if verbose:
            print(f"[new_optimizer] final repacking: {time.perf_counter() - repack_started:.3f}s")
        return height, result_packer

    if packer == "rectpack":
        result_packer = newPacker(sort_algo=SORT_NONE, rotation=False)
        result_packer.add_bin(machine_width, 9_999_999)
    elif packer == "skyline":
        result_packer = SkylinePacker(machine_width)
    else:
        raise ValueError("packer must be 'rectpack' or 'skyline'.")
    for item in result:
        width, height = (
            (item.height, item.width)
            if item.flip
            else (item.width, item.height)
        )
        result_packer.add_rect(width, height, item.id)
    if packer == "rectpack":
        result_packer.pack()

    rectangles = result_packer.rect_list()
    height = max(
        (y + rectangle_height for _, _, y, _, rectangle_height, _ in rectangles),
        default=0.0,
    )
    if verbose:
        print(f"[new_optimizer] final repacking: {time.perf_counter() - repack_started:.3f}s")
    return height, result_packer


def run_genetic_algorithm_auto(
    items: list[dict[str, Any]],
    machine_width: int,
    parameter_results_path: str,
    *,
    size_category: str | None = None,
    seed: int | None = None,
    verbose: bool = False,
    packer: str = "skyline",
    **overrides: Any,
) -> tuple[float, Any]:
    """Run the optimizer with the best Optuna profile for a size category."""
    from parameter_search.search import (
        infer_size_category,
        load_category_profiles,
        parameters_for_category,
    )

    profiles = load_category_profiles(parameter_results_path)
    if size_category is None:
        size_category = infer_size_category(items, machine_width, profiles)
    parameters = parameters_for_category(profiles, size_category)
    parameters.update(overrides)
    return run_genetic_algorithm(
        items,
        machine_width,
        seed=seed,
        verbose=verbose,
        packer=packer,
        **parameters,
    )


def compare_genetic_packers(
    items: list[dict[str, Any]],
    machine_width: int,
    population_size: int = 40,
    generations: int = 80,
    mutation_rate: float = 0.15,
    seed: int | None = 0,
    verbose: bool = False,
    **optimizer_options: Any,
) -> dict[str, dict[str, float | int]]:
    """Run both packers on identical input and compare total runtime/results."""
    measurements: dict[str, dict[str, float | int]] = {}
    for backend in ("rectpack", "skyline"):
        started = time.perf_counter()
        height, packer = run_genetic_algorithm(
            items,
            machine_width,
            population_size=population_size,
            generations=generations,
            mutation_rate=mutation_rate,
            seed=seed,
            verbose=verbose,
            packer=backend,
            **optimizer_options,
        )
        elapsed = time.perf_counter() - started
        measurements[backend] = {
            "height": float(height),
            "placed": len(packer.rect_list()),
            "missing": len(items) - len(packer.rect_list()),
            "seconds": elapsed,
        }

    rectpack_result = measurements["rectpack"]
    skyline_result = measurements["skyline"]
    print(
        "[new_optimizer] packer comparison: "
        f"rectpack={rectpack_result['seconds']:.3f}s/"
        f"{rectpack_result['height']:.2f}mm, "
        f"skyline={skyline_result['seconds']:.3f}s/"
        f"{skyline_result['height']:.2f}mm, "
        f"speedup={rectpack_result['seconds'] / skyline_result['seconds']:.2f}x, "
        f"height_delta={skyline_result['height'] - rectpack_result['height']:.2f}mm"
    )
    return measurements


def compare_genetic_packers_batch(
    cases: list[dict[str, Any]],
    population_size: int = 40,
    generations: int = 80,
    mutation_rate: float = 0.15,
    seed: int | None = 0,
    verbose: bool = False,
    **optimizer_options: Any,
) -> tuple[list[dict[str, Any]], dict[str, float]]:
    """Compare both packers for many cases and return rows plus aggregates."""
    rows = []
    for case in cases:
        comparison = compare_genetic_packers(
            case["items"],
            case["machine_width"],
            population_size=population_size,
            generations=generations,
            mutation_rate=mutation_rate,
            seed=seed,
            verbose=verbose,
            **optimizer_options,
        )
        rectpack_result = comparison["rectpack"]
        skyline_result = comparison["skyline"]
        rows.append(
            {
                "case_id": case.get("case_id", ""),
                "items": len(case["items"]),
                "rectpack_seconds": rectpack_result["seconds"],
                "skyline_seconds": skyline_result["seconds"],
                "speedup": rectpack_result["seconds"] / skyline_result["seconds"],
                "rectpack_height": rectpack_result["height"],
                "skyline_height": skyline_result["height"],
                "height_delta": skyline_result["height"] - rectpack_result["height"],
                "rectpack_missing": rectpack_result["missing"],
                "skyline_missing": skyline_result["missing"],
            }
        )

    if not rows:
        return [], {
            "cases": 0.0,
            "rectpack_seconds": 0.0,
            "skyline_seconds": 0.0,
            "average_speedup": 0.0,
            "average_height_delta": 0.0,
            "skyline_better_cases": 0.0,
            "skyline_equal_cases": 0.0,
            "skyline_worse_cases": 0.0,
        }

    summary = {
        "cases": float(len(rows)),
        "rectpack_seconds": sum(row["rectpack_seconds"] for row in rows),
        "skyline_seconds": sum(row["skyline_seconds"] for row in rows),
        "average_speedup": sum(row["speedup"] for row in rows) / len(rows),
        "average_height_delta": sum(row["height_delta"] for row in rows) / len(rows),
        "skyline_better_cases": float(sum(row["height_delta"] < 0 for row in rows)),
        "skyline_equal_cases": float(sum(row["height_delta"] == 0 for row in rows)),
        "skyline_worse_cases": float(sum(row["height_delta"] > 0 for row in rows)),
    }
    return rows, summary
