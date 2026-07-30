"""Persistent overspeed confirmation and duplicate-event suppression."""

from __future__ import annotations

from dataclasses import dataclass

from services.types import SpeedReading


@dataclass
class _Candidate:
    started_at: float
    frames: int = 0


class ViolationManager:
    def __init__(
        self,
        confirmation_frames: int = 5,
        confirmation_seconds: float = 1.0,
        cooldown_seconds: float = 30.0,
    ):
        self.confirmation_frames = max(1, confirmation_frames)
        self.confirmation_seconds = max(0.0, confirmation_seconds)
        self.cooldown_seconds = max(0.0, cooldown_seconds)
        self._candidates: dict[tuple[str, int], _Candidate] = {}
        self._last_confirmed: dict[tuple[str, int], float] = {}

    def evaluate(self, camera_id: str, tracking_id: int, speed: SpeedReading, timestamp: float) -> bool:
        key = (camera_id, tracking_id)
        if speed.smoothed_speed is None or speed.smoothed_speed <= speed.speed_limit:
            self._candidates.pop(key, None)
            return False
        last = self._last_confirmed.get(key)
        if last is not None and timestamp - last < self.cooldown_seconds:
            return False
        candidate = self._candidates.setdefault(key, _Candidate(timestamp))
        candidate.frames += 1
        confirmed = (
            candidate.frames >= self.confirmation_frames
            or timestamp - candidate.started_at >= self.confirmation_seconds
        )
        if confirmed:
            self._last_confirmed[key] = timestamp
            self._candidates.pop(key, None)
            return True
        return False

