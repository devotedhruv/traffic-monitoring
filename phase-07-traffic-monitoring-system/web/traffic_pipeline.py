"""Calibrated, auditable traffic-video analysis pipeline.

The module deliberately keeps enforcement-sensitive capabilities explicit.  A generic
vehicle model may count and track vehicles, while number-plate and helmet results are
only enabled when their dedicated weights (and OCR engine for plates) are configured.
"""

from __future__ import annotations

import logging
import math
import re
import shutil
import subprocess
import tempfile
import time
from collections import Counter, deque
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Callable, Literal

import cv2
import numpy as np
from pydantic import BaseModel, Field, model_validator

from config.settings import (
    ANALYSIS_FPS,
    DETECTOR_IMAGE_SIZE,
    HELMET_MODEL_PATH,
    MODEL_PATH,
    PLATE_MODEL_PATH,
    TESSERACT_CMD,
    TRACKER_CONFIG,
)

log = logging.getLogger("trafficops.traffic_pipeline")

VEHICLE_CLASSES = {"bicycle", "car", "motorcycle", "bus", "truck"}
CLASS_ALIASES = {
    "bike": "bicycle",
    "motorbike": "motorcycle",
    "motor cycle": "motorcycle",
    "auto": "car",
    "vehicle": "car",
}
TRACK_COLORS = {
    "car": (255, 130, 35),
    "truck": (25, 170, 245),
    "bus": (150, 70, 230),
    "motorcycle": (210, 190, 20),
    "bicycle": (20, 190, 235),
}


class NormalizedPoint(BaseModel):
    """A point relative to the source frame dimensions."""

    x: float = Field(ge=0, le=1)
    y: float = Field(ge=0, le=1)


class CalibrationSettings(BaseModel):
    """Road-plane calibration sent by the upload UI.

    Source points must be ordered far-left, far-right, near-right, near-left.  They
    represent a measured road rectangle whose physical width/length are supplied.
    """

    enabled: bool = True
    sourcePoints: list[NormalizedPoint] = Field(default_factory=list, max_length=4)
    roadWidthMeters: float = Field(default=8, ge=2, le=80)
    roadLengthMeters: float = Field(default=30, ge=5, le=1000)
    laneCount: int = Field(default=2, ge=1, le=8)
    countingLinePosition: float = Field(default=0.62, ge=0.05, le=0.95)
    stabilize: bool = True
    analysisFps: float = Field(default=ANALYSIS_FPS, ge=5, le=30)
    tracker: Literal["botsort.yaml", "bytetrack.yaml"] = TRACKER_CONFIG
    allowedDirection: Literal[
        "both",
        "approaching",
        "moving_away",
        "left_to_right",
        "right_to_left",
    ] = "both"

    @model_validator(mode="after")
    def require_complete_road_plane(self) -> "CalibrationSettings":
        if self.enabled and len(self.sourcePoints) != 4:
            raise ValueError("Enabled perspective calibration requires exactly four points")
        return self


@dataclass
class _RoadPlane:
    homography: np.ndarray | None
    source_polygon: np.ndarray | None
    width_meters: float
    length_meters: float
    counting_position: float
    lane_count: int
    calibrated: bool

    @property
    def counting_y(self) -> float:
        return self.length_meters * self.counting_position

    def contains(self, point: tuple[float, float]) -> bool:
        if self.source_polygon is None:
            return True
        return cv2.pointPolygonTest(self.source_polygon, point, False) >= 0

    def project(
        self, point: tuple[float, float], meters_per_pixel: float
    ) -> tuple[float, float]:
        if self.homography is None:
            return point[0] * meters_per_pixel, point[1] * meters_per_pixel
        source = np.array([[point]], dtype=np.float32)
        projected = cv2.perspectiveTransform(source, self.homography)[0][0]
        return float(projected[0]), float(projected[1])

    def line_pixels(self) -> tuple[tuple[int, int], tuple[int, int]] | None:
        if self.source_polygon is None:
            return None
        top_left, top_right, bottom_right, bottom_left = self.source_polygon
        position = self.counting_position
        left = top_left * (1 - position) + bottom_left * position
        right = top_right * (1 - position) + bottom_right * position
        return tuple(left.astype(int)), tuple(right.astype(int))

    def lane_for(self, point: tuple[float, float]) -> int | None:
        if not self.calibrated or self.width_meters <= 0:
            return None
        lane = int(point[0] / self.width_meters * self.lane_count) + 1
        return min(self.lane_count, max(1, lane))


