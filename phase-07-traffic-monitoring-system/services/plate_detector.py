"""Dedicated plate detection and OpenCV plate enhancement."""

from __future__ import annotations

import logging
from dataclasses import dataclass
from pathlib import Path

import cv2
import numpy as np

from services.types import BoundingBox

log = logging.getLogger("trafficops.plate_detector")


@dataclass(frozen=True)
class PlateCandidate:
    bounding_box: BoundingBox
    confidence: float
    crop: np.ndarray
    enhanced: np.ndarray
    quality: float


class PlateEnhancer:
    def enhance(self, image: np.ndarray) -> tuple[np.ndarray, float]:
        if image.size == 0:
            return image, 0.0
        corrected = self._correct_perspective(image)
        gray = cv2.cvtColor(corrected, cv2.COLOR_BGR2GRAY) if corrected.ndim == 3 else corrected
        scale = max(1.0, 320 / max(gray.shape[1], 1))
        if scale > 1:
            gray = cv2.resize(gray, None, fx=scale, fy=scale, interpolation=cv2.INTER_CUBIC)
        denoised = cv2.bilateralFilter(gray, 7, 45, 45)
        enhanced = cv2.createCLAHE(clipLimit=2.2, tileGridSize=(8, 8)).apply(denoised)
        blur_score = float(cv2.Laplacian(enhanced, cv2.CV_64F).var())
        exposure = float(np.mean(enhanced))
        exposure_quality = max(0.0, 1.0 - abs(exposure - 135.0) / 135.0)
        quality = min(1.0, blur_score / 180.0) * exposure_quality
        return enhanced, round(quality, 3)

    def _correct_perspective(self, image: np.ndarray) -> np.ndarray:
        gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY) if image.ndim == 3 else image
        edges = cv2.Canny(gray, 60, 180)
        contours, _ = cv2.findContours(edges, cv2.RETR_LIST, cv2.CHAIN_APPROX_SIMPLE)
        area = image.shape[0] * image.shape[1]
        for contour in sorted(contours, key=cv2.contourArea, reverse=True)[:8]:
            perimeter = cv2.arcLength(contour, True)
            polygon = cv2.approxPolyDP(contour, 0.025 * perimeter, True)
            if len(polygon) != 4 or cv2.contourArea(polygon) < area * 0.25:
                continue
            points = polygon.reshape(4, 2).astype(np.float32)
            sums = points.sum(axis=1)
            differences = np.diff(points, axis=1).reshape(-1)
            ordered = np.asarray([
                points[np.argmin(sums)], points[np.argmin(differences)],
                points[np.argmax(sums)], points[np.argmax(differences)],
            ], dtype=np.float32)
            top_left, top_right, bottom_right, bottom_left = ordered
            width = int(max(np.linalg.norm(bottom_right - bottom_left), np.linalg.norm(top_right - top_left)))
            height = int(max(np.linalg.norm(top_right - bottom_right), np.linalg.norm(top_left - bottom_left)))
            if width < 20 or height < 8 or width / max(height, 1) < 1.4:
                continue
            target = np.asarray([[0, 0], [width - 1, 0], [width - 1, height - 1], [0, height - 1]], dtype=np.float32)
            return cv2.warpPerspective(image, cv2.getPerspectiveTransform(ordered, target), (width, height))
        return image


class PlateDetector:
    def __init__(self, model_path: str = "", confidence_threshold: float = 0.35):
        self.confidence_threshold = confidence_threshold
        self.enhancer = PlateEnhancer()
        self.model = None
        if model_path and Path(model_path).is_file():
            try:
                from ultralytics import YOLO

                self.model = YOLO(model_path)
            except Exception:
                log.exception("Could not load plate model %s", model_path)

    @property
    def available(self) -> bool:
        return self.model is not None

    def detect(self, vehicle_crop: np.ndarray) -> PlateCandidate | None:
        if self.model is None or vehicle_crop.size == 0:
            return None
        result = self.model.predict(vehicle_crop, conf=self.confidence_threshold, verbose=False)[0]
        boxes = result.boxes
        if boxes is None or len(boxes) == 0:
            return None
        confidences = boxes.conf.tolist()
        index = max(range(len(confidences)), key=confidences.__getitem__)
        x1, y1, x2, y2 = boxes.xyxy.tolist()[index]
        box = BoundingBox(x1, y1, x2, y2).clamp(vehicle_crop.shape[1], vehicle_crop.shape[0])
        crop = vehicle_crop[int(box.y1):int(box.y2), int(box.x1):int(box.x2)]
        enhanced, quality = self.enhancer.enhance(crop)
        return PlateCandidate(box, float(confidences[index]), crop, enhanced, quality)

