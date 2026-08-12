"""Isolated, in-memory analysis jobs for manually uploaded road videos."""

from __future__ import annotations

import logging
import math
import os
import json
import ipaddress
import mimetypes
import shutil
import socket
import tempfile
import threading
import time
import uuid
from collections import Counter, deque
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Annotated, Any
from urllib.parse import urlparse

import cv2
import numpy as np
from fastapi import APIRouter, HTTPException, Query, Request, status
from fastapi.responses import FileResponse
from pydantic import BaseModel, Field, ValidationError

from config.settings import METERS_PER_PIXEL, MODEL_PATH, SPEED_LIMIT
from web.traffic_pipeline import CalibrationSettings, analyze_video as analyze_calibrated_video

log = logging.getLogger("trafficops.video_analysis")

router = APIRouter(prefix="/api/video-analysis", tags=["video-analysis"])

SUPPORTED_EXTENSIONS = {".mp4", ".mov", ".avi", ".mkv", ".webm", ".mpeg", ".mpg", ".m4v"}
VEHICLE_CLASSES = {"bicycle", "car", "motorcycle", "bus", "truck"}
MAX_UPLOAD_BYTES = int(os.getenv("TRAFFIC_MAX_UPLOAD_MB", "500")) * 1024 * 1024
JOB_TTL_SECONDS = 6 * 60 * 60
MAX_LINK_DURATION_SECONDS = int(os.getenv("TRAFFIC_MAX_LINK_DURATION_MINUTES", "120")) * 60
DEFAULT_LINK_HOSTS = {
    "youtube.com", "youtu.be",
    "drive.google.com",
    "facebook.com", "fb.watch",
    "instagram.com",
    "tiktok.com",
    "twitter.com", "x.com",
    "vimeo.com",
    "dailymotion.com", "dai.ly",
    "twitch.tv",
    "reddit.com", "redd.it",
    "streamable.com",
    "loom.com",
    "dropbox.com",
    "1drv.ms", "onedrive.live.com",
}
ALLOWED_LINK_HOSTS = DEFAULT_LINK_HOSTS | {
    host.strip().lower().lstrip(".")
    for host in os.getenv("TRAFFIC_ALLOWED_VIDEO_LINK_HOSTS", "").split(",")
    if host.strip()
}


@dataclass
class _Track:
    tracking_id: int
    type_votes: Counter[str] = field(default_factory=Counter)
    color_votes: Counter[str] = field(default_factory=Counter)
    confidence: float = 0.0
    first_seen: float = 0.0
    last_seen: float = 0.0
    first_point: tuple[float, float] | None = None
    previous_point: tuple[float, float] | None = None
    previous_timestamp: float | None = None
    last_point: tuple[float, float] | None = None
    speed_samples: deque[float] = field(default_factory=lambda: deque(maxlen=90))
    frames_tracked: int = 0


class _JobStore:
    def __init__(self) -> None:
        self._jobs: dict[str, dict[str, Any]] = {}
        self._lock = threading.RLock()

    def create(self, filename: str, source_type: str = "upload") -> str:
        self._purge()
        job_id = uuid.uuid4().hex
        now = time.time()
        with self._lock:
            self._jobs[job_id] = {
                "id": job_id,
                "filename": filename,
                "sourceType": source_type,
                "status": "queued",
                "progress": 0,
                "stage": "Waiting for the analysis worker",
                "result": None,
                "error": None,
                "createdAt": _iso_time(now),
                "updatedAt": _iso_time(now),
                "_updated": now,
            }
        return job_id

    def update(self, job_id: str, **changes: Any) -> None:
        with self._lock:
            job = self._jobs.get(job_id)
            if job is None:
                return
            now = time.time()
            job.update(changes)
            job["updatedAt"] = _iso_time(now)
            job["_updated"] = now

    def get(self, job_id: str) -> dict[str, Any] | None:
        self._purge()
        with self._lock:
            job = self._jobs.get(job_id)
            if job is None:
                return None
            return {key: value for key, value in job.items() if not key.startswith("_")}

    def artifact_path(self, job_id: str) -> str | None:
        self._purge()
        with self._lock:
            job = self._jobs.get(job_id)
            path = job.get("_outputPath") if job else None
            return str(path) if path else None

    def _purge(self) -> None:
        cutoff = time.time() - JOB_TTL_SECONDS
        with self._lock:
            expired = [
                job_id
                for job_id, job in self._jobs.items()
                if job.get("_updated", 0) < cutoff
            ]
            for job_id in expired:
                job = self._jobs.pop(job_id, None)
                if job and job.get("_outputPath"):
                    Path(str(job["_outputPath"])).unlink(missing_ok=True)


