"""Sample representative frames from traffic videos without 30-FPS duplication."""

from __future__ import annotations

import argparse
import hashlib
import json
import logging
import os
from pathlib import Path
from typing import Any

import cv2
import numpy as np

try:
    from ml.scripts.common import METADATA_ROOT, utc_now
    from ml.scripts.dataset_registry import portable_path, register_source, safe_identifier, source_reference
except ModuleNotFoundError:
    from common import METADATA_ROOT, utc_now
    from dataset_registry import portable_path, register_source, safe_identifier, source_reference


LOG = logging.getLogger("sadakdrishti.ml.extract_frames")
VIDEO_EXTENSIONS = {".avi", ".m4v", ".mkv", ".mov", ".mp4", ".mpeg", ".mpg", ".webm"}


def parse_resize(value: str) -> tuple[int, int]:
    try:
        width, height = (int(item) for item in value.lower().split("x", 1))
    except (TypeError, ValueError) as exc:
        raise argparse.ArgumentTypeError("Resize must be WIDTHxHEIGHT, for example 1280x720") from exc
    if width < 1 or height < 1:
        raise argparse.ArgumentTypeError("Resize dimensions must be positive")
    return width, height


def difference_hash(frame: np.ndarray) -> int:
    gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY) if frame.ndim == 3 else frame
    small = cv2.resize(gray, (9, 8), interpolation=cv2.INTER_AREA)
    bits = small[:, 1:] > small[:, :-1]
    value = 0
    for bit in bits.flat:
        value = (value << 1) | int(bit)
    return value


def hamming_distance(first: int, second: int) -> int:
    return (first ^ second).bit_count()


def discover_videos(source: Path, recursive: bool) -> list[Path]:
    if source.is_file():
        return [source] if source.suffix.lower() in VIDEO_EXTENSIONS else []
    iterator = source.rglob("*") if recursive else source.glob("*")
    return sorted(path for path in iterator if path.is_file() and path.suffix.lower() in VIDEO_EXTENSIONS)


def session_id(video: Path) -> str:
    signature = f"{video.resolve()}:{video.stat().st_size}:{video.stat().st_mtime_ns}"
    return f"{video.stem}-{hashlib.sha1(signature.encode()).hexdigest()[:10]}"


def register_video_session(video: Path, output: Path, session: str, args: argparse.Namespace) -> None:
    source_id = safe_identifier(session)
    record = {
        "session_id": session,
        "source_video": source_reference(video),
        "camera_id": args.camera_id,
        "location_label": args.location_label,
        "output": portable_path(output),
        "registered_at": utc_now(),
        "license": args.license,
        "authorization_notes": args.authorization_notes,
    }
    path = METADATA_ROOT / "sessions.jsonl"
    existing: list[dict[str, object]] = []
    if path.is_file():
        for line in path.read_text(encoding="utf-8").splitlines():
            if line.strip():
                existing.append(json.loads(line))
    existing = [item for item in existing if item.get("session_id") != session]
    existing.append(record)
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(".jsonl.tmp")
    temporary.write_text("".join(json.dumps(item, ensure_ascii=False) + "\n" for item in existing), encoding="utf-8")
    os.replace(temporary, path)
    register_source({
        "source_id": source_id, "name": session, "provider": "Authorized local video",
        "dataset_type": "own_nepal", "source_identifier": source_reference(video),
        "license": args.license, "downloaded_at": None, "original_classes": [],
        "target_classes": [], "annotation_format": "images_only", "status": "needs_annotation",
        "raw_path": portable_path(output), "notes": args.authorization_notes,
    }, replace=True)