@dataclass
class _Track:
    tracking_id: int
    type_votes: Counter[str] = field(default_factory=Counter)
    color_votes: Counter[str] = field(default_factory=Counter)
    plate_votes: Counter[str] = field(default_factory=Counter)
    lane_votes: Counter[int] = field(default_factory=Counter)
    plate_confidence: float = 0
    violations: set[str] = field(default_factory=set)
    confidence: float = 0
    first_seen: float = 0
    last_seen: float = 0
    first_point: tuple[float, float] | None = None
    last_point: tuple[float, float] | None = None
    first_ground_point: tuple[float, float] | None = None
    last_ground_point: tuple[float, float] | None = None
    previous_ground_point: tuple[float, float] | None = None
    previous_timestamp: float | None = None
    ground_history: deque[tuple[float, tuple[float, float]]] = field(
        default_factory=lambda: deque(maxlen=45)
    )
    speed_samples: deque[float] = field(default_factory=lambda: deque(maxlen=120))
    trail: deque[tuple[int, int]] = field(default_factory=lambda: deque(maxlen=36))
    frames_tracked: int = 0
    counted_at: float | None = None
    previous_line_side: int | None = None
    last_box: tuple[int, int, int, int] | None = None


class _FrameStabilizer:
    """Feature-based global camera-motion compensation relative to the first frame."""

    def __init__(self) -> None:
        self._previous_gray: np.ndarray | None = None
        self._cumulative = np.eye(3, dtype=np.float64)

    def apply(self, frame: np.ndarray) -> tuple[np.ndarray, bool]:
        gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
        if self._previous_gray is None:
            self._previous_gray = gray
            return frame, False

        previous_points = cv2.goodFeaturesToTrack(
            self._previous_gray,
            maxCorners=280,
            qualityLevel=0.01,
            minDistance=18,
            blockSize=3,
        )
        if previous_points is None or len(previous_points) < 12:
            self._previous_gray = gray
            return frame, False
        current_points, status, _ = cv2.calcOpticalFlowPyrLK(
            self._previous_gray, gray, previous_points, None
        )
        if current_points is None or status is None:
            self._previous_gray = gray
            return frame, False
        valid = status.reshape(-1).astype(bool)
        if valid.sum() < 10:
            self._previous_gray = gray
            return frame, False
        transform, inliers = cv2.estimateAffinePartial2D(
            current_points[valid],
            previous_points[valid],
            method=cv2.RANSAC,
            ransacReprojThreshold=2.5,
        )
        self._previous_gray = gray
        if transform is None or inliers is None or int(inliers.sum()) < 8:
            return frame, False
        dx, dy = float(transform[0, 2]), float(transform[1, 2])
        rotation_scale = transform[:, :2]
        if math.hypot(dx, dy) > max(frame.shape[:2]) * 0.08:
            return frame, False
        if not 0.92 <= abs(float(np.linalg.det(rotation_scale))) <= 1.08:
            return frame, False
        affine = np.vstack([transform, [0, 0, 1]])
        self._cumulative = self._cumulative @ affine
        stabilized = cv2.warpPerspective(
            frame,
            self._cumulative,
            (frame.shape[1], frame.shape[0]),
            flags=cv2.INTER_LINEAR,
            borderMode=cv2.BORDER_REPLICATE,
        )
        return stabilized, True


