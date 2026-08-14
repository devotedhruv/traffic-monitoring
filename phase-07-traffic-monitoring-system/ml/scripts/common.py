"""Shared, dependency-light utilities for the SadakDrishti ML command-line tools."""

from __future__ import annotations

import hashlib
import json
import math
import os
import shutil
import subprocess
import tempfile
from collections import Counter
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterable, Literal

import yaml


REPOSITORY_ROOT = Path(__file__).resolve().parents[2]
ML_ROOT = REPOSITORY_ROOT / "ml"
CONFIG_ROOT = ML_ROOT / "configs"
DATASET_ROOT = ML_ROOT / "datasets"
RAW_DATASET_ROOT = DATASET_ROOT / "_raw"
METADATA_ROOT = DATASET_ROOT / "metadata"
MODEL_ROOT = ML_ROOT / "models"
REPORT_ROOT = ML_ROOT / "reports"
IMAGE_EXTENSIONS = {".bmp", ".jpeg", ".jpg", ".png", ".tif", ".tiff", ".webp"}
SPLITS = ("train", "val", "test")
MODEL_TYPES = ("vehicle", "plate", "helmet")
DATASET_TO_MODEL = {"vehicles": "vehicle", "plates": "plate", "helmets": "helmet"}
MODEL_TO_DATASET = {value: key for key, value in DATASET_TO_MODEL.items()}
EXPECTED_CLASSES = {
    "vehicle": {0: "person", 1: "bicycle", 2: "car", 3: "motorcycle", 4: "bus", 5: "truck"},
    "plate": {0: "license_plate"},
    "helmet": {0: "helmet", 1: "no_helmet"},
}
ENVIRONMENT_KEYS = {
    "vehicle": ("TRAFFIC_VEHICLE_MODEL_PATH", "TRAFFIC_MODEL_PATH", "TRAFFIC_LIVE_MODEL_PATH"),
    "plate": ("TRAFFIC_PLATE_MODEL_PATH",),
    "helmet": ("TRAFFIC_HELMET_MODEL_PATH",),
}


@dataclass(frozen=True)
class DatasetConfig:
    yaml_path: Path
    root: Path
    splits: dict[str, Path]
    names: dict[int, str]


@dataclass(frozen=True)
class Annotation:
    class_id: int
    x_center: float
    y_center: float
    width: float
    height: float

    @property
    def area(self) -> float:
        return self.width * self.height


@dataclass(frozen=True)
class ValidationIssue:
    severity: Literal["error", "warning"]
    code: str
    path: str
    message: str
    line: int | None = None


@dataclass
class ValidationReport:
    dataset: str
    images: int
    annotations: int
    empty_images: int
    class_counts: dict[int, int]
    split_counts: dict[str, int]
    issues: list[ValidationIssue]

    @property
    def errors(self) -> int:
        return sum(issue.severity == "error" for issue in self.issues)

    @property
    def warnings(self) -> int:
        return sum(issue.severity == "warning" for issue in self.issues)

    def as_dict(self) -> dict[str, Any]:
        payload = asdict(self)
        payload["errors"] = self.errors
        payload["warnings"] = self.warnings
        return payload


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


