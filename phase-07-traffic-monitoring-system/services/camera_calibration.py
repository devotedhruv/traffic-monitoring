"""Camera-specific homography calibration and real-world projection."""

from __future__ import annotations

import hashlib
import json
import os
import threading
from dataclasses import asdict, dataclass
from pathlib import Path

import cv2
import numpy as np


@dataclass(frozen=True)
class CameraCalibration:
    camera_id: str
    image_points: list[list[float]]
    world_points: list[list[float]]
    calibration_id: str
    quality: float = 1.0

    def homography(self) -> np.ndarray:
        image = np.asarray(self.image_points, dtype=np.float32)
        world = np.asarray(self.world_points, dtype=np.float32)
        return cv2.getPerspectiveTransform(image, world)

    def project(self, point: tuple[float, float]) -> tuple[float, float]:
        projected = cv2.perspectiveTransform(
            np.asarray([[[point[0], point[1]]]], dtype=np.float32), self.homography()
        )[0][0]
        return float(projected[0]), float(projected[1])


class CameraCalibrationStore:
    """Thread-safe JSON-backed calibration store keyed by camera ID."""

    def __init__(self, path: str | Path):
        self.path = Path(path)
        self._lock = threading.RLock()
        self._calibrations: dict[str, CameraCalibration] = {}
        self._load()

    def _load(self) -> None:
        if not self.path.exists():
            return
        try:
            payload = json.loads(self.path.read_text(encoding="utf-8"))
            for camera_id, value in payload.items():
                self._calibrations[camera_id] = CameraCalibration(**value)
        except (OSError, ValueError, TypeError):
            self._calibrations = {}

    def _save(self) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        temporary = self.path.with_suffix(f"{self.path.suffix}.tmp")
        temporary.write_text(
            json.dumps({key: asdict(value) for key, value in self._calibrations.items()}, indent=2),
            encoding="utf-8",
        )
        os.replace(temporary, self.path)

    def get(self, camera_id: str) -> CameraCalibration | None:
        with self._lock:
            return self._calibrations.get(camera_id)

    def set(
        self,
        camera_id: str,
        image_points: list[list[float]],
        world_points: list[list[float]],
        quality: float = 1.0,
    ) -> CameraCalibration:
        if len(image_points) != 4 or len(world_points) != 4:
            raise ValueError("Exactly four image points and four world points are required")
        image = np.asarray(image_points, dtype=np.float32)
        world = np.asarray(world_points, dtype=np.float32)
        if image.shape != (4, 2) or world.shape != (4, 2):
            raise ValueError("Calibration points must be [x, y] pairs")
        if abs(cv2.contourArea(image)) < 1 or abs(cv2.contourArea(world)) < 0.01:
            raise ValueError("Calibration points must describe non-zero areas")
        digest = hashlib.sha256(
            json.dumps([camera_id, image_points, world_points], sort_keys=True).encode("utf-8")
        ).hexdigest()[:12]
        calibration = CameraCalibration(
            camera_id=camera_id,
            image_points=image.astype(float).tolist(),
            world_points=world.astype(float).tolist(),
            calibration_id=f"cal-{digest}",
            quality=max(0.0, min(1.0, float(quality))),
        )
        calibration.homography()
        with self._lock:
            self._calibrations[camera_id] = calibration
            self._save()
        return calibration