jobs = _JobStore()
_analysis_gate = threading.Lock()


def _parse_calibration(value: str | None) -> CalibrationSettings | None:
    if not value:
        return None
    try:
        payload = json.loads(value)
        return CalibrationSettings.model_validate(payload)
    except (json.JSONDecodeError, ValidationError, TypeError) as exc:
        raise HTTPException(
            status_code=422,
            detail="Road calibration is invalid. Mark four road points and check its measurements.",
        ) from exc


@router.post("", status_code=status.HTTP_202_ACCEPTED)
async def start_video_analysis(
    request: Request,
    filename: Annotated[str, Query(min_length=1, max_length=180)],
    location: Annotated[str, Query(max_length=160)] = "",
    speed_limit: Annotated[float, Query(alias="speedLimit", ge=5, le=200)] = SPEED_LIMIT,
    meters_per_pixel: Annotated[
        float, Query(alias="metersPerPixel", gt=0.0001, le=10)
    ] = METERS_PER_PIXEL,
    calibration: Annotated[str | None, Query(max_length=4096)] = None,
):
    """Accept a raw video body and queue it without touching live or historical data."""
    extension = Path(filename).suffix.lower()
    if extension not in SUPPORTED_EXTENSIONS:
        raise HTTPException(
            status_code=415,
            detail=f"Unsupported video format. Use: {', '.join(sorted(SUPPORTED_EXTENSIONS))}",
        )

    content_type = request.headers.get("content-type", "").split(";", 1)[0].lower()
    if content_type and not (
        content_type.startswith("video/") or content_type == "application/octet-stream"
    ):
        raise HTTPException(status_code=415, detail="The uploaded file must be a video")
    calibration_settings = _parse_calibration(calibration)
    if calibration_settings is None or not calibration_settings.enabled:
        raise HTTPException(
            status_code=422,
            detail=(
                "Four-point road calibration is required. Mark the visible road plane "
                "and provide its actual measured width and length."
            ),
        )

    content_length = request.headers.get("content-length")
    if content_length:
        try:
            if int(content_length) > MAX_UPLOAD_BYTES:
                raise HTTPException(status_code=413, detail=_upload_limit_message())
        except ValueError:
            pass

    temporary_path = ""
    size = 0
    try:
        with tempfile.NamedTemporaryFile(
            prefix="trafficops-upload-", suffix=extension, delete=False
        ) as temporary:
            temporary_path = temporary.name
            async for chunk in request.stream():
                if not chunk:
                    continue
                size += len(chunk)
                if size > MAX_UPLOAD_BYTES:
                    raise HTTPException(status_code=413, detail=_upload_limit_message())
                temporary.write(chunk)
        if size == 0:
            raise HTTPException(status_code=400, detail="The uploaded video is empty")
    except Exception:
        if temporary_path:
            Path(temporary_path).unlink(missing_ok=True)
        raise

    job_id = jobs.create(Path(filename).name)
    worker = threading.Thread(
        target=_run_analysis_job,
        args=(
            job_id,
            temporary_path,
            Path(filename).name,
            content_type or "application/octet-stream",
            size,
            location.strip(),
            float(speed_limit),
            float(meters_per_pixel),
            calibration_settings,
        ),
        name=f"video-analysis-{job_id[:8]}",
        daemon=True,
    )
    worker.start()
    return jobs.get(job_id)


