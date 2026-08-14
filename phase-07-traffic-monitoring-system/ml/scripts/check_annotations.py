"""Generate JSON, CSV, and optional headless charts for YOLO annotations."""

from __future__ import annotations

import argparse
import csv
import json
import os
from collections import Counter
from pathlib import Path
from statistics import mean

os.environ.setdefault("MPLBACKEND", "Agg")
os.environ.setdefault("MPLCONFIGDIR", "/tmp/sadakdrishti-matplotlib")

try:
    from ml.scripts.common import (
        DATASET_TO_MODEL, REPORT_ROOT, SPLITS, dataset_config_path, image_files,
        load_dataset_config, matching_label_path, parse_annotation_file, write_json,
    )
except ModuleNotFoundError:
    from common import (
        DATASET_TO_MODEL, REPORT_ROOT, SPLITS, dataset_config_path, image_files,
        load_dataset_config, matching_label_path, parse_annotation_file, write_json,
    )


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Summarize class balance, object sizes, empty images, and split coverage.")
    parser.add_argument("--dataset", choices=tuple(DATASET_TO_MODEL), help="Bundled dataset name")
    parser.add_argument("--data", type=Path, help="Explicit dataset YAML instead of --dataset")
    parser.add_argument("--output", type=Path, help="Report directory")
    parser.add_argument("--no-plots", action="store_true", help="Do not generate PNG graphs")
    return parser.parse_args()


def size_bucket(area: float) -> str:
    if area < 0.001:
        return "tiny"
    if area < 0.01:
        return "small"
    if area < 0.10:
        return "medium"
    return "large"


def main() -> int:
    args = parse_args()
    if bool(args.dataset) == bool(args.data):
        raise SystemExit("Choose exactly one of --dataset or --data")
    model_type = DATASET_TO_MODEL.get(args.dataset, Path(args.data).stem.rstrip("s") if args.data else "dataset")
    config = load_dataset_config(args.data or dataset_config_path(args.dataset))
    output = (args.output or REPORT_ROOT / model_type / "annotation-statistics").resolve()
    output.mkdir(parents=True, exist_ok=True)
    classes: Counter[int] = Counter()
    sizes: Counter[str] = Counter()
    split_images: dict[str, int] = {}
    split_annotations: dict[str, int] = {}
    total_images = total_annotations = empty_images = 0
    object_counts: list[int] = []
    rows: list[dict[str, object]] = []
    for split in SPLITS:
        image_root = config.splits[split]
        label_root = config.root / "labels" / split
        images = image_files(image_root)
        split_images[split] = len(images)
        split_annotations[split] = 0
        total_images += len(images)
        for image in images:
            label = matching_label_path(image, image_root, label_root)
            annotations, _ = parse_annotation_file(label, set(config.names)) if label.is_file() else ([], [])
            if not annotations:
                empty_images += 1
            count = len(annotations)
            total_annotations += count
            split_annotations[split] += count
            object_counts.append(count)
            classes.update(item.class_id for item in annotations)
            sizes.update(size_bucket(item.area) for item in annotations)
            rows.append({"split": split, "image": image.name, "annotations": count})
    nonzero = [count for count in classes.values() if count > 0]
    imbalance_ratio = max(nonzero) / min(nonzero) if nonzero else None
    warnings: list[str] = []
    missing_classes = [config.names[index] for index in config.names if classes[index] == 0]
    if missing_classes:
        warnings.append(f"Classes with no annotations: {', '.join(missing_classes)}")
    if imbalance_ratio is not None and imbalance_ratio >= 5:
        warnings.append(f"Class imbalance ratio is {imbalance_ratio:.2f}:1; inspect per-class recall before training")
    if total_images and empty_images / total_images > 0.25:
        warnings.append("More than 25% of images are empty; confirm this is intentional hard-negative coverage")
    report = {
        "dataset": config.root.name,
        "imageCount": total_images,
        "annotationCount": total_annotations,
        "emptyImages": empty_images,
        "averageObjectsPerImage": round(mean(object_counts), 3) if object_counts else 0.0,
        "classDistribution": {config.names[index]: classes[index] for index in config.names},
        "objectSizeDistribution": dict(sizes),
        "splitImages": split_images,
        "splitAnnotations": split_annotations,
        "classImbalanceRatio": round(imbalance_ratio, 3) if imbalance_ratio is not None else None,
        "warnings": warnings,
    }
    write_json(output / "annotations.json", report)
    with (output / "images.csv").open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=("split", "image", "annotations"))
        writer.writeheader()
        writer.writerows(rows)
    if not args.no_plots:
        try:
            import matplotlib.pyplot as plt

            figure, axes = plt.subplots(1, 2, figsize=(12, 4.5))
            class_names = [config.names[index] for index in config.names]
            axes[0].bar(class_names, [classes[index] for index in config.names], color="#245DB3")
            axes[0].set_title("Class distribution")
            axes[0].tick_params(axis="x", rotation=35)
            axes[1].bar(SPLITS, [split_images[item] for item in SPLITS], color="#DC143C")
            axes[1].set_title("Images by split")
            figure.tight_layout()
            figure.savefig(output / "distribution.png", dpi=160)
            plt.close(figure)
        except ImportError:
            warnings.append("matplotlib is unavailable; graphs were skipped")
            write_json(output / "annotations.json", report)
    print(json.dumps(report, indent=2, ensure_ascii=False))
    print(f"Reports written to {output}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

