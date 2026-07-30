"""Calibrated, timestamp-based vehicle speed estimation."""

from __future__ import annotations

import math
import statistics
from collections import defaultdict, deque
from dataclasses import dataclass, field

from services.camera_calibration import CameraCalibrationStore
from services.types import SpeedReading


@dataclass
class _SpeedState:
    first_timestamp: float
    previous_timestamp: float
    previous_point: tuple[float, float]
    samples: deque[float]
    accepted_total: float = 0.0
    accepted_count: int = 0
    maximum: float = 0.0
    rejected_count: int = 0


class SpeedEstimator:
    def __init__(
        self,
        calibrations: CameraCalibrationStore,
        speed_limit: float,
        smoothing_window: int = 7,
        minimum_samples: int = 3,
        minimum_duration: float = 0.5,
        maximum_speed: float = 200.0,
        maximum_acceleration: float = 80.0,
        near_limit_ratio: float = 0.9,
        severe_ratio: float = 1.25,
    ):
        self.calibrations = calibrations
        self.speed_limit = float(speed_limit)
        self.smoothing_window = max(3, int(smoothing_window))
        self.minimum_samples = max(2, int(minimum_samples))
        self.minimum_duration = max(0.0, float(minimum_duration))
        self.maximum_speed = float(maximum_speed)
        self.maximum_acceleration = float(maximum_acceleration)
        self.near_limit_ratio = float(near_limit_ratio)
        self.severe_ratio = float(severe_ratio)
        self._states: dict[tuple[str, int], _SpeedState] = {}

    def update(
        self,
        camera_id: str,
        tracking_id: int,
        image_point: tuple[float, float],
        timestamp: float,
    ) -> SpeedReading:
        calibration = self.calibrations.get(camera_id)
        if calibration is None:
            return self._empty("SPEED_CALIBRATION_REQUIRED", "REQUIRED")

        world_point = calibration.project(image_point)
        key = (camera_id, tracking_id)
        state = self._states.get(key)
        if state is None:
            self._states[key] = _SpeedState(
                first_timestamp=timestamp,
                previous_timestamp=timestamp,
                previous_point=world_point,
                samples=deque(maxlen=self.smoothing_window),
            )
            return self._empty("INSUFFICIENT_TRACKING_DATA", "CALIBRATED")

        elapsed = timestamp - state.previous_timestamp
        distance = math.dist(world_point, state.previous_point)
        state.previous_timestamp = timestamp
        state.previous_point = world_point
        if elapsed <= 0:
            return self._reading(state, timestamp, calibration.quality, None)

        instant = distance / elapsed * 3.6
        previous_stable = statistics.median(state.samples) if state.samples else None
        acceleration = abs(instant - previous_stable) / elapsed if previous_stable is not None else 0.0
        if not math.isfinite(instant) or instant < 0 or instant > self.maximum_speed or acceleration > self.maximum_acceleration:
            state.rejected_count += 1
            return self._reading(state, timestamp, calibration.quality, None)

        state.samples.append(instant)
        state.accepted_total += instant
        state.accepted_count += 1
        state.maximum = max(state.maximum, instant)
        return self._reading(state, timestamp, calibration.quality, instant)

    def _reading(
        self,
        state: _SpeedState,
        timestamp: float,
        calibration_quality: float,
        instant: float | None,
    ) -> SpeedReading:
        duration = max(0.0, timestamp - state.first_timestamp)
        enough = len(state.samples) >= self.minimum_samples and duration >= self.minimum_duration
        if not enough:
            return self._empty(
                "INSUFFICIENT_TRACKING_DATA", "CALIBRATED", len(state.samples)
            )

        median = statistics.median(state.samples)
        tolerance = max(8.0, median * 0.35)
        filtered = [sample for sample in state.samples if abs(sample - median) <= tolerance]
        smoothed = sum(filtered) / len(filtered) if filtered else median
        average = state.accepted_total / state.accepted_count
        reliability = state.accepted_count / max(1, state.accepted_count + state.rejected_count)
        maturity = min(1.0, len(state.samples) / max(self.minimum_samples * 2, 1))
        confidence = max(0.0, min(1.0, calibration_quality * reliability * (0.5 + 0.5 * maturity)))
        status = self._status(smoothed)
        return SpeedReading(
            instant_speed=round(instant if instant is not None else smoothed, 2),
            smoothed_speed=round(smoothed, 2),
            average_speed=round(average, 2),
            maximum_speed=round(state.maximum, 2),
            speed_limit=self.speed_limit,
            overspeed_amount=round(max(0.0, smoothed - self.speed_limit), 2),
            confidence=round(confidence, 3),
            status=status,
            calibration_status="CALIBRATED",
            sample_count=state.accepted_count,
        )

    def _status(self, speed: float) -> str:
        if speed >= self.speed_limit * self.severe_ratio:
            return "SEVERE_OVERSPEED"
        if speed > self.speed_limit:
            return "OVERSPEED"
        if speed >= self.speed_limit * self.near_limit_ratio:
            return "NEAR_SPEED_LIMIT"
        return "WITHIN_SPEED_LIMIT"

    def _empty(self, status: str, calibration_status: str, samples: int = 0) -> SpeedReading:
        return SpeedReading(
            instant_speed=None,
            smoothed_speed=None,
            average_speed=None,
            maximum_speed=None,
            speed_limit=self.speed_limit,
            overspeed_amount=0.0,
            confidence=0.0,
            status=status,
            calibration_status=calibration_status,
            sample_count=samples,
        )

    def forget(self, camera_id: str, tracking_id: int) -> None:
        self._states.pop((camera_id, tracking_id), None)

