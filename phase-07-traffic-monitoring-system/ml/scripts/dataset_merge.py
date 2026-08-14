"""Validated, provenance-preserving merge for versioned SadakDrishti datasets."""

from __future__ import annotations

import json
import shutil
from collections import Counter
from pathlib import Path
from typing import Any

import yaml

try:
    from ml.scripts.common import DATASET_ROOT, EXPECTED_CLASSES, IMAGE_EXTENSIONS, SPLITS, load_dataset_config, matching_label_path, parse_annotation_file, utc_now, validate_dataset, validate_expected_classes, write_json
    from ml.scripts.dataset_registry import portable_path, read_sources, resolve_record_path, safe_identifier
except ModuleNotFoundError:
    from common import DATASET_ROOT, EXPECTED_CLASSES, IMAGE_EXTENSIONS, SPLITS, load_dataset_config, matching_label_path, parse_annotation_file, utc_now, validate_dataset, validate_expected_classes, write_json
    from dataset_registry import portable_path, read_sources, resolve_record_path, safe_identifier


def resolve_source(value: str) -> tuple[str, Path, dict[str, Any] | None]:
    candidate = Path(value).expanduser()
    if candidate.exists():
        return safe_identifier(candidate.name), candidate.resolve(), None
    record = next((item for item in read_sources() if item["source_id"] == safe_identifier(value)), None)
    if record is None:
        raise KeyError(f"Source is neither a path nor registered source ID: {value}")
    return record["source_id"], resolve_record_path(record), record


def _yaml_names(root: Path) -> dict[int, str] | None:
    for candidate in [root / "data.yaml", root / "dataset.yaml", *sorted(root.glob("*.yaml"))]:
        if not candidate.is_file():
            continue
        payload = yaml.safe_load(candidate.read_text(encoding="utf-8")) or {}
        names = payload.get("names")
        if isinstance(names, list):
            return dict(enumerate(map(str, names)))
        if isinstance(names, dict):
            return {int(key): str(value) for key, value in names.items()}
    return None


def merge_sources(model_type: str, sources: list[str], output_version: str, output: Path | None = None) -> dict[str, Any]:
    canonical = EXPECTED_CLASSES[model_type]
    expected_prefix = f"{model_type}-v"
    if not output_version.startswith(expected_prefix) or not output_version[len(expected_prefix):].isdigit():
        raise ValueError(f"Dataset version must look like {expected_prefix}1")
    destination = (output or DATASET_ROOT / "versions" / model_type / output_version).resolve()
    if destination.exists() and any(destination.iterdir()):
        raise FileExistsError(f"Version destination is not empty: {destination}")
    resolved = [resolve_source(value) for value in sources]
    counts: Counter[str] = Counter()
    provenance: list[dict[str, Any]] = []
    for source_id, root, record in resolved:
        if record and record.get("dataset_type") != model_type:
            raise ValueError(f"Source {source_id} is {record.get('dataset_type')}, not {model_type}")
        names = _yaml_names(root)
        if names != canonical:
            raise ValueError(f"Source {source_id} does not use canonical {model_type} classes; run remap_classes.py first")
        yaml_path = next((path for path in (root / "data.yaml", root / "dataset.yaml") if path.is_file()), None)
        if yaml_path is None:
            raise ValueError(f"Source {source_id} is missing data.yaml")
        config = load_dataset_config(yaml_path)
        validate_expected_classes(model_type, config.names)
        validation = validate_dataset(config)
        if validation.errors:
            raise ValueError(f"Source {source_id} has {validation.errors} critical validation errors")
        for split in SPLITS:
            image_root, label_root = root / "images" / split, root / "labels" / split
            if not image_root.is_dir() or not label_root.is_dir():
                raise ValueError(f"Source {source_id} has no complete {split} split; run split_dataset.py first")
            for image in sorted(path for path in image_root.rglob("*") if path.is_file() and path.suffix.lower() in IMAGE_EXTENSIONS):
                label = matching_label_path(image, image_root, label_root)
                if not label.is_file():
                    raise ValueError(f"Source {source_id} is missing label for {image.name}")
                _, issues = parse_annotation_file(label, set(canonical))
                critical = [issue for issue in issues if issue.severity == "error"]
                if critical:
                    raise ValueError(f"Source {source_id} contains invalid label {label}: {critical[0].message}")
                relative = image.relative_to(image_root)
                safe_name = f"{safe_identifier(source_id)}__{relative.as_posix().replace('/', '__')}"
                image_destination = destination / "images" / split / safe_name
                label_destination = destination / "labels" / split / Path(safe_name).with_suffix(".txt")
                if image_destination.exists() or label_destination.exists():
                    raise FileExistsError(f"Merge collision: {safe_name}")
                image_destination.parent.mkdir(parents=True, exist_ok=True)
                label_destination.parent.mkdir(parents=True, exist_ok=True)
                shutil.copy2(image, image_destination)
                shutil.copy2(label, label_destination)
                counts[split] += 1
                provenance.append({
                    "image": image_destination.relative_to(destination).as_posix(),
                    "label": label_destination.relative_to(destination).as_posix(),
                    "source_id": source_id,
                    "source_path": portable_path(image),
                    "split": split,
                })
    dataset_yaml = {
        "path": ".", "train": "images/train", "val": "images/val", "test": "images/test", "names": canonical,
    }
    destination.mkdir(parents=True, exist_ok=True)
    (destination / "data.yaml").write_text(yaml.safe_dump(dataset_yaml, sort_keys=False, allow_unicode=True), encoding="utf-8")
    (destination / "provenance.jsonl").write_text(
        "".join(json.dumps(item, ensure_ascii=False) + "\n" for item in provenance), encoding="utf-8",
    )
    metadata = {
        "dataset_version": output_version, "type": model_type, "created_at": utc_now(),
        "sources": [source_id for source_id, _, _ in resolved],
        "train_images": counts["train"], "val_images": counts["val"], "test_images": counts["test"],
        "classes": list(canonical.values()), "path": portable_path(destination),
        "quality_status": "merged_unvalidated",
    }
    write_json(destination / "dataset_metadata.json", metadata)
    return metadata
