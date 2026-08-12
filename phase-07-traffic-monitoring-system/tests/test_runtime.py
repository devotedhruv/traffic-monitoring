import threading
import unittest

import numpy as np

from services.plate_ocr import PlateAggregator
from web.runtime import (
    AnalysisFrame, CalibratedSpeedTracker, FrameAnnotation, LiveRoadProfile,
    PerspectiveSpeedTracker, TrafficRuntime, should_persist_detection,
)
from web.violations import (
    HelmetSpecialist, HelmetVoteTracker, LaneRule, LaneViolationTracker, associate_rider,
    person_is_vehicle_associated,
)


class LiveRuntimeTests(unittest.TestCase):
    def test_plate_text_requires_consistent_valid_multi_frame_reads(self):
        aggregator = PlateAggregator(minimum_confirmed_observations=2)

        first = aggregator.add(7, "BA 12 PA 1234", 0.92, 1.0)
        invalid = aggregator.add(7, "1234", 0.99, 1.1)
        confirmed = aggregator.add(7, "BA-12-PA-1234", 0.9, 1.2)

        self.assertNotEqual(first.status, "CONFIRMED")
        self.assertNotEqual(invalid.status, "CONFIRMED")
        self.assertEqual(confirmed.status, "CONFIRMED")
        self.assertEqual(confirmed.text, "BA 12 PA 1234")

    def test_speed_uses_supplied_media_timestamps(self):
        tracker = CalibratedSpeedTracker(meters_per_pixel=0.05)

        self.assertEqual(tracker.update(7, (0, 0), 1.0), 0)
        speed = tracker.update(7, (10, 0), 1.5)

        self.assertAlmostEqual(speed, 3.6)

    def test_perspective_speed_uses_ground_metres_and_requires_mature_track(self):
        tracker = PerspectiveSpeedTracker(
            100,
            100,
            normalized_points=((0, 0), (1, 0), (1, 1), (0, 1)),
            road_width_meters=100,
            road_length_meters=100,
            calibration_quality=1.0,
            minimum_samples=3,
            minimum_confidence=0.1,
        )

        readings = [tracker.update(7, (50, 10 + index), index * 0.1) for index in range(7)]

        self.assertFalse(readings[2].ready)
        self.assertTrue(readings[-1].ready)
        self.assertAlmostEqual(readings[-1].speed, 36.0, places=1)
        self.assertGreaterEqual(readings[-1].sample_count, 3)

        outside = tracker.update(8, (120, 120), 1.0)
        self.assertFalse(outside.ready)
        self.assertEqual(outside.calibration, "OUTSIDE_CALIBRATED_ZONE")

    def test_analysis_queue_keeps_the_newest_frame(self):
        runtime = TrafficRuntime()
        first = AnalysisFrame(0, 0.0, np.zeros((2, 2, 3), dtype=np.uint8))
        latest = AnalysisFrame(0, 0.5, np.ones((2, 2, 3), dtype=np.uint8))

        runtime._offer_analysis(first)
        runtime._offer_analysis(latest)

        queued = runtime._analysis_queue.get_nowait()
        self.assertEqual(queued.timestamp, 0.5)
        self.assertTrue(np.array_equal(queued.frame, latest.frame))

    def test_browser_queue_drops_stale_frames_without_stopping_tracking(self):
        runtime = TrafficRuntime()
        runtime.running = True
        runtime.source_mode = "browser"

        self.assertTrue(runtime.offer_browser_frame(1.0, np.zeros((2, 2, 3), dtype=np.uint8)))
        self.assertTrue(runtime.offer_browser_frame(2.0, np.ones((2, 2, 3), dtype=np.uint8)))
        self.assertTrue(runtime.offer_browser_frame(3.0, np.full((2, 2, 3), 2, dtype=np.uint8)))

        queued = [runtime._browser_queue.get_nowait(), runtime._browser_queue.get_nowait()]
        self.assertEqual([item.timestamp for item in queued], [2.0, 3.0])

    def test_live_profile_serializes_measured_geometry(self):
        profile = LiveRoadProfile(
            ((0.2, 0.3), (0.8, 0.3), (0.9, 0.9), (0.1, 0.9)),
            road_width_meters=9,
            road_length_meters=42,
            lane_count=3,
            quality=0.85,
        )

        payload = profile.as_dict()

        self.assertEqual(payload["roadLengthMeters"], 42)
        self.assertEqual(payload["laneCount"], 3)
        self.assertEqual(len(payload["sourcePoints"]), 4)

    def test_ordered_file_analysis_waits_for_measurement_completion(self):
        runtime = TrafficRuntime()
        runtime.running = True
        completed = threading.Event()
        item = AnalysisFrame(0, 0.5, np.zeros((2, 2, 3), dtype=np.uint8), completed)
        producer = threading.Thread(target=runtime._offer_ordered_analysis, args=(item,))

        producer.start()
        queued = runtime._analysis_queue.get(timeout=1)
        self.assertIs(queued, item)
        self.assertTrue(producer.is_alive())
        completed.set()
        producer.join(timeout=1)

        runtime.running = False
        self.assertFalse(producer.is_alive())

    def test_prerecorded_file_is_persisted_only_on_its_first_pass(self):
        self.assertTrue(should_persist_detection(file_source=True, generation=0))
        self.assertFalse(should_persist_detection(file_source=True, generation=1))
        self.assertFalse(should_persist_detection(file_source=True, generation=25))
        self.assertTrue(should_persist_detection(file_source=False, generation=25))

    def test_confidence_updates_are_bounded(self):
        runtime = TrafficRuntime()

        self.assertEqual(runtime.set_confidence(0.2), 0.2)
        self.assertEqual(runtime.set_confidence(0.01), 0.05)
        self.assertEqual(runtime.set_confidence(1.0), 0.9)

    def test_annotations_are_not_reused_after_a_loop_boundary(self):
        runtime = TrafficRuntime()
        with runtime._annotation_lock:
            runtime._annotations = (
                FrameAnnotation(3, "car", 0.9, (5, 5, 30, 30), 12.0, "NORMAL"),
            )
            runtime._annotation_generation = 2
            runtime._annotation_timestamp = 0.5

        current = runtime._draw_annotations(np.zeros((40, 40, 3), dtype=np.uint8), 2, 0.6)
        next_loop = runtime._draw_annotations(np.zeros((40, 40, 3), dtype=np.uint8), 3, 0.1)

        self.assertTrue(np.any(current))
        self.assertFalse(np.any(next_loop))

    def test_clean_stream_hides_overlays_without_clearing_tracking_state(self):
        runtime = TrafficRuntime()
        frame = np.zeros((40, 40, 3), dtype=np.uint8)
        with runtime._annotation_lock:
            runtime._annotations = (
                FrameAnnotation(3, "car", 0.9, (5, 5, 30, 30), 12.0, "NORMAL"),
            )
            runtime._annotation_generation = 2
            runtime._annotation_timestamp = 0.5

        annotated = runtime._render_stream_frame(frame, 2, 0.6)
        runtime.set_overlays_visible(False)
        clean = runtime._render_stream_frame(frame, 2, 0.6)

        self.assertTrue(np.any(annotated))
        self.assertFalse(np.any(clean))
        self.assertEqual(runtime._annotations[0].track_id, 3)

    def test_overlay_filters_match_objects_and_specific_violations(self):
        runtime = TrafficRuntime()
        car = FrameAnnotation(1, "car", 0.9, (2, 2, 12, 12), 20, "NORMAL")
        person = FrameAnnotation(2, "person", 0.8, (15, 2, 25, 18), 0, "NORMAL")
        rider = FrameAnnotation(
            6, "person", 0.8, (28, 2, 38, 18), 0, "NORMAL", vehicle_associated=True
        )
        no_helmet = FrameAnnotation(
            3, "motorcycle", 0.85, (28, 2, 38, 18), 18, "NORMAL", ("NO_HELMET",)
        )
        wrong_lane = FrameAnnotation(
            4, "bus", 0.88, (41, 2, 55, 18), 22, "NORMAL", ("WRONG_LANE",)
        )
        overspeed = FrameAnnotation(5, "car", 0.92, (58, 2, 70, 18), 68, "OVERSPEED")

        runtime.set_overlay_filters(["car"])
        self.assertTrue(runtime._annotation_is_visible(car))
        self.assertTrue(runtime._annotation_is_visible(overspeed))
        self.assertFalse(runtime._annotation_is_visible(person))
        runtime.set_overlay_filters(["bike", "person"])
        self.assertTrue(runtime._annotation_is_visible(person))
        self.assertFalse(runtime._annotation_is_visible(rider))
        self.assertTrue(runtime._annotation_is_visible(no_helmet))
        self.assertFalse(runtime._annotation_is_visible(wrong_lane))
        runtime.set_overlay_filters(["violation"])
        self.assertTrue(runtime._annotation_is_visible(no_helmet))
        self.assertTrue(runtime._annotation_is_visible(wrong_lane))
        self.assertTrue(runtime._annotation_is_visible(overspeed))
        self.assertFalse(runtime._annotation_is_visible(car))
        runtime.set_overlay_filters(["no_helmet"])
        self.assertTrue(runtime._annotation_is_visible(no_helmet))
        self.assertFalse(runtime._annotation_is_visible(wrong_lane))
        runtime.set_overlay_filters(["wrong_lane"])
        self.assertTrue(runtime._annotation_is_visible(wrong_lane))
        runtime.set_overlay_filters(["overspeed"])
        self.assertTrue(runtime._annotation_is_visible(overspeed))
        self.assertFalse(runtime._annotation_is_visible(no_helmet))

    def test_missing_helmet_weights_are_reported_without_crashing(self):
        specialist = HelmetSpecialist("/missing/helmet-best.pt", 0.35)

        self.assertFalse(specialist.available)
        self.assertIn("not configured", specialist.reason.lower())
        result = specialist.inspect(
            np.zeros((80, 80, 3), dtype=np.uint8), (20, 30, 60, 70), []
        )
        self.assertEqual(result, ("UNKNOWN", 0.0))

    def test_no_helmet_requires_multiple_confident_observations_and_emits_once(self):
        tracker = HelmetVoteTracker(confirmations=3)

        self.assertIsNone(tracker.update(9, "NO_HELMET", 0.8))
        self.assertIsNone(tracker.update(9, "UNKNOWN", 0.0))
        self.assertIsNone(tracker.update(9, "NO_HELMET", 0.7))
        self.assertAlmostEqual(tracker.update(9, "NO_HELMET", 0.9), 0.8)
        self.assertIsNone(tracker.update(9, "NO_HELMET", 0.95))

    def test_unknown_helmet_observations_never_create_a_violation(self):
        tracker = HelmetVoteTracker(confirmations=3)

        for _ in range(10):
            self.assertIsNone(tracker.update(11, "UNKNOWN", 0.0))

    def test_rider_association_rejects_unrelated_pedestrians(self):
        motorcycle = (40, 50, 80, 95)
        rider = (45, 15, 76, 76)
        pedestrian = (120, 10, 155, 90)

        self.assertEqual(associate_rider(motorcycle, [pedestrian, rider]), rider)
        self.assertIsNone(associate_rider(motorcycle, [pedestrian]))

    def test_person_filter_excludes_people_associated_with_any_vehicle(self):
        rider = (45, 15, 76, 76)
        pedestrian = (120, 10, 155, 90)
        motorcycle = (40, 50, 80, 95)
        person_inside_car = (45, 30, 65, 70)
        car = (40, 40, 80, 80)

        self.assertTrue(person_is_vehicle_associated(rider, [("motorcycle", motorcycle)]))
        self.assertTrue(person_is_vehicle_associated(person_inside_car, [("car", car)]))
        self.assertFalse(person_is_vehicle_associated(pedestrian, [("motorcycle", motorcycle), ("car", car)]))

    def test_stable_illegal_lane_emits_once_after_grace_and_mature_trajectory(self):
        tracker = LaneViolationTracker(
            (LaneRule(1, 0.0, 0.5, "approaching", ("car",), 0.02),),
            road_width_meters=10,
            confirmations=3,
            grace_seconds=0.5,
            minimum_trajectory_seconds=0.5,
            minimum_distance_meters=0.5,
        )
        decisions = []
        for index in range(8):
            decisions.extend(tracker.update(7, "motorcycle", (2.5, index * 0.3), index * 0.2))

        self.assertEqual([item.violation_type for item in decisions], ["WRONG_LANE"])
        self.assertEqual(decisions[0].lane_id, 1)

    def test_legal_lane_boundary_and_immature_tracks_do_not_violate(self):
        rule = LaneRule(1, 0.0, 0.5, "approaching", ("car",), 0.05)
        legal = LaneViolationTracker((rule,), 10, confirmations=3, grace_seconds=0.2)
        boundary = LaneViolationTracker((rule,), 10, confirmations=3, grace_seconds=0.2)

        legal_events = []
        boundary_events = []
        for index in range(8):
            legal_events.extend(legal.update(1, "car", (2.5, index * 0.4), index * 0.2))
            boundary_events.extend(boundary.update(2, "truck", (4.8, index * 0.4), index * 0.2))

        self.assertEqual(legal_events, [])
        self.assertEqual(boundary_events, [])

        immature = LaneViolationTracker((rule,), 10, confirmations=3, minimum_trajectory_seconds=2)
        self.assertEqual(immature.update(3, "truck", (2.5, 0), 0), ())
        self.assertEqual(immature.update(3, "truck", (2.5, 1), 0.2), ())

    def test_wrong_direction_remains_separate_from_wrong_lane(self):
        tracker = LaneViolationTracker(
            (LaneRule(1, 0, 1, "both", (), 0.02),), 10,
            global_allowed_direction="approaching", confirmations=3,
            grace_seconds=0.2, minimum_trajectory_seconds=0.2,
            minimum_distance_meters=0.2,
        )
        decisions = []
        for index in range(6):
            decisions.extend(tracker.update(5, "car", (5, 4 - index * 0.4), index * 0.2))

        self.assertEqual([item.violation_type for item in decisions], ["WRONG_DIRECTION"])


if __name__ == "__main__":
    unittest.main()
