"""Command-line entry point for the Corel layout optimizer."""

import json
import multiprocessing
import os
import sys
from pathlib import Path

# Ładujemy TYLKO nowy silnik, wyrzuciliśmy stary moduł 'optimizer'
from new_optimizer import run_genetic_algorithm_auto

POPULATION_SIZE = 60
GENERATION_COUNT = 100
PROJECT_ROOT = Path(__file__).resolve().parent
RUNTIME_PATH = PROJECT_ROOT / "runtime"
PARAMETER_RESULTS_PATH = (
    PROJECT_ROOT / "parameter_search" / "artifacts"
    / "parameter_search_category_3s_results.json"
)
TOP_N = 2

def save_layout(packer, items, machine_width, roll_height, output_path, strategy_name):
    """Saving the layout result to a JSON file."""
    items_by_id = {item["id"]: item for item in items}
    elements = []
    
    if packer is not None:
        for _, x, y, width, height, raw_item_id in packer.rect_list():
            # Rozpakowanie krotki, jeśli algorytm ją zwrócił
            if isinstance(raw_item_id, tuple):
                item_id = raw_item_id[1]
            else:
                item_id = raw_item_id
                
            item = items_by_id[item_id]
            rotated = bool(width == item.get("h", width) and height == item.get("w", height) and width != height)
            
            elements.append({
                "id": item_id,
                "nazwa": item.get("nazwa", item_id),
                "typ": item.get("typ", "unknown"),
                "x": x,
                "y": y,
                "w": width,
                "h": height,
                "obrocony": rotated,
                "plik": item.get("plik", ""),
            })

    with open(output_path, "w", encoding="utf-8") as output_file:
        json.dump({
            "szerokosc_maszyny": machine_width,
            "wysokosc_rolki": roll_height,
            "nazwa_strategii": strategy_name,
            "elementy": elements,
        }, output_file, ensure_ascii=False, indent=4)


def optimize_order(order):
    RUNTIME_PATH.mkdir(parents=True, exist_ok=True)
    machine_width = order.get("szerokosc_maszyny", 443)
    
    items = order.get("elementy", [])
    if not items:
        return
        
    for i, item in enumerate(items):
        if "id" not in item:
            item["id"] = f"{item.get('nazwa', 'item')}_{i}"

    print(" -> Running new_optimizer evaluation...")
    height, packer = run_genetic_algorithm_auto(
        items,
        machine_width,
        str(PARAMETER_RESULTS_PATH),
        packer="skyline"
    )
    
    save_layout(
        packer,
        items,
        machine_width,
        height,
        RUNTIME_PATH / "Optimal_1.json",
        "Podstawowa (Skyline)"
    )
    
    metadata = {
        "top1": items,
        "nazwa1": "Podstawowa (Skyline)"
    }
    
    with open(RUNTIME_PATH / "meta_zlecenia.json", "w", encoding="utf-8") as metadata_file:
        json.dump(metadata, metadata_file, ensure_ascii=False)

def main():
    multiprocessing.freeze_support()
    if len(sys.argv) <= 1 or not sys.argv[1].endswith(".json"):
        return
    order_path = sys.argv[1]
    with open(order_path, "r", encoding="utf-8") as order_file:
        optimize_order(json.load(order_file))
    try:
        os.remove(order_path)
    except OSError:
        pass


if __name__ == "__main__":
    main()