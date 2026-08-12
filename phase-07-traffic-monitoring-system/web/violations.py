"""Auditable live helmet and lane-violation evaluation helpers."""

from __future__ import annotations

import math
from collections import Counter, defaultdict, deque
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Iterable

import numpy as np


ALLOWED_DIRECTIONS = {
    "both", "approaching", "moving_away", "left_to_right", "right_to_left",
}
ROAD_VEHICLE_TYPES = {"bicycle", "car", "motorcycle", "bus", "truck"}


def _label(value: object) -> str:
    return "".join(character for character in str(value).lower() if character.isalnum())


@dataclass(frozen=True)
class LaneRule:
    lane_id: int
    min_x: float
    max_x: float
    allowed_direction: str = "both"
    allowed_vehicle_types: tuple[str, ...] = ()
    boundary_tolerance: float = 0.03

    @classmethod
    def from_dict(cls, value: dict[str, Any]) -> "LaneRule":
        lane_id = int(value.get("laneId", 0))
        min_x = float(value.get("minX", value.get("minXNormalized", -1)))
        max_x = float(value.get("maxX", value.get("maxXNormalized", -1)))
        direction = str(value.get("allowedDirection", "both")).strip().lower()
        types = tuple(str(item).strip().lower() for item in value.get("allowedVehicleTypes", []))
        tolerance = float(value.get("boundaryTolerance", 0.03))
        if lane_id < 1:
            raise ValueError("laneId must be at least 1")
        if not 0 <= min_x < max_x <= 1:
            raise ValueError("lane boundaries must satisfy 0 <= minX < maxX <= 1")
        if direction not in ALLOWED_DIRECTIONS:
            raise ValueError(f"Unsupported allowedDirection: {direction}")
        if any(item not in ROAD_VEHICLE_TYPES for item in types):
            raise ValueError("allowedVehicleTypes contains an unsupported vehicle class")
        if not 0 <= tolerance < (max_x - min_x) / 2:
            raise ValueError("boundaryTolerance is too large for the lane")
        return cls(lane_id, min_x, max_x, direction, types, tolerance)

    def as_dict(self) -> dict[str, Any]:
        return {
            "laneId": self.lane_id,
            "minX": self.min_x,
            "maxX": self.max_x,
            "allowedDirection": self.allowed_direction,
            "allowedVehicleTypes": list(self.allowed_vehicle_types),
            "boundaryTolerance": self.boundary_tolerance,
        }


def parse_lane_rules(values: Iterable[dict[str, Any]]) -> tuple[LaneRule, ...]:
    rules = tuple(sorted((LaneRule.from_dict(value) for value in values), key=lambda rule: rule.min_x))
    if len({rule.lane_id for rule in rules}) != len(rules):
        raise ValueError("laneId values must be unique")
    for previous, current in zip(rules, rules[1:]):
        if current.min_x < previous.max_x:
            raise ValueError("Lane boundaries must not overlap")
    return rules


class HelmetVoteTracker:
    """Confirm no-helmet only from repeated recent, confident observations."""

    def __init__(self, confirmations: int = 3, window: int | None = None):
        self.confirmations = max(2, int(confirmations))
        self.window = max(self.confirmations, int(window or self.confirmations * 2 + 1))
        self._observations: dict[int, deque[tuple[str, float]]] = defaultdict(
            lambda: deque(maxlen=self.window)
        )
        self._emitted: set[int] = set()

    def update(self, tracking_id: int, result: str, confidence: float) -> float | None:
        normalized = result.upper()
        if normalized not in {"HELMET", "NO_HELMET", "UNKNOWN"}:
            normalized = "UNKNOWN"
        self._observations[tracking_id].append((normalized, max(0.0, min(1.0, confidence))))
        if tracking_id in self._emitted:
            return None
        recent = self._observations[tracking_id]
        no_helmet = [score for label, score in recent if label == "NO_HELMET"]
        helmets = sum(label == "HELMET" for label, _ in recent)
        if len(no_helmet) >= self.confirmations and len(no_helmet) > helmets:
            self._emitted.add(tracking_id)
            return round(sum(no_helmet) / len(no_helmet), 3)
        return None


