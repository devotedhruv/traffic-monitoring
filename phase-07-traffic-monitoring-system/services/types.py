"""Shared, dependency-light data structures for the vision pipeline."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


@dataclass(frozen=True)
class BoundingBox:
    x1: float
    y1: float
    x2: float
    y2: float

    @property
    def width(self) -> float:
        return max(0.0, self.x2 - self.x1)

    @property
    def height(self) -> float:
        return max(0.0, self.y2 - self.y1)

    @property
    def bottom_center(self) -> tuple[float, float]:
        return ((self.x1 + self.x2) / 2.0, self.y2)

    def clamp(self, width: int, height: int) -> "BoundingBox":
        return BoundingBox(
            max(0.0, min(float(width), self.x1)),
            max(0.0, min(float(height), self.y1)),
            max(0.0, min(float(width), self.x2)),
            max(0.0, min(float(height), self.y2)),
        )

    def as_dict(self) -> dict[str, float]:
        return {"x1": self.x1, "y1": self.y1, "x2": self.x2, "y2": self.y2}


@dataclass(frozen=True)
class VehicleObservation:
    tracking_id: int
    vehicle_type: str
    confidence: float
    bounding_box: BoundingBox


@dataclass
class TrackRecord:
    tracking_id: int
    vehicle_type: str
    confidence: float
    bounding_box: BoundingBox
    first_seen_at: float
    last_seen_at: float
    frames_tracked: int = 1
    selection_status: str = "TRACKING"
    trajectory: list[tuple[float, float, float]] = field(default_factory=list)

    @property
    def tracking_duration(self) -> float:
        return max(0.0, self.last_seen_at - self.first_seen_at)


@dataclass(frozen=True)
class SpeedReading:
    instant_speed: float | None
    smoothed_speed: float | None
    average_speed: float | None
    maximum_speed: float | None
    speed_limit: float
    overspeed_amount: float
    confidence: float
    status: str
    calibration_status: str
    sample_count: int


@dataclass(frozen=True)
class PlateRead:
    text: str | None = None
    confidence: float = 0.0
    status: str = "NOT_DETECTED"
    observations: int = 0


@dataclass
class ProcessedVehicle:
    track: TrackRecord
    speed: SpeedReading
    plate: PlateRead
    vehicle_color: str = "UNKNOWN"
    direction: str = "UNKNOWN"
    lane: str = "UNKNOWN"
    vehicle_image_path: str | None = None
    plate_image_path: str | None = None
    violation_confirmed: bool = False
    violation_id: str | None = None
    metadata: dict[str, Any] = field(default_factory=dict)