@router.get("/{job_id}")
def get_video_analysis(job_id: str):
    job = jobs.get(job_id)
    if job is None:
        raise HTTPException(status_code=404, detail="Video analysis job not found")
    return job


@router.get("/{job_id}/video")
def get_annotated_video(job_id: str):
    """Stream the temporary annotated evidence video for a completed job."""
    path = jobs.artifact_path(job_id)
    if not path or not Path(path).is_file():
        raise HTTPException(status_code=404, detail="Annotated video is not available")
    return FileResponse(
        path,
        media_type="video/mp4",
        filename=f"trafficops-{job_id[:8]}-annotated.mp4",
    )


def _run_analysis_job(
    job_id: str,
    path: str,
    filename: str,
    content_type: str,
    size: int,
    location: str,
    speed_limit: float,
    meters_per_pixel: float,
    calibration: CalibrationSettings | None,
) -> None:
    try:
        with _analysis_gate:
            jobs.update(
                job_id,
                status="processing",
                progress=2,
                stage="Reading video metadata",
            )
            result, artifact_path = analyze_calibrated_video(
                path=path,
                filename=filename,
                content_type=content_type,
                size=size,
                location=location,
                speed_limit=speed_limit,
                meters_per_pixel=meters_per_pixel,
                calibration=calibration,
                progress=lambda value, stage: jobs.update(
                    job_id, progress=value, stage=stage
                ),
                artifact_url=f"/api/video-analysis/{job_id}/video",
            )
            jobs.update(
                job_id,
                status="completed",
                progress=100,
                stage="Analysis complete",
                result=result,
                _outputPath=artifact_path,
            )
    except Exception as exc:
        log.exception("Uploaded video analysis failed for job %s", job_id)
        jobs.update(
            job_id,
            status="failed",
            progress=100,
            stage="Analysis failed",
            error=_public_error(exc),
        )
    finally:
        Path(path).unlink(missing_ok=True)


def _run_link_analysis_job(
    job_id: str,
    video_url: str,
    location: str,
    speed_limit: float,
    meters_per_pixel: float,
    calibration: CalibrationSettings | None,
) -> None:
    temporary_directory = ""
    try:
        with _analysis_gate:
            jobs.update(
                job_id,
                status="processing",
                progress=2,
                stage="Connecting to the public video source",
            )
            temporary_directory = tempfile.mkdtemp(prefix="trafficops-link-")
            path, source = _download_link_video(
                job_id, video_url, Path(temporary_directory)
            )
            filename = _source_filename(source, path.suffix)
            jobs.update(
                job_id,
                filename=filename,
                progress=28,
                stage="Preparing downloaded video for analysis",
            )
            result, artifact_path = analyze_calibrated_video(
                path=str(path),
                filename=filename,
                content_type=mimetypes.guess_type(path.name)[0] or "application/octet-stream",
                size=path.stat().st_size,
                location=location,
                speed_limit=speed_limit,
                meters_per_pixel=meters_per_pixel,
                calibration=calibration,
                progress=lambda value, stage: jobs.update(
                    job_id,
                    progress=_scaled_progress(value, 28),
                    stage=stage,
                ),
                artifact_url=f"/api/video-analysis/{job_id}/video",
                source_metadata=source,
            )
            jobs.update(
                job_id,
                status="completed",
                progress=100,
                stage="Analysis complete",
                result=result,
                _outputPath=artifact_path,
            )
    except Exception as exc:
        log.exception("Linked video analysis failed for job %s", job_id)
        jobs.update(
            job_id,
            status="failed",
            progress=100,
            stage="Analysis failed",
            error=_public_error(exc),
        )
    finally:
        if temporary_directory:
            shutil.rmtree(temporary_directory, ignore_errors=True)