@dataclass
class _LaneTrack:
    first_seen: float
    points: deque[tuple[float, float, float]] = field(default_factory=lambda: deque(maxlen=24))
    recent_lanes: deque[int | None] = field(default_factory=lambda: deque(maxlen=16))
    candidate_lane: int | None = None
    candidate_since: float = 0.0


@dataclass(frozen=True)
class LaneDecision:
    violation_type: str
    confidence: float
    lane_id: int | None
    direction: str


def trajectory_direction(
    first: tuple[float, float], last: tuple[float, float], minimum_distance: float,
) -> str:
    dx, dy = last[0] - first[0], last[1] - first[1]
    if math.hypot(dx, dy) < minimum_distance:
        return "unclear"
    if abs(dy) >= abs(dx):
        return "approaching" if dy > 0 else "moving_away"
    return "left_to_right" if dx > 0 else "right_to_left"


def direction_is_wrong(direction: str, allowed: str) -> bool:
    return direction != "unclear" and allowed != "both" and direction != allowed


class LaneViolationTracker:
    """Evaluate mature ground-plane trajectories against stable lane rules."""

    def __init__(
        self,
        rules: Iterable[LaneRule],
        road_width_meters: float,
        global_allowed_direction: str = "both",
        confirmations: int = 5,
        grace_seconds: float = 1.0,
        minimum_trajectory_seconds: float = 0.75,
        minimum_distance_meters: float = 1.0,
    ):
        self.rules = tuple(rules)
        self.road_width = max(0.01, float(road_width_meters))
        self.global_direction = (
            global_allowed_direction if global_allowed_direction in ALLOWED_DIRECTIONS else "both"
        )
        self.confirmations = max(3, int(confirmations))
        self.grace_seconds = max(0.0, float(grace_seconds))
        self.minimum_duration = max(0.0, float(minimum_trajectory_seconds))
        self.minimum_distance = max(0.0, float(minimum_distance_meters))
        self._tracks: dict[int, _LaneTrack] = {}
        self._emitted: set[tuple[int, str]] = set()

    def update(
        self,
        tracking_id: int,
        vehicle_type: str,
        ground_point: tuple[float, float],
        timestamp: float,
    ) -> tuple[LaneDecision, ...]:
        state = self._tracks.setdefault(tracking_id, _LaneTrack(timestamp))
        state.points.append((ground_point[0], ground_point[1], timestamp))
        x_normalized = ground_point[0] / self.road_width
        rule = self._rule_for(x_normalized)
        lane_id = rule.lane_id if rule else None
        state.recent_lanes.append(lane_id)
        if lane_id != state.candidate_lane:
            state.candidate_lane = lane_id
            state.candidate_since = timestamp
        if len(state.points) < 2 or timestamp - state.first_seen < self.minimum_duration:
            return ()
        direction = trajectory_direction(
            (state.points[0][0], state.points[0][1]),
            (state.points[-1][0], state.points[-1][1]),
            self.minimum_distance,
        )
        if direction == "unclear":
            return ()
        decisions: list[LaneDecision] = []
        global_key = (tracking_id, "WRONG_DIRECTION")
        if direction_is_wrong(direction, self.global_direction) and global_key not in self._emitted:
            self._emitted.add(global_key)
            decisions.append(LaneDecision("WRONG_DIRECTION", 0.8, lane_id, direction))
        if rule is None or timestamp - state.candidate_since < self.grace_seconds:
            return tuple(decisions)
        recent = list(state.recent_lanes)[-(self.confirmations + 2):]
        votes = Counter(item for item in recent if item is not None)
        stable_votes = votes.get(rule.lane_id, 0)
        stable = stable_votes >= self.confirmations and stable_votes / max(1, len(recent)) >= 0.7
        type_wrong = bool(rule.allowed_vehicle_types and vehicle_type not in rule.allowed_vehicle_types)
        lane_direction_wrong = direction_is_wrong(direction, rule.allowed_direction)
        lane_key = (tracking_id, "WRONG_LANE")
        if stable and (type_wrong or lane_direction_wrong) and lane_key not in self._emitted:
            self._emitted.add(lane_key)
            confidence = min(0.98, 0.65 + 0.35 * stable_votes / len(state.recent_lanes))
            decisions.append(LaneDecision("WRONG_LANE", round(confidence, 3), rule.lane_id, direction))
        return tuple(decisions)

    def _rule_for(self, x_normalized: float) -> LaneRule | None:
        for rule in self.rules:
            if (
                rule.min_x + rule.boundary_tolerance
                <= x_normalized
                <= rule.max_x - rule.boundary_tolerance
            ):
                return rule
        return None


