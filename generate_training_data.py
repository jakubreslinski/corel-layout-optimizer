"""Run the genetic algorithm sequentially and save layouts as training data."""

import argparse
import json
import random
import time
from pathlib import Path
from typing import Any

from optimizer import generate_strategies, run_genetic_algorithm, save_layout


DEFAULT_WIDTH = 433
DEFAULT_OUTPUT_DIR = Path(__file__).resolve().parent / "data" / "training"


def load_orders(path: Path) -> list[dict[str, Any]]:
    with path.open(encoding="utf-8") as orders_file:
        orders = json.load(orders_file)
    if not isinstance(orders, list):
        raise ValueError(f"{path} must contain a JSON array of orders.")
    return orders


def optimize_orders(
    orders: list[dict[str, Any]],
    output_dir: Path = DEFAULT_OUTPUT_DIR,
    population_size: int = 60,
    generations: int = 100,
    seed: int | None = None,
) -> list[Path]:
    """Optimize each order one at a time and save its best basic layout."""
    if population_size < 4:
        raise ValueError("population_size must be at least 4")
    if generations < 1:
        raise ValueError("generations must be at least 1")
    output_dir.mkdir(parents=True, exist_ok=True)
    saved_paths = []

    for order_number, order in enumerate(orders, start=1):
        width = DEFAULT_WIDTH
        order_for_optimizer = dict(order)
        order_for_optimizer["szerokosc_maszyny"] = width
        strategies = generate_strategies(order_for_optimizer)
        items = strategies.get("Basic (loose)")
        if not items:
            raise ValueError(f"order {order_number} does not contain any optimizable items")

        if seed is not None:
            random.seed(seed + order_number - 1)
        print(f"Optimizing order {order_number}/{len(orders)}...")
        height, packer = run_genetic_algorithm(
            items,
            width,
            population_size=population_size,
            generations=generations,
        )
        output_path = output_dir / f"uklad_ai_{time.time_ns()}.json"
        save_layout(
            packer,
            items,
            width,
            height,
            output_path,
            "Basic (loose)",
        )
        saved_paths.append(output_path)
        print(f"Saved {output_path} (width={width}, height={height})")

    return saved_paths


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("orders", type=Path, help="JSON file containing an array of orders")
    parser.add_argument("--output-dir", type=Path, default=DEFAULT_OUTPUT_DIR)
    parser.add_argument("--population-size", type=int, default=60)
    parser.add_argument("--generations", type=int, default=100)
    parser.add_argument("--seed", type=int)
    args = parser.parse_args()

    optimize_orders(
        load_orders(args.orders),
        output_dir=args.output_dir,
        population_size=args.population_size,
        generations=args.generations,
        seed=args.seed,
    )


if __name__ == "__main__":
    main()