def load_yaml(path: Path) -> dict[str, Any]:
    if not path.is_file():
        raise FileNotFoundError(f"YAML file does not exist: {path}")
    payload = yaml.safe_load(path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise ValueError(f"Expected a YAML mapping in {path}")
    return payload


def dataset_config_path(dataset: str) -> Path:
    normalized = dataset.strip().lower()
    if normalized in DATASET_TO_MODEL:
        normalized = DATASET_TO_MODEL[normalized]
    if normalized not in MODEL_TYPES:
        raise ValueError(f"Unknown dataset/model type: {dataset}")
    return CONFIG_ROOT / f"{normalized}.yaml"


def _normalize_names(value: Any) -> dict[int, str]:
    if isinstance(value, list):
        names = {index: str(name) for index, name in enumerate(value)}
    elif isinstance(value, dict):
        try:
            names = {int(index): str(name) for index, name in value.items()}
        except (TypeError, ValueError) as exc:
            raise ValueError("Dataset class IDs must be integers") from exc
    else:
        raise ValueError("Dataset YAML must contain a names list or mapping")
    if sorted(names) != list(range(len(names))):
        raise ValueError("Dataset class IDs must be contiguous and start at 0")
    if any(not name.strip() for name in names.values()):
        raise ValueError("Dataset class names must not be blank")
    return names


def load_dataset_config(path: Path | str) -> DatasetConfig:
    yaml_path = Path(path).expanduser().resolve()
    payload = load_yaml(yaml_path)
    missing = [key for key in ("path", "train", "val", "test", "names") if key not in payload]
    if missing:
        raise ValueError(f"Dataset YAML is missing required keys: {', '.join(missing)}")
    configured_root = Path(str(payload["path"])).expanduser()
    root = configured_root if configured_root.is_absolute() else (yaml_path.parent / configured_root)
    root = root.resolve()
    splits = {split: (root / str(payload[split])).resolve() for split in SPLITS}
    return DatasetConfig(yaml_path=yaml_path, root=root, splits=splits, names=_normalize_names(payload["names"]))


def validate_expected_classes(model_type: str, names: dict[int, str]) -> None:
    expected = EXPECTED_CLASSES[model_type]
    if names != expected:
        raise ValueError(f"{model_type} classes must be {expected}; received {names}")


def image_files(directory: Path) -> list[Path]:
    if not directory.is_dir():
        return []
    return sorted(path for path in directory.rglob("*") if path.is_file() and path.suffix.lower() in IMAGE_EXTENSIONS)


def matching_label_path(image: Path, image_root: Path, label_root: Path) -> Path:
    return (label_root / image.relative_to(image_root)).with_suffix(".txt")


def matching_image(label: Path, label_root: Path, image_root: Path) -> Path | None:
    relative = label.relative_to(label_root).with_suffix("")
    for extension in sorted(IMAGE_EXTENSIONS):
        candidate = image_root / relative.with_suffix(extension)
        if candidate.is_file():
            return candidate
    return None


def parse_annotation_file(path: Path, valid_class_ids: set[int]) -> tuple[list[Annotation], list[ValidationIssue]]:
    annotations: list[Annotation] = []
    issues: list[ValidationIssue] = []
    try:
        lines = path.read_text(encoding="utf-8-sig").splitlines()
    except (OSError, UnicodeError) as exc:
        return [], [ValidationIssue("error", "unreadable_label", str(path), str(exc))]
    seen: set[tuple[int, float, float, float, float]] = set()
    for line_number, raw_line in enumerate(lines, 1):
        line = raw_line.strip()
        if not line:
            continue
        fields = line.split()
        if len(fields) != 5:
            issues.append(ValidationIssue(
                "error", "invalid_field_count", str(path),
                f"Expected 5 YOLO fields, found {len(fields)}", line_number,
            ))
            continue
        try:
            class_value = float(fields[0])
            coordinates = tuple(float(value) for value in fields[1:])
        except ValueError:
            issues.append(ValidationIssue(
                "error", "non_numeric_annotation", str(path),
                "Class and box coordinates must be numeric", line_number,
            ))
            continue
        if not class_value.is_integer():
            issues.append(ValidationIssue(
                "error", "invalid_class_id", str(path), "Class ID must be an integer", line_number,
            ))
            continue
        class_id = int(class_value)
        if class_id not in valid_class_ids:
            issues.append(ValidationIssue(
                "error", "invalid_class_id", str(path),
                f"Class ID {class_id} is not defined by the dataset", line_number,
            ))
            continue
        if not all(math.isfinite(value) for value in coordinates):
            issues.append(ValidationIssue(
                "error", "non_finite_box", str(path), "Box coordinates must be finite", line_number,
            ))
            continue
        x_center, y_center, width, height = coordinates
        if width <= 0 or height <= 0:
            if width <= 0:
                issues.append(ValidationIssue(
                    "error", "zero_width", str(path), "Box width must be greater than zero", line_number,
                ))
            if height <= 0:
                issues.append(ValidationIssue(
                    "error", "zero_height", str(path), "Box height must be greater than zero", line_number,
                ))
            continue
        if any(value < 0 or value > 1 for value in coordinates):
            issues.append(ValidationIssue(
                "error", "coordinate_out_of_range", str(path),
                "YOLO coordinates must remain inside [0, 1]", line_number,
            ))
            continue
        if (
            x_center - width / 2 < -1e-6 or x_center + width / 2 > 1 + 1e-6
            or y_center - height / 2 < -1e-6 or y_center + height / 2 > 1 + 1e-6
        ):
            issues.append(ValidationIssue(
                "error", "box_outside_image", str(path),
                "Box edges extend outside the normalized image", line_number,
            ))
            continue
        annotation = Annotation(class_id, x_center, y_center, width, height)
        signature = (class_id, *[round(value, 8) for value in coordinates])
        if signature in seen:
            issues.append(ValidationIssue(
                "warning", "duplicate_annotation", str(path),
                "Duplicate class and bounding box", line_number,
            ))
            continue
        seen.add(signature)
        annotations.append(annotation)
        if annotation.area < 0.000025:
            issues.append(ValidationIssue(
                "warning", "suspicious_tiny_box", str(path),
                f"Bounding-box area is only {annotation.area:.7f} of the image", line_number,
            ))
        elif annotation.area > 0.95:
            issues.append(ValidationIssue(
                "warning", "suspicious_large_box", str(path),
                f"Bounding-box area is {annotation.area:.3f} of the image", line_number,
            ))
    return annotations, issues


def validate_dataset(config: DatasetConfig, check_images: bool = True) -> ValidationReport:
    issues: list[ValidationIssue] = []
    class_counts: Counter[int] = Counter()
    split_counts: dict[str, int] = {}
    total_images = total_annotations = empty_images = 0
    cv2: Any | None = None
    if check_images:
        try:
            import cv2 as imported_cv2

            cv2 = imported_cv2
        except ImportError:
            issues.append(ValidationIssue(
                "warning", "opencv_unavailable", str(config.root),
                "OpenCV is unavailable; corrupted-image checks were skipped",
            ))
    image_hashes: dict[str, tuple[str, Path]] = {}
    for split, image_root in config.splits.items():
        label_root = config.root / "labels" / split
        if not image_root.is_dir():
            issues.append(ValidationIssue("error", "missing_image_directory", str(image_root), "Split image directory is missing"))
        if not label_root.is_dir():
            issues.append(ValidationIssue("error", "missing_label_directory", str(label_root), "Split label directory is missing"))
        images = image_files(image_root)
        split_counts[split] = len(images)
        total_images += len(images)
        if not images:
            issues.append(ValidationIssue(
                "error", "empty_split", str(image_root),
                f"The {split} split contains no images and cannot be used for release-quality training",
            ))
        for image in images:
            try:
                if image.stat().st_size == 0:
                    issues.append(ValidationIssue("error", "empty_image", str(image), "Image file is empty"))
                else:
                    digest = sha256_file(image)
                    previous = image_hashes.get(digest)
                    if previous is not None:
                        previous_split, previous_path = previous
                        severity: Literal["error", "warning"] = "error" if previous_split != split else "warning"
                        code = "duplicate_image_across_splits" if previous_split != split else "duplicate_image"
                        issues.append(ValidationIssue(
                            severity, code, str(image),
                            f"Image bytes duplicate {previous_path} from the {previous_split} split",
                        ))
                    else:
                        image_hashes[digest] = (split, image)
                    if cv2 is not None:
                        decoded = cv2.imread(str(image), cv2.IMREAD_UNCHANGED)
                        if decoded is None or decoded.size == 0:
                            issues.append(ValidationIssue("error", "corrupted_image", str(image), "OpenCV could not decode this image"))
            except OSError as exc:
                issues.append(ValidationIssue("error", "unreadable_image", str(image), str(exc)))
            label = matching_label_path(image, image_root, label_root)
            if not label.is_file():
                issues.append(ValidationIssue("error", "missing_label", str(label), f"No YOLO label for {image.name}"))
                continue
            annotations, annotation_issues = parse_annotation_file(label, set(config.names))
            issues.extend(annotation_issues)
            if not annotations:
                empty_images += 1
                issues.append(ValidationIssue(
                    "warning", "empty_label", str(label),
                    "Label contains no objects; verify that this is an intentional negative image",
                ))
            total_annotations += len(annotations)
            class_counts.update(annotation.class_id for annotation in annotations)
        if label_root.is_dir():
            for label in sorted(label_root.rglob("*.txt")):
                if matching_image(label, label_root, image_root) is None:
                    issues.append(ValidationIssue("error", "missing_image", str(label), "Label has no matching image"))
    return ValidationReport(
        dataset=config.root.name,
        images=total_images,
        annotations=total_annotations,
        empty_images=empty_images,
        class_counts=dict(sorted(class_counts.items())),
        split_counts=split_counts,
        issues=issues,
    )


def write_json(path: Path, payload: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(f"{path.suffix}.tmp")
    temporary.write_text(json.dumps(payload, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    os.replace(temporary, path)


def load_training_defaults(model_type: str) -> dict[str, Any]:
    if model_type not in MODEL_TYPES:
        raise ValueError(f"Unsupported model type: {model_type}")
    payload = load_yaml(CONFIG_ROOT / "training_defaults.yaml")
    task = payload.get(model_type)
    if not isinstance(task, dict):
        raise ValueError(f"Missing {model_type} defaults")
    shared = {key: value for key, value in payload.items() if key not in MODEL_TYPES}
    return {**shared, **task}


def resolved_dataset_yaml(config: DatasetConfig) -> tempfile.NamedTemporaryFile[str]:
    payload = {
        "path": str(config.root),
        **{split: str(config.splits[split].relative_to(config.root)) for split in SPLITS},
        "names": config.names,
    }
    temporary = tempfile.NamedTemporaryFile("w", suffix=".yaml", prefix="sadakdrishti-data-", encoding="utf-8", delete=False)
    yaml.safe_dump(payload, temporary, sort_keys=False, allow_unicode=True)
    temporary.flush()
    return temporary


def git_commit() -> str | None:
    try:
        completed = subprocess.run(
            ["git", "rev-parse", "HEAD"], cwd=REPOSITORY_ROOT,
            capture_output=True, text=True, timeout=5, check=False,
        )
        return completed.stdout.strip() if completed.returncode == 0 else None
    except (OSError, subprocess.SubprocessError):
        return None


def read_registry(model_type: str, registry_root: Path = MODEL_ROOT) -> dict[str, Any]:
    if model_type not in MODEL_TYPES:
        raise ValueError(f"Unsupported model type: {model_type}")
    path = registry_root / model_type / "metadata.json"
    if not path.is_file():
        return {"schemaVersion": 1, "modelType": model_type, "productionVersion": None, "models": []}
    payload = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict) or not isinstance(payload.get("models"), list):
        raise ValueError(f"Invalid model registry: {path}")
    if payload.get("modelType") != model_type:
        raise ValueError(f"Registry model type does not match {model_type}")
    return payload


def next_model_version(registry: dict[str, Any], model_type: str) -> str:
    highest = 0
    prefix = f"{model_type}-v"
    for item in registry.get("models", []):
        version = str(item.get("version", ""))
        if version.startswith(prefix) and version[len(prefix):].isdigit():
            highest = max(highest, int(version[len(prefix):]))
    return f"{model_type}-v{highest + 1}"


def register_model(
    model_type: str,
    source: Path,
    metadata: dict[str, Any],
    registry_root: Path = MODEL_ROOT,
    copy_weights: bool = True,
) -> dict[str, Any]:
    source = source.expanduser().resolve()
    if not source.is_file():
        raise FileNotFoundError(f"Model weights do not exist: {source}")
    registry = read_registry(model_type, registry_root)
    version = str(metadata.get("version") or next_model_version(registry, model_type))
    prefix = f"{model_type}-v"
    if not version.startswith(prefix) or not version[len(prefix):].isdigit():
        raise ValueError(f"Model version must look like {prefix}1")
    if any(item.get("version") == version for item in registry["models"]):
        raise ValueError(f"Model version already exists: {version}")
    destination_dir = registry_root / model_type
    destination_dir.mkdir(parents=True, exist_ok=True)
    destination = destination_dir / f"{version}.pt"
    if copy_weights:
        shutil.copy2(source, destination)
    else:
        destination = source
    try:
        model_path = destination.resolve().relative_to(REPOSITORY_ROOT).as_posix()
    except ValueError:
        model_path = str(destination.resolve())
    record = {
        "modelName": metadata.get("modelName", version),
        "version": version,
        "modelType": model_type,
        "baseModel": metadata.get("baseModel"),
        "datasetVersion": metadata.get("datasetVersion"),
        "trainingDate": metadata.get("trainingDate", utc_now()),
        "epochs": metadata.get("epochs"),
        "imageSize": metadata.get("imageSize"),
        "precision": metadata.get("precision"),
        "recall": metadata.get("recall"),
        "mAP50": metadata.get("mAP50"),
        "mAP50_95": metadata.get("mAP50_95"),
        "evaluationDataset": metadata.get("evaluationDataset"),
        "evaluationSplit": metadata.get("evaluationSplit"),
        "evaluatedAt": metadata.get("evaluatedAt"),
        "metricsPath": metadata.get("metricsPath"),
        "modelPath": model_path,
        "notes": metadata.get("notes", ""),
        "gitCommit": metadata.get("gitCommit", git_commit()),
        "promotedAt": None,
    }
    registry["models"].append(record)
    write_json(destination_dir / "metadata.json", registry)
    write_json(destination_dir / f"{version}.json", record)
    return record


def update_env_file(env_file: Path, updates: dict[str, str]) -> None:
    lines = env_file.read_text(encoding="utf-8").splitlines() if env_file.is_file() else []
    output: list[str] = []
    remaining = dict(updates)
    for line in lines:
        stripped = line.strip()
        if stripped and not stripped.startswith("#") and "=" in line:
            key = line.split("=", 1)[0].strip()
            if key in remaining:
                output.append(f"{key}={remaining.pop(key)}")
                continue
        output.append(line)
    if remaining and output and output[-1] != "":
        output.append("")
    output.extend(f"{key}={value}" for key, value in remaining.items())
    env_file.parent.mkdir(parents=True, exist_ok=True)
    temporary = env_file.with_suffix(f"{env_file.suffix}.tmp")
    temporary.write_text("\n".join(output).rstrip() + "\n", encoding="utf-8")
    os.replace(temporary, env_file)


def promote_model(
    model_type: str,
    model: Path,
    env_file: Path,
    registry_root: Path = MODEL_ROOT,
) -> dict[str, Any]:
    if model_type not in MODEL_TYPES:
        raise ValueError(f"Unsupported model type: {model_type}")
    model = model.expanduser().resolve()
    if not model.is_file() or model.suffix.lower() != ".pt":
        raise FileNotFoundError(f"Expected existing .pt weights: {model}")
    try:
        relative_path = model.relative_to(REPOSITORY_ROOT).as_posix()
    except ValueError as exc:
        raise ValueError("Production weights must be inside the repository so configuration stays portable") from exc
    registry = read_registry(model_type, registry_root)
    selected = next(
        (item for item in registry["models"] if Path(str(item.get("modelPath", ""))).name == model.name),
        None,
    )
    if selected is None:
        raise ValueError("Model must be registered with register_model.py before promotion")
    selected_path = Path(str(selected.get("modelPath", "")))
    selected_path = selected_path.resolve() if selected_path.is_absolute() else (REPOSITORY_ROOT / selected_path).resolve()
    if selected_path != model:
        raise ValueError("Requested model path does not match the registered model artifact")
    if selected.get("modelType") != model_type:
        raise ValueError(f"Registered task {selected.get('modelType')} does not match {model_type}")
    metrics = (selected.get("precision"), selected.get("recall"), selected.get("mAP50"), selected.get("mAP50_95"))
    if any(value is None for value in metrics):
        raise ValueError("Promotion requires measured precision, recall, mAP50, and mAP50-95")
    if not selected.get("datasetVersion") or not selected.get("evaluationDataset"):
        raise ValueError("Promotion requires both training dataset version and evaluation dataset metadata")
    if selected.get("evaluationSplit") not in {"val", "test"}:
        raise ValueError("Promotion requires an evaluationSplit of val or test")
    if model.stat().st_size <= 0:
        raise ValueError("Registered model file is empty")
    previous = registry.get("productionVersion")
    promoted_at = utc_now()
    update_env_file(env_file, {key: relative_path for key in ENVIRONMENT_KEYS[model_type]})
    registry["productionVersion"] = selected["version"]
    selected["promotedAt"] = promoted_at
    history = registry.setdefault("promotionHistory", [])
    history.append({
        "previousVersion": previous,
        "productionVersion": selected["version"],
        "promotedAt": promoted_at,
        "modelPath": relative_path,
    })
    write_json(registry_root / model_type / "metadata.json", registry)
    write_json(registry_root / model_type / f"{selected['version']}.json", selected)
    return {
        "modelType": model_type,
        "modelPath": relative_path,
        "environmentKeys": list(ENVIRONMENT_KEYS[model_type]),
        "productionVersion": selected["version"],
        "previousProductionVersion": previous,
    }


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def format_table(headers: Iterable[str], rows: Iterable[Iterable[Any]]) -> str:
    string_rows = [[str(value) for value in row] for row in rows]
    header_row = [str(value) for value in headers]
    widths = [len(value) for value in header_row]
    for row in string_rows:
        widths = [max(width, len(row[index])) for index, width in enumerate(widths)]
    lines = [" | ".join(value.ljust(widths[index]) for index, value in enumerate(header_row))]
    lines.append("-+-".join("-" * width for width in widths))
    lines.extend(" | ".join(value.ljust(widths[index]) for index, value in enumerate(row)) for row in string_rows)
    return "\n".join(lines)
