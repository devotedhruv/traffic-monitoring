"""Track lifecycle, selection, trajectory, loss, and same-ID reappearance state."""

from __future__ import annotations

import threading
from collections.abc import Iterable

from services.types import TrackRecord, VehicleObservation


class VehicleTracker:
    def __init__(self, lost_timeout: float = 1.0, reidentification_window: float = 5.0, trajectory_limit: int = 120):
        self.lost_timeout = max(0.1, float(lost_timeout))
        self.reidentification_window = max(self.lost_timeout, float(reidentification_window))
        self.trajectory_limit = max(10, int(trajectory_limit))
        self._tracks: dict[int, TrackRecord] = {}
        self._selected_id: int | None = None
        self._lock = threading.RLock()

    @property
    def selected_id(self) -> int | None:
        with self._lock:
            return self._selected_id

    def select(self, tracking_id: int) -> TrackRecord:
        with self._lock:
            track = self._tracks.get(tracking_id)
            if track is None or track.selection_status == "LOST":
                raise KeyError(tracking_id)
            self._selected_id = tracking_id
            track.selection_status = "SELECTED"
            return track

    def clear_selection(self) -> None:
        with self._lock:
            self._selected_id = None

    def get(self, tracking_id: int) -> TrackRecord | None:
        with self._lock:
            return self._tracks.get(tracking_id)

    def update(self, observations: Iterable[VehicleObservation], timestamp: float) -> list[TrackRecord]:
        with self._lock:
            visible_ids: set[int] = set()
            visible: list[TrackRecord] = []
            for observation in observations:
                visible_ids.add(observation.tracking_id)
                track = self._tracks.get(observation.tracking_id)
                reidentified = bool(
                    track
                    and track.selection_status == "LOST"
                    and timestamp - track.last_seen_at <= self.reidentification_window
                )
                if track is None:
                    track = TrackRecord(
                        tracking_id=observation.tracking_id,
                        vehicle_type=observation.vehicle_type,
                        confidence=observation.confidence,
                        bounding_box=observation.bounding_box,
                        first_seen_at=timestamp,
                        last_seen_at=timestamp,
                    )
                    self._tracks[observation.tracking_id] = track
                else:
                    track.vehicle_type = observation.vehicle_type
                    track.confidence = observation.confidence
                    track.bounding_box = observation.bounding_box
                    track.last_seen_at = timestamp
                    track.frames_tracked += 1
                x, y = observation.bounding_box.bottom_center
                track.trajectory.append((x, y, timestamp))
                if len(track.trajectory) > self.trajectory_limit:
                    del track.trajectory[:-self.trajectory_limit]
                if reidentified:
                    track.selection_status = "RE-IDENTIFIED"
                elif observation.tracking_id == self._selected_id:
                    track.selection_status = "TRACKING"
                else:
                    track.selection_status = "TRACKING"
                visible.append(track)

            stale_ids: list[int] = []
            for tracking_id, track in self._tracks.items():
                if tracking_id in visible_ids:
                    continue
                missing_for = timestamp - track.last_seen_at
                if missing_for >= self.lost_timeout:
                    track.selection_status = "LOST"
                if missing_for > self.reidentification_window and tracking_id != self._selected_id:
                    stale_ids.append(tracking_id)
            for tracking_id in stale_ids:
                del self._tracks[tracking_id]

            if self._selected_id is not None:
                selected = self._tracks.get(self._selected_id)
                if selected and selected.selection_status == "LOST":
                    visible.append(selected)
                elif selected is None:
                    self._selected_id = None
            return visible

    def active(self) -> list[TrackRecord]:
        with self._lock:
            return list(self._tracks.values())

