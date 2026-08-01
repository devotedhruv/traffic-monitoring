"""YOLO detector/tracker adapter returning normalized vehicle observations."""

from __future__ import annotations

from typing import Any

from config.settings import TRACKER_CONFIG
from services.types import BoundingBox, VehicleObservation

DEFAULT_VEHICLE_CLASSES = {
    "car", "motorcycle", "bus", "truck", "van", "bicycle", "taxi", "other"
}


class VehicleDetector:
    def __init__(
        self,
        model: Any,
        tracker_config: str = TRACKER_CONFIG,
        confidence_threshold: float = 0.3,
        supported_classes: set[str] | None = None,
    ):
        self.model = model
        self.tracker_config = tracker_config
        self.confidence_threshold = confidence_threshold
        self.supported_classes = supported_classes or DEFAULT_VEHICLE_CLASSES

    def detect(self, frame: Any) -> list[VehicleObservation]:
        result = self.model.track(
            source=frame,
            persist=True,
            tracker=self.tracker_config,
            conf=self.confidence_threshold,
            verbose=False,
        )[0]
        boxes = result.boxes
        if boxes is None or boxes.id is None:
            return []
        confidences = boxes.conf.tolist() if boxes.conf is not None else [0.0] * len(boxes)
        observations: list[VehicleObservation] = []
        for tracking_id, class_id, confidence, coordinates in zip(
            boxes.id.tolist(), boxes.cls.tolist(), confidences, boxes.xyxy.tolist()
        ):
            vehicle_type = str(self.model.names[int(class_id)]).lower()
            if vehicle_type not in self.supported_classes:
                continue
            observations.append(VehicleObservation(
                tracking_id=int(tracking_id),
                vehicle_type=vehicle_type,
                confidence=float(confidence),
                bounding_box=BoundingBox(*map(float, coordinates)),
            ))
        return observations