def extract_video(video: Path, output: Path, args: argparse.Namespace, manifest: Any) -> tuple[int, int]:
    capture = cv2.VideoCapture(str(video))
    if not capture.isOpened():
        LOG.error("Could not open %s", video)
        return 0, 0
    fps = float(capture.get(cv2.CAP_PROP_FPS) or 0.0)
    if fps <= 0:
        fps = 30.0
        LOG.warning("%s does not report a valid FPS; assuming %.1f", video, fps)
    sample_frames = args.every_frames or max(1, round(args.every_seconds * fps))
    start_frame = max(0, round(args.start * fps))
    end_frame = round(args.end * fps) if args.end is not None else None
    capture.set(cv2.CAP_PROP_POS_FRAMES, start_frame)
    current = start_frame
    saved = duplicates = 0
    previous_hash: int | None = None
    generated_session = session_id(video)
    session = args.session_id or generated_session
    while True:
        if end_frame is not None and current > end_frame:
            break
        capture.set(cv2.CAP_PROP_POS_FRAMES, current)
        ok, frame = capture.read()
        if not ok or frame is None:
            break
        timestamp = current / fps
        perceptual_hash = difference_hash(frame)
        if (
            previous_hash is not None
            and not args.keep_near_duplicates
            and hamming_distance(previous_hash, perceptual_hash) <= args.duplicate_distance
        ):
            duplicates += 1
            current += sample_frames
            continue
        previous_hash = perceptual_hash
        if args.resize_width:
            height = max(1, round(frame.shape[0] * args.resize_width / frame.shape[1]))
            frame = cv2.resize(frame, (args.resize_width, height), interpolation=cv2.INTER_AREA)
        elif args.resize:
            frame = cv2.resize(frame, args.resize, interpolation=cv2.INTER_AREA)
        filename = f"{session}__f{current:010d}__t{round(timestamp * 1000):012d}.jpg"
        destination = output / filename
        if destination.exists():
            LOG.warning("Skipping existing extracted frame instead of overwriting: %s", destination)
            current += sample_frames
            continue
        if not cv2.imwrite(str(destination), frame, [cv2.IMWRITE_JPEG_QUALITY, args.jpeg_quality]):
            LOG.error("Could not write %s", destination)
            current += sample_frames
            continue
        manifest.write(json.dumps({
            "image": destination.name,
            "source_video": source_reference(video),
            "camera_id": args.camera_id,
            "session_id": session,
            "frame_number": current,
            "timestamp_seconds": round(timestamp, 3),
            "location_label": args.location_label,
            "source": "own_nepal",
            "source_fps": round(fps, 3),
            "perceptual_hash": f"{perceptual_hash:016x}",
        }, ensure_ascii=False) + "\n")
        saved += 1
        if args.max_frames is not None and saved >= args.max_frames:
            break
        current += sample_frames
    capture.release()
    return saved, duplicates


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Sample Nepal traffic videos into traceable frames while reducing neighboring duplicates.",
    )
    parser.add_argument("--input", type=Path, required=True, help="Video file or directory containing videos")
    parser.add_argument("--output", type=Path, required=True, help="Directory for sampled JPEG frames and frames.jsonl")
    interval = parser.add_mutually_exclusive_group()
    interval.add_argument("--every-seconds", type=float, default=2.0, help="Seconds between samples (default: 2)")
    interval.add_argument("--every-frames", type=int, help="Frames between samples instead of elapsed seconds")
    parser.add_argument("--start", type=float, default=0.0, help="Start timestamp in seconds")
    parser.add_argument("--end", type=float, help="Optional inclusive end timestamp in seconds")
    parser.add_argument("--resize", type=parse_resize, metavar="WIDTHxHEIGHT", help="Resize saved frames")
    parser.add_argument("--resize-width", type=int, help="Preserve aspect ratio while resizing to this width")
    parser.add_argument("--max-frames", type=int, help="Maximum sampled frames saved per input video")
    parser.add_argument("--camera-id", default="unknown", help="Stable non-secret camera identifier for grouping")
    parser.add_argument("--session-id", help="Stable collection session; only valid with one input video")
    parser.add_argument("--location-label", default="", help="Human-readable collection location, for example Surkhet")
    parser.add_argument("--license", default="UNKNOWN", help="Verified footage usage status/license; never assumed")
    parser.add_argument("--authorization-notes", default="", help="Non-secret authorization/retention note")
    parser.add_argument("--recursive", action=argparse.BooleanOptionalAction, default=True, help="Search input directories recursively")
    parser.add_argument("--keep-near-duplicates", action="store_true", help="Disable adjacent perceptual duplicate filtering")
    parser.add_argument("--duplicate-distance", type=int, default=3, help="Maximum 64-bit dHash distance treated as a duplicate")
    parser.add_argument("--jpeg-quality", type=int, default=92, choices=range(60, 101), metavar="60-100")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")
    if not args.input.exists():
        raise SystemExit(f"Input does not exist: {args.input}")
    if args.every_seconds is not None and args.every_seconds <= 0:
        raise SystemExit("--every-seconds must be greater than zero")
    if args.every_frames is not None and args.every_frames < 1:
        raise SystemExit("--every-frames must be at least 1")
    if args.start < 0 or (args.end is not None and args.end <= args.start):
        raise SystemExit("Timestamps must satisfy 0 <= start < end")
    if args.resize_width is not None and args.resize_width < 1:
        raise SystemExit("--resize-width must be positive")
    if args.max_frames is not None and args.max_frames < 1:
        raise SystemExit("--max-frames must be positive")
    args.output.mkdir(parents=True, exist_ok=True)
    videos = discover_videos(args.input, args.recursive)
    if not videos:
        raise SystemExit(f"No supported videos found under {args.input}")
    if args.session_id and len(videos) != 1:
        raise SystemExit("--session-id can only be used when exactly one input video is selected")
    saved = duplicates = 0
    manifest_path = args.output / "frames.jsonl"
    with manifest_path.open("a", encoding="utf-8") as manifest:
        for video in videos:
            video_saved, video_duplicates = extract_video(video, args.output, args, manifest)
            saved += video_saved
            duplicates += video_duplicates
            LOG.info("%s: saved %d, skipped %d near-duplicates", video.name, video_saved, video_duplicates)
            register_video_session(video, args.output, args.session_id or session_id(video), args)
    LOG.info("Finished: %d frames saved; %d near-duplicates skipped; manifest=%s", saved, duplicates, manifest_path)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
