"""Rewrite YOLO class IDs to canonical SadakDrishti IDs in a new dataset copy."""

from __future__ import annotations

import argparse
import json
import shutil
from collections import Counter
from pathlib import Path
from typing import Any

import yaml

try:
    from ml.scripts.class_mapping import default_mapping
    from ml.scripts.common import EXPECTED_CLASSES, IMAGE_EXTENSIONS, load_yaml, write_json
except ModuleNotFoundError:
    from class_mapping import default_mapping
    from common import EXPECTED_CLASSES, IMAGE_EXTENSIONS, load_yaml, write_json


def discover_names(dataset: Path, data_yaml: Path | None = None) -> list[str]:
    candidates = [data_yaml] if data_yaml else sorted([*dataset.rglob("*.yaml"), *dataset.rglob("*.yml")])
    for candidate in candidates:
        if candidate is None or not candidate.is_file():
            continue
        names = load_yaml(candidate).get("names")
        if isinstance(names, list):
            return [str(item) for item in names]
        if isinstance(names, dict):
            return [str(names[key]) for key in sorted(names, key=lambda item: int(item))]
    raise ValueError("Could not discover source class names; provide --data-yaml")


def load_mapping(path: Path | None, model_type: str, names: list[str]) -> dict[str, str | None]:
    if path is None:
        return default_mapping(model_type, names)
    payload = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise ValueError("Mapping JSON must be an object of source class name to canonical name or null")
    return {str(key): None if value is None else str(value) for key, value in payload.items()}


def remap(dataset: Path, output: Path, model_type: str, mapping_path: Path | None = None, data_yaml: Path | None = None) -> dict[str, Any]:
    dataset, output = dataset.resolve(), output.resolve()
    if dataset == output or dataset in output.parents:
        raise ValueError("Output must not modify or live inside the immutable source dataset")
    if output.exists() and any(output.iterdir()):
        raise FileExistsError(f"Output is not empty: {output}")
    names = discover_names(dataset, data_yaml)
    mapping = load_mapping(mapping_path, model_type, names)
    canonical = EXPECTED_CLASSES[model_type]
    target_ids = {name: class_id for class_id, name in canonical.items()}
    unknown_targets = sorted({value for value in mapping.values() if value is not None and value not in target_ids})
    if unknown_targets:
        raise ValueError(f"Mapping contains unsupported canonical classes: {unknown_targets}")
    for name in names:
        if name not in mapping:
            mapping[name] = None
    source_counts: Counter[str] = Counter()
    target_counts: Counter[str] = Counter()
    ignored = invalid = 0
    images_root = dataset / "images" if (dataset / "images").is_dir() else dataset
    labels_root = dataset / "labels" if (dataset / "labels").is_dir() else dataset
    images = sorted(path for path in images_root.rglob("*") if path.is_file() and path.suffix.lower() in IMAGE_EXTENSIONS)
    for image in images:
        relative = image.relative_to(images_root)
        destination = output / "images" / relative
        destination.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(image, destination)
        label = (labels_root / relative).with_suffix(".txt")
        output_label = (output / "labels" / relative).with_suffix(".txt")
        output_label.parent.mkdir(parents=True, exist_ok=True)
        rows: list[str] = []
        if label.is_file():
            for raw in label.read_text(encoding="utf-8-sig").splitlines():
                fields = raw.split()
                if len(fields) != 5:
                    invalid += 1
                    continue
                try:
                    source_id = int(fields[0])
                    if source_id < 0 or source_id >= len(names):
                        raise ValueError
                    [float(value) for value in fields[1:]]
                except ValueError:
                    invalid += 1
                    continue
                source_name = names[source_id]
                source_counts[source_name] += 1
                target = mapping.get(source_name)
                if target is None:
                    ignored += 1
                    continue
                target_counts[target] += 1
                rows.append(" ".join([str(target_ids[target]), *fields[1:]]))
        output_label.write_text("\n".join(rows) + ("\n" if rows else ""), encoding="utf-8")
    output.mkdir(parents=True, exist_ok=True)
    data = {
        "path": ".", "train": "images", "val": "images", "test": "images",
        "names": canonical,
    }
    (output / "data.yaml").write_text(yaml.safe_dump(data, sort_keys=False, allow_unicode=True), encoding="utf-8")
    if (dataset / "frames.jsonl").is_file():
        shutil.copy2(dataset / "frames.jsonl", output / "frames.jsonl")
    report = {
        "model_type": model_type, "source_classes": names, "mapping": mapping,
        "original_class_counts": dict(source_counts), "mapped_class_counts": dict(target_counts),
        "ignored_annotations": ignored, "invalid_annotations": invalid, "images": len(images),
    }
    write_json(output / "class_mapping_report.json", report)
    return report


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Rewrite YOLO label class IDs into canonical SadakDrishti classes.")
    parser.add_argument("--dataset", type=Path, required=True)
    parser.add_argument("--type", choices=tuple(EXPECTED_CLASSES), required=True)
    parser.add_argument("--mapping", type=Path, help="JSON source-name mapping; omitted uses conservative known aliases")
    parser.add_argument("--data-yaml", type=Path, help="Source dataset YAML when it cannot be auto-discovered")
    parser.add_argument("--output", type=Path, required=True)
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    print(json.dumps(remap(args.dataset, args.output, args.type, args.mapping, args.data_yaml), indent=2, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