def _download_link_video(
    job_id: str, video_url: str, directory: Path
) -> tuple[Path, dict[str, Any]]:
    try:
        from yt_dlp import YoutubeDL
        from yt_dlp.utils import DownloadError
    except ModuleNotFoundError as exc:
        raise RuntimeError("The link downloader is not installed") from exc

    def progress_hook(event: dict[str, Any]) -> None:
        if event.get("status") == "finished":
            jobs.update(job_id, progress=26, stage="Video download complete")
            return
        if event.get("status") != "downloading":
            return
        downloaded = float(event.get("downloaded_bytes") or 0)
        if downloaded > MAX_UPLOAD_BYTES:
            raise DownloadError(_upload_limit_message())
        total = float(event.get("total_bytes") or event.get("total_bytes_estimate") or 0)
        progress = 4 + int(min(1.0, downloaded / total) * 21) if total else 8
        jobs.update(job_id, progress=progress, stage="Downloading public video")

    def link_filter(info: dict[str, Any], *, incomplete: bool = False) -> str | None:
        if info.get("is_live"):
            return "Live streams are not supported; use a finished video"
        duration = info.get("duration")
        if duration and float(duration) > MAX_LINK_DURATION_SECONDS:
            minutes = MAX_LINK_DURATION_SECONDS // 60
            return f"Video is longer than the {minutes}-minute link limit"
        return None

    options = {
        "format": (
            "bestvideo[height<=1080][ext=mp4]/bestvideo[height<=1080]/"
            "best[height<=1080][ext=mp4]/best[height<=1080]/best"
        ),
        "outtmpl": str(directory / "source.%(ext)s"),
        "noplaylist": True,
        "playlistend": 1,
        "max_downloads": 1,
        "max_filesize": MAX_UPLOAD_BYTES,
        "socket_timeout": 20,
        "retries": 2,
        "fragment_retries": 2,
        "continuedl": False,
        "overwrites": True,
        "cachedir": False,
        "ignoreconfig": True,
        "usenetrc": False,
        "cookiefile": None,
        "cookiesfrombrowser": None,
        "js_runtimes": {"node": {}},
        "quiet": True,
        "no_warnings": True,
        "progress_hooks": [progress_hook],
        "match_filter": link_filter,
    }
    try:
        with YoutubeDL(options) as downloader:
            information = downloader.extract_info(video_url, download=True)
            information = downloader.sanitize_info(information)
    except DownloadError as exc:
        raise ValueError(_link_download_error(str(exc))) from exc
    if not isinstance(information, dict) or information.get("_type") == "playlist":
        raise ValueError("Use a single public video link, not a playlist or folder")

    files = [
        candidate
        for candidate in directory.iterdir()
        if candidate.is_file()
        and candidate.suffix.lower() in SUPPORTED_EXTENSIONS
        and not candidate.name.endswith(".part")
    ]
    if not files:
        raise ValueError("The link did not provide a supported downloadable video file")
    path = max(files, key=lambda candidate: candidate.stat().st_size)
    size = path.stat().st_size
    if size <= 0:
        raise ValueError("The linked video download was empty")
    if size > MAX_UPLOAD_BYTES:
        raise ValueError(_upload_limit_message())

    return path, {
        "sourceType": "link",
        "sourceUrl": video_url,
        "sourcePlatform": str(
            information.get("extractor_key")
            or information.get("extractor")
            or urlparse(video_url).hostname
            or "Public link"
        )[:80],
        "sourceTitle": str(information.get("title") or "Linked road video")[:180],
        "sourceUploader": str(
            information.get("uploader") or information.get("channel") or ""
        )[:160],
    }


