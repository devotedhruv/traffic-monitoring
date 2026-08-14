"""Warmup-aware CPU/CUDA YOLO inference benchmark with measured timings only."""

from __future__ import annotations

import argparse
import json
import time
from pathlib import Path
from statistics import mean

try:
    from ml.scripts.common import REPORT_ROOT, utc_now, write_json
except ModuleNotFoundError:
    from common import REPORT_ROOT, utc_now, write_json


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Measure YOLO preprocess, inference, postprocess, FPS, size, and parameters.")
    parser.add_argument("--model", type=Path, required=True)
    parser.add_argument("--source", type=Path, required=True, help="Representative image, directory, or video")
    parser.add_argument("--device", default="cpu")
    parser.add_argument("--imgsz", type=int, default=640)
    parser.add_argument("--warmup", type=int, default=5)
    parser.add_argument("--iterations", type=int, default=30)
    parser.add_argument("--output", type=Path)
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    if not args.model.is_file() or not args.source.is_file():
        raise SystemExit("--model and --source must exist")
    if args.warmup < 0 or args.iterations < 1:
        raise SystemExit("--warmup must be >= 0 and --iterations must be positive")
    try:
        import torch
        from ultralytics import YOLO
    except ImportError as exc:
        raise SystemExit("Install ml/requirements-ml.txt before benchmarking") from exc
    if str(args.device).lower() != "cpu" and not torch.cuda.is_available():
        raise SystemExit("CUDA was requested but is unavailable. Re-run with --device cpu.")
    model = YOLO(str(args.model.resolve()))
    try:
        import cv2
        benchmark_input = cv2.imread(str(args.source))
        if benchmark_input is None:
            capture = cv2.VideoCapture(str(args.source))
            ok, benchmark_input = capture.read()
            capture.release()
            if not ok or benchmark_input is None:
                raise ValueError("OpenCV could not decode an image or first video frame")
    except ImportError as exc:
        raise SystemExit("OpenCV is required to load benchmark media") from exc
    for _ in range(args.warmup):
        model.predict(source=benchmark_input, imgsz=args.imgsz, device=args.device, verbose=False, stream=False)
    preprocess: list[float] = []; inference: list[float] = []; postprocess: list[float] = []; wall: list[float] = []
    result_counts: list[int] = []
    for _ in range(args.iterations):
        started = time.perf_counter()
        results = model.predict(source=benchmark_input, imgsz=args.imgsz, device=args.device, verbose=False, stream=False)
        wall.append((time.perf_counter() - started) * 1000)
        result_counts.append(len(results))
        if results:
            speed = results[0].speed or {}
            preprocess.append(float(speed.get("preprocess", 0)))
            inference.append(float(speed.get("inference", 0)))
            postprocess.append(float(speed.get("postprocess", 0)))
    average_wall = mean(wall)
    report = {
        "benchmarkedAt": utc_now(), "model": str(args.model.resolve()), "source": str(args.source.resolve()),
        "device": str(args.device), "imgsz": args.imgsz, "warmupIterations": args.warmup,
        "measuredIterations": args.iterations, "preprocessMs": round(mean(preprocess), 4) if preprocess else None,
        "inferenceMs": round(mean(inference), 4) if inference else None,
        "postprocessMs": round(mean(postprocess), 4) if postprocess else None,
        "wallLatencyMs": round(average_wall, 4),
        "approximateFps": round(mean(result_counts) * 1000 / average_wall, 3) if average_wall else None,
        "modelSizeBytes": args.model.stat().st_size,
        "parameterCount": sum(parameter.numel() for parameter in model.model.parameters()),
        "cudaAvailable": bool(torch.cuda.is_available()),
    }
    output = args.output or REPORT_ROOT / args.model.stem / f"benchmark-{args.device}.json"
    write_json(output, report)
    print(json.dumps(report, indent=2, ensure_ascii=False)); print(f"Benchmark report: {output}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