class _SpecialistModels:
    """Optional plate/OCR and helmet models, never silently simulated."""

    def __init__(self) -> None:
        from ultralytics import YOLO

        self.plate_model = None
        self.helmet_model = None
        self.ocr_command = shutil.which(TESSERACT_CMD) if TESSERACT_CMD else None
        if PLATE_MODEL_PATH and Path(PLATE_MODEL_PATH).is_file():
            self.plate_model = YOLO(PLATE_MODEL_PATH)
        if HELMET_MODEL_PATH and Path(HELMET_MODEL_PATH).is_file():
            self.helmet_model = YOLO(HELMET_MODEL_PATH)

    def capabilities(self) -> dict[str, dict[str, Any]]:
        plate_ready = self.plate_model is not None and self.ocr_command is not None
        return {
            "vehicleDetection": {"available": True, "model": Path(MODEL_PATH).name},
            "perspectiveSpeed": {"available": True},
            "lineCrossing": {"available": True},
            "laneDirection": {"available": True, "method": "calibrated trajectory"},
            "plateRecognition": {
                "available": plate_ready,
                "reason": None if plate_ready else "Dedicated plate weights and Tesseract OCR are not configured",
            },
            "helmetDetection": {
                "available": self.helmet_model is not None,
                "reason": None if self.helmet_model is not None else "Dedicated helmet weights are not configured",
            },
        }

    def inspect(self, frame: np.ndarray, track: _Track, vehicle_type: str) -> None:
        if track.last_box is None:
            return
        x1, y1, x2, y2 = track.last_box
        crop = frame[max(0, y1):max(0, y2), max(0, x1):max(0, x2)]
        if crop.size == 0:
            return
        if self.plate_model is not None and self.ocr_command is not None:
            plate = self._read_plate(crop)
            if plate:
                text, confidence = plate
                track.plate_votes[text] += 1
                track.plate_confidence = max(track.plate_confidence, confidence)
        if self.helmet_model is not None and vehicle_type == "motorcycle":
            prediction = self.helmet_model.predict(crop, conf=0.3, verbose=False)[0]
            if prediction.boxes is None:
                return
            for class_id in prediction.boxes.cls.tolist():
                label = _normalized_label(self.helmet_model.names[int(class_id)])
                if "nohelmet" in label or "withouthelmet" in label:
                    track.violations.add("NO_HELMET")

    def _read_plate(self, crop: np.ndarray) -> tuple[str, float] | None:
        prediction = self.plate_model.predict(crop, conf=0.3, verbose=False)[0]
        if prediction.boxes is None or len(prediction.boxes) == 0:
            return None
        confidences = prediction.boxes.conf.tolist()
        best = int(np.argmax(confidences))
        x1, y1, x2, y2 = map(int, prediction.boxes.xyxy.tolist()[best])
        plate_crop = crop[max(0, y1):max(0, y2), max(0, x1):max(0, x2)]
        if plate_crop.size == 0:
            return None
        gray = cv2.cvtColor(plate_crop, cv2.COLOR_BGR2GRAY)
        gray = cv2.resize(gray, None, fx=2.5, fy=2.5, interpolation=cv2.INTER_CUBIC)
        gray = cv2.bilateralFilter(gray, 7, 45, 45)
        encoded, payload = cv2.imencode(".png", gray)
        if not encoded:
            return None
        try:
            completed = subprocess.run(
                [self.ocr_command, "stdin", "stdout", "--psm", "7"],
                input=payload.tobytes(),
                stdout=subprocess.PIPE,
                stderr=subprocess.DEVNULL,
                timeout=8,
                check=False,
            )
        except (OSError, subprocess.TimeoutExpired):
            return None
        text = re.sub(r"[^A-Z0-9]", "", completed.stdout.decode(errors="ignore").upper())
        if not 4 <= len(text) <= 14:
            return None
        return text, float(confidences[best])


