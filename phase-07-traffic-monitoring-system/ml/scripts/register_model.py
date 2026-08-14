"""Register evaluated detector weights and their measured metadata without promoting them."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

try:
    from ml.scripts.common import MODEL_TYPES, REPOSITORY_ROOT, register_model
except ModuleNotFoundError:
    from common import MODEL_TYPES, REPOSITORY_ROOT, register_model


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Copy one evaluated model into the versioned SadakDrishti registry.")
    parser.add_argument("--type", choices=MODEL_TYPES, required=True)
    parser.add_argument("--model", type=Path, required=True)
    parser.add_argument("--version", required=True)
    parser.add_argument("--base-model", required=True)
    parser.add_argument("--dataset-version", required=True)
    parser.add_argument("--metrics", type=Path, required=True, help="metrics.json produced by evaluate_model.py")
    parser.add_argument("--training-metadata", type=Path, help="sadakdrishti-training.json")
    parser.add_argument("--notes", default="")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    if not args.metrics.is_file():
        raise SystemExit(f"Evaluation metrics do not exist: {args.metrics}")
    metrics = json.loads(args.metrics.read_text(encoding="utf-8"))
    if Path(str(metrics.get("model", ""))).name != args.model.name:
        raise SystemExit("Evaluation metrics refer to a different model file")
    required = ("precision", "recall", "mAP50", "mAP50_95", "data", "split", "evaluatedAt")
    if any(metrics.get(key) is None for key in required):
        raise SystemExit("Evaluation metrics are incomplete; precision, recall, mAP, data, split, and date are required")
    training = {}
    if args.training_metadata:
        training = json.loads(args.training_metadata.read_text(encoding="utf-8"))
    try:
        metrics_path = args.metrics.resolve().relative_to(REPOSITORY_ROOT).as_posix()
    except ValueError:
        metrics_path = args.metrics.name
    evaluation_dataset = Path(str(metrics["data"])).expanduser()
    try:
        evaluation_dataset_value = evaluation_dataset.resolve().relative_to(REPOSITORY_ROOT).as_posix()
    except ValueError:
        evaluation_dataset_value = evaluation_dataset.name
    record = register_model(args.type, args.model, {
        "version": args.version, "baseModel": args.base_model, "datasetVersion": args.dataset_version,
        "epochs": training.get("epochs"), "imageSize": training.get("imgsz"),
        "precision": metrics["precision"], "recall": metrics["recall"],
        "mAP50": metrics["mAP50"], "mAP50_95": metrics["mAP50_95"],
        "evaluationDataset": evaluation_dataset_value, "evaluationSplit": metrics["split"],
        "evaluatedAt": metrics["evaluatedAt"], "metricsPath": metrics_path,
        "notes": args.notes,
    })
    print(json.dumps(record, indent=2, ensure_ascii=False)); return 0


if __name__ == "__main__":
    raise SystemExit(main())