def _analyze_video(
    job_id: str,
    path: str,
    filename: str,
    content_type: str,
    size: int,
    location: str,
    speed_limit: float,
    meters_per_pixel: float,
    source_metadata: dict[str, Any] | None = None,
    progress_base: int = 0,
) -> dict[str, Any]:
    from ultralytics import YOLO

    started = time.monotonic()
    capture = cv2.VideoCapture(path)
    if not capture.isOpened():
        raise ValueError("This video could not be opened. It may be damaged or use an unsupported codec.")

    fps = float(capture.get(cv2.CAP_PROP_FPS))
    total_frames = int(capture.get(cv2.CAP_PROP_FRAME_COUNT))
    width = int(capture.get(cv2.CAP_PROP_FRAME_WIDTH))
    height = int(capture.get(cv2.CAP_PROP_FRAME_HEIGHT))
    if not math.isfinite(fps) or fps <= 0:
        fps = 25.0
    duration = total_frames / fps if total_frames > 0 else 0.0
    if source_metadata and duration > MAX_LINK_DURATION_SECONDS:
        raise ValueError(
            f"Linked videos must be {MAX_LINK_DURATION_SECONDS // 60} minutes or shorter"
        )
    sample_interval = max(1, round(fps / 12))
    analyzed_frames = 0
    frame_index = 0
    tracks: dict[int, _Track] = {}

    try:
        jobs.update(
            job_id,
            progress=_scaled_progress(5, progress_base),
            stage="Loading the vehicle detection model",
        )
        model = YOLO(MODEL_PATH)
        jobs.update(
            job_id,
            progress=_scaled_progress(8, progress_base),
            stage="Detecting and tracking road users",
        )

        while True:
            grabbed = capture.grab()
            if not grabbed:
                break
            frame_index += 1
            if (frame_index - 1) % sample_interval:
                continue
            ok, frame = capture.retrieve()
            if not ok:
                continue
            analyzed_frames += 1
            timestamp = (frame_index - 1) / fps
            result = model.track(
                frame,
                persist=True,
                tracker="bytetrack.yaml",
                conf=0.3,
                verbose=False,
            )[0]
            boxes = result.boxes
            if boxes is not None and boxes.id is not None:
                confidences = (
                    boxes.conf.tolist() if boxes.conf is not None else [0.0] * len(boxes)
                )
                for tracking_raw, class_raw, confidence_raw, box_raw in zip(
                    boxes.id.tolist(),
                    boxes.cls.tolist(),
                    confidences,
                    boxes.xyxy.tolist(),
                ):
                    vehicle_type = str(model.names[int(class_raw)]).lower()
                    if vehicle_type not in VEHICLE_CLASSES:
                        continue
                    tracking_id = int(tracking_raw)
                    x1, y1, x2, y2 = map(float, box_raw)
                    point = ((x1 + x2) / 2.0, y2)
                    track = tracks.get(tracking_id)
                    if track is None:
                        track = _Track(
                            tracking_id=tracking_id,
                            first_seen=timestamp,
                            first_point=point,
                        )
                        tracks[tracking_id] = track

                    track.type_votes[vehicle_type] += 1
                    track.confidence = max(track.confidence, float(confidence_raw))
                    track.last_seen = timestamp
                    track.last_point = point
                    track.frames_tracked += 1
                    _record_speed(track, point, timestamp, meters_per_pixel)

                    if track.frames_tracked == 1 or (
                        track.frames_tracked <= 24 and track.frames_tracked % 8 == 0
                    ):
                        color = _vehicle_color(frame, (x1, y1, x2, y2))
                        if color != "UNKNOWN":
                            track.color_votes[color] += 1

            if total_frames > 0 and analyzed_frames % 3 == 0:
                progress = _scaled_progress(
                    min(94, 8 + int(frame_index / total_frames * 86)),
                    progress_base,
                )
                jobs.update(
                    job_id,
                    progress=progress,
                    stage=f"Analyzing frame {min(frame_index, total_frames):,} of {total_frames:,}",
                )
    finally:
        capture.release()

    jobs.update(
        job_id,
        progress=_scaled_progress(96, progress_base),
        stage="Preparing traffic insights",
    )
    vehicles = [_serialize_track(track, speed_limit) for track in tracks.values()]
    vehicles.sort(key=lambda item: (item["firstSeenSeconds"], item["trackingId"]))
    vehicle_speeds = [
        vehicle["estimatedSpeed"]
        for vehicle in vehicles
        if vehicle["estimatedSpeed"] is not None
    ]
    overspeed = sum(vehicle["status"] == "OVERSPEED" for vehicle in vehicles)
    type_counts = Counter(vehicle["vehicleType"] for vehicle in vehicles)
    color_counts = Counter(
        vehicle["color"] for vehicle in vehicles if vehicle["color"] != "UNKNOWN"
    )
    timeline = _build_timeline(vehicles, duration)
    peak_bucket = max(timeline, key=lambda item: item["detections"], default=None)

    video_details = {
            "filename": filename,
            "mimeType": content_type,
            "sizeBytes": size,
            "durationSeconds": round(duration, 2),
            "fps": round(fps, 2),
            "width": width,
            "height": height,
            "totalFrames": total_frames,
            "analyzedFrames": analyzed_frames,
            "location": location or "Not specified",
            "sourceType": "upload",
            "sourceUrl": None,
            "sourcePlatform": None,
            "sourceTitle": None,
            "sourceUploader": None,
    }
    if source_metadata:
        for key in (
            "sourceType", "sourceUrl", "sourcePlatform", "sourceTitle", "sourceUploader"
        ):
            if key in source_metadata:
                video_details[key] = source_metadata[key]

    return {
        "video": video_details,
        "summary": {
            "totalVehicles": len(vehicles),
            "overspeedVehicles": overspeed,
            "averageSpeed": (
                round(sum(vehicle_speeds) / len(vehicle_speeds), 2)
                if vehicle_speeds
                else None
            ),
            "maxSpeed": round(max(vehicle_speeds), 2) if vehicle_speeds else None,
            "speedLimit": speed_limit,
            "peakTrafficAtSeconds": (
                peak_bucket["startSeconds"] if peak_bucket and peak_bucket["detections"] else None
            ),
        },
        "vehicleTypes": [
            {"name": name, "value": count}
            for name, count in type_counts.most_common()
        ],
        "vehicleColors": [
            {"name": name, "value": count}
            for name, count in color_counts.most_common()
        ],
        "timeline": timeline,
        "vehicles": vehicles,
        "analysis": {
            "completedAt": _iso_time(time.time()),
            "processingSeconds": round(time.monotonic() - started, 2),
            "model": Path(MODEL_PATH).name,
            "sampleEveryFrames": sample_interval,
            "calibrationMetersPerPixel": meters_per_pixel,
            "speedMethod": "Tracked pixel displacement × road calibration scale",
            "speedIsEstimated": True,
            "plateRecognitionAvailable": False,
            "note": (
                "Speed is an estimate. For enforcement-grade results, calibrate the uploaded "
                "camera perspective against known road distances."
            ),
        },
    }


