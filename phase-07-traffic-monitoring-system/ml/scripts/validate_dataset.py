"""Validate a SadakDrishti YOLO dataset before training."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

try:
    from ml.scripts.common import (
        DATASET_TO_MODEL, dataset_config_path, load_dataset_config, validate_dataset,
        validate_expected_classes, write_json,
    )
except ModuleNotFoundError:
    from common import (
        DATASET_TO_MODEL, dataset_config_path, load_dataset_config, validate_dataset,
        validate_expected_classes, write_json,
    )


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Check images, labels, YOLO boxes, classes, duplicates, and split layout.")
    parser.add_argument("--dataset", choices=tuple(DATASET_TO_MODEL), help="Bundled dataset name")
    parser.add_argument("--data", type=Path, help="Explicit dataset YAML instead of --dataset")
    parser.add_argument("--report", type=Path, help="Optional JSON report path")
    parser.add_argument("--skip-image-decode", action="store_true", help="Skip OpenCV corruption checks")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    if bool(args.dataset) == bool(args.data):
        raise SystemExit("Choose exactly one of --dataset or --data")
    model_type = DATASET_TO_MODEL[args.dataset] if args.dataset else Path(args.data).stem.rstrip("s")
    config = load_dataset_config(args.data or dataset_config_path(args.dataset))
    if model_type in {"vehicle", "plate", "helmet"}:
        validate_expected_classes(model_type, config.names)
    report = validate_dataset(config, check_images=not args.skip_image_decode)
    print(json.dumps(report.as_dict(), indent=2, ensure_ascii=False))
    if args.report:
        write_json(args.report, report.as_dict())
    return 1 if report.errors else 0


if __name__ == "__main__":
    raise SystemExit(main())

