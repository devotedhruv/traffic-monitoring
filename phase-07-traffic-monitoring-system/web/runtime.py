"""Background computer-vision worker shared by MJPEG and WebSocket clients."""

import asyncio
import json
import logging
import math
import subprocess
import threading
import time
from collections import defaultdict, deque
from dataclasses import dataclass
from pathlib import Path
from queue import Empty, Full, Queue
from typing import Any

import cv2
import numpy as np

from config.settings import (
    ANALYSIS_FPS, CAMERA_ID, CAMERA_NAME, LIVE_CONFIDENCE, LIVE_IMAGE_SIZE, LIVE_MODEL_PATH,
    LIVE_ACCURATE_FILE_MODE, LIVE_FILE_ANALYSIS_FPS, LIVE_MIN_SPEED_CONFIDENCE,
    LIVE_MIN_SPEED_SAMPLES, HELMET_MODEL_PATH, LIVE_ALLOWED_DIRECTION,
    LIVE_HELMET_CONFIDENCE, LIVE_HELMET_CONFIRMATIONS, LIVE_HELMET_SAMPLE_SECONDS,
    LIVE_LANE_CONFIRMATIONS, LIVE_LANE_GRACE_SECONDS, LIVE_LANE_MIN_DISTANCE_METERS,
    LIVE_LANE_MIN_TRAJECTORY_SECONDS, LIVE_LANE_RULES_JSON,
    LIVE_PREPROCESS_FILES, LIVE_STREAM_FPS, LIVE_STREAM_WIDTH, LIVE_TRACKER_CONFIG,
    LIVE_ROAD_CALIBRATION_QUALITY, LIVE_ROAD_LENGTH_METERS, LIVE_ROAD_POINTS,
    LIVE_ROAD_WIDTH_METERS,
    METERS_PER_PIXEL, PLATE_CONFIDENCE, PLATE_MIN_QUALITY, PLATE_MODEL_PATH,
    PLATE_OCR_ENGINE, PLATE_OCR_LANGUAGES, PLATE_SAMPLE_SECONDS, PROJECT_ROOT,
    SPEED_LIMIT, TESSERACT_CMD, VIDEO_SOURCE,
)
from services.camera_calibration import CameraCalibration
from services.plate_detector import PlateDetector
from services.plate_ocr import PlateOCRService, create_ocr_engine, ocr_dependency_status
from services.speed_estimator import SpeedEstimator
from src.database import (
    get_alert_for_violation, get_camera_calibration, get_camera_lane_rules,
    save_vehicle, save_violation,
    update_vehicle_measurement, update_vehicle_plate,
)
from web.violations import (
    HelmetSpecialist, HelmetVoteTracker, LaneRule, LaneViolationTracker,
    parse_lane_rules, person_is_vehicle_associated,
)

log = logging.getLogger("trafficops.runtime")
VEHICLE_CLASSES = {"bicycle", "car", "motorcycle", "bus", "truck"}
OVERLAY_FILTERS = {
    "all", "car", "bike", "bus", "truck", "person", "violation",
    "no_helmet", "wrong_lane", "overspeed",
}


def _prepare_live_file(source: str) -> tuple[str, float]:
    """Create a reusable, lower-cost proxy for oversized demo files."""
    source_path = Path(source)
    if not LIVE_PREPROCESS_FILES or not source_path.is_file():
        return source, 1.0
    probe = cv2.VideoCapture(str(source_path))
    try:
        source_fps = float(probe.get(cv2.CAP_PROP_FPS) or 0)
        source_width = int(probe.get(cv2.CAP_PROP_FRAME_WIDTH) or 0)
    finally:
        probe.release()
    if source_fps <= LIVE_STREAM_FPS * 1.05 and source_width <= LIVE_STREAM_WIDTH:
        return source, 1.0

    proxy_width = min(source_width, LIVE_STREAM_WIDTH) if source_width > 0 else LIVE_STREAM_WIDTH
    proxy_fps = min(source_fps, LIVE_STREAM_FPS) if source_fps > 0 else LIVE_STREAM_FPS
    spatial_scale = source_width / proxy_width if source_width > 0 else 1.0

    metadata = source_path.stat()
    cache_directory = PROJECT_ROOT / "output" / "live-cache"
    cache_directory.mkdir(parents=True, exist_ok=True)
    cache_name = (
        f"{source_path.stem}-{metadata.st_size}-{metadata.st_mtime_ns}-"
        f"{proxy_width}w-{proxy_fps:g}fps.mp4"
    )
    cached = cache_directory / cache_name
    if cached.exists() and cached.stat().st_size > 0:
        return str(cached), spatial_scale

    temporary = cached.with_suffix(".pending.mp4")
    temporary.unlink(missing_ok=True)
    log.info("Preparing live video proxy %s", cached)
    try:
        completed = subprocess.run(
            [
                "ffmpeg", "-nostdin", "-hide_banner", "-loglevel", "error", "-y",
                "-i", str(source_path),
                "-vf", f"fps={proxy_fps:g},scale={proxy_width}:-2",
                "-an", "-c:v", "libx264", "-preset", "veryfast", "-crf", "23",
                "-movflags", "+faststart", str(temporary),
            ],
            stdout=subprocess.DEVNULL,
            stderr=subprocess.PIPE,
            check=False,
            timeout=600,
        )
        if completed.returncode != 0 or not temporary.exists() or temporary.stat().st_size == 0:
            detail = completed.stderr.decode(errors="ignore")[-400:].strip()
            log.warning("Live proxy creation failed; using original video: %s", detail)
            temporary.unlink(missing_ok=True)
            return source, 1.0
        temporary.replace(cached)
        return str(cached), spatial_scale
    except (OSError, subprocess.SubprocessError) as exc:
        log.warning("Live proxy creation failed; using original video: %s", exc)
        temporary.unlink(missing_ok=True)
        return source, 1.0


@dataclass
class TrackPoint:
    x: float
    y: float
    timestamp: float


@dataclass(frozen=True)
class AnalysisFrame:
    generation: int
    timestamp: float
    frame: Any
    completed: threading.Event | None = None


@dataclass(frozen=True)
class BrowserFrame:
    timestamp: float
    frame: Any


@dataclass(frozen=True)
class LiveRoadProfile:
    source_points: tuple[tuple[float, float], ...]
    road_width_meters: float
    road_length_meters: float
    lane_count: int
    quality: float = LIVE_ROAD_CALIBRATION_QUALITY

    def as_dict(self) -> dict[str, Any]:
        return {
            "sourcePoints": [
                {"x": round(x, 6), "y": round(y, 6)} for x, y in self.source_points
            ],
            "roadWidthMeters": self.road_width_meters,
            "roadLengthMeters": self.road_length_meters,
            "laneCount": self.lane_count,
            "quality": self.quality,
        }


@dataclass(frozen=True)
class FrameAnnotation:
    track_id: int | None
    vehicle_type: str
    confidence: float
    box: tuple[int, int, int, int]
    speed: float
    status: str
    violations: tuple[str, ...] = ()
    plate: str | None = None
    vehicle_associated: bool = False