class HelmetSpecialist:
    """Load one validated helmet model and inspect only associated rider head crops."""

    def __init__(self, weights_path: str, confidence: float):
        self.model: Any | None = None
        self.reason: str | None = "Dedicated helmet weights are not configured"
        self.confidence = confidence
        path = Path(weights_path) if weights_path else None
        if path is None or not path.is_file():
            return
        try:
            from ultralytics import YOLO

            model = YOLO(str(path))
            names = {_label(name) for name in model.names.values()}
            if not ({"nohelmet", "withouthelmet"} & names):
                self.reason = "Helmet weights do not expose a no_helmet class"
                return
            self.model = model
            self.reason = None
        except Exception as exc:  # model incompatibility must not stop traffic monitoring
            self.reason = f"Helmet model could not be loaded: {exc}"

    @property
    def available(self) -> bool:
        return self.model is not None

    def inspect(
        self,
        frame: np.ndarray,
        motorcycle_box: tuple[int, int, int, int],
        person_boxes: Iterable[tuple[int, int, int, int]],
    ) -> tuple[str, float]:
        if self.model is None:
            return "UNKNOWN", 0.0
        rider = associate_rider(motorcycle_box, person_boxes)
        if rider is None:
            return "UNKNOWN", 0.0
        x1, y1, x2, y2 = rider
        height, width = frame.shape[:2]
        head_bottom = y1 + round((y2 - y1) * 0.48)
        margin_x = round((x2 - x1) * 0.18)
        margin_y = round((y2 - y1) * 0.08)
        crop = frame[
            max(0, y1 - margin_y):min(height, head_bottom + margin_y),
            max(0, x1 - margin_x):min(width, x2 + margin_x),
        ]
        if crop.size == 0 or crop.shape[0] < 12 or crop.shape[1] < 12:
            return "UNKNOWN", 0.0
        prediction = self.model.predict(crop, conf=self.confidence, verbose=False)[0]
        if prediction.boxes is None or len(prediction.boxes) == 0:
            return "UNKNOWN", 0.0
        best_result = ("UNKNOWN", 0.0)
        confidences = prediction.boxes.conf.tolist()
        for class_id, score in zip(prediction.boxes.cls.tolist(), confidences):
            label = _label(self.model.names[int(class_id)])
            result = (
                "NO_HELMET" if label in {"nohelmet", "withouthelmet"}
                else "HELMET" if label in {"helmet", "withhelmet"}
                else "UNKNOWN"
            )
            if result != "UNKNOWN" and float(score) > best_result[1]:
                best_result = (result, float(score))
        return best_result


def associate_rider(
    motorcycle: tuple[int, int, int, int],
    people: Iterable[tuple[int, int, int, int]],
) -> tuple[int, int, int, int] | None:
    mx1, my1, mx2, my2 = motorcycle
    motorcycle_width = max(1, mx2 - mx1)
    motorcycle_height = max(1, my2 - my1)
    best: tuple[float, tuple[int, int, int, int]] | None = None
    for person in people:
        px1, py1, px2, py2 = person
        person_width = max(1, px2 - px1)
        intersection = max(0, min(mx2, px2) - max(mx1, px1))
        horizontal_overlap = intersection / min(motorcycle_width, person_width)
        center_delta = abs((px1 + px2 - mx1 - mx2) / 2) / motorcycle_width
        vertical_match = my1 - motorcycle_height <= py2 <= my2 + motorcycle_height * 0.25
        if horizontal_overlap < 0.2 or center_delta > 0.8 or not vertical_match:
            continue
        score = horizontal_overlap - center_delta * 0.2
        if best is None or score > best[0]:
            best = (score, person)
    return best[1] if best else None
