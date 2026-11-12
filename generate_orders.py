"""Generate reproducible random orders, one JSON file per order."""

import argparse
import json
import random
import sys
from pathlib import Path
from typing import Any


DEFAULT_WIDTH = 443

DEMO_DATABASE = [
    {"nazwa": "1", "typ": "k1", "w": 50, "h": 50, "plik": "fake_1.cdr"},
    {"nazwa": "2", "typ": "k2", "w": 100, "h": 50, "plik": "fake_2.cdr"},
    {"nazwa": "3", "typ": "k3", "w": 80, "h": 80, "plik": "fake_3.cdr"},
    {"nazwa": "4", "typ": "k4", "w": 210, "h": 297, "plik": "fake_4.cdr"},
    {"nazwa": "5", "typ": "k5", "w": 150, "h": 300, "plik": "fake_5.cdr"},
    {"nazwa": "6", "typ": "k6", "w": 200, "h": 200, "plik": "fake_6.cdr"},
    {"nazwa": "7", "typ": "k7", "w": 50, "h": 240, "plik": "fake_7.cdr"},
]


def ensure_database_exists(path: Path) -> None:
    """Create a demo database if the file does not exist."""
    if path.exists():
        return
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as f:
        json.dump(DEMO_DATABASE, f, ensure_ascii=False, indent=4)
    print(f"[INFO] Created demo database in: {path}", file=sys.stderr)


def load_database(path: Path) -> list[dict[str, Any]]:
    ensure_database_exists(path)
    with path.open(encoding="utf-8") as database_file:
        database = json.load(database_file)
    if not isinstance(database, list):
        raise ValueError(f"{path} must contain a JSON array.")
    return database


def eligible_items(database: list[dict[str, Any]], width: int) -> list[dict[str, Any]]:
    """Keep ordinary prints that fit across the roll in at least one rotation."""
    result = []
    skipped = 0
    for item in database:
        if not isinstance(item, dict):
            skipped += 1
            continue
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
            skipped += 1
            continue
        if item_width > 0 and item_height > 0 and min(item_width, item_height) <= width:
            result.append(item)
    if skipped:
        print(f"[WARN] Skipped {skipped} of {len(database)} records (bad data).", file=sys.stderr)
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

    # Sorting makes the result depend only on the seed, not on record order.
    items = sorted(eligible_items(database, width), key=lambda i: str(i.get("nazwa", "")))
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
                "case_id": f"order-{order_number:04d}",
                "szerokosc_maszyny": width,
                "elementy": selected,
            }
        )
    return orders


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--count", type=int, default=1, help="number of order files to create")
    parser.add_argument(
        "--database",
        type=Path,
        default=Path(__file__).resolve().parent / "data" / "print_database.json",
    )
    parser.add_argument(
        "--output-dir",
        type=Path,
        default=Path(__file__).resolve().parent / "experiments" / "orders",
        help="directory for the order_XXXX.json files",
    )
    parser.add_argument("--width", type=int, default=DEFAULT_WIDTH, help="machine width")
    parser.add_argument("--seed", type=int, default=42)
    parser.add_argument("--min-distinct", type=int, default=3)
    parser.add_argument("--max-distinct", type=int, default=6)
    parser.add_argument("--min-quantity", type=int, default=7)
    parser.add_argument("--max-quantity", type=int, default=13)
    args = parser.parse_args()

    try:
        orders = generate_orders(
            load_database(args.database),
            count=args.count,
            width=args.width,
            min_distinct_items=args.min_distinct,
            max_distinct_items=args.max_distinct,
            min_quantity=args.min_quantity,
            max_quantity=args.max_quantity,
            seed=args.seed,
        )
    except ValueError as error:
        parser.error(str(error))

    args.output_dir.mkdir(parents=True, exist_ok=True)
    for number, order in enumerate(orders, start=1):
        path = args.output_dir / f"order_{number:04d}.json"
        with path.open("w", encoding="utf-8") as output_file:
            json.dump(order, output_file, ensure_ascii=False, indent=4)
        print(f"Saved {path}")


if __name__ == "__main__":
    main()