def _record_speed(
    track: _Track,
    point: tuple[float, float],
    timestamp: float,
    meters_per_pixel: float,
) -> None:
    if track.previous_point is not None and track.previous_timestamp is not None:
        elapsed = timestamp - track.previous_timestamp
        if elapsed > 0:
            speed = math.dist(point, track.previous_point) * meters_per_pixel / elapsed * 3.6
            previous = (
                sum(track.speed_samples) / len(track.speed_samples)
                if track.speed_samples
                else None
            )
            acceleration = abs(speed - previous) / elapsed if previous is not None else 0.0
            if math.isfinite(speed) and 0.5 <= speed <= 200 and acceleration <= 120:
                track.speed_samples.append(speed)
    track.previous_point = point
    track.previous_timestamp = timestamp


def _serialize_track(track: _Track, speed_limit: float) -> dict[str, Any]:
    vehicle_type = track.type_votes.most_common(1)[0][0] if track.type_votes else "unknown"
    color = track.color_votes.most_common(1)[0][0] if track.color_votes else "UNKNOWN"
    speed = _trimmed_average(list(track.speed_samples))
    peak_speed = max(track.speed_samples) if track.speed_samples else None
    return {
        "trackingId": track.tracking_id,
        "vehicleType": vehicle_type,
        "color": color,
        "plate": None,
        "plateStatus": "NOT_AVAILABLE",
        "confidence": round(track.confidence, 3),
        "firstSeenSeconds": round(track.first_seen, 2),
        "lastSeenSeconds": round(track.last_seen, 2),
        "trackedForSeconds": round(max(0.0, track.last_seen - track.first_seen), 2),
        "framesTracked": track.frames_tracked,
        "estimatedSpeed": round(speed, 2) if speed is not None else None,
        "peakSpeed": round(peak_speed, 2) if peak_speed is not None else None,
        "speedLimit": speed_limit,
        "status": (
            "INSUFFICIENT_DATA"
            if speed is None
            else "OVERSPEED"
            if speed > speed_limit
            else "NORMAL"
        ),
        "direction": _direction_label(track.first_point, track.last_point),
    }


