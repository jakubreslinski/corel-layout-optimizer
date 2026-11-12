"""Generate reproducible random orders for layout training."""

import argparse
import json
import random
from pathlib import Path
from typing import Any


DEFAULT_WIDTH = 443


def load_database(path: Path) -> list[dict[str, Any]]:
    with path.open(encoding="utf-8") as database_file:
        database = json.load(database_file)
    if not isinstance(database, list):
        raise ValueError(f"{path} must contain a JSON array.")
    return database


def eligible_items(database: list[dict[str, Any]], width: int) -> list[dict[str, Any]]:
    """Keep ordinary prints that fit across the roll in at least one rotation."""
    result = []
    for item in database:
        name = str(item.get("nazwa", "")).casefold()
        if (
            "combo" in name
            or "czesc" in name
            or "część" in name
            or "sklad_combo" in item
            or "czesc_z" in item
        ):
            continue
        try:
            item_width = float(item["w"])
            item_height = float(item["h"])
        except (KeyError, TypeError, ValueError):
            continue
        if item_width > 0 and item_height > 0 and min(item_width, item_height) <= width:
            result.append(item)
    return result


def generate_orders(
    database: list[dict[str, Any]],
    count: int,
    width: int = DEFAULT_WIDTH,
    min_distinct_items: int = 3,
    max_distinct_items: int = 6,
    min_quantity: int = 7,
    max_quantity: int = 13,
    seed: int = 42,
) -> list[dict[str, Any]]:
    """Generate ``count`` orders, each containing repeated database prints."""
    if count < 1:
        raise ValueError("count must be at least 1")
    if min_distinct_items < 1 or max_distinct_items < min_distinct_items:
        raise ValueError("distinct item limits are invalid")
    if min_quantity < 1 or max_quantity < min_quantity:
        raise ValueError("quantity limits are invalid")

    items = eligible_items(database, width)
    if len(items) < min_distinct_items:
        raise ValueError(
            f"the database has only {len(items)} eligible items; "
            f"{min_distinct_items} are required"
        )

    rng = random.Random(seed)
    orders = []
    for order_number in range(1, count + 1):
        distinct_count = rng.randint(
            min_distinct_items,
            min(max_distinct_items, len(items)),
        )
        selected = []
        for item in rng.sample(items, distinct_count):
            selected.extend(dict(item) for _ in range(rng.randint(min_quantity, max_quantity)))
        orders.append(
            {
                "case_id": f"training-{order_number:04d}",
                "szerokosc_maszyny": width,
                "elementy": selected,
            }
        )
    return orders


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--count", type=int, required=True, help="number of orders to generate")
    parser.add_argument(
        "--database",
        type=Path,
        default=Path(__file__).resolve().parent / "data" / "print_database.json",
    )
    parser.add_argument(
        "--output",
        type=Path,
        default=Path(__file__).resolve().parent / "experiments" / "training_orders.json",
    )
    parser.add_argument("--seed", type=int, default=42)
    parser.add_argument("--min-distinct", type=int, default=3)
    parser.add_argument("--max-distinct", type=int, default=6)
    parser.add_argument("--min-quantity", type=int, default=7)
    parser.add_argument("--max-quantity", type=int, default=13)
    args = parser.parse_args()

    orders = generate_orders(
        load_database(args.database),
        count=args.count,
        min_distinct_items=args.min_distinct,
        max_distinct_items=args.max_distinct,
        min_quantity=args.min_quantity,
        max_quantity=args.max_quantity,
        seed=args.seed,
    )
    args.output.parent.mkdir(parents=True, exist_ok=True)
    with args.output.open("w", encoding="utf-8") as output_file:
        json.dump(orders, output_file, ensure_ascii=False, indent=4)
    print(f"Generated {len(orders)} orders in {args.output}")


if __name__ == "__main__":
    main()
