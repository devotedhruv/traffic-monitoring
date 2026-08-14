"""Render deterministic YOLO annotation previews for human QA."""

from __future__ import annotations

import argparse
import random
from pathlib import Path

import cv2

try:
    from ml.scripts.common import DATASET_TO_MODEL, REPORT_ROOT, dataset_config_path, image_files, load_dataset_config, matching_label_path, parse_annotation_file
except ModuleNotFoundError:
    from common import DATASET_TO_MODEL, REPORT_ROOT, dataset_config_path, image_files, load_dataset_config, matching_label_path, parse_annotation_file


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Draw YOLO boxes and class labels into a review directory.")
    parser.add_argument("--dataset", choices=tuple(DATASET_TO_MODEL))
    parser.add_argument("--data", type=Path)
    parser.add_argument("--split", choices=("train", "val", "test"), default="train")
    parser.add_argument("--count", type=int, default=50)
    parser.add_argument("--seed", type=int, default=42)
    parser.add_argument("--output", type=Path)
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    if bool(args.dataset) == bool(args.data):
        raise SystemExit("Choose exactly one of --dataset or --data")
    if args.count < 1:
        raise SystemExit("--count must be positive")
    config = load_dataset_config(args.data or dataset_config_path(args.dataset))
    model_type = DATASET_TO_MODEL.get(args.dataset, Path(args.data).stem if args.data else "dataset")
    output = (args.output or REPORT_ROOT / "datasets" / f"{model_type}-preview").resolve()
    output.mkdir(parents=True, exist_ok=True)
    image_root = config.splits[args.split]
    label_root = config.root / "labels" / args.split
    images = image_files(image_root)
    random.Random(args.seed).shuffle(images)
    rendered = 0
    for image in images[:args.count]:
        frame = cv2.imread(str(image))
        if frame is None:
            continue
        annotations, _ = parse_annotation_file(matching_label_path(image, image_root, label_root), set(config.names))
        height, width = frame.shape[:2]
        for item in annotations:
            x1 = round((item.x_center - item.width / 2) * width)
            y1 = round((item.y_center - item.height / 2) * height)
            x2 = round((item.x_center + item.width / 2) * width)
            y2 = round((item.y_center + item.height / 2) * height)
            cv2.rectangle(frame, (x1, y1), (x2, y2), (38, 93, 179), 2)
            cv2.putText(frame, config.names[item.class_id], (x1, max(18, y1 - 5)), cv2.FONT_HERSHEY_SIMPLEX, 0.55, (220, 20, 60), 2)
        cv2.imwrite(str(output / image.name), frame)
        rendered += 1
    print(f"Rendered {rendered} annotation previews to {output}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

