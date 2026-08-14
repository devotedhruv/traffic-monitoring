"""Dataset provenance and import primitives shared by the ML CLIs."""

from __future__ import annotations

import json
import os
import re
import shutil
import tempfile
import zipfile
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Iterable

try:
    from ml.scripts.common import (
        DATASET_ROOT, IMAGE_EXTENSIONS, METADATA_ROOT, RAW_DATASET_ROOT,
        REPOSITORY_ROOT, load_yaml, utc_now, write_json,
    )
except ModuleNotFoundError:
    from common import (
        DATASET_ROOT, IMAGE_EXTENSIONS, METADATA_ROOT, RAW_DATASET_ROOT,
        REPOSITORY_ROOT, load_yaml, utc_now, write_json,
    )


DATASET_TYPES = ("vehicle", "plate", "helmet", "plate_chars", "own_nepal")
RAW_CATEGORIES = {
    "vehicle": "vehicles",
    "plate": "plates",
    "helmet": "helmets",
    "plate_chars": "plate_chars",
    "own_nepal": "own_nepal",
}


def safe_identifier(value: str) -> str:
    normalized = re.sub(r"[^a-z0-9_-]+", "-", value.strip().lower()).strip("-_")
    if not normalized:
        raise ValueError("Source identifier must contain letters or digits")
    return normalized


def portable_path(path: Path) -> str:
    resolved = path.expanduser().resolve()
    try:
        return resolved.relative_to(REPOSITORY_ROOT).as_posix()
    except ValueError:
        return str(resolved)


def source_reference(path: Path) -> str:
    """Keep provenance useful without persisting developer-machine absolute paths."""
    resolved = path.expanduser().resolve()
    try:
        return resolved.relative_to(REPOSITORY_ROOT).as_posix()
    except ValueError:
        return f"external:{resolved.name}"


def source_registry_path(metadata_root: Path = METADATA_ROOT) -> Path:
    return metadata_root / "sources.jsonl"


def read_sources(metadata_root: Path = METADATA_ROOT) -> list[dict[str, Any]]:
    path = source_registry_path(metadata_root)
    if not path.is_file():
        return []
    records: list[dict[str, Any]] = []
    for line_number, line in enumerate(path.read_text(encoding="utf-8").splitlines(), 1):
        if not line.strip():
            continue
        try:
            item = json.loads(line)
        except json.JSONDecodeError as exc:
            raise ValueError(f"Invalid source registry JSON on line {line_number}: {path}") from exc
        if not isinstance(item, dict) or not item.get("source_id"):
            raise ValueError(f"Invalid source record on line {line_number}: {path}")
        records.append(item)
    return records


def register_source(record: dict[str, Any], metadata_root: Path = METADATA_ROOT, replace: bool = False) -> dict[str, Any]:
    source_id = safe_identifier(str(record.get("source_id", "")))
    dataset_type = str(record.get("dataset_type", "")).strip().lower()
    if dataset_type not in DATASET_TYPES:
        raise ValueError(f"dataset_type must be one of {', '.join(DATASET_TYPES)}")
    existing = read_sources(metadata_root)
    match = next((item for item in existing if item["source_id"] == source_id), None)
    if match is not None and not replace:
        raise ValueError(f"Dataset source is already registered: {source_id}")
    normalized = {
        "source_id": source_id,
        "name": str(record.get("name") or source_id),
        "provider": str(record.get("provider") or "Local"),
        "dataset_type": dataset_type,
        "source_identifier": str(record.get("source_identifier") or ""),
        "license": str(record.get("license") or "UNKNOWN"),
        "downloaded_at": record.get("downloaded_at"),
        "registered_at": record.get("registered_at") or utc_now(),
        "original_classes": list(record.get("original_classes") or []),
        "target_classes": list(record.get("target_classes") or []),
        "annotation_format": str(record.get("annotation_format") or "unknown"),
        "status": str(record.get("status") or "imported_unvalidated"),
        "raw_path": record.get("raw_path"),
        "processed_path": record.get("processed_path"),
        "notes": str(record.get("notes") or ""),
    }
    updated = [normalized if item["source_id"] == source_id else item for item in existing]
    if match is None:
        updated.append(normalized)
    path = source_registry_path(metadata_root)
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(".jsonl.tmp")
    temporary.write_text(
        "".join(json.dumps(item, ensure_ascii=False) + "\n" for item in updated),
        encoding="utf-8",
    )
    os.replace(temporary, path)
    return normalized


def update_source(source_id: str, changes: dict[str, Any], metadata_root: Path = METADATA_ROOT) -> dict[str, Any]:
    current = source_by_id(source_id, metadata_root)
    return register_source({**current, **changes}, metadata_root=metadata_root, replace=True)


