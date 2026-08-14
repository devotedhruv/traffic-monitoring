"""Mine sparse, deduplicated hard examples for the next active-learning cycle."""

from __future__ import annotations

import argparse
import json
import logging
from pathlib import Path
from typing import Any, Iterator

import cv2
import numpy as np

try:
    from ml.scripts.common import IMAGE_EXTENSIONS, ML_ROOT, MODEL_TYPES, utc_now
except ModuleNotFoundError:
    from common import IMAGE_EXTENSIONS, ML_ROOT, MODEL_TYPES, utc_now


LOG = logging.getLogger("sadakdrishti.ml.hard_examples")
VIDEO_EXTENSIONS = {".avi", ".m4v", ".mkv", ".mov", ".mp4", ".mpeg", ".mpg", ".webm"}
CATEGORIES = {
    "vehicle": ("false_positive", "false_negative", "wrong_class", "low_confidence"),
    "plate": ("missed", "false_positive", "low_confidence", "poor_crop"),
    "helmet": ("false_helmet", "false_no_helmet", "uncertain", "difficult_head"),
}


def dhash(frame: np.ndarray) -> int:
    gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
    sample = cv2.resize(gray, (9, 8), interpolation=cv2.INTER_AREA)
    value = 0
    for bit in (sample[:, 1:] > sample[:, :-1]).flat:
        value = (value << 1) | int(bit)
    return value


def frames(source: Path, every_seconds: float) -> Iterator[tuple[Path, np.ndarray, float, int]]:
    paths = [source] if source.is_file() else sorted(path for path in source.rglob("*") if path.is_file())
    for path in paths:
        if path.suffix.lower() in IMAGE_EXTENSIONS:
            frame = cv2.imread(str(path))
            if frame is not None:
                yield path, frame, 0.0, 0
            continue
        if path.suffix.lower() not in VIDEO_EXTENSIONS:
            continue
        capture = cv2.VideoCapture(str(path))
        fps = float(capture.get(cv2.CAP_PROP_FPS) or 30.0)
        stride = max(1, round(every_seconds * fps))
        index = 0
        while True:
            capture.set(cv2.CAP_PROP_POS_FRAMES, index)
            ok, frame = capture.read()
            if not ok or frame is None:
                break
            yield path, frame, index / fps, index
            index += stride
        capture.release()


def xywh_to_xyxy(item: tuple[float, float, float, float], width: int, height: int) -> tuple[float, float, float, float]:
    x, y, box_width, box_height = item
    return ((x - box_width / 2) * width, (y - box_height / 2) * height,
            (x + box_width / 2) * width, (y + box_height / 2) * height)


def iou(first: tuple[float, float, float, float], second: tuple[float, float, float, float]) -> float:
    x1, y1 = max(first[0], second[0]), max(first[1], second[1])
    x2, y2 = min(first[2], second[2]), min(first[3], second[3])
    intersection = max(0.0, x2 - x1) * max(0.0, y2 - y1)
    first_area = max(0.0, first[2] - first[0]) * max(0.0, first[3] - first[1])
    second_area = max(0.0, second[2] - second[0]) * max(0.0, second[3] - second[1])
    return intersection / max(first_area + second_area - intersection, 1e-9)


def ground_truth(image: Path, labels: Path | None, width: int, height: int) -> list[tuple[int, tuple[float, float, float, float]]]:
    if labels is None:
        return []
    label = labels / f"{image.stem}.txt"
    if not label.is_file():
        return []
    output = []
    for line in label.read_text(encoding="utf-8").splitlines():
        fields = line.split()
        if len(fields) != 5:
            continue
        output.append((int(fields[0]), xywh_to_xyxy(tuple(float(value) for value in fields[1:]), width, height)))
    return output