def analyze_video(
    *,
    path: str,
    filename: str,
    content_type: str,
    size: int,
    location: str,
    speed_limit: float,
    meters_per_pixel: float,
    calibration: CalibrationSettings | None,
    progress: Callable[[int, str], None],
    artifact_url: str,
    source_metadata: dict[str, Any] | None = None,
) -> tuple[dict[str, Any], str | None]:
    """Analyze a video and return its public report plus annotated-video path."""

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
    settings = calibration or CalibrationSettings(enabled=False, stabilize=False)
    road = _build_road_plane(settings, width, height)
    sample_interval = max(1, round(fps / settings.analysisFps))
    output_fps = max(1.0, fps / sample_interval)
    tracks: dict[int, _Track] = {}
    analyzed_frames = 0
    frame_index = 0
    stabilization_frames = 0
    stabilizer = _FrameStabilizer() if settings.stabilize else None
    raw_output = tempfile.NamedTemporaryFile(
        prefix="trafficops-annotated-", suffix="-raw.mp4", delete=False
    ).name
    output_writer = cv2.VideoWriter(
        raw_output,
        cv2.VideoWriter_fourcc(*"mp4v"),
        output_fps,
        (width, height),
    )
    if not output_writer.isOpened():
        output_writer.release()
        output_writer = None
        Path(raw_output).unlink(missing_ok=True)

    progress(5, "Loading YOLO11 vehicle detector and specialist capabilities")
    model = YOLO(MODEL_PATH)
    specialists = _SpecialistModels()
    class_ids = [
        int(class_id)
        for class_id, name in model.names.items()
        if _vehicle_label(name) in VEHICLE_CLASSES
    ]
    if not class_ids:
        raise RuntimeError("The configured detector has no supported road-vehicle classes")
    progress(9, "Tracking vehicles with BoT-SORT and ground-plane trajectories")

    analysis_failed = False
    try:
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
            if stabilizer is not None:
                frame, stabilized = stabilizer.apply(frame)
                stabilization_frames += int(stabilized)
            result = model.track(
                source=frame,
                persist=True,
                tracker=settings.tracker,
                classes=class_ids,
                conf=0.18,
                iou=0.55,
                imgsz=DETECTOR_IMAGE_SIZE,
                verbose=False,
            )[0]
            boxes = result.boxes
            visible_tracks: list[_Track] = []
            if boxes is not None and boxes.id is not None:
                confidences = boxes.conf.tolist() if boxes.conf is not None else [0.0] * len(boxes)
                for tracking_raw, class_raw, confidence_raw, box_raw in zip(
                    boxes.id.tolist(), boxes.cls.tolist(), confidences, boxes.xyxy.tolist()
                ):
                    vehicle_type = _vehicle_label(model.names[int(class_raw)])
                    if vehicle_type not in VEHICLE_CLASSES:
                        continue
                    x1, y1, x2, y2 = map(float, box_raw)
                    image_point = ((x1 + x2) / 2, y2)
                    if not road.contains(image_point):
                        continue
                    ground_point = road.project(image_point, meters_per_pixel)
                    tracking_id = int(tracking_raw)
                    track = tracks.get(tracking_id)
                    if track is None:
                        track = _Track(
                            tracking_id=tracking_id,
                            first_seen=timestamp,
                            first_point=image_point,
                            first_ground_point=ground_point,
                        )
                        tracks[tracking_id] = track
                    track.type_votes[vehicle_type] += 1
                    track.confidence = max(track.confidence, float(confidence_raw))
                    track.last_seen = timestamp
                    track.last_point = image_point
                    track.last_ground_point = ground_point
                    lane = road.lane_for(ground_point)
                    if lane is not None:
                        track.lane_votes[lane] += 1
                    track.frames_tracked += 1
                    track.trail.append((round(image_point[0]), round(image_point[1])))
                    track.last_box = tuple(map(round, (x1, y1, x2, y2)))
                    _record_ground_speed(track, ground_point, timestamp)
                    _record_line_crossing(track, ground_point, timestamp, road.counting_y)
                    if track.frames_tracked in {1, 6, 18}:
                        color = _vehicle_color(frame, (x1, y1, x2, y2))
                        if color != "UNKNOWN":
                            track.color_votes[color] += 1
                    if track.frames_tracked in {6, 18, 36}:
                        specialists.inspect(frame, track, vehicle_type)
                    visible_tracks.append(track)

            annotated = frame.copy()
            _draw_road_guides(annotated, road)
            for track in visible_tracks:
                _draw_track(annotated, track)
            if output_writer is not None:
                output_writer.write(annotated)
            if total_frames > 0 and analyzed_frames % 3 == 0:
                progress(
                    min(94, 9 + int(frame_index / total_frames * 85)),
                    f"Analyzing frame {min(frame_index, total_frames):,} of {total_frames:,}",
                )
    except Exception:
        analysis_failed = True
        raise
    finally:
        capture.release()
        if output_writer is not None:
            output_writer.release()
        if analysis_failed:
            Path(raw_output).unlink(missing_ok=True)

    progress(96, "Validating tracks and preparing annotated evidence")
    minimum_frames = max(3, round(output_fps * 0.25))
    mature_tracks = [
        track
        for track in tracks.values()
        if track.frames_tracked >= minimum_frames
        and track.last_seen - track.first_seen >= 0.15
    ]
    vehicles = [
        _serialize_track(track, speed_limit, road.calibrated, settings.allowedDirection)
        for track in mature_tracks
    ]
    vehicles.sort(key=lambda item: (item["firstSeenSeconds"], item["trackingId"]))
    vehicle_speeds = [item["estimatedSpeed"] for item in vehicles if item["estimatedSpeed"] is not None]
    overspeed = sum(item["status"] == "OVERSPEED" for item in vehicles)
    line_crossings = sum(item["countedAtSeconds"] is not None for item in vehicles)
    type_counts = Counter(item["vehicleType"] for item in vehicles)
    color_counts = Counter(item["color"] for item in vehicles if item["color"] != "UNKNOWN")
    timeline = _build_timeline(vehicles, duration)
    violation_events = _build_violation_events(vehicles)
    violation_counts = Counter(event["type"] for event in violation_events)
    peak_bucket = max(timeline, key=lambda item: item["detections"], default=None)
    artifact_path = _transcode_output(raw_output) if output_writer is not None else None
    capabilities = specialists.capabilities()
    capabilities["wrongDirectionDetection"] = {
        "available": settings.allowedDirection != "both",
        "method": "calibrated trajectory compared with the configured travel direction"
        if settings.allowedDirection != "both"
        else None,
        "reason": None
        if settings.allowedDirection != "both"
        else "Allowed travel direction is set to both directions",
    }
    capabilities["wrongLaneDetection"] = {
        "available": False,
        "reason": "Per-lane movement and vehicle-class rules are not configured for uploaded video analysis",
    }

    video_details: dict[str, Any] = {
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
        for key in ("sourceType", "sourceUrl", "sourcePlatform", "sourceTitle", "sourceUploader"):
            if key in source_metadata:
                video_details[key] = source_metadata[key]

    calibrated_note = (
        "Speed uses four-point perspective calibration and ground-plane trajectories. "
        "Validate the measured road rectangle before operational use."
        if road.calibrated
        else "Perspective calibration was not supplied. Speed uses a fallback pixel scale and is low confidence."
    )
    result = {
        "video": video_details,
        "summary": {
            "totalVehicles": len(vehicles),
            "lineCrossingVehicles": line_crossings,
            "overspeedVehicles": overspeed,
            "totalViolations": len(violation_events),
            "violationCounts": dict(sorted(violation_counts.items())),
            "averageSpeed": round(sum(vehicle_speeds) / len(vehicle_speeds), 2) if vehicle_speeds else None,
            "maxSpeed": round(max(vehicle_speeds), 2) if vehicle_speeds else None,
            "speedLimit": speed_limit,
            "peakTrafficAtSeconds": peak_bucket["startSeconds"] if peak_bucket and peak_bucket["detections"] else None,
        },
        "vehicleTypes": [{"name": name, "value": count} for name, count in type_counts.most_common()],
        "vehicleColors": [{"name": name, "value": count} for name, count in color_counts.most_common()],
        "timeline": timeline,
        "vehicles": vehicles,
        "violations": violation_events,
        "artifacts": {
            "annotatedVideoUrl": artifact_url if artifact_path else None,
            "frameRate": round(output_fps, 2),
            "containsSampledFrames": sample_interval > 1,
        },
        "capabilities": capabilities,
        "analysis": {
            "completedAt": _iso_time(time.time()),
            "processingSeconds": round(time.monotonic() - started, 2),
            "model": Path(MODEL_PATH).name,
            "tracker": settings.tracker.removesuffix(".yaml"),
            "sampleEveryFrames": sample_interval,
            "analysisFps": round(output_fps, 2),
            "calibrationMetersPerPixel": meters_per_pixel,
            "perspectiveCalibrated": road.calibrated,
            "roadWidthMeters": road.width_meters if road.calibrated else None,
            "roadLengthMeters": road.length_meters if road.calibrated else None,
            "laneCount": road.lane_count if road.calibrated else None,
            "speedMethod": "Ground-plane homography trajectory" if road.calibrated else "Tracked pixel displacement × fallback road scale",
            "speedIsEstimated": True,
            "stabilizationEnabled": settings.stabilize,
            "stabilizedFrames": stabilization_frames,
            "plateRecognitionAvailable": capabilities["plateRecognition"]["available"],
            "note": calibrated_note,
        },
    }
    return result, artifact_path


def _build_violation_events(vehicles: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Flatten track-level rule results into seekable evidence events."""
    events: list[dict[str, Any]] = []
    for vehicle in vehicles:
        detected_at = vehicle["countedAtSeconds"]
        if detected_at is None:
            detected_at = vehicle["firstSeenSeconds"]
        for violation in vehicle["violations"]:
            events.append(
                {
                    "id": f'{vehicle["trackingId"]}:{violation}',
                    "trackingId": vehicle["trackingId"],
                    "type": violation,
                    "vehicleType": vehicle["vehicleType"],
                    "plate": vehicle["plate"],
                    "lane": vehicle["lane"],
                    "direction": vehicle["direction"],
                    "speed": vehicle["estimatedSpeed"],
                    "speedLimit": vehicle["speedLimit"],
                    "confidence": vehicle["confidence"],
                    "detectedAtSeconds": detected_at,
                }
            )
    return sorted(events, key=lambda event: (event["detectedAtSeconds"], event["trackingId"], event["type"]))


def _build_road_plane(settings: CalibrationSettings, width: int, height: int) -> _RoadPlane:
    if not settings.enabled or len(settings.sourcePoints) != 4:
        return _RoadPlane(None, None, settings.roadWidthMeters, settings.roadLengthMeters, settings.countingLinePosition, settings.laneCount, False)
    source = np.array(
        [[point.x * width, point.y * height] for point in settings.sourcePoints],
        dtype=np.float32,
    )
    if not cv2.isContourConvex(source.astype(np.int32)):
        raise ValueError("Calibration points must form a convex road rectangle")
    if abs(cv2.contourArea(source)) < width * height * 0.01:
        raise ValueError("Calibration area is too small; mark a larger visible road region")
    destination = np.array(
        [
            [0, 0],
            [settings.roadWidthMeters, 0],
            [settings.roadWidthMeters, settings.roadLengthMeters],
            [0, settings.roadLengthMeters],
        ],
        dtype=np.float32,
    )
    homography = cv2.getPerspectiveTransform(source, destination)
    if not np.isfinite(homography).all() or abs(float(np.linalg.det(homography))) < 1e-10:
        raise ValueError("Calibration points do not define a usable perspective transform")
    return _RoadPlane(homography, source, settings.roadWidthMeters, settings.roadLengthMeters, settings.countingLinePosition, settings.laneCount, True)


def _record_ground_speed(track: _Track, point: tuple[float, float], timestamp: float) -> None:
    track.ground_history.append((timestamp, point))
    candidates = [
        (sample_time, sample_point)
        for sample_time, sample_point in track.ground_history
        if 0.35 <= timestamp - sample_time <= 1.25
    ]
    if candidates:
        sample_time, sample_point = min(
            candidates,
            key=lambda sample: abs((timestamp - sample[0]) - 0.65),
        )
        elapsed = timestamp - sample_time
        speed = math.dist(point, sample_point) / elapsed * 3.6
        previous = _trimmed_average(list(track.speed_samples))
        acceleration = abs(speed - previous) / elapsed if previous is not None else 0
        if math.isfinite(speed) and 0.5 <= speed <= 200 and acceleration <= 60:
            track.speed_samples.append(speed)
    track.previous_ground_point = point
    track.previous_timestamp = timestamp


def _record_line_crossing(
    track: _Track,
    point: tuple[float, float],
    timestamp: float,
    counting_y: float,
) -> None:
    delta = point[1] - counting_y
    side = 1 if delta > 0 else -1 if delta < 0 else 0
    if track.previous_line_side is not None and side and side != track.previous_line_side:
        if track.frames_tracked >= 3 and track.counted_at is None:
            track.counted_at = timestamp
    if side:
        track.previous_line_side = side


def _serialize_track(
    track: _Track,
    speed_limit: float,
    calibrated: bool,
    allowed_direction: str,
) -> dict[str, Any]:
    vehicle_type = track.type_votes.most_common(1)[0][0] if track.type_votes else "unknown"
    color = track.color_votes.most_common(1)[0][0] if track.color_votes else "UNKNOWN"
    plate = track.plate_votes.most_common(1)[0][0] if track.plate_votes else None
    lane = track.lane_votes.most_common(1)[0][0] if track.lane_votes else None
    minimum_speed_samples = 3 if calibrated else 5
    reliable_samples = len(track.speed_samples) >= minimum_speed_samples
    speed = _trimmed_average(list(track.speed_samples)) if reliable_samples else None
    peak_speed = (
        float(np.percentile(list(track.speed_samples), 90))
        if reliable_samples
        else None
    )
    direction = _direction_label(track.first_ground_point, track.last_ground_point)
    if _is_wrong_direction(direction, allowed_direction):
        track.violations.add("WRONG_DIRECTION")
    if speed is not None and speed > speed_limit:
        track.violations.add("OVERSPEED")
    return {
        "trackingId": track.tracking_id,
        "vehicleType": vehicle_type,
        "color": color,
        "plate": plate,
        "plateStatus": "RECOGNIZED" if plate else "NOT_AVAILABLE",
        "plateConfidence": round(track.plate_confidence, 3) if plate else None,
        "lane": lane,
        "confidence": round(track.confidence, 3),
        "firstSeenSeconds": round(track.first_seen, 2),
        "lastSeenSeconds": round(track.last_seen, 2),
        "countedAtSeconds": round(track.counted_at, 2) if track.counted_at is not None else None,
        "trackedForSeconds": round(max(0, track.last_seen - track.first_seen), 2),
        "framesTracked": track.frames_tracked,
        "speedSamples": len(track.speed_samples),
        "estimatedSpeed": round(speed, 2) if speed is not None else None,
        "peakSpeed": round(peak_speed, 2) if peak_speed is not None else None,
        "speedConfidence": "HIGH" if calibrated and len(track.speed_samples) >= 8 else "MEDIUM" if calibrated and reliable_samples else "LOW",
        "speedLimit": speed_limit,
        "status": "INSUFFICIENT_DATA" if speed is None else "OVERSPEED" if speed > speed_limit else "NORMAL",
        "direction": direction,
        "violations": sorted(track.violations),
    }


def _is_wrong_direction(direction: str, allowed: str) -> bool:
    if allowed == "both" or direction in {"Unknown", "Stationary / unclear"}:
        return False
    normalized = direction.lower().replace(" ", "_")
    if allowed == "approaching":
        return not normalized.startswith("approaching")
    if allowed == "moving_away":
        return not normalized.startswith("moving_away")
    return normalized != allowed


def _draw_road_guides(frame: np.ndarray, road: _RoadPlane) -> None:
    if road.source_polygon is None:
        return
    polygon = road.source_polygon.astype(np.int32).reshape((-1, 1, 2))
    overlay = frame.copy()
    cv2.fillPoly(overlay, [polygon], (20, 140, 70))
    cv2.addWeighted(overlay, 0.09, frame, 0.91, 0, frame)
    cv2.polylines(frame, [polygon], True, (60, 220, 120), 2, cv2.LINE_AA)
    top_left, top_right, bottom_right, bottom_left = road.source_polygon
    for lane_index in range(1, road.lane_count):
        ratio = lane_index / road.lane_count
        top = top_left * (1 - ratio) + top_right * ratio
        bottom = bottom_left * (1 - ratio) + bottom_right * ratio
        cv2.line(frame, tuple(top.astype(int)), tuple(bottom.astype(int)), (80, 190, 115), 1, cv2.LINE_AA)
    line = road.line_pixels()
    if line:
        cv2.line(frame, line[0], line[1], (50, 230, 245), 3, cv2.LINE_AA)
        cv2.putText(frame, "COUNT LINE", line[0], cv2.FONT_HERSHEY_SIMPLEX, 0.55, (50, 230, 245), 2, cv2.LINE_AA)


def _draw_track(frame: np.ndarray, track: _Track) -> None:
    if track.last_box is None:
        return
    vehicle_type = track.type_votes.most_common(1)[0][0] if track.type_votes else "car"
    color = TRACK_COLORS.get(vehicle_type, (70, 210, 110))
    x1, y1, x2, y2 = track.last_box
    cv2.rectangle(frame, (x1, y1), (x2, y2), color, 2, cv2.LINE_AA)
    if len(track.trail) > 1:
        cv2.polylines(frame, [np.array(track.trail, dtype=np.int32)], False, color, 2, cv2.LINE_AA)
    speed = _trimmed_average(list(track.speed_samples)) if len(track.speed_samples) >= 3 else None
    label = f"#{track.tracking_id} {vehicle_type}"
    if track.lane_votes:
        label += f" L{track.lane_votes.most_common(1)[0][0]}"
    if speed is not None:
        label += f" {speed:.1f} km/h"
    if track.counted_at is not None:
        label += " | counted"
    (text_width, text_height), _ = cv2.getTextSize(label, cv2.FONT_HERSHEY_SIMPLEX, 0.5, 1)
    cv2.rectangle(frame, (x1, max(0, y1 - text_height - 10)), (x1 + text_width + 8, y1), color, -1)
    cv2.putText(frame, label, (x1 + 4, max(text_height + 2, y1 - 5)), cv2.FONT_HERSHEY_SIMPLEX, 0.5, (8, 16, 12), 1, cv2.LINE_AA)


def _transcode_output(raw_path: str) -> str | None:
    raw = Path(raw_path)
    if not raw.is_file() or raw.stat().st_size == 0:
        raw.unlink(missing_ok=True)
        return None
    final_path = tempfile.NamedTemporaryFile(
        prefix="trafficops-annotated-", suffix=".mp4", delete=False
    ).name
    ffmpeg = shutil.which("ffmpeg")
    if ffmpeg:
        completed = subprocess.run(
            [
                ffmpeg,
                "-y",
                "-loglevel",
                "error",
                "-i",
                str(raw),
                "-an",
                "-c:v",
                "libx264",
                "-preset",
                "veryfast",
                "-crf",
                "23",
                "-pix_fmt",
                "yuv420p",
                "-movflags",
                "+faststart",
                final_path,
            ],
            stdout=subprocess.DEVNULL,
            stderr=subprocess.PIPE,
            timeout=300,
            check=False,
        )
        if completed.returncode == 0 and Path(final_path).stat().st_size > 0:
            raw.unlink(missing_ok=True)
            return final_path
        log.warning("Annotated-video transcoding failed: %s", completed.stderr.decode(errors="ignore")[-500:])
    Path(final_path).unlink(missing_ok=True)
    return str(raw)


def _build_timeline(vehicles: list[dict[str, Any]], duration: float) -> list[dict[str, Any]]:
    if duration <= 0:
        return []
    bucket_size = max(1, math.ceil(duration / 12))
    bucket_count = max(1, math.ceil(duration / bucket_size))
    timeline = [
        {"label": _format_offset(index * bucket_size), "startSeconds": index * bucket_size, "detections": 0, "overspeed": 0}
        for index in range(bucket_count)
    ]
    for vehicle in vehicles:
        appearance = vehicle.get("countedAtSeconds")
        if appearance is None:
            appearance = vehicle["firstSeenSeconds"]
        index = min(len(timeline) - 1, int(appearance // bucket_size))
        timeline[index]["detections"] += 1
        if vehicle["status"] == "OVERSPEED":
            timeline[index]["overspeed"] += 1
    return timeline


def _trimmed_average(values: list[float]) -> float | None:
    if not values:
        return None
    ordered = np.asarray(sorted(values), dtype=np.float64)
    if len(ordered) >= 3:
        median = float(np.median(ordered))
        mad = float(np.median(np.abs(ordered - median)))
        tolerance = max(4.0, 3.0 * 1.4826 * mad)
        inliers = ordered[np.abs(ordered - median) <= tolerance]
        if len(inliers):
            ordered = inliers
    trim = int(len(ordered) * 0.1) if len(ordered) >= 10 else 0
    selected = ordered[trim:len(ordered) - trim] if trim else ordered
    return float(np.mean(selected))


def _direction_label(
    start: tuple[float, float] | None, end: tuple[float, float] | None
) -> str:
    if start is None or end is None:
        return "Unknown"
    dx, dy = end[0] - start[0], end[1] - start[1]
    if math.hypot(dx, dy) < 0.75:
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
    crop = frame[max(0, int(y1)):min(height, int(y2)), max(0, int(x1)):min(width, int(x2))]
    if crop.size == 0:
        return "UNKNOWN"
    crop_height, crop_width = crop.shape[:2]
    body = crop[int(crop_height * 0.15):int(crop_height * 0.8), int(crop_width * 0.15):int(crop_width * 0.85)]
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


def _vehicle_label(value: Any) -> str:
    normalized = str(value).lower().replace("_", " ").replace("-", " ").strip()
    return CLASS_ALIASES.get(normalized, normalized)


def _normalized_label(value: Any) -> str:
    return re.sub(r"[^a-z0-9]", "", str(value).lower())


def _format_offset(seconds: float) -> str:
    minutes, remaining = divmod(int(seconds), 60)
    hours, minutes = divmod(minutes, 60)
    return f"{hours:02d}:{minutes:02d}:{remaining:02d}" if hours else f"{minutes:02d}:{remaining:02d}"


def _iso_time(timestamp: float) -> str:
    from datetime import datetime, timezone

    return datetime.fromtimestamp(timestamp, tz=timezone.utc).isoformat().replace("+00:00", "Z")
