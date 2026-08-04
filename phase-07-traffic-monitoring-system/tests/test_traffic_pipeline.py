import unittest

from pydantic import ValidationError

from web.traffic_pipeline import (
    CalibrationSettings,
    NormalizedPoint,
    _Track,
    _build_road_plane,
    _record_ground_speed,
    _record_line_crossing,
)


class TrafficPipelineTests(unittest.TestCase):
    def setUp(self):
        self.calibration = CalibrationSettings(
            sourcePoints=[
                NormalizedPoint(x=0, y=0),
                NormalizedPoint(x=1, y=0),
                NormalizedPoint(x=1, y=1),
                NormalizedPoint(x=0, y=1),
            ],
            roadWidthMeters=10,
            roadLengthMeters=20,
            countingLinePosition=0.5,
        )

    def test_enabled_calibration_requires_exactly_four_points(self):
        with self.assertRaises(ValidationError):
            CalibrationSettings(sourcePoints=[])
        fallback = CalibrationSettings(enabled=False, sourcePoints=[])
        self.assertFalse(fallback.enabled)

    def test_homography_projects_image_points_to_ground_metres(self):
        plane = _build_road_plane(self.calibration, width=100, height=100)
        self.assertTrue(plane.calibrated)
        projected = plane.project((50, 50), meters_per_pixel=0.1)
        self.assertAlmostEqual(projected[0], 5, places=3)
        self.assertAlmostEqual(projected[1], 10, places=3)
        self.assertEqual(plane.line_pixels(), ((0, 50), (100, 50)))
        self.assertEqual(plane.lane_for((2, 10)), 1)
        self.assertEqual(plane.lane_for((8, 10)), 2)

    def test_ground_speed_and_crossing_use_physical_trajectory(self):
        track = _Track(tracking_id=7, first_seen=0)
        _record_ground_speed(track, (1, 4), 0)
        _record_ground_speed(track, (1, 14), 1)
        self.assertAlmostEqual(track.speed_samples[-1], 36, places=3)

        track.frames_tracked = 3
        _record_line_crossing(track, (1, 9), 0.8, counting_y=10)
        _record_line_crossing(track, (1, 11), 1.0, counting_y=10)
        self.assertEqual(track.counted_at, 1.0)


if __name__ == "__main__":
    unittest.main()