def classify(
    model_type: str,
    predictions: list[tuple[int, float, tuple[float, float, float, float]]],
    truth: list[tuple[int, tuple[float, float, float, float]]],
    low: float,
    high: float,
) -> list[str]:
    categories: set[str] = set()
    if not truth:
        uncertain = any(low <= confidence < high for _, confidence, _ in predictions)
        if model_type == "plate" and uncertain:
            categories.add("low_confidence")
        elif model_type == "helmet" and uncertain:
            categories.add("low_confidence")
        elif model_type == "vehicle" and uncertain:
            categories.add("uncertain")
        return sorted(categories)
    matched_truth: set[int] = set()
    for predicted_class, confidence, predicted_box in predictions:
        best_index, best_overlap = -1, 0.0
        for index, (_, true_box) in enumerate(truth):
            overlap = iou(predicted_box, true_box)
            if overlap > best_overlap:
                best_index, best_overlap = index, overlap
        if best_index < 0 or best_overlap < 0.5:
            categories.add("false_positive")
            continue
        matched_truth.add(best_index)
        true_class = truth[best_index][0]
        if predicted_class != true_class:
            if model_type == "vehicle":
                categories.add("wrong_class")
            elif model_type == "helmet":
                categories.add("false_helmet" if predicted_class == 0 else "false_no_helmet")
        elif confidence < high:
            categories.add("low_confidence" if model_type in {"plate", "vehicle"} else "uncertain")
    if len(matched_truth) < len(truth):
        categories.add("false_negative" if model_type == "vehicle" else "missed" if model_type == "plate" else "uncertain")
    return sorted(category for category in categories if category in CATEGORIES[model_type])


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Collect uncertain or incorrect frames without blindly storing every frame.")
    parser.add_argument("--type", choices=MODEL_TYPES, required=True)
    parser.add_argument("--model", type=Path, required=True)
    parser.add_argument("--input", type=Path, required=True, help="Image/video file or directory")
    parser.add_argument("--output", type=Path, default=ML_ROOT / "hard_examples")
    parser.add_argument("--labels", type=Path, help="Optional YOLO labels for objective FP/FN/wrong-class mining")
    parser.add_argument("--low-confidence", type=float, default=0.15)
    parser.add_argument("--high-confidence", type=float, default=0.55)
    parser.add_argument("--imgsz", type=int, default=640)
    parser.add_argument("--device", default="cpu")
    parser.add_argument("--every-seconds", type=float, default=2.0)
    parser.add_argument("--duplicate-distance", type=int, default=4)
    parser.add_argument("--max-examples", type=int, default=500)
    parser.add_argument("--camera-id", default="unknown")
    parser.add_argument("--track-id", type=int)
    parser.add_argument("--manual-review", action="store_true", help="Mark every saved candidate as pending human review")
    parser.add_argument("--force-category", choices=tuple(sorted({item for values in CATEGORIES.values() for item in values})), help="Manual review category; must be valid for --type")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")
    if not args.model.is_file() or not args.input.exists():
        raise SystemExit("--model and --input must exist")
    if not 0 <= args.low_confidence < args.high_confidence <= 1:
        raise SystemExit("Confidence thresholds must satisfy 0 <= low < high <= 1")
    if args.force_category and args.force_category not in CATEGORIES[args.type]:
        raise SystemExit(f"{args.force_category} is not a valid {args.type} hard-example category")
    from ultralytics import YOLO

    model = YOLO(str(args.model.resolve()))
    output = args.output / args.type
    output.mkdir(parents=True, exist_ok=True)
    manifest = output / "manifest.jsonl"
    hashes: list[int] = []
    saved = 0
    with manifest.open("a", encoding="utf-8") as handle:
        for source, frame, timestamp, frame_index in frames(args.input, args.every_seconds):
            result = model.predict(frame, conf=args.low_confidence, imgsz=args.imgsz, device=args.device, verbose=False)[0]
            predictions: list[tuple[int, float, tuple[float, float, float, float]]] = []
            if result.boxes is not None:
                predictions = [
                    (int(class_id), float(confidence), tuple(float(value) for value in box))
                    for class_id, confidence, box in zip(
                        result.boxes.cls.tolist(), result.boxes.conf.tolist(), result.boxes.xyxy.tolist()
                    )
                ]
            truth = ground_truth(source, args.labels, frame.shape[1], frame.shape[0])
            categories = classify(args.type, predictions, truth, args.low_confidence, args.high_confidence)
            if args.force_category:
                categories = [args.force_category]
            if not categories:
                continue
            fingerprint = dhash(frame)
            if any((fingerprint ^ existing).bit_count() <= args.duplicate_distance for existing in hashes[-200:]):
                continue
            hashes.append(fingerprint)
            for category in categories:
                directory = output / category
                directory.mkdir(parents=True, exist_ok=True)
                filename = f"{args.camera_id}__{source.stem}__f{frame_index:010d}__t{round(timestamp * 1000):012d}.jpg"
                destination = directory / filename
                cv2.imwrite(str(destination), frame, [cv2.IMWRITE_JPEG_QUALITY, 92])
                handle.write(json.dumps({
                    "createdAt": utc_now(), "modelType": args.type, "category": category,
                    "image": str(destination), "source": str(source.resolve()),
                    "timestampSeconds": round(timestamp, 3), "cameraId": args.camera_id,
                    "trackId": args.track_id, "predictionCount": len(predictions),
                    "predictions": [
                        {"classId": class_id, "confidence": round(confidence, 4), "box": [round(value, 2) for value in box]}
                        for class_id, confidence, box in predictions
                    ],
                    "reviewStatus": "pending" if args.manual_review else "unreviewed",
                    "hasGroundTruth": bool(truth),
                }, ensure_ascii=False) + "\n")
            saved += 1
            if saved >= args.max_examples:
                break
    LOG.info("Saved %d deduplicated hard-example frames under %s", saved, output)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