class CalibratedSpeedTracker:
    """Estimate speed from tracked-pixel displacement and a calibrated scale."""

    def __init__(self, meters_per_pixel: float = METERS_PER_PIXEL):
        self.scale = meters_per_pixel
        self.points: dict[int, TrackPoint] = {}
        self.samples: dict[int, deque[float]] = defaultdict(lambda: deque(maxlen=5))

    def update(self, track_id: int, center: tuple[float, float], timestamp: float) -> float:
        previous = self.points.get(track_id)
        self.points[track_id] = TrackPoint(*center, timestamp)
        if previous is None:
            return 0
        elapsed = timestamp - previous.timestamp
        if elapsed <= 0:
            return 0
        pixels = math.hypot(center[0] - previous.x, center[1] - previous.y)
        speed = pixels * self.scale / elapsed * 3.6
        if 0 <= speed <= 200:
            self.samples[track_id].append(speed)
        values = self.samples[track_id]
        return round(sum(values) / len(values), 2) if values else 0


@dataclass(frozen=True)
class LiveSpeedMeasurement:
    speed: float
    confidence: float
    sample_count: int
    ready: bool
    calibration: str


def should_persist_detection(file_source: bool, generation: int) -> bool:
    """Persist cameras continuously, but store a prerecorded file only once."""
    return not file_source or generation == 0


class _StaticCalibrationStore:
    def __init__(self, calibration: CameraCalibration):
        self.calibration = calibration

    def get(self, camera_id: str) -> CameraCalibration | None:
        return self.calibration if camera_id == self.calibration.camera_id else None


class PerspectiveSpeedTracker:
    """Project the configured road zone into metres and reject immature speed estimates."""

    def __init__(
        self,
        frame_width: int,
        frame_height: int,
        normalized_points: tuple[tuple[float, float], ...] = LIVE_ROAD_POINTS,
        road_width_meters: float = LIVE_ROAD_WIDTH_METERS,
        road_length_meters: float = LIVE_ROAD_LENGTH_METERS,
        calibration_quality: float = LIVE_ROAD_CALIBRATION_QUALITY,
        minimum_samples: int = LIVE_MIN_SPEED_SAMPLES,
        minimum_confidence: float = LIVE_MIN_SPEED_CONFIDENCE,
    ):
        if len(normalized_points) != 4:
            raise ValueError("Live perspective calibration requires four road points")
        image_points = np.asarray(
            [[x * frame_width, y * frame_height] for x, y in normalized_points],
            dtype=np.float32,
        )
        if not cv2.isContourConvex(image_points.astype(np.int32)):
            raise ValueError("Live road calibration points must form a convex polygon")
        if abs(cv2.contourArea(image_points)) < frame_width * frame_height * 0.01:
            raise ValueError("Live road calibration area is too small")
        world_points = [
            [0.0, 0.0],
            [float(road_width_meters), 0.0],
            [float(road_width_meters), float(road_length_meters)],
            [0.0, float(road_length_meters)],
        ]
        calibration = CameraCalibration(
            camera_id=CAMERA_ID,
            image_points=image_points.astype(float).tolist(),
            world_points=world_points,
            calibration_id="live-road-profile",
            quality=float(calibration_quality),
        )
        calibration.homography()
        self._calibration = calibration
        self._polygon = image_points
        self._minimum_samples = int(minimum_samples)
        self._minimum_confidence = float(minimum_confidence)
        self._estimator = SpeedEstimator(
            _StaticCalibrationStore(calibration),
            SPEED_LIMIT,
            smoothing_window=9,
            minimum_samples=self._minimum_samples,
            minimum_duration=0.6,
            maximum_speed=160.0,
            maximum_acceleration=45.0,
        )

    def update(
        self, tracking_id: int, image_point: tuple[float, float], timestamp: float
    ) -> LiveSpeedMeasurement:
        if cv2.pointPolygonTest(self._polygon, image_point, False) < 0:
            self._estimator.forget(CAMERA_ID, tracking_id)
            return LiveSpeedMeasurement(0.0, 0.0, 0, False, "OUTSIDE_CALIBRATED_ZONE")
        reading = self._estimator.update(CAMERA_ID, tracking_id, image_point, timestamp)
        speed = float(reading.smoothed_speed or 0.0)
        ready = bool(
            speed > 0
            and reading.sample_count >= self._minimum_samples
            and reading.confidence >= self._minimum_confidence
        )
        return LiveSpeedMeasurement(
            round(speed, 2),
            float(reading.confidence),
            int(reading.sample_count),
            ready,
            "PERSPECTIVE_ESTIMATED",
        )

    def project(self, image_point: tuple[float, float]) -> tuple[float, float] | None:
        if cv2.pointPolygonTest(self._polygon, image_point, False) < 0:
            return None
        return self._calibration.project(image_point)


class EventBroker:
    """Thread-safe fan-out so every WebSocket receives every event."""

    def __init__(self) -> None:
        self._subscribers: set[Queue[dict[str, Any]]] = set()
        self._lock = threading.Lock()

    def subscribe(self) -> Queue[dict[str, Any]]:
        queue: Queue[dict[str, Any]] = Queue(maxsize=200)
        with self._lock:
            self._subscribers.add(queue)
        return queue

    def unsubscribe(self, queue: Queue[dict[str, Any]]) -> None:
        with self._lock:
            self._subscribers.discard(queue)

    def publish(self, event: dict[str, Any]) -> None:
        with self._lock:
            subscribers = tuple(self._subscribers)
        for queue in subscribers:
            try:
                queue.put_nowait(event)
            except Exception:
                try:
                    queue.get_nowait()
                    queue.put_nowait(event)
                except Empty:
                    pass


broker = EventBroker()