def _trimmed_average(values: list[float]) -> float | None:
    if not values:
        return None
    ordered = sorted(values)
    trim = int(len(ordered) * 0.1) if len(ordered) >= 10 else 0
    selected = ordered[trim : len(ordered) - trim] if trim else ordered
    return sum(selected) / len(selected)


def _direction_label(
    start: tuple[float, float] | None, end: tuple[float, float] | None
) -> str:
    if start is None or end is None:
        return "Unknown"
    dx, dy = end[0] - start[0], end[1] - start[1]
    if math.hypot(dx, dy) < 8:
        return "Stationary / unclear"
    if abs(dx) > abs(dy) * 1.25:
        return "Left to right" if dx > 0 else "Right to left"
    if abs(dy) > abs(dx) * 1.25:
        return "Approaching" if dy > 0 else "Moving away"
    horizontal = "right" if dx > 0 else "left"
    vertical = "approaching" if dy > 0 else "moving away"
    return f"{vertical}, toward {horizontal}"


def _vehicle_color(frame: np.ndarray, coordinates: tuple[float, float, float, float]) -> str:
    height, width = frame.shape[:2]
    x1, y1, x2, y2 = coordinates
    crop = frame[
        max(0, int(y1)) : min(height, int(y2)),
        max(0, int(x1)) : min(width, int(x2)),
    ]
    if crop.size == 0:
        return "UNKNOWN"
    crop_height, crop_width = crop.shape[:2]
    body = crop[
        int(crop_height * 0.15) : int(crop_height * 0.8),
        int(crop_width * 0.15) : int(crop_width * 0.85),
    ]
    if body.size == 0:
        return "UNKNOWN"
    hsv = cv2.cvtColor(body, cv2.COLOR_BGR2HSV).reshape(-1, 3)
    saturation = float(np.median(hsv[:, 1]))
    value = float(np.median(hsv[:, 2]))
    if value < 45:
        return "BLACK"
    if saturation < 30 and value > 205:
        return "WHITE"
    if saturation < 35:
        return "SILVER / GRAY"
    colorful = hsv[hsv[:, 1] > 40]
    if not len(colorful):
        return "UNKNOWN"
    hue = float(np.median(colorful[:, 0]))
    if hue < 10 or hue >= 170:
        return "RED"
    if hue < 22:
        return "ORANGE"
    if hue < 36:
        return "YELLOW"
    if hue < 85:
        return "GREEN"
    if hue < 135:
        return "BLUE"
    return "PURPLE"


