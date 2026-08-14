"""Compare evaluated models without reducing production selection to mAP alone."""

from __future__ import annotations

import argparse
import json
import subprocess
import sys
from pathlib import Path
from typing import Any

try:
    from ml.scripts.common import REPORT_ROOT, format_table, write_json
except ModuleNotFoundError:
    from common import REPORT_ROOT, format_table, write_json


def metric_report(value: Path, args: argparse.Namespace) -> Path:
    if value.is_file() and value.name == "metrics.json":
        return value
    if value.is_dir() and (value / "metrics.json").is_file():
        return value / "metrics.json"
    candidate = REPORT_ROOT / value.stem / "metrics.json"
    if candidate.is_file():
        return candidate
    if value.is_file() and value.suffix.lower() == ".pt" and args.data:
        command = [
            sys.executable, str(Path(__file__).with_name("evaluate_model.py")),
            "--model", str(value), "--data", str(args.data), "--split", args.split,
            "--imgsz", str(args.imgsz), "--batch", str(args.batch),
            "--device", args.device, "--output", str(REPORT_ROOT / value.stem),
        ]
        completed = subprocess.run(command, check=False)
        if completed.returncode == 0 and candidate.is_file():
            return candidate
    raise FileNotFoundError(f"No metrics.json found for {value}; run evaluate_model.py first")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Compare evaluated YOLO models by accuracy, latency, and model size.")
    parser.add_argument("models", nargs="*", type=Path, help="Model files, report directories, or metrics.json files")
    parser.add_argument("--model-a", type=Path, help="First model/report (named alternative to positional inputs)")
    parser.add_argument("--model-b", type=Path, help="Second model/report (named alternative to positional inputs)")
    parser.add_argument("--data", type=Path, help="Dataset YAML used to evaluate .pt files without existing reports")
    parser.add_argument("--split", choices=("val", "test"), default="test")
    parser.add_argument("--imgsz", type=int, default=640)
    parser.add_argument("--batch", type=int, default=16)
    parser.add_argument("--device", default="cpu")
    parser.add_argument("--output", type=Path, default=REPORT_ROOT / "model-comparison.json")
    return parser.parse_args()


def display(value: Any, digits: int = 4) -> str:
    if value is None:
        return "n/a"
    if isinstance(value, (int, float)):
        return f"{value:.{digits}f}"
    return str(value)


def main() -> int:
    args = parse_args()
    if args.model_a or args.model_b:
        if not args.model_a or not args.model_b or args.models:
            raise SystemExit("Use both --model-a and --model-b, or use positional models")
        args.models = [args.model_a, args.model_b]
    if len(args.models) < 2:
        raise SystemExit("Provide at least two evaluated models or reports")
    reports = [json.loads(metric_report(item, args).read_text(encoding="utf-8")) for item in args.models]
    rows: list[list[str]] = []
    comparison: list[dict[str, Any]] = []
    for report in reports:
        latency = report.get("latencyMs", {}).get("inference")
        size_mb = float(report.get("modelSizeBytes", 0)) / (1024 * 1024)
        record = {
            "model": Path(str(report.get("model", "unknown"))).name,
            "precision": report.get("precision"),
            "recall": report.get("recall"),
            "mAP50": report.get("mAP50"),
            "mAP50_95": report.get("mAP50_95"),
            "inferenceLatencyMs": latency,
            "modelSizeMB": round(size_mb, 3),
            "parameterCount": report.get("parameterCount"),
        }
        comparison.append(record)
        rows.append([
            record["model"], display(record["precision"]), display(record["recall"]),
            display(record["mAP50"]), display(record["mAP50_95"]), display(latency, 2), display(size_mb, 2), display(record["parameterCount"], 0),
        ])
    print(format_table(
        ("model", "precision", "recall", "mAP50", "mAP50-95", "latency ms", "size MB", "parameters"), rows,
    ))
    print("\nNo model is auto-promoted. Review class-specific errors, latency budget, and fixed-test-set regressions.")
    write_json(args.output, {
        "models": comparison,
        "decision": "manual_review_required",
        "guidance": "Do not promote on a marginal aggregate mAP increase without reviewing recall, per-class errors, latency, and deployment constraints.",
    })
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
