"""Conversion of orders into alternative optimization strategies."""

import json
from pathlib import Path


DATABASE_PATH = Path(__file__).resolve().parents[1] / "data" / "print_database.json"


def generate_strategies(order, database_path=DATABASE_PATH):
    """Build unique loose, combo, component, and mixed item strategies."""
    try:
        with open(database_path, "r", encoding="utf-8") as database_file:
            database = json.load(database_file)
    except FileNotFoundError:
        database = []

    items_by_name = {item["nazwa"]: item for item in database}
    requested = {}
    for element in order.get("elementy", []):
        name = element.get("nazwa", "unnamed")
        requested[name] = requested.get(name, 0) + 1
        items_by_name.setdefault(name, element)

    combos = sorted(
        (item for item in database if "sklad_combo" in item),
        key=lambda item: sum(item["sklad_combo"].values()),
        reverse=True,
    )
    components_by_parent = {}
    for item in database:
        if "czesc_z" in item:
            components_by_parent.setdefault(item["czesc_z"], []).append(item["nazwa"])

    def apply_combos(requirements):
        remaining = requirements.copy()
        result = {}
        for combo in combos:
            composition = combo["sklad_combo"]
            repetitions = min(
                (remaining.get(name, 0) // quantity for name, quantity in composition.items()),
                default=0,
            )
            if repetitions:
                result[combo["nazwa"]] = repetitions
                for name, quantity in composition.items():
                    remaining[name] -= quantity * repetitions
        for name, quantity in remaining.items():
            if quantity > 0:
                result[name] = result.get(name, 0) + quantity
        return result

    def apply_components(requirements):
        result = {}
        for name, quantity in requirements.items():
            for component in components_by_parent.get(name, [name]):
                result[component] = result.get(component, 0) + quantity
        return result

    candidates = [
        ("Basic (loose)", requested),
        ("Combo sets", apply_combos(requested)),
        ("Split into components", apply_components(requested)),
    ]
    component_strategy = apply_components(requested)
    candidates.append(("Components in combos", apply_combos(component_strategy)))

    unique = {}
    signatures = set()
    for name, strategy in candidates:
        signature = tuple(sorted(strategy.items()))
        if signature not in signatures:
            signatures.add(signature)
            unique[name] = strategy

    return {
        name: _to_optimizer_items(strategy, items_by_name)
        for name, strategy in unique.items()
    }


def _to_optimizer_items(strategy, items_by_name):
    result = []
    item_id = 1
    for name, quantity in strategy.items():
        reference = items_by_name.get(name, {})
        for _ in range(quantity):
            result.append(
                {
                    "id": f"{name} ({item_id})",
                    "nazwa": name,
                    "typ": reference.get("typ", "unknown"),
                    "w": reference.get("w", 100),
                    "h": reference.get("h", 100),
                    "plik": reference.get("plik", ""),
                }
            )
            item_id += 1
    return result
