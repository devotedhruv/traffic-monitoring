"""Shared Ultralytics YOLO11 fine-tuning entry point used by task wrappers."""

from __future__ import annotations

import argparse
import json
import logging
import platform
import shlex
import sys
from pathlib import Path
from typing import Any

try:
    from ml.scripts.common import (
        CONFIG_ROOT, ML_ROOT, MODEL_TYPES, dataset_config_path, git_commit, load_dataset_config,
        load_training_defaults, resolved_dataset_yaml, utc_now, validate_dataset, validate_expected_classes,
    )
except ModuleNotFoundError:
    from common import (
        CONFIG_ROOT, ML_ROOT, MODEL_TYPES, dataset_config_path, git_commit, load_dataset_config,
        load_training_defaults, resolved_dataset_yaml, utc_now, validate_dataset, validate_expected_classes,
    )


LOG = logging.getLogger("sadakdrishti.ml.train")


def add_training_arguments(parser: argparse.ArgumentParser, model_type: str) -> None:
    defaults = load_training_defaults(model_type)
    parser.add_argument("--data", type=Path, default=dataset_config_path(model_type), help="YOLO dataset YAML")
    parser.add_argument("--model", default=defaults["model"], help="Pretrained YOLO11 weights or Ultralytics model name")
    parser.add_argument("--epochs", type=int, default=defaults["epochs"])
    parser.add_argument("--imgsz", type=int, default=defaults["imgsz"])
    parser.add_argument("--batch", type=int, default=defaults["batch"], help="Batch size; -1 lets Ultralytics auto-size")
    parser.add_argument("--device", default=defaults["device"], help="CUDA index, comma-separated GPUs, mps, or cpu")
    parser.add_argument("--workers", type=int, default=defaults["workers"])
    parser.add_argument("--patience", type=int, default=defaults["patience"])
    parser.add_argument("--project", type=Path, default=ML_ROOT / "runs" / model_type)
    parser.add_argument("--name", default=f"{model_type}-experiment")
    parser.add_argument("--resume", nargs="?", const=True, default=False, help="Resume last run or a supplied checkpoint")
    parser.add_argument("--seed", type=int, default=defaults["seed"])
    parser.add_argument("--cache", action="store_true", help="Cache images when storage/RAM permits")
    parser.add_argument("--skip-validation", action="store_true", help="Skip SadakDrishti preflight validation")


def parse_task_args(model_type: str, description: str) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=description)
    add_training_arguments(parser, model_type)
    return parser.parse_args()


def _model_reference(value: str) -> str:
    path = Path(value).expanduser()
    if path.is_file():
        return str(path.resolve())
    repository_candidate = (Path.cwd() / path).resolve()
    if repository_candidate.is_file():
        return str(repository_candidate)
    bundled_candidate = (ML_ROOT.parent / "models" / path.name).resolve()
    if bundled_candidate.is_file():
        return str(bundled_candidate)
    # Ultralytics names such as yolo11s.pt are intentionally allowed. The
    # framework may resolve or download them when network access is available.
    return value


def run_training(model_type: str, args: argparse.Namespace) -> Path:
    if model_type not in MODEL_TYPES:
        raise ValueError(f"Unsupported model type: {model_type}")
    config = load_dataset_config(args.data)
    validate_expected_classes(model_type, config.names)
    split_evidence = config.root / "split_manifest.json"
    merged_evidence = config.root / "provenance.jsonl"
    if not split_evidence.is_file() and not merged_evidence.is_file():
        raise SystemExit(
            f"Dataset provenance/split evidence is missing under {config.root}. "
            "Create it with split_dataset.py or dataset_cli.py merge before training."
        )
    report = validate_dataset(config, check_images=not args.skip_validation)
    if report.errors:
        raise SystemExit(
            f"Dataset validation found {report.errors} critical errors. "
            f"Run: python ml/scripts/validate_dataset.py --data {args.data}"
        )
    if report.images == 0:
        raise SystemExit(f"Dataset is empty: add images and labels under {config.root}")
    defaults = load_training_defaults(model_type)
    augmentation = defaults.get("augmentation", {})
    if not isinstance(augmentation, dict):
        augmentation = {}
    try:
        from ultralytics import YOLO
        import torch
        import ultralytics
    except ImportError as exc:
        raise SystemExit("Ultralytics is not installed. Install ml/requirements-ml.txt") from exc
    temporary = resolved_dataset_yaml(config)
    temporary_path = Path(temporary.name)
    temporary.close()
    started_at = utc_now()
    try:
        model = YOLO(_model_reference(args.model))
        training_args: dict[str, Any] = {
            "data": str(temporary_path),
            "epochs": args.epochs,
            "imgsz": args.imgsz,
            "batch": args.batch,
            "device": args.device,
            "workers": args.workers,
            "patience": args.patience,
            "project": str(args.project),
            "name": args.name,
            "resume": args.resume,
            "pretrained": True,
            "seed": args.seed,
            "deterministic": True,
            "cache": args.cache,
            "plots": True,
            "save": True,
            "close_mosaic": defaults.get("close_mosaic", 10),
            "cos_lr": defaults.get("cos_lr", True),
            **augmentation,
        }
        LOG.info("Training %s from %s with data %s", model_type, args.model, config.root)
        results = model.train(**training_args)
        save_dir = Path(getattr(results, "save_dir", Path(args.project) / args.name)).resolve()
        dataset_metadata_path = config.root / "dataset_metadata.json"
        dataset_metadata = json.loads(dataset_metadata_path.read_text(encoding="utf-8")) if dataset_metadata_path.is_file() else {}
        cuda_available = bool(torch.cuda.is_available())
        (save_dir / "sadakdrishti-training.json").write_text(json.dumps({
            "schemaVersion": 1,
            "modelType": model_type,
            "baseModel": args.model,
            "dataset": str(config.root),
            "datasetVersion": dataset_metadata.get("dataset_version") or config.root.name,
            "seed": args.seed,
            "epochs": args.epochs,
            "imgsz": args.imgsz,
            "batch": args.batch,
            "gitCommit": git_commit(),
            "startedAt": started_at,
            "finishedAt": utc_now(),
            "command": shlex.join(sys.argv),
            "environment": {
                "python": platform.python_version(),
                "platform": platform.platform(),
                "ultralytics": getattr(ultralytics, "__version__", None),
                "torch": getattr(torch, "__version__", None),
                "cudaAvailable": cuda_available,
                "cudaVersion": getattr(torch.version, "cuda", None),
                "gpu": torch.cuda.get_device_name(0) if cuda_available else None,
            },
            "arguments": training_args,
        }, indent=2, default=str) + "\n", encoding="utf-8")
        print(f"Training outputs: {save_dir}")
        return save_dir
    finally:
        temporary_path.unlink(missing_ok=True)


def generic_main() -> int:
    parser = argparse.ArgumentParser(description="Fine-tune a SadakDrishti YOLO11 detector")
    parser.add_argument("--type", choices=MODEL_TYPES, required=True)
    known, remaining = parser.parse_known_args()
    task_parser = argparse.ArgumentParser(description=f"Train the {known.type} detector")
    add_training_arguments(task_parser, known.type)
    args = task_parser.parse_args(remaining)
    run_training(known.type, args)
    return 0


if __name__ == "__main__":
    raise SystemExit(generic_main())
