"""Split YOLO images by source session so neighboring video frames never leak."""

from __future__ import annotations

import argparse
import json
import logging
import random
import shutil
from collections import defaultdict
from pathlib import Path

import yaml

try:
    from ml.scripts.common import DATASET_ROOT, DATASET_TO_MODEL, EXPECTED_CLASSES, IMAGE_EXTENSIONS, SPLITS, write_json
    from ml.scripts.dataset_registry import portable_path, update_source
except ModuleNotFoundError:  # Direct execution from ml/scripts.
    from common import DATASET_ROOT, DATASET_TO_MODEL, EXPECTED_CLASSES, IMAGE_EXTENSIONS, SPLITS, write_json
    from dataset_registry import portable_path, update_source


LOG = logging.getLogger("sadakdrishti.ml.split_dataset")


def load_groups(manifest: Path | None) -> dict[str, dict[str, str]]:
    if manifest is None or not manifest.is_file():
        return {}
    groups: dict[str, dict[str, str]] = {}
    for line_number, line in enumerate(manifest.read_text(encoding="utf-8").splitlines(), 1):
        if not line.strip():
            continue
        try:
            item = json.loads(line)
            image = str(item["image"])
            source_video = item.get("source_video") or item.get("sourceVideo")
            session = item.get("session_id") or item.get("session")
            camera = item.get("camera_id") or item.get("cameraId")
            sequence = item.get("sequence_id") or item.get("sequenceId")
            selected = next(
                ((kind, value) for kind, value in (
                    ("source_video", source_video), ("session_id", session),
                    ("camera_id", camera), ("sequence_id", sequence),
                ) if value),
                None,
            )
            if selected is None:
                raise KeyError("source_video/session_id/camera_id/sequence_id")
            kind, value = selected
            groups[image] = {"group": f"{kind}:{value}", "group_kind": kind, "group_value": str(value)}
        except (KeyError, TypeError, ValueError) as exc:
            raise ValueError(f"Invalid frame manifest line {line_number}: {manifest}") from exc
    return groups


def load_sessions(manifest: Path | None) -> dict[str, str]:
    """Backward-compatible view used by existing callers and tests."""
    return {image: value["group"] for image, value in load_groups(manifest).items()}


def inferred_session(image: Path) -> str:
    if "__f" in image.stem:
        return image.stem.split("__f", 1)[0]
    return image.parent.name if image.parent.name not in {"images", "raw"} else image.stem


def assign_groups(groups: dict[str, list[Path]], seed: int, ratios: tuple[float, float, float]) -> dict[str, str]:
    randomizer = random.Random(seed)
    ordered = list(groups)
    randomizer.shuffle(ordered)
    ordered.sort(key=lambda group: len(groups[group]), reverse=True)
    targets = {split: sum(map(len, groups.values())) * ratio for split, ratio in zip(SPLITS, ratios)}
    counts = {split: 0 for split in SPLITS}
    assignment: dict[str, str] = {}
    for group in ordered:
        split = min(SPLITS, key=lambda name: counts[name] / max(targets[name], 1.0))
        assignment[group] = split
        counts[split] += len(groups[group])
    return assignment


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Create deterministic 70/20/10 YOLO splits grouped by video/session.")
    parser.add_argument("--input", type=Path, required=True, help="Directory containing raw images")
    parser.add_argument("--dataset", choices=tuple(DATASET_TO_MODEL), required=True, help="Target dataset")
    parser.add_argument("--output", type=Path, help="Target dataset root (default: ml/datasets/<dataset>)")
    parser.add_argument("--labels", type=Path, help="Optional raw YOLO-label directory; defaults to --input")
    parser.add_argument("--manifest", type=Path, help="frames.jsonl produced by extract_frames.py")
    parser.add_argument("--train", type=float, default=0.70)
    parser.add_argument("--val", type=float, default=0.20)
    parser.add_argument("--test", type=float, default=0.10)
    parser.add_argument("--seed", type=int, default=42)
    parser.add_argument("--require-labels", action="store_true", help="Fail if any source image has no label")
    parser.add_argument("--move", action="store_true", help="Move instead of copying source files")
    parser.add_argument("--source-id", help="Registered provenance source to link to this processed split")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")
    ratios = (args.train, args.val, args.test)
    if any(value <= 0 for value in ratios) or not 0.999 <= sum(ratios) <= 1.001:
        raise SystemExit("--train, --val, and --test must be positive and sum to 1")
    if not args.input.is_dir():
        raise SystemExit(f"Input image directory does not exist: {args.input}")
    output = (args.output or DATASET_ROOT / args.dataset).resolve()
    labels_root = (args.labels or args.input).resolve()
    manifest_groups = load_groups(args.manifest or (args.input / "frames.jsonl"))
    images = sorted(path for path in args.input.rglob("*") if path.is_file() and path.suffix.lower() in IMAGE_EXTENSIONS)
    if not images:
        raise SystemExit(f"No supported images found under {args.input}")
    groups: dict[str, list[Path]] = defaultdict(list)
    for image in images:
        group_info = manifest_groups.get(image.name)
        group = group_info["group"] if group_info else f"inferred:{inferred_session(image)}"
        groups[group].append(image)
    assignments = assign_groups(groups, args.seed, ratios)
    operation = shutil.move if args.move else shutil.copy2
    records: list[dict[str, object]] = []
    split_counts = {split: 0 for split in SPLITS}
    for group, group_images in sorted(groups.items()):
        split = assignments[group]
        image_output = output / "images" / split
        label_output = output / "labels" / split
        image_output.mkdir(parents=True, exist_ok=True)
        label_output.mkdir(parents=True, exist_ok=True)
        for image in group_images:
            relative = image.relative_to(args.input)
            label = labels_root / relative.with_suffix(".txt")
            if not label.is_file():
                alternate = labels_root / f"{image.stem}.txt"
                label = alternate if alternate.is_file() else label
            if args.require_labels and not label.is_file():
                raise SystemExit(f"Missing label for {image}: expected {label}")
            image_destination = image_output / relative
            if image_destination.exists():
                raise SystemExit(f"Duplicate output filename: {image_destination}")
            image_destination.parent.mkdir(parents=True, exist_ok=True)
            operation(str(image), str(image_destination))
            label_destination = (label_output / relative).with_suffix(".txt")
            label_destination.parent.mkdir(parents=True, exist_ok=True)
            if label.is_file():
                operation(str(label), str(label_destination))
            else:
                label_destination.touch()
            split_counts[split] += 1
            group_info = manifest_groups.get(image.name, {})
            records.append({
                "image": relative.as_posix(), "group": group,
                "group_kind": group_info.get("group_kind", "inferred"),
                "split": split,
            })
    write_json(output / "split_manifest.json", {
        "seed": args.seed,
        "ratios": dict(zip(SPLITS, ratios)),
        "counts": split_counts,
        "groups": assignments,
        "files": records,
    })
    model_type = DATASET_TO_MODEL[args.dataset]
    (output / "data.yaml").write_text(yaml.safe_dump({
        "path": ".", "train": "images/train", "val": "images/val", "test": "images/test",
        "names": EXPECTED_CLASSES[model_type],
    }, sort_keys=False, allow_unicode=True), encoding="utf-8")
    if args.source_id:
        update_source(args.source_id, {
            "processed_path": portable_path(output),
            "status": "split_unvalidated",
            "target_classes": list(EXPECTED_CLASSES[model_type].values()),
        })
    LOG.info("Created %s with train=%d val=%d test=%d; sessions remain isolated", output, *(split_counts[item] for item in SPLITS))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