def _build_timeline(vehicles: list[dict[str, Any]], duration: float) -> list[dict[str, Any]]:
    if duration <= 0:
        return []
    bucket_size = max(1, math.ceil(duration / 12))
    bucket_count = max(1, math.ceil(duration / bucket_size))
    timeline = [
        {
            "label": _format_offset(index * bucket_size),
            "startSeconds": index * bucket_size,
            "detections": 0,
            "overspeed": 0,
        }
        for index in range(bucket_count)
    ]
    for vehicle in vehicles:
        index = min(
            len(timeline) - 1,
            int(vehicle["firstSeenSeconds"] // bucket_size),
        )
        timeline[index]["detections"] += 1
        if vehicle["status"] == "OVERSPEED":
            timeline[index]["overspeed"] += 1
    return timeline


def _format_offset(seconds: float) -> str:
    minutes, remaining = divmod(int(seconds), 60)
    hours, minutes = divmod(minutes, 60)
    return f"{hours:02d}:{minutes:02d}:{remaining:02d}" if hours else f"{minutes:02d}:{remaining:02d}"


def _validate_video_link(value: str) -> str:
    normalized = value.strip()
    parsed = urlparse(normalized)
    if parsed.scheme not in {"http", "https"} or not parsed.hostname:
        raise HTTPException(status_code=400, detail="Enter a valid public HTTPS video link")
    if parsed.username or parsed.password:
        raise HTTPException(status_code=400, detail="Links containing credentials are not allowed")
    hostname = parsed.hostname.lower().rstrip(".")
    if not _host_allowed(hostname):
        supported = "YouTube, Google Drive, Instagram, TikTok, Facebook, X, Vimeo, and other listed sources"
        raise HTTPException(status_code=400, detail=f"Unsupported link host. Try {supported}")
    try:
        addresses = {
            item[4][0]
            for item in socket.getaddrinfo(
                hostname,
                parsed.port or (443 if parsed.scheme == "https" else 80),
                type=socket.SOCK_STREAM,
            )
        }
    except (OSError, ValueError) as exc:
        raise HTTPException(status_code=400, detail="The video link host could not be reached") from exc
    if not addresses or any(not _is_public_address(address) for address in addresses):
        raise HTTPException(
            status_code=400,
            detail="Private or internal-network video links are not allowed",
        )
    return normalized


def _host_allowed(hostname: str) -> bool:
    return any(
        hostname == allowed or hostname.endswith(f".{allowed}")
        for allowed in ALLOWED_LINK_HOSTS
    )


def _is_public_address(value: str) -> bool:
    address = ipaddress.ip_address(value)
    return bool(address.is_global)


def _source_filename(source: dict[str, Any], extension: str) -> str:
    title = str(source.get("sourceTitle") or "Linked road video").strip()
    cleaned = "".join(
        character if character.isalnum() or character in " ._-" else "_"
        for character in title
    ).strip(" .")
    return f"{(cleaned or 'Linked road video')[:160]}{extension.lower()}"


def _link_download_error(message: str) -> str:
    normalized = message.lower()
    if "unsupported url" in normalized:
        return "This public video URL is not supported by the link downloader"
    if "private" in normalized or "login" in normalized or "sign in" in normalized:
        return "This video is private or requires sign-in; use a public video link"
    if "live stream" in normalized or "is live" in normalized:
        return "Live streams are not supported; use a finished video"
    if "larger than max-filesize" in normalized or "file is larger" in normalized:
        return _upload_limit_message()
    if "longer than" in normalized:
        return f"Linked videos must be {MAX_LINK_DURATION_SECONDS // 60} minutes or shorter"
    return (
        "The platform could not provide a public downloadable video. "
        "Check the link, visibility, and platform restrictions."
    )


def _scaled_progress(progress: int, base: int) -> int:
    return min(99, base + round(max(0, progress) / 100 * (100 - base)))


def _public_error(error: Exception) -> str:
    if isinstance(error, ValueError):
        return str(error)
    if isinstance(error, RuntimeError) and "link downloader" in str(error).lower():
        return str(error)
    return "The analysis worker could not process this video. Check its format and try again."


def _upload_limit_message() -> str:
    return f"Video is too large. Maximum upload size is {MAX_UPLOAD_BYTES // (1024 * 1024)} MB"


def _iso_time(timestamp: float) -> str:
    return (
        datetime.fromtimestamp(timestamp, tz=timezone.utc)
        .isoformat()
        .replace("+00:00", "Z")
    )
