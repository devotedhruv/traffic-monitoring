"""Background computer-vision worker shared by MJPEG and WebSocket clients."""

import asyncio
import logging
import math
import threading
import time
from collections import defaultdict, deque
from dataclasses import dataclass
from queue import Empty, Queue
from typing import Any

import cv2

from config.settings import (
    CAMERA_ID, CAMERA_NAME, METERS_PER_PIXEL, MODEL_PATH, SPEED_LIMIT, VIDEO_SOURCE,
)
from src.database import save_vehicle, update_vehicle_measurement

log = logging.getLogger("trafficops.runtime")
VEHICLE_CLASSES = {"car", "motorcycle", "bus", "truck"}


@dataclass
class TrackPoint:
    x: float
    y: float
    timestamp: float


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
        self.latest_detection: dict[str, Any] | None = None
        self.error: str | None = None
        self._frame: bytes | None = None
        self._frame_version = 0
        self._condition = threading.Condition()
        self._thread: threading.Thread | None = None

    def start(self) -> None:
        if self.running:
            return
        self.running = True
        self._thread = threading.Thread(target=self._run, name="traffic-cv-worker", daemon=True)
        self._thread.start()

    def stop(self) -> None:
        self.running = False
        with self._condition:
            self._condition.notify_all()
        if self._thread and self._thread.is_alive():
            self._thread.join(timeout=5)

    def wait_for_frame(self, version: int, timeout: float = 2) -> tuple[int, bytes | None]:
        with self._condition:
            if version == self._frame_version and self.running:
                self._condition.wait(timeout)
            return self._frame_version, self._frame

    def _publish(self, event: dict[str, Any]) -> None:
        broker.publish(event)

    def _set_frame(self, frame: Any) -> None:
        ok, encoded = cv2.imencode(".jpg", frame, [cv2.IMWRITE_JPEG_QUALITY, 82])
        if not ok:
            return
        with self._condition:
            self._frame = encoded.tobytes()
            self._frame_version += 1
            self._condition.notify_all()

    def _run(self) -> None:
        camera = None
        try:
            from ultralytics import YOLO

            log.info("Loading model %s", MODEL_PATH)
            model = YOLO(MODEL_PATH)
            source: int | str = int(VIDEO_SOURCE) if VIDEO_SOURCE.isdigit() else VIDEO_SOURCE
            camera = cv2.VideoCapture(source)
            if not camera.isOpened():
                raise RuntimeError(f"Cannot open video source: {VIDEO_SOURCE}")

            speed_tracker = CalibratedSpeedTracker()
            persisted: dict[int, int] = {}
            last_emitted: dict[int, float] = {}
            frame_counter = 0
            fps_started = time.monotonic()

            while self.running:
                ok, frame = camera.read()
                if not ok:
                    if isinstance(source, str):
                        camera.set(cv2.CAP_PROP_POS_FRAMES, 0)
                        continue
                    raise RuntimeError("Camera disconnected")

                now = time.monotonic()
                result = model.track(frame, persist=True, tracker="bytetrack.yaml", verbose=False)[0]
                output = result.plot()
                boxes = result.boxes
                if boxes is not None and boxes.id is not None:
                    for track_raw, class_raw, box_raw in zip(
                        boxes.id.tolist(), boxes.cls.tolist(), boxes.xyxy.tolist()
                    ):
                        track_id = int(track_raw)
                        vehicle_type = str(model.names[int(class_raw)])
                        if vehicle_type not in VEHICLE_CLASSES:
                            continue
                        x1, y1, x2, y2 = box_raw
                        speed = speed_tracker.update(track_id, ((x1 + x2) / 2, (y1 + y2) / 2), now)
                        status = "OVERSPEED" if speed > SPEED_LIMIT else "NORMAL"
                        color = (0, 0, 255) if status == "OVERSPEED" else (0, 210, 120)
                        cv2.putText(output, f"{speed:.1f} km/h", (int(x1), max(20, int(y1) - 8)), cv2.FONT_HERSHEY_SIMPLEX, 0.55, color, 2)
                        if speed <= 0:
                            continue
                        detection = {
                            "id": track_id, "trackingId": track_id, "vehicleType": vehicle_type,
                            "plate": None, "speed": speed, "speedLimit": SPEED_LIMIT,
                            "status": status, "detectedAt": _utc_now(),
                            "cameraId": CAMERA_ID, "cameraName": CAMERA_NAME, "snapshotUrl": None,
                        }
                        if track_id not in persisted and len(speed_tracker.samples[track_id]) >= 3:
                            record_id = save_vehicle(
                                "UNKNOWN", speed, status, track_id, vehicle_type, CAMERA_ID
                            )
                            detection["id"] = record_id
                            persisted[track_id] = record_id
                        elif track_id in persisted:
                            detection["id"] = persisted[track_id]
                        if now - last_emitted.get(track_id, 0) >= 0.5:
                            if track_id in persisted:
                                update_vehicle_measurement(persisted[track_id], speed, status)
                            self.latest_detection = detection
                            self._publish({"type": "vehicle_detection", "data": detection})
                            last_emitted[track_id] = now

                frame_counter += 1
                elapsed = time.monotonic() - fps_started
                if elapsed >= 1:
                    self.fps = frame_counter / elapsed
                    frame_counter = 0
                    fps_started = time.monotonic()
                    self._publish({"type": "system_status", "data": {
                        "connection": "connected", "fps": round(self.fps, 1),
                        "cameraId": CAMERA_ID, "timestamp": _utc_now(),
                    }})
                cv2.putText(output, f"FPS {self.fps:.1f}", (18, 30), cv2.FONT_HERSHEY_SIMPLEX, 0.65, (0, 220, 255), 2)
                self._set_frame(output)
        except Exception as exc:
            self.error = str(exc)
            self._publish({"type": "system_status", "data": {
                "connection": "offline", "fps": 0, "cameraId": CAMERA_ID,
                "timestamp": _utc_now(),
            }})
            log.exception("Traffic runtime stopped")
        finally:
            self.running = False
            if camera is not None:
                camera.release()
            with self._condition:
                self._condition.notify_all()


def _utc_now() -> str:
    from datetime import datetime, timezone
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


runtime = TrafficRuntime()


async def next_event(queue: Queue[dict[str, Any]]) -> dict[str, Any]:
    return await asyncio.to_thread(queue.get)