def source_by_id(source_id: str, metadata_root: Path = METADATA_ROOT) -> dict[str, Any]:
    normalized = safe_identifier(source_id)
    record = next((item for item in read_sources(metadata_root) if item["source_id"] == normalized), None)
    if record is None:
        raise KeyError(f"Unknown dataset source: {normalized}")
    return record


def _names_from_yaml(path: Path) -> list[str]:
    try:
        names = load_yaml(path).get("names", {})
    except (OSError, ValueError):
        return []
    if isinstance(names, list):
        return [str(item) for item in names]
    if isinstance(names, dict):
        try:
            return [str(names[key]) for key in sorted(names, key=lambda value: int(value))]
        except (TypeError, ValueError):
            return [str(item) for item in names.values()]
    return []


def inspect_dataset(root: Path) -> dict[str, Any]:
    root = root.expanduser().resolve()
    images = sorted(path for path in root.rglob("*") if path.is_file() and path.suffix.lower() in IMAGE_EXTENSIONS)
    labels = sorted(path for path in root.rglob("*.txt") if path.is_file())
    yaml_files = sorted([*root.rglob("*.yaml"), *root.rglob("*.yml")])
    classes: list[str] = []
    data_yaml = None
    for candidate in yaml_files:
        discovered = _names_from_yaml(candidate)
        if discovered:
            data_yaml, classes = candidate, discovered
            break
    image_stems = {path.stem for path in images}
    paired_labels = sum(path.stem in image_stems for path in labels)
    annotation_format = "yolo" if labels and (data_yaml or any("labels" in path.parts for path in labels) or paired_labels) else "unknown"
    status = "needs_annotation" if images and not labels else "imported_unvalidated"
    return {
        "root": portable_path(root),
        "image_count": len(images),
        "label_count": len(labels),
        "yaml": portable_path(data_yaml) if data_yaml else None,
        "annotation_format": annotation_format,
        "classes": classes,
        "status": status,
    }


def _safe_extract(archive: Path, destination: Path) -> None:
    destination_resolved = destination.resolve()
    with zipfile.ZipFile(archive) as payload:
        for member in payload.infolist():
            candidate = (destination / member.filename).resolve()
            if candidate != destination_resolved and destination_resolved not in candidate.parents:
                raise ValueError(f"Unsafe path in ZIP archive: {member.filename}")
        payload.extractall(destination)


def import_local_source(
    input_path: Path,
    dataset_type: str,
    source_name: str,
    provider: str = "Local",
    source_identifier: str | None = None,
    license_name: str = "UNKNOWN",
    notes: str = "",
    metadata_root: Path = METADATA_ROOT,
    raw_root: Path = RAW_DATASET_ROOT,
) -> tuple[Path, dict[str, Any], dict[str, Any]]:
    input_path = input_path.expanduser().resolve()
    if dataset_type not in DATASET_TYPES:
        raise ValueError(f"Unsupported dataset type: {dataset_type}")
    if not input_path.exists():
        raise FileNotFoundError(f"Import input does not exist: {input_path}")
    source_id = safe_identifier(source_name)
    destination = raw_root / RAW_CATEGORIES[dataset_type] / source_id
    if destination.exists():
        raise FileExistsError(f"Import destination already exists: {destination}")
    destination.parent.mkdir(parents=True, exist_ok=True)
    if input_path.is_file():
        if input_path.suffix.lower() != ".zip":
            raise ValueError("Local file imports must be ZIP archives; directories are also supported")
        destination.mkdir()
        try:
            _safe_extract(input_path, destination)
        except Exception:
            shutil.rmtree(destination, ignore_errors=True)
            raise
    else:
        shutil.copytree(input_path, destination)
    inspection = inspect_dataset(destination)
    record = register_source({
        "source_id": source_id,
        "name": source_name,
        "provider": provider,
        "dataset_type": dataset_type,
        "source_identifier": source_identifier or source_reference(input_path),
        "license": license_name,
        "downloaded_at": utc_now() if provider.lower() != "local" else None,
        "original_classes": inspection["classes"],
        "target_classes": [],
        "annotation_format": inspection["annotation_format"],
        "status": inspection["status"],
        "raw_path": portable_path(destination),
        "notes": notes,
    }, metadata_root=metadata_root)
    write_json(destination / "sadakdrishti-import.json", {"source": record, "inspection": inspection})
    return destination, record, inspection


def resolve_record_path(record: dict[str, Any]) -> Path:
    value = record.get("processed_path") or record.get("raw_path")
    if not value:
        raise ValueError(f"Source {record.get('source_id')} has no stored path")
    path = Path(str(value)).expanduser()
    return path.resolve() if path.is_absolute() else (REPOSITORY_ROOT / path).resolve()
