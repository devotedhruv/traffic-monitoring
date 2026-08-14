"""Explicit canonical class aliases; questionable vehicle mappings are intentionally absent."""

from __future__ import annotations

from typing import Final


ALIASES: Final[dict[str, dict[str, str]]] = {
    "vehicle": {
        "person": "person", "pedestrian": "person",
        "bicycle": "bicycle",
        "car": "car",
        "motorbike": "motorcycle", "motorcycle": "motorcycle", "bike": "motorcycle",
        "bus": "bus", "truck": "truck",
    },
    "plate": {
        "plate": "license_plate", "number plate": "license_plate",
        "number_plate": "license_plate", "license plate": "license_plate",
        "license-plate": "license_plate", "license_plate": "license_plate",
        "licence": "license_plate", "licence plate": "license_plate",
        "licence_plate": "license_plate",
    },
    "helmet": {
        "helmet": "helmet", "with helmet": "helmet", "with_helmet": "helmet",
        "no helmet": "no_helmet", "no-helmet": "no_helmet", "no_helmet": "no_helmet",
        "without helmet": "no_helmet", "without_helmet": "no_helmet",
    },
}


def normalized_name(value: str) -> str:
    return " ".join(value.strip().lower().replace("-", " ").split())


def default_mapping(model_type: str, names: list[str]) -> dict[str, str | None]:
    if model_type not in ALIASES:
        raise ValueError(f"Unsupported mapping type: {model_type}")
    aliases = ALIASES[model_type]
    output: dict[str, str | None] = {}
    for name in names:
        normalized = normalized_name(name)
        output[name] = aliases.get(normalized) or aliases.get(normalized.replace(" ", "_"))
    return output

