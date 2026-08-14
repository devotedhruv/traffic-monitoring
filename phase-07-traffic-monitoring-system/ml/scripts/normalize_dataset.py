"""Copy heterogeneous image/YOLO exports into a non-destructive images/labels layout."""

from __future__ import annotations

import argparse
import json
import shutil
from collections import Counter
from pathlib import Path

try:
    from ml.scripts.common import IMAGE_EXTENSIONS, write_json
    from ml.scripts.dataset_registry import inspect_dataset, portable_path, safe_identifier
except ModuleNotFoundError:
    from common import IMAGE_EXTENSIONS, write_json
    from dataset_registry import inspect_dataset, portable_path, safe_identifier


def image_candidates(root: Path) -> list[Path]:
    return sorted(path for path in root.rglob("*") if path.is_file() and path.suffix.lower() in IMAGE_EXTENSIONS)


def find_label(image: Path, root: Path) -> Path | None:
    candidates = [
        image.with_suffix(".txt"),
        root / "labels" / image.relative_to(root / "images").with_suffix(".txt") if root / "images" in image.parents else root / "labels" / f"{image.stem}.txt",
    ]
    for candidate in candidates:
        if candidate.is_file():
            return candidate
    matches = [path for path in root.rglob(f"{image.stem}.txt") if path.is_file()]
    return matches[0] if len(matches) == 1 else None


def normalize(source: Path, output: Path, source_id: str) -> dict[str, object]:
    source, output = source.resolve(), output.resolve()
    if source == output or source in output.parents:
        raise ValueError("Output must not be inside the immutable raw source")
    if output.exists() and any(output.iterdir()):
        raise FileExistsError(f"Output is not empty: {output}")
    images = image_candidates(source)
    if not images:
        raise ValueError(f"No supported images found under {source}")
    image_output, label_output = output / "images", output / "labels"
    image_output.mkdir(parents=True, exist_ok=True)
    label_output.mkdir(parents=True, exist_ok=True)
    frame_metadata: dict[str, dict[str, object]] = {}
    for manifest in source.rglob("frames.jsonl"):
        for line in manifest.read_text(encoding="utf-8").splitlines():
            if not line.strip():
                continue
            item = json.loads(line)
            if item.get("image"):
                frame_metadata[str(item["image"])] = item
    records: list[dict[str, object]] = []
    normalized_frames: list[dict[str, object]] = []
    stems: Counter[str] = Counter(path.stem for path in images)
    label_count = 0
    for index, image in enumerate(images):
        relative = image.relative_to(source)
        prefix = safe_identifier(source_id)
        name = f"{prefix}__{index:07d}__{image.name}" if stems[image.stem] > 1 else f"{prefix}__{image.name}"
        destination = image_output / name
        if destination.exists():
            raise FileExistsError(f"Filename collision: {destination}")
        shutil.copy2(image, destination)
        label = find_label(image, source)
        label_destination = label_output / Path(name).with_suffix(".txt")
        if label:
            shutil.copy2(label, label_destination)
            label_count += 1
        records.append({
            "image": f"images/{name}", "label": f"labels/{label_destination.name}" if label else None,
            "source_id": source_id, "source_relative_path": relative.as_posix(),
            "status": "unvalidated" if label else "needs_annotation",
        })
        metadata = frame_metadata.get(relative.as_posix()) or frame_metadata.get(image.name)
        if metadata:
            normalized_frames.append({**metadata, "image": name, "normalized_source_image": relative.as_posix()})
    manifest = output / "normalization_manifest.jsonl"
    manifest.write_text("".join(json.dumps(item, ensure_ascii=False) + "\n" for item in records), encoding="utf-8")
    if normalized_frames:
        (output / "frames.jsonl").write_text(
            "".join(json.dumps(item, ensure_ascii=False) + "\n" for item in normalized_frames),
            encoding="utf-8",
        )
    inspection = inspect_dataset(source)
    yaml_path = next(iter(sorted([*source.rglob("*.yaml"), *source.rglob("*.yml")])), None)
    if yaml_path is not None:
        shutil.copy2(yaml_path, output / "source_data.yaml")
    summary = {
        "source": portable_path(source), "output": portable_path(output), "source_id": source_id,
        "images": len(images), "labels": label_count,
        "needs_annotation": len(images) - label_count,
        "source_classes": inspection.get("classes", []),
        "frame_metadata_records": len(normalized_frames),
    }
    write_json(output / "normalization_report.json", summary)
    return summary


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Normalize a copied raw dataset without modifying its source.")
    parser.add_argument("--input", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--source-id", required=True)
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    print(json.dumps(normalize(args.input, args.output, args.source_id), indent=2, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
