"""Train a TrafficOps detector using an Ultralytics-formatted dataset.

Examples:
    python training/train_model.py --task vehicle --data training/datasets/vehicles.yaml
    python training/train_model.py --task plate --data training/datasets/plates.yaml
    python training/train_model.py --task helmet --data training/datasets/helmets.yaml
"""

from __future__ import annotations

import argparse
from pathlib import Path

from ultralytics import YOLO


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Fine-tune a TrafficOps YOLO detector")
    parser.add_argument("--task", choices=("vehicle", "plate", "helmet"), required=True)
    parser.add_argument("--data", type=Path, required=True, help="Ultralytics dataset YAML")
    parser.add_argument("--base-model", default="models/yolo11s.pt")
    parser.add_argument("--epochs", type=int, default=120)
    parser.add_argument("--image-size", type=int, default=960)
    parser.add_argument("--batch", type=int, default=8)
    parser.add_argument("--device", default="0", help="CUDA index, 'cpu', or comma-separated GPUs")
    parser.add_argument("--workers", type=int, default=4)
    parser.add_argument("--patience", type=int, default=25)
    parser.add_argument("--project", default="training/runs")
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    if not args.data.is_file():
        raise SystemExit(f"Dataset configuration does not exist: {args.data}")
    if not Path(args.base_model).is_file():
        raise SystemExit(f"Base weights do not exist: {args.base_model}")

    model = YOLO(args.base_model)
    model.train(
        data=str(args.data),
        epochs=args.epochs,
        imgsz=args.image_size,
        batch=args.batch,
        device=args.device,
        workers=args.workers,
        patience=args.patience,
        project=args.project,
        name=f"trafficops-{args.task}",
        pretrained=True,
        close_mosaic=10,
        cos_lr=True,
        plots=True,
        seed=42,
    )


if __name__ == "__main__":
    main()
