"""Generate JSON, CSV, Markdown, dimensions, source, and validation dataset reports."""

from __future__ import annotations

import argparse
import csv
import json
from collections import Counter
from pathlib import Path

import cv2

try:
    from ml.scripts.common import DATASET_TO_MODEL, REPORT_ROOT, SPLITS, dataset_config_path, image_files, load_dataset_config, matching_label_path, parse_annotation_file, validate_dataset, write_json
except ModuleNotFoundError:
    from common import DATASET_TO_MODEL, REPORT_ROOT, SPLITS, dataset_config_path, image_files, load_dataset_config, matching_label_path, parse_annotation_file, validate_dataset, write_json


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Produce release-oriented dataset statistics in JSON, CSV, and Markdown.")
    parser.add_argument("--dataset", choices=tuple(DATASET_TO_MODEL))
    parser.add_argument("--data", type=Path)
    parser.add_argument("--output", type=Path)
    parser.add_argument("--no-plots", action="store_true")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    if bool(args.dataset) == bool(args.data):
        raise SystemExit("Choose exactly one of --dataset or --data")
    config = load_dataset_config(args.data or dataset_config_path(args.dataset))
    task = DATASET_TO_MODEL.get(args.dataset, Path(args.data).stem if args.data else "dataset")
    output = (args.output or REPORT_ROOT / "datasets" / config.root.name).resolve()
    output.mkdir(parents=True, exist_ok=True)
    validation = validate_dataset(config)
    class_counts: Counter[str] = Counter()
    size_counts: Counter[str] = Counter()
    dimensions: Counter[str] = Counter()
    source_counts: Counter[str] = Counter()
    rows: list[dict[str, object]] = []
    labeled = objects = empty_labels = corrupted = 0
    for split in SPLITS:
        image_root, label_root = config.splits[split], config.root / "labels" / split
        for image in image_files(image_root):
            frame = cv2.imread(str(image))
            if frame is None:
                corrupted += 1
                width = height = 0
            else:
                height, width = frame.shape[:2]
                dimensions[f"{width}x{height}"] += 1
            label = matching_label_path(image, image_root, label_root)
            annotations, _ = parse_annotation_file(label, set(config.names)) if label.is_file() else ([], [])
            if label.is_file():
                labeled += 1
            if not annotations:
                empty_labels += 1
            for annotation in annotations:
                class_counts[config.names[annotation.class_id]] += 1
                area = annotation.area
                size_counts["tiny" if area < .001 else "small" if area < .01 else "medium" if area < .1 else "large"] += 1
            objects += len(annotations)
            source = image.name.split("__", 1)[0] if "__" in image.name else "unknown"
            source_counts[source] += 1
            rows.append({"split": split, "image": image.name, "width": width, "height": height, "objects": len(annotations), "source": source})
    report = {
        "dataset": config.root.name, "task": task, "total_images": validation.images,
        "labeled_images": labeled, "unlabeled_images": validation.images - labeled,
        "total_objects": objects, "average_objects_per_image": round(objects / validation.images, 3) if validation.images else 0,
        "objects_per_class": dict(class_counts), "split_distribution": validation.split_counts,
        "source_distribution": dict(source_counts), "object_size_distribution": dict(size_counts),
        "image_dimensions": dict(dimensions), "empty_labels": empty_labels,
        "corruption_count": corrupted, "critical_errors": validation.errors,
        "warnings": validation.warnings,
    }
    nonzero_class_counts = [count for count in class_counts.values() if count]
    imbalance_ratio = max(nonzero_class_counts) / min(nonzero_class_counts) if nonzero_class_counts else None
    report["class_imbalance_ratio"] = round(imbalance_ratio, 3) if imbalance_ratio is not None else None
    quality_warnings: list[str] = []
    missing_classes = [name for name in config.names.values() if class_counts[name] == 0]
    if missing_classes:
        quality_warnings.append(f"Classes with no objects: {', '.join(missing_classes)}")
    if imbalance_ratio is not None and imbalance_ratio >= 5:
        quality_warnings.append(f"Class imbalance is {imbalance_ratio:.2f}:1; inspect per-class recall and sampling")
    report["quality_warnings"] = quality_warnings
    write_json(output / "dataset_report.json", report)
    with (output / "images.csv").open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=("split", "image", "width", "height", "objects", "source"))
        writer.writeheader(); writer.writerows(rows)
    markdown = [f"# Dataset report: {config.root.name}", "", f"- Images: {validation.images}", f"- Objects: {objects}", f"- Critical errors: {validation.errors}", f"- Warnings: {validation.warnings}", "", "## Classes", ""]
    markdown.extend(f"- {name}: {count}" for name, count in sorted(class_counts.items()))
    (output / "dataset_report.md").write_text("\n".join(markdown) + "\n", encoding="utf-8")
    if not args.no_plots:
        try:
            import matplotlib
            matplotlib.use("Agg")
            import matplotlib.pyplot as plt
            figure, axes = plt.subplots(1, 2, figsize=(12, 4))
            axes[0].bar(class_counts.keys(), class_counts.values(), color="#2c5fb3")
            axes[0].set_title("Objects per class"); axes[0].tick_params(axis="x", rotation=30)
            axes[1].bar(validation.split_counts.keys(), validation.split_counts.values(), color="#dc143c")
            axes[1].set_title("Images per split")
            figure.tight_layout(); figure.savefig(output / "dataset_distribution.png", dpi=160); plt.close(figure)
        except ImportError:
            pass
    print(json.dumps(report, indent=2, ensure_ascii=False))
    return 1 if validation.errors else 0


if __name__ == "__main__":
    raise SystemExit(main())
