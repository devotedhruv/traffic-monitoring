"""Evaluate a YOLO detector and export production-reviewable metrics."""

from __future__ import annotations

import argparse
import csv
import json
import os
from pathlib import Path
from typing import Any

os.environ.setdefault("MPLBACKEND", "Agg")
os.environ.setdefault("MPLCONFIGDIR", "/tmp/sadakdrishti-matplotlib")

try:
    from ml.scripts.common import (
        REPORT_ROOT, load_dataset_config, resolved_dataset_yaml, utc_now, write_json,
    )
except ModuleNotFoundError:
    from common import REPORT_ROOT, load_dataset_config, resolved_dataset_yaml, utc_now, write_json


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Evaluate vehicle, plate, or helmet weights on a fixed YOLO split.")
    parser.add_argument("--model", type=Path, required=True, help="Trained .pt weights")
    parser.add_argument("--data", type=Path, required=True, help="YOLO dataset YAML")
    parser.add_argument("--split", choices=("val", "test"), default="test")
    parser.add_argument("--imgsz", type=int, default=640)
    parser.add_argument("--batch", type=int, default=16)
    parser.add_argument("--device", default="cpu")
    parser.add_argument("--workers", type=int, default=4)
    parser.add_argument("--conf", type=float, default=0.25)
    parser.add_argument("--iou", type=float, default=0.6)
    parser.add_argument("--output", type=Path, help="Report directory (default: ml/reports/<model-stem>)")
    parser.add_argument("--save-predictions", action="store_true", help="Save annotated prediction images")
    return parser.parse_args()


def _float(value: Any) -> float | None:
    try:
        return round(float(value), 6)
    except (TypeError, ValueError):
        return None


def summarize(results: Any, names: dict[int, str], model: Path, data: Path, split: str) -> dict[str, Any]:
    box = results.box
    class_metrics: list[dict[str, Any]] = []
    evaluated_classes = [int(value) for value in getattr(box, "ap_class_index", range(len(names)))]
    class_positions = {class_id: position for position, class_id in enumerate(evaluated_classes)}
    for index, name in names.items():
        try:
            position = class_positions[index]
            precision, recall, map50, map50_95 = box.class_result(position)
        except (IndexError, KeyError, TypeError, ValueError):
            precision = recall = map50 = map50_95 = None
        class_metrics.append({
            "classId": index,
            "className": name,
            "precision": _float(precision),
            "recall": _float(recall),
            "mAP50": _float(map50),
            "mAP50_95": _float(map50_95),
        })
    matrix = getattr(getattr(results, "confusion_matrix", None), "matrix", None)
    false_positives = false_negatives = None
    if matrix is not None and getattr(matrix, "shape", (0, 0))[0] == len(names) + 1:
        true_positives = float(matrix.diagonal()[:len(names)].sum())
        false_positives = int(matrix[:len(names), :].sum() - true_positives)
        false_negatives = int(matrix[:, :len(names)].sum() - true_positives)
    speed = getattr(results, "speed", {}) or {}
    return {
        "schemaVersion": 1,
        "evaluatedAt": utc_now(),
        "model": str(model.resolve()),
        "modelSizeBytes": model.stat().st_size,
        "data": str(data.resolve()),
        "datasetVersion": None,
        "split": split,
        "precision": _float(box.mp),
        "recall": _float(box.mr),
        "mAP50": _float(box.map50),
        "mAP50_95": _float(box.map),
        "falsePositives": false_positives,
        "falseNegatives": false_negatives,
        "latencyMs": {
            "preprocess": _float(speed.get("preprocess")),
            "inference": _float(speed.get("inference")),
            "postprocess": _float(speed.get("postprocess")),
        },
        "classes": class_metrics,
        "artifacts": {
            "confusionMatrix": "confusion_matrix.png",
            "normalizedConfusionMatrix": "confusion_matrix_normalized.png",
            "ultralyticsDirectory": "ultralytics",
        },
    }


def main() -> int:
    args = parse_args()
    if not args.model.is_file():
        raise SystemExit(f"Model weights do not exist: {args.model}")
    config = load_dataset_config(args.data)
    if not config.splits[args.split].is_dir():
        raise SystemExit(f"Dataset split does not exist: {config.splits[args.split]}")
    output = (args.output or REPORT_ROOT / args.model.stem).resolve()
    output.mkdir(parents=True, exist_ok=True)
    try:
        from ultralytics import YOLO
    except ImportError as exc:
        raise SystemExit("Ultralytics is not installed. Install ml/requirements-ml.txt") from exc
    temporary = resolved_dataset_yaml(config)
    temporary_path = Path(temporary.name)
    temporary.close()
    try:
        model = YOLO(str(args.model.resolve()))
        try:
            parameter_count = sum(parameter.numel() for parameter in model.model.parameters())
        except (AttributeError, TypeError):
            parameter_count = None
        results = model.val(
            data=str(temporary_path), split=args.split, imgsz=args.imgsz, batch=args.batch,
            device=args.device, workers=args.workers, conf=args.conf, iou=args.iou,
            plots=True, save_json=True, save_txt=args.save_predictions,
            project=str(output), name="ultralytics", exist_ok=True,
        )
    finally:
        temporary_path.unlink(missing_ok=True)
    report = summarize(results, config.names, args.model, args.data, args.split)
    metadata_path = config.root / "dataset_metadata.json"
    dataset_metadata = json.loads(metadata_path.read_text(encoding="utf-8")) if metadata_path.is_file() else {}
    report["datasetVersion"] = dataset_metadata.get("dataset_version") or config.root.name
    report["parameterCount"] = parameter_count
    write_json(output / "metrics.json", report)
    with (output / "per_class_metrics.csv").open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=("classId", "className", "precision", "recall", "mAP50", "mAP50_95"))
        writer.writeheader()
        writer.writerows(report["classes"])
    ultralytics_dir = Path(getattr(results, "save_dir", output / "ultralytics"))
    report["artifacts"]["ultralyticsDirectory"] = str(ultralytics_dir)
    for filename in ("confusion_matrix.png", "confusion_matrix_normalized.png"):
        source = ultralytics_dir / filename
        if source.is_file():
            (output / filename).write_bytes(source.read_bytes())
    write_json(output / "metrics.json", report)
    print(json.dumps(report, indent=2, ensure_ascii=False))
    print(f"Evaluation report: {output / 'metrics.json'}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