class TrafficRuntime:
    def __init__(self) -> None:
        self.running = False
        self.fps = 0.0
        self.analysis_fps = 0.0
        self.source_fps = 0.0
        self.loop_count = 0
        self.confidence_threshold = LIVE_CONFIDENCE
        self.show_overlays = True
        self.overlay_filters = frozenset({"all"})
        self.lane_rules: tuple[LaneRule, ...] = ()
        self._lane_rules_version = 0
        self.helmet_available = False
        self.helmet_reason: str | None = "Dedicated helmet weights are not configured"
        self.plate_available = False
        self.plate_reason: str | None = "Dedicated plate weights and OCR are not configured"
        self.vehicle_model_loaded = False
        self.plate_model_loaded = False
        ocr_status = ocr_dependency_status(PLATE_OCR_ENGINE, TESSERACT_CMD, PLATE_OCR_LANGUAGES)
        self.ocr_backend = str(ocr_status["backend"])
        self.ocr_available = bool(ocr_status["available"])
        self.ocr_languages = list(ocr_status["languages"])
        self.active_tracks = 0
        self.active_detections = 0
        self.latest_detection: dict[str, Any] | None = None
        self.error: str | None = None
        self._configured_default_road_profile: LiveRoadProfile | None = (
            LiveRoadProfile(
                tuple(LIVE_ROAD_POINTS), LIVE_ROAD_WIDTH_METERS,
                LIVE_ROAD_LENGTH_METERS, 2,
            ) if LIVE_ROAD_POINTS else None
        )
        self.road_profile = self._configured_default_road_profile
        self._road_profile_version = 0
        self.speed_calibration = "PERSPECTIVE_ESTIMATED" if self.road_profile else "FALLBACK_PIXEL_SCALE"
        self.speed_processing_mode = "REAL_TIME"
        self.source_mode = "configured"
        self.camera_name = CAMERA_NAME
        self.browser_connected = False
        self.session_started_at: str | None = None
        self._frame: bytes | None = None
        self._frame_version = 0
        self._condition = threading.Condition()
        self._thread: threading.Thread | None = None
        self._stop_event = threading.Event()
        self._analysis_queue: Queue[AnalysisFrame] = Queue(maxsize=1)
        self._browser_queue: Queue[BrowserFrame] = Queue(maxsize=2)
        self._annotation_lock = threading.Lock()
        self._annotations: tuple[FrameAnnotation, ...] = ()
        self._annotation_generation = -1
        self._annotation_timestamp = -1.0
        self._generation = 0

    def start(self) -> None:
        if self.running:
            return
        self.error = None
        self.fps = 0.0
        self.analysis_fps = 0.0
        self.loop_count = 0
        self.active_tracks = 0
        self.active_detections = 0
        self.session_started_at = _utc_now()
        self._stop_event.clear()
        self._analysis_queue = Queue(maxsize=1)
        with self._annotation_lock:
            self._annotations = ()
            self._annotation_generation = -1
            self._annotation_timestamp = -1.0
        self.running = True
        self._thread = threading.Thread(target=self._run, name="traffic-cv-worker", daemon=True)
        self._thread.start()

    def stop(self) -> None:
        self.running = False
        self._stop_event.set()
        with self._condition:
            self._condition.notify_all()
        if self._thread and self._thread.is_alive():
            self._thread.join(timeout=5)

    def use_browser_source(self, name: str = "Browser Webcam") -> None:
        self.stop()
        self.source_mode = "browser"
        self.camera_name = " ".join(name.split())[:80] or "Browser Webcam"
        self.browser_connected = False
        self.load_road_profile()
        self._browser_queue = Queue(maxsize=2)
        self.start()

    def restore_configured_source(self) -> None:
        self.stop()
        self.source_mode = "configured"
        self.camera_name = CAMERA_NAME
        self.browser_connected = False
        self.load_road_profile()
        self._browser_queue = Queue(maxsize=2)
        self.start()

    def set_browser_connected(self, connected: bool) -> None:
        self.browser_connected = bool(connected)

    def offer_browser_frame(self, timestamp: float, frame: Any) -> bool:
        if self.source_mode != "browser" or not self.running:
            return False
        item = BrowserFrame(float(timestamp), frame)
        try:
            self._browser_queue.put_nowait(item)
            return True
        except Full:
            pass
        try:
            self._browser_queue.get_nowait()
        except Empty:
            pass
        try:
            self._browser_queue.put_nowait(item)
            return True
        except Full:
            return False

    def set_road_profile(self, profile: LiveRoadProfile | None) -> None:
        self.road_profile = profile
        self._road_profile_version += 1
        self.speed_calibration = "PERSPECTIVE_ESTIMATED" if profile else "FALLBACK_PIXEL_SCALE"

    def calibration_storage_key(self) -> str:
        return f"{CAMERA_ID}:browser" if self.source_mode == "browser" else CAMERA_ID

    def load_road_profile(self) -> LiveRoadProfile | None:
        saved = get_camera_calibration(self.calibration_storage_key())
        if saved:
            try:
                points = tuple(
                    (float(point["x"]), float(point["y"]))
                    for point in saved.get("sourcePoints", [])
                )
                profile = LiveRoadProfile(
                    points,
                    float(saved["roadWidthMeters"]),
                    float(saved["roadLengthMeters"]),
                    int(saved.get("laneCount", 2)),
                    float(saved.get("quality", LIVE_ROAD_CALIBRATION_QUALITY)),
                )
                if len(points) == 4:
                    self.set_road_profile(profile)
                    return profile
            except (KeyError, TypeError, ValueError):
                log.warning("Ignoring invalid saved road calibration for %s", CAMERA_ID)
        fallback = self._configured_default_road_profile if self.source_mode == "configured" else None
        self.set_road_profile(fallback)
        return fallback

    def wait_for_frame(self, version: int, timeout: float = 2) -> tuple[int, bytes | None]:
        with self._condition:
            if version == self._frame_version and self.running:
                self._condition.wait(timeout)
            return self._frame_version, self._frame

    def _publish(self, event: dict[str, Any]) -> None:
        broker.publish(event)

    def set_confidence(self, confidence: float) -> float:
        self.confidence_threshold = min(0.9, max(0.05, float(confidence)))
        return self.confidence_threshold

    def set_overlays_visible(self, visible: bool) -> bool:
        """Control stream rendering without stopping detection or tracking."""
        self.show_overlays = bool(visible)
        return self.show_overlays

    def set_overlay_filters(self, filters: list[str]) -> frozenset[str]:
        """Select which analyzed objects are drawn without changing AI processing."""
        selected = {str(value).strip().lower() for value in filters}
        invalid = selected - OVERLAY_FILTERS
        if invalid:
            raise ValueError(f"Unsupported overlay filters: {', '.join(sorted(invalid))}")
        self.overlay_filters = frozenset({"all"} if not selected or "all" in selected else selected)
        return self.overlay_filters

    def _annotation_is_visible(self, item: FrameAnnotation) -> bool:
        selected = self.overlay_filters
        if "all" in selected:
            return True
        labels: set[str] = set()
        if item.vehicle_type == "car":
            labels.add("car")
        if item.vehicle_type in {"bicycle", "motorcycle"}:
            labels.add("bike")
        if item.vehicle_type == "bus":
            labels.add("bus")
        if item.vehicle_type == "truck":
            labels.add("truck")
        if item.vehicle_type == "person" and not item.vehicle_associated:
            labels.add("person")
        if item.status == "OVERSPEED" or item.violations:
            labels.add("violation")
        if item.status == "OVERSPEED" or "OVERSPEED" in item.violations:
            labels.add("overspeed")
        if "NO_HELMET" in item.violations:
            labels.add("no_helmet")
        if "WRONG_LANE" in item.violations:
            labels.add("wrong_lane")
        return bool(labels & selected)

    def set_lane_rules(self, rules: tuple[LaneRule, ...]) -> tuple[LaneRule, ...]:
        self.lane_rules = tuple(rules)
        self._lane_rules_version += 1
        return self.lane_rules

    def load_lane_rules(self) -> tuple[LaneRule, ...]:
        configured_rules = get_camera_lane_rules(CAMERA_ID)
        if not configured_rules and LIVE_LANE_RULES_JSON:
            try:
                parsed_json = json.loads(LIVE_LANE_RULES_JSON)
                configured_rules = parsed_json if isinstance(parsed_json, list) else []
            except json.JSONDecodeError:
                log.warning("Ignoring invalid TRAFFIC_LIVE_LANE_RULES JSON")
        if not configured_rules:
            return self.set_lane_rules(())
        try:
            return self.set_lane_rules(parse_lane_rules(configured_rules))
        except (TypeError, ValueError) as exc:
            log.warning("Ignoring invalid live lane rules: %s", exc)
            return self.set_lane_rules(())

    def capabilities(self) -> dict[str, dict[str, Any]]:
        calibrated = self.road_profile is not None
        return {
            "models": {
                "vehicle": {
                    "configured": bool(LIVE_MODEL_PATH), "loaded": self.vehicle_model_loaded,
                    "version": Path(LIVE_MODEL_PATH).stem if LIVE_MODEL_PATH else None,
                },
                "plate": {
                    "configured": bool(PLATE_MODEL_PATH), "loaded": self.plate_model_loaded,
                    "version": Path(PLATE_MODEL_PATH).stem if PLATE_MODEL_PATH else None,
                },
                "helmet": {
                    "configured": bool(HELMET_MODEL_PATH), "loaded": self.helmet_available,
                    "version": Path(HELMET_MODEL_PATH).stem if HELMET_MODEL_PATH else None,
                },
            },
            "ocr": {
                "backend": self.ocr_backend,
                "available": self.ocr_available,
                "languages": self.ocr_languages,
            },
            "tracking": {
                "configuration": Path(LIVE_TRACKER_CONFIG).name,
            },
            "cameraCalibration": {
                "configured": calibrated,
                "id": "live-road-profile" if calibrated else None,
                "quality": self.road_profile.quality if self.road_profile else 0.0,
            },
            "plateRecognition": {
                "available": self.plate_available,
                "reason": self.plate_reason,
                "model": Path(PLATE_MODEL_PATH).name if self.plate_available else None,
            },
            "helmetDetection": {
                "available": self.helmet_available,
                "reason": self.helmet_reason,
                "model": Path(HELMET_MODEL_PATH).name if self.helmet_available else None,
            },
            "wrongLaneDetection": {
                "available": calibrated and bool(self.lane_rules),
                "reason": None if calibrated and self.lane_rules else (
                    "Perspective road calibration is not configured" if not calibrated
                    else "Camera lane rules are not configured"
                ),
                "method": "calibrated ground-plane trajectory" if calibrated else None,
            },
            "wrongDirectionDetection": {
                "available": calibrated and LIVE_ALLOWED_DIRECTION != "both",
                "reason": None if calibrated and LIVE_ALLOWED_DIRECTION != "both" else (
                    "Perspective road calibration is not configured" if not calibrated
                    else "A global allowed direction is not configured"
                ),
            },
        }

    def _set_frame(self, frame: Any) -> None:
        ok, encoded = cv2.imencode(".jpg", frame, [cv2.IMWRITE_JPEG_QUALITY, 72])
        if not ok:
            return
        with self._condition:
            self._frame = encoded.tobytes()
            self._frame_version += 1
            self._condition.notify_all()

    def _offer_analysis(self, item: AnalysisFrame) -> None:
        try:
            self._analysis_queue.put_nowait(item)
            return
        except Full:
            pass
        try:
            self._analysis_queue.get_nowait()
        except Empty:
            pass
        try:
            self._analysis_queue.put_nowait(item)
        except Full:
            pass

    def _offer_ordered_analysis(self, item: AnalysisFrame) -> None:
        """Preserve sampled file frames and wait until their analysis is complete."""
        while self.running and not self._stop_event.is_set():
            try:
                self._analysis_queue.put(item, timeout=0.2)
                break
            except Full:
                continue
        if item.completed is None:
            return
        while self.running and not self._stop_event.is_set():
            if item.completed.wait(0.2):
                return

    def _clear_analysis_queue(self) -> None:
        while True:
            try:
                self._analysis_queue.get_nowait()
            except Empty:
                return

    def _draw_annotations(
        self, frame: Any, generation: int, timestamp: float,
        scale_x: float = 1.0, scale_y: float = 1.0,
    ) -> Any:
        with self._annotation_lock:
            annotations = self._annotations
            annotation_generation = self._annotation_generation
            annotation_timestamp = self._annotation_timestamp
        if annotation_generation != generation or timestamp - annotation_timestamp > 1.0:
            return frame
        for item in annotations:
            if not self._annotation_is_visible(item):
                continue
            source_x1, source_y1, source_x2, source_y2 = item.box
            x1, x2 = round(source_x1 * scale_x), round(source_x2 * scale_x)
            y1, y2 = round(source_y1 * scale_y), round(source_y2 * scale_y)
            color = (45, 55, 235) if item.status == "OVERSPEED" or item.violations else (52, 211, 116)
            cv2.rectangle(frame, (x1, y1), (x2, y2), color, 2)
            measurement = f" {item.speed:.1f} km/h" if item.speed > 0 else ""
            identity = f"#{item.track_id} " if item.track_id is not None else ""
            label = f"{identity}{item.vehicle_type} {item.confidence:.2f}{measurement}"
            if item.plate:
                label += f" | {item.plate}"
            if item.violations:
                label += " | " + ", ".join(value.replace("_", " ") for value in item.violations)
            (width, height), baseline = cv2.getTextSize(label, cv2.FONT_HERSHEY_SIMPLEX, 0.48, 1)
            label_top = max(0, y1 - height - baseline - 7)
            cv2.rectangle(frame, (x1, label_top), (x1 + width + 8, y1), color, -1)
            cv2.putText(
                frame, label, (x1 + 4, y1 - baseline - 3), cv2.FONT_HERSHEY_SIMPLEX,
                0.48, (8, 18, 14), 1, cv2.LINE_AA,
            )
        return frame

    def _render_stream_frame(self, frame: Any, generation: int, timestamp: float) -> Any:
        height, width = frame.shape[:2]
        if width <= LIVE_STREAM_WIDTH:
            output = frame.copy()
            scale_x = scale_y = 1.0
        else:
            output_height = max(1, round(height * LIVE_STREAM_WIDTH / width))
            output = cv2.resize(
                frame, (LIVE_STREAM_WIDTH, output_height), interpolation=cv2.INTER_LINEAR
            )
            scale_x = LIVE_STREAM_WIDTH / width
            scale_y = output_height / height
        if not self.show_overlays:
            return output
        return self._draw_annotations(
            output, generation, timestamp,
            scale_x=scale_x,
            scale_y=scale_y,
        )

    def _save_plate_image(
        self, record_id: int, tracking_id: int, image: Any, generation: int
    ) -> str | None:
        if image is None or not getattr(image, "size", 0):
            return None
        directory = PROJECT_ROOT / "output" / "plates"
        directory.mkdir(parents=True, exist_ok=True)
        path = directory / f"vehicle-{record_id}-g{generation}-t{tracking_id}.jpg"
        return str(path) if cv2.imwrite(str(path), image) else None

    def _save_detection_snapshot(
        self,
        frame: Any,
        box: tuple[int, int, int, int],
        tracking_id: int,
        vehicle_type: str,
        generation: int,
    ) -> str | None:
        """Persist one immutable, contextual crop from the first detected frame."""
        if frame is None or not getattr(frame, "size", 0):
            return None
        frame_height, frame_width = frame.shape[:2]
        x1, y1, x2, y2 = box
        x1, x2 = sorted((max(0, min(frame_width, x1)), max(0, min(frame_width, x2))))
        y1, y2 = sorted((max(0, min(frame_height, y1)), max(0, min(frame_height, y2))))
        if x2 <= x1 or y2 <= y1:
            return None
        margin_x = max(12, round((x2 - x1) * 0.35))
        margin_y = max(12, round((y2 - y1) * 0.35))
        crop_x1, crop_y1 = max(0, x1 - margin_x), max(0, y1 - margin_y)
        crop_x2, crop_y2 = min(frame_width, x2 + margin_x), min(frame_height, y2 + margin_y)
        snapshot = frame[crop_y1:crop_y2, crop_x1:crop_x2].copy()
        if not snapshot.size:
            return None

        relative_box = (x1 - crop_x1, y1 - crop_y1, x2 - crop_x1, y2 - crop_y1)
        cv2.rectangle(
            snapshot, relative_box[:2], relative_box[2:], (52, 211, 116), 2
        )
        label = f"#{tracking_id} {vehicle_type}"
        (_, text_height), baseline = cv2.getTextSize(
            label, cv2.FONT_HERSHEY_SIMPLEX, 0.5, 1
        )
        label_y = max(text_height + baseline + 6, relative_box[1])
        cv2.putText(
            snapshot, label, (relative_box[0] + 3, label_y - baseline - 3),
            cv2.FONT_HERSHEY_SIMPLEX, 0.5, (52, 211, 116), 1, cv2.LINE_AA,
        )

        longest_edge = max(snapshot.shape[:2])
        if longest_edge > 960:
            scale = 960 / longest_edge
            snapshot = cv2.resize(
                snapshot,
                (max(1, round(snapshot.shape[1] * scale)), max(1, round(snapshot.shape[0] * scale))),
                interpolation=cv2.INTER_AREA,
            )
        safe_session = "".join(
            character for character in (self.session_started_at or "runtime")
            if character.isalnum()
        )[-24:]
        directory = PROJECT_ROOT / "output" / "detections"
        directory.mkdir(parents=True, exist_ok=True)
        path = directory / f"{safe_session}-g{generation}-t{tracking_id}.jpg"
        temporary = path.with_suffix(".pending.jpg")
        if not cv2.imwrite(str(temporary), snapshot, [cv2.IMWRITE_JPEG_QUALITY, 88]):
            return None
        temporary.replace(path)
        return str(path)

    def _save_live_violation(
        self,
        frame: Any,
        box: tuple[int, int, int, int],
        vehicle_id: int | None,
        tracking_id: int,
        vehicle_type: str,
        violation_type: str,
        confidence: float,
        source_generation: int,
        direction: str | None,
        lane_id: int | None,
        speed: float | None = None,
    ) -> dict[str, Any] | None:
        session_key = self.session_started_at or "runtime"
        safe_session = "".join(
            character for character in session_key if character.isalnum()
        )[-24:]
        evidence_directory = PROJECT_ROOT / "output" / "violations"
        evidence_directory.mkdir(parents=True, exist_ok=True)
        evidence_path = evidence_directory / (
            f"{safe_session}-g{source_generation}-t{tracking_id}-{violation_type.lower()}.jpg"
        )
        x1, y1, x2, y2 = box
        frame_height, frame_width = frame.shape[:2]
        margin_x = max(8, round((x2 - x1) * 0.2))
        margin_y = max(8, round((y2 - y1) * 0.2))
        crop = frame[
            max(0, y1 - margin_y):min(frame_height, y2 + margin_y),
            max(0, x1 - margin_x):min(frame_width, x2 + margin_x),
        ]
        stored_path: str | None = None
        if crop.size and cv2.imwrite(str(evidence_path), crop):
            stored_path = str(evidence_path)
        event = save_violation(
            vehicle_id=vehicle_id,
            tracking_id=tracking_id,
            violation_type=violation_type,
            confidence=max(0.0, min(1.0, float(confidence))),
            camera_id=CAMERA_ID,
            vehicle_type=vehicle_type,
            session_key=session_key,
            source_generation=source_generation,
            lane_id=lane_id,
            direction=direction,
            evidence_path=stored_path,
            speed=speed,
            speed_limit=SPEED_LIMIT,
        )
        if event is None:
            return None
        event["cameraName"] = self.camera_name
        self._publish({"type": "violation_event", "data": event})
        alert = get_alert_for_violation(event["id"])
        if alert is not None:
            self._publish({"type": "alert_event", "data": alert})
        return event

    def _analysis_loop(
        self, model: Any, vehicle_class_ids: list[int], meters_per_pixel: float,
        file_source: bool, helmet_specialist: HelmetSpecialist,
        plate_detector: PlateDetector, plate_ocr: PlateOCRService,
    ) -> None:
        try:
            self._process_analysis_loop(
                model, vehicle_class_ids, meters_per_pixel, file_source, helmet_specialist,
                plate_detector, plate_ocr,
            )
        except Exception as exc:
            self.error = str(exc)
            self.running = False
            self._stop_event.set()
            self._publish({"type": "system_status", "data": {
                "connection": "offline", "fps": 0, "analysisFps": 0,
                "cameraId": CAMERA_ID, "timestamp": _utc_now(),
            }})
            with self._condition:
                self._condition.notify_all()
            log.exception("Traffic analysis worker stopped")

    def _process_analysis_loop(
        self, model: Any, vehicle_class_ids: list[int], meters_per_pixel: float,
        file_source: bool, helmet_specialist: HelmetSpecialist,
        plate_detector: PlateDetector, plate_ocr: PlateOCRService,
    ) -> None:
        from ultralytics.trackers.byte_tracker import BYTETracker
        from ultralytics.utils import IterableSimpleNamespace, YAML

        tracker_options = IterableSimpleNamespace(**YAML.load(LIVE_TRACKER_CONFIG))
        if tracker_options.tracker_type != "bytetrack":
            raise ValueError("Live monitoring requires a ByteTrack configuration")
        tracker = BYTETracker(tracker_options)
        fallback_speed_tracker = CalibratedSpeedTracker(meters_per_pixel)
        perspective_speed_tracker: PerspectiveSpeedTracker | None = None
        persisted: dict[int, int] = {}
        last_emitted: dict[int, float] = {}
        last_helmet_sample: dict[int, float] = {}
        last_plate_sample: dict[int, float] = {}
        plate_images: dict[int, Any] = {}
        confirmed_plates: dict[int, str] = {}
        plate_snapshot_urls: dict[int, str] = {}
        detection_snapshot_urls: dict[int, str] = {}
        confirmed_violations: dict[int, set[str]] = defaultdict(set)
        helmet_votes = HelmetVoteTracker(LIVE_HELMET_CONFIRMATIONS)
        lane_tracker: LaneViolationTracker | None = None
        lane_rules_version = -1
        road_profile_version = -1
        generation = -1
        analyzed_frames = 0
        fps_started = time.monotonic()
        while self.running:
            try:
                item = self._analysis_queue.get(timeout=0.2)
            except Empty:
                continue
            if item.generation != generation:
                tracker.reset()
                fallback_speed_tracker = CalibratedSpeedTracker(meters_per_pixel)
                perspective_speed_tracker = None
                persisted = {}
                last_emitted = {}
                last_helmet_sample = {}
                last_plate_sample = {}
                plate_images = {}
                confirmed_plates = {}
                plate_snapshot_urls = {}
                detection_snapshot_urls = {}
                confirmed_violations = defaultdict(set)
                helmet_votes = HelmetVoteTracker(LIVE_HELMET_CONFIRMATIONS)
                lane_tracker = None
                lane_rules_version = -1
                generation = item.generation
            if road_profile_version != self._road_profile_version:
                perspective_speed_tracker = None
                lane_tracker = None
                lane_rules_version = -1
                road_profile_version = self._road_profile_version
            profile = self.road_profile
            if profile is not None and perspective_speed_tracker is None:
                frame_height, frame_width = item.frame.shape[:2]
                perspective_speed_tracker = PerspectiveSpeedTracker(
                    frame_width,
                    frame_height,
                    normalized_points=profile.source_points,
                    road_width_meters=profile.road_width_meters,
                    road_length_meters=profile.road_length_meters,
                    calibration_quality=profile.quality,
                )
                self.speed_calibration = "PERSPECTIVE_ESTIMATED"
            track_options: dict[str, Any] = {
                "source": item.frame,
                "conf": self.confidence_threshold,
                "imgsz": LIVE_IMAGE_SIZE,
                "verbose": False,
            }
            if vehicle_class_ids:
                track_options["classes"] = vehicle_class_ids
            result = model.predict(**track_options)[0]
            if item.generation != self._generation:
                if item.completed is not None:
                    item.completed.set()
                continue

            annotations: list[FrameAnnotation] = []
            boxes = result.boxes
            tracked_by_detection: dict[int, int] = {}
            if boxes is not None:
                tracks = tracker.update(boxes.cpu().numpy(), item.frame)
                tracked_by_detection = {
                    int(track[-1]): int(track[4]) for track in tracks
                    if len(track) >= 8
                }
            if boxes is not None and len(boxes):
                confidences = boxes.conf.tolist() if boxes.conf is not None else [0.0] * len(boxes)
                person_boxes = [
                    tuple(int(value) for value in box_raw)
                    for class_raw, box_raw in zip(boxes.cls.tolist(), boxes.xyxy.tolist())
                    if str(model.names[int(class_raw)]) == "person"
                ]
                vehicle_boxes = [
                    (
                        str(model.names[int(class_raw)]),
                        tuple(int(value) for value in box_raw),
                    )
                    for class_raw, box_raw in zip(boxes.cls.tolist(), boxes.xyxy.tolist())
                    if str(model.names[int(class_raw)]) in VEHICLE_CLASSES
                ]
                if perspective_speed_tracker is not None and lane_rules_version != self._lane_rules_version:
                    lane_tracker = LaneViolationTracker(
                        self.lane_rules,
                        profile.road_width_meters if profile else LIVE_ROAD_WIDTH_METERS,
                        LIVE_ALLOWED_DIRECTION,
                        LIVE_LANE_CONFIRMATIONS,
                        LIVE_LANE_GRACE_SECONDS,
                        LIVE_LANE_MIN_TRAJECTORY_SECONDS,
                        LIVE_LANE_MIN_DISTANCE_METERS,
                    )
                    lane_rules_version = self._lane_rules_version
                for detection_index, (class_raw, confidence, box_raw) in enumerate(zip(
                    boxes.cls.tolist(), confidences, boxes.xyxy.tolist()
                )):
                    track_id = tracked_by_detection.get(detection_index)
                    vehicle_type = str(model.names[int(class_raw)])
                    x1, y1, x2, y2 = (int(value) for value in box_raw)
                    if vehicle_type == "person":
                        person_box = (x1, y1, x2, y2)
                        annotations.append(FrameAnnotation(
                            track_id, vehicle_type, float(confidence), person_box,
                            0.0, "NORMAL", vehicle_associated=(
                                person_is_vehicle_associated(person_box, vehicle_boxes)
                            ),
                        ))
                        continue
                    if vehicle_type not in VEHICLE_CLASSES:
                        continue
                    measurement = LiveSpeedMeasurement(
                        0.0, 0.0, 0, False, self.speed_calibration
                    )
                    if track_id is not None:
                        image_point = ((x1 + x2) / 2, y2)
                        if perspective_speed_tracker is not None:
                            measurement = perspective_speed_tracker.update(
                                track_id, image_point, item.timestamp
                            )
                        else:
                            fallback_speed = fallback_speed_tracker.update(
                                track_id, image_point, item.timestamp
                            )
                            fallback_samples = len(fallback_speed_tracker.samples[track_id])
                            measurement = LiveSpeedMeasurement(
                                fallback_speed,
                                0.2 if fallback_samples >= LIVE_MIN_SPEED_SAMPLES else 0.0,
                                fallback_samples,
                                fallback_samples >= LIVE_MIN_SPEED_SAMPLES,
                                "FALLBACK_PIXEL_SCALE",
                            )
                    speed_available = measurement.ready
                    speed = measurement.speed if speed_available else 0.0
                    status = (
                        "OVERSPEED"
                        if measurement.ready
                        and measurement.confidence >= LIVE_MIN_SPEED_CONFIDENCE
                        and speed > SPEED_LIMIT
                        else "NORMAL"
                    )
                    if track_id is None:
                        annotations.append(FrameAnnotation(
                            None, vehicle_type, float(confidence), (x1, y1, x2, y2), speed, status
                        ))
                        continue
                    detection = {
                        "id": track_id, "trackingId": track_id, "vehicleType": vehicle_type,
                        "plate": None, "speed": speed, "speedLimit": SPEED_LIMIT,
                        "status": status, "detectedAt": _utc_now(),
                        "cameraId": CAMERA_ID, "cameraName": self.camera_name, "snapshotUrl": None,
                        "confidence": float(confidence),
                        "speedConfidence": round(measurement.confidence, 3),
                        "speedSamples": measurement.sample_count,
                        "speedCalibration": measurement.calibration,
                        "speedAvailable": speed_available,
                        "plateConfidence": None,
                        "plateStatus": "NOT_CONFIGURED" if not self.plate_available else "NOT_DETECTED",
                        "plateSnapshotUrl": None,
                    }
                    persist_detection = should_persist_detection(file_source, item.generation)
                    if persist_detection and track_id not in persisted:
                        snapshot_path = self._save_detection_snapshot(
                            item.frame, (x1, y1, x2, y2), track_id,
                            vehicle_type, item.generation,
                        )
                        record_id = save_vehicle(
                            "UNKNOWN", speed if speed_available else None,
                            status, track_id, vehicle_type, CAMERA_ID, snapshot_path,
                        )
                        detection["id"] = record_id
                        detection["snapshotUrl"] = (
                            f"/api/vehicles/{record_id}/snapshot" if snapshot_path else None
                        )
                        if detection["snapshotUrl"]:
                            detection_snapshot_urls[track_id] = detection["snapshotUrl"]
                        persisted[track_id] = record_id
                    elif track_id in persisted:
                        detection["id"] = persisted[track_id]
                        detection["snapshotUrl"] = detection_snapshot_urls.get(track_id)
                    plate_read = plate_ocr.result(track_id)
                    if (
                        self.plate_available
                        and item.timestamp - last_plate_sample.get(track_id, -100.0)
                        >= PLATE_SAMPLE_SECONDS
                    ):
                        vehicle_crop = item.frame[
                            max(0, y1):min(item.frame.shape[0], y2),
                            max(0, x1):min(item.frame.shape[1], x2),
                        ]
                        candidate = plate_detector.detect(vehicle_crop)
                        last_plate_sample[track_id] = item.timestamp
                        if candidate is not None and candidate.quality >= PLATE_MIN_QUALITY:
                            plate_images[track_id] = candidate.crop.copy()
                            plate_ocr.submit(
                                track_id, candidate.enhanced, analyzed_frames, item.timestamp,
                                candidate.quality,
                            )
                    if plate_read.status == "CONFIRMED" and plate_read.text:
                        detection["plate"] = plate_read.text
                        detection["plateConfidence"] = plate_read.confidence
                        detection["plateStatus"] = plate_read.status
                        if track_id in persisted and confirmed_plates.get(track_id) != plate_read.text:
                            plate_path = self._save_plate_image(
                                persisted[track_id], track_id, plate_images.get(track_id), item.generation
                            )
                            update_vehicle_plate(
                                persisted[track_id], plate_read.text, plate_read.confidence,
                                plate_read.status, plate_path,
                            )
                            detection["plateSnapshotUrl"] = (
                                f"/api/vehicles/{persisted[track_id]}/plate-image"
                                if plate_path else None
                            )
                            if detection["plateSnapshotUrl"]:
                                plate_snapshot_urls[track_id] = detection["plateSnapshotUrl"]
                            confirmed_plates[track_id] = plate_read.text
                        detection["plateSnapshotUrl"] = plate_snapshot_urls.get(track_id)
                    if persist_detection:
                        if status == "OVERSPEED" and "OVERSPEED" not in confirmed_violations[track_id]:
                            event = self._save_live_violation(
                                item.frame, (x1, y1, x2, y2), persisted.get(track_id),
                                track_id, vehicle_type, "OVERSPEED", measurement.confidence,
                                item.generation, direction=None, lane_id=None, speed=speed,
                            )
                            if event:
                                confirmed_violations[track_id].add("OVERSPEED")
                        if (
                            helmet_specialist.available
                            and vehicle_type == "motorcycle"
                            and item.timestamp - last_helmet_sample.get(track_id, -100.0)
                            >= LIVE_HELMET_SAMPLE_SECONDS
                        ):
                            helmet_result, helmet_confidence = helmet_specialist.inspect(
                                item.frame, (x1, y1, x2, y2), person_boxes
                            )
                            last_helmet_sample[track_id] = item.timestamp
                            confirmed = helmet_votes.update(
                                track_id, helmet_result, helmet_confidence
                            )
                            if confirmed is not None:
                                event = self._save_live_violation(
                                    item.frame, (x1, y1, x2, y2), persisted.get(track_id),
                                    track_id, vehicle_type, "NO_HELMET", confirmed,
                                    item.generation, direction=None, lane_id=None,
                                    speed=speed if speed_available else None,
                                )
                                if event:
                                    confirmed_violations[track_id].add("NO_HELMET")
                        if perspective_speed_tracker is not None and lane_tracker is not None:
                            ground_point = perspective_speed_tracker.project(((x1 + x2) / 2, y2))
                            if ground_point is not None:
                                for decision in lane_tracker.update(
                                    track_id, vehicle_type, ground_point, item.timestamp
                                ):
                                    event = self._save_live_violation(
                                        item.frame, (x1, y1, x2, y2), persisted.get(track_id),
                                        track_id, vehicle_type, decision.violation_type,
                                        decision.confidence, item.generation,
                                        direction=decision.direction, lane_id=decision.lane_id,
                                        speed=speed if speed_available else None,
                                    )
                                    if event:
                                        confirmed_violations[track_id].add(decision.violation_type)
                    detection["violations"] = sorted(confirmed_violations[track_id])
                    annotations.append(FrameAnnotation(
                        track_id, vehicle_type, float(confidence), (x1, y1, x2, y2),
                        speed, status, tuple(sorted(confirmed_violations[track_id])),
                        detection.get("plate"),
                    ))
                    if item.timestamp - last_emitted.get(track_id, -1.0) >= 0.5:
                        if persist_detection and track_id in persisted and speed_available:
                            update_vehicle_measurement(persisted[track_id], speed, status)
                        if speed_available:
                            self.latest_detection = detection
                        self._publish({"type": "vehicle_detection", "data": detection})
                        last_emitted[track_id] = item.timestamp

            with self._annotation_lock:
                self._annotations = tuple(annotations)
                self._annotation_generation = item.generation
                self._annotation_timestamp = item.timestamp
            self.active_detections = len(annotations)
            self.active_tracks = len({item.track_id for item in annotations if item.track_id is not None})

            analyzed_frames += 1
            elapsed = time.monotonic() - fps_started
            if elapsed >= 1:
                self.analysis_fps = analyzed_frames / elapsed
                analyzed_frames = 0
                fps_started = time.monotonic()
            if item.completed is not None:
                item.completed.set()

    def _run_browser_stream(self) -> None:
        generation = self._generation + 1
        self._generation = generation
        next_analysis_timestamp: float | None = None
        next_stream_timestamp: float | None = None
        previous_timestamp: float | None = None
        frames = 0
        fps_started = time.monotonic()
        last_frame_at = time.monotonic()
        reconnect_sent = False
        while self.running and self.source_mode == "browser":
            try:
                browser_frame = self._browser_queue.get(timeout=0.5)
            except Empty:
                if time.monotonic() - last_frame_at > 3 and not reconnect_sent:
                    self.fps = 0.0
                    self._publish({"type": "system_status", "data": {
                        "connection": "reconnecting", "fps": 0, "analysisFps": round(self.analysis_fps, 1),
                        "activeTracks": self.active_tracks, "activeDetections": self.active_detections,
                        "cameraId": CAMERA_ID, "timestamp": _utc_now(),
                    }})
                    reconnect_sent = True
                continue
            timestamp = browser_frame.timestamp
            if previous_timestamp is not None and timestamp <= previous_timestamp:
                generation += 1
                self._generation = generation
                self._clear_analysis_queue()
                next_analysis_timestamp = None
                next_stream_timestamp = None
            previous_timestamp = timestamp
            last_frame_at = time.monotonic()
            reconnect_sent = False
            if next_analysis_timestamp is None:
                next_analysis_timestamp = timestamp
            if next_stream_timestamp is None:
                next_stream_timestamp = timestamp
            if timestamp + 1e-6 >= next_analysis_timestamp:
                self._offer_analysis(AnalysisFrame(
                    generation, timestamp, browser_frame.frame.copy()
                ))
                next_analysis_timestamp = timestamp + 1 / ANALYSIS_FPS
            if timestamp + 1e-6 >= next_stream_timestamp:
                output = self._render_stream_frame(
                    browser_frame.frame, generation, timestamp
                )
                self._set_frame(output)
                next_stream_timestamp = timestamp + 1 / LIVE_STREAM_FPS
                frames += 1
                elapsed = time.monotonic() - fps_started
                if elapsed >= 1:
                    self.fps = frames / elapsed
                    self.source_fps = self.fps
                    frames = 0
                    fps_started = time.monotonic()
                    self._publish({"type": "system_status", "data": {
                        "connection": "connected", "fps": round(self.fps, 1),
                        "analysisFps": round(self.analysis_fps, 1),
                        "activeTracks": self.active_tracks,
                        "activeDetections": self.active_detections,
                        "cameraId": CAMERA_ID, "timestamp": _utc_now(),
                    }})

    def _run(self) -> None:
        camera = None
        analysis_thread = None
        plate_ocr: PlateOCRService | None = None
        try:
            from ultralytics import YOLO

            log.info("Loading live model %s", LIVE_MODEL_PATH)
            model = YOLO(LIVE_MODEL_PATH)
            self.vehicle_model_loaded = True
            helmet_specialist = HelmetSpecialist(HELMET_MODEL_PATH, LIVE_HELMET_CONFIDENCE)
            self.helmet_available = helmet_specialist.available
            self.helmet_reason = helmet_specialist.reason
            plate_detector = PlateDetector(PLATE_MODEL_PATH, PLATE_CONFIDENCE)
            self.plate_model_loaded = plate_detector.available
            plate_ocr = PlateOCRService(create_ocr_engine(
                PLATE_OCR_ENGINE,
                command=TESSERACT_CMD,
                languages=PLATE_OCR_LANGUAGES,
            ))
            self.ocr_backend = str(getattr(plate_ocr.engine, "backend", PLATE_OCR_ENGINE))
            self.ocr_available = plate_ocr.available
            configured_languages = str(getattr(plate_ocr.engine, "languages", ""))
            self.ocr_languages = [item for item in configured_languages.split("+") if item]
            self.plate_available = plate_detector.available and plate_ocr.available
            if not plate_detector.available:
                self.plate_reason = "Dedicated number-plate detector weights are not configured"
            elif not plate_ocr.available:
                self.plate_reason = f"{PLATE_OCR_ENGINE.title()} OCR is not installed or available"
            else:
                self.plate_reason = None
            self.load_lane_rules()
            vehicle_class_ids = [
                int(class_id) for class_id, name in model.names.items()
                if str(name) in VEHICLE_CLASSES or str(name) == "person"
            ]
            if self.source_mode == "browser":
                source = None
                spatial_scale = 1.0
            elif VIDEO_SOURCE.isdigit():
                source: int | str = int(VIDEO_SOURCE)
                spatial_scale = 1.0
            else:
                source, spatial_scale = _prepare_live_file(VIDEO_SOURCE)
            if source is not None:
                camera = cv2.VideoCapture(source)
                if not camera.isOpened():
                    raise RuntimeError(f"Cannot open video source: {VIDEO_SOURCE}")
            is_file = isinstance(source, str) and Path(source).is_file()
            accurate_file_mode = bool(is_file and LIVE_ACCURATE_FILE_MODE)
            analysis_target_fps = LIVE_FILE_ANALYSIS_FPS if accurate_file_mode else ANALYSIS_FPS
            self.speed_processing_mode = (
                "ORDERED_FILE_ANALYSIS" if accurate_file_mode else "REAL_TIME"
            )
            source_fps = float(camera.get(cv2.CAP_PROP_FPS) or 0) if camera else LIVE_STREAM_FPS
            self.source_fps = source_fps if 1 <= source_fps <= 120 else 25.0
            analysis_thread = threading.Thread(
                target=self._analysis_loop,
                args=(
                    model, vehicle_class_ids, METERS_PER_PIXEL * spatial_scale,
                    is_file, helmet_specialist, plate_detector, plate_ocr,
                ),
                name="traffic-ai-analysis",
                daemon=True,
            )
            analysis_thread.start()

            if self.source_mode == "browser":
                self._run_browser_stream()
                return

            generation = 0
            self._generation = generation
            frame_index = 0
            loop_started = time.monotonic()
            next_analysis_timestamp = 0.0
            next_stream_timestamp = 0.0
            frame_counter = 0
            fps_started = time.monotonic()

            while self.running:
                if is_file and not accurate_file_mode:
                    target_frame = int((time.monotonic() - loop_started) * self.source_fps)
                    while frame_index < target_frame:
                        if not camera.grab():
                            break
                        frame_index += 1
                ok, frame = camera.read()
                if not ok:
                    if is_file:
                        camera.set(cv2.CAP_PROP_POS_FRAMES, 0)
                        generation += 1
                        self._generation = generation
                        self.loop_count = generation
                        frame_index = 0
                        loop_started = time.monotonic()
                        next_analysis_timestamp = 0.0
                        next_stream_timestamp = 0.0
                        self._clear_analysis_queue()
                        with self._annotation_lock:
                            self._annotations = ()
                            self._annotation_generation = generation
                            self._annotation_timestamp = -1.0
                        continue
                    raise RuntimeError("Camera disconnected")

                media_timestamp = frame_index / self.source_fps if is_file else time.monotonic()
                if is_file and not accurate_file_mode:
                    delay = loop_started + media_timestamp - time.monotonic()
                    if delay > 0 and self._stop_event.wait(delay):
                        break

                if media_timestamp + 1e-6 >= next_analysis_timestamp:
                    if accurate_file_mode:
                        self._offer_ordered_analysis(AnalysisFrame(
                            generation, media_timestamp, frame.copy(), threading.Event()
                        ))
                    else:
                        self._offer_analysis(AnalysisFrame(generation, media_timestamp, frame.copy()))
                    next_analysis_timestamp += 1 / analysis_target_fps
                    if next_analysis_timestamp <= media_timestamp:
                        next_analysis_timestamp = media_timestamp + 1 / analysis_target_fps

                if media_timestamp + 1e-6 >= next_stream_timestamp:
                    output = self._render_stream_frame(frame, generation, media_timestamp)
                    self._set_frame(output)
                    next_stream_timestamp += 1 / LIVE_STREAM_FPS
                    if next_stream_timestamp <= media_timestamp:
                        next_stream_timestamp = media_timestamp + 1 / LIVE_STREAM_FPS
                    frame_counter += 1
                    elapsed = time.monotonic() - fps_started
                    if elapsed >= 1:
                        self.fps = frame_counter / elapsed
                        frame_counter = 0
                        fps_started = time.monotonic()
                        self._publish({"type": "system_status", "data": {
                            "connection": "connected", "fps": round(self.fps, 1),
                            "analysisFps": round(self.analysis_fps, 1),
                            "activeTracks": self.active_tracks,
                            "activeDetections": self.active_detections,
                            "cameraId": CAMERA_ID, "timestamp": _utc_now(),
                        }})
                frame_index += 1
        except Exception as exc:
            self.error = str(exc)
            self._publish({"type": "system_status", "data": {
                "connection": "offline", "fps": 0, "analysisFps": 0, "cameraId": CAMERA_ID,
                "timestamp": _utc_now(),
            }})
            log.exception("Traffic runtime stopped")
        finally:
            self.running = False
            self.vehicle_model_loaded = False
            self.plate_model_loaded = False
            self.helmet_available = False
            if self.source_mode == "browser":
                self.browser_connected = False
            self._stop_event.set()
            if analysis_thread is not None and analysis_thread.is_alive():
                analysis_thread.join(timeout=5)
            if camera is not None:
                camera.release()
            if plate_ocr is not None:
                plate_ocr.close()
            with self._condition:
                self._condition.notify_all()


def _utc_now() -> str:
    from datetime import datetime, timezone
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


runtime = TrafficRuntime()


async def next_event(queue: Queue[dict[str, Any]]) -> dict[str, Any]:
    return await asyncio.to_thread(queue.get)
