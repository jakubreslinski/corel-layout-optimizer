"""Persistence of optimized layouts."""

import json


def save_layout(packer, items, machine_width, roll_height, output_path, strategy_name):
    """Serialize a rectpack result using the application's existing JSON schema."""
    items_by_id = {item["id"]: item for item in items}
    elements = []
    if packer is not None:

        for _, x, y, width, height, raw_item_id in packer.rect_list():

            if isinstance(raw_item_id, tuple):
                item_id = raw_item_id[1]
            else:
                item_id = raw_item_id
                
            item = items_by_id[item_id]
            rotated = width == item["h"] and height == item["w"] and width != height
            elements.append(
                {
                    "id": item_id,
                    "nazwa": item.get("nazwa", item_id),
                    "typ": item["typ"],
                    "x": x,
                    "y": y,
                    "w": width,
                    "h": height,
                    "obrocony": rotated,
                    "plik": item.get("plik", ""),
                }
            )

    with open(output_path, "w", encoding="utf-8") as output_file:
        json.dump(
            {
                "szerokosc_maszyny": machine_width,
                "wysokosc_rolki": roll_height,
                "nazwa_strategii": strategy_name,
                "elementy": elements,
            },
            output_file,
            ensure_ascii=False,
            indent=4,
        )
