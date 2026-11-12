"""Genetic layout baseline."""

from typing import Any

from optimizer import run_genetic_algorithm


def genetic_baseline(
    items: list[dict[str, Any]],
    machine_width: int,
    population_size: int = 30,
    generations: int = 30,
) -> tuple[float, Any]:
    """Run the project's existing genetic algorithm."""
    return run_genetic_algorithm(
        items,
        machine_width,
        population_size=population_size,
        generations=generations,
    )
