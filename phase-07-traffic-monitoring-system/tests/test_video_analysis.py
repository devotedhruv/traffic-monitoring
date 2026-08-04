import unittest

from web.video_analysis import (
    _build_timeline,
    _direction_label,
    _host_allowed,
    _is_public_address,
    _link_download_error,
    _source_filename,
    _trimmed_average,
)


class VideoAnalysisHelperTests(unittest.TestCase):
    def test_direction_labels_cover_horizontal_and_vertical_motion(self):
        self.assertEqual(_direction_label((10, 10), (100, 12)), "Left to right")
        self.assertEqual(_direction_label((100, 12), (10, 10)), "Right to left")
        self.assertEqual(_direction_label((10, 10), (11, 100)), "Approaching")
        self.assertEqual(_direction_label((10, 100), (11, 10)), "Moving away")

    def test_trimmed_average_ignores_extreme_samples(self):
        values = [30.0] * 9 + [190.0]
        self.assertEqual(_trimmed_average(values), 30.0)
        self.assertIsNone(_trimmed_average([]))

    def test_timeline_counts_first_appearances_and_violations(self):
        vehicles = [
            {"firstSeenSeconds": 1.0, "status": "NORMAL"},
            {"firstSeenSeconds": 2.0, "status": "OVERSPEED"},
            {"firstSeenSeconds": 11.0, "status": "NORMAL"},
        ]
        timeline = _build_timeline(vehicles, 12)
        self.assertEqual(sum(item["detections"] for item in timeline), 3)
        self.assertEqual(sum(item["overspeed"] for item in timeline), 1)

    def test_link_hosts_and_network_addresses_are_constrained(self):
        self.assertTrue(_host_allowed("www.youtube.com"))
        self.assertTrue(_host_allowed("drive.google.com"))
        self.assertFalse(_host_allowed("youtube.com.attacker.example"))
        self.assertTrue(_is_public_address("8.8.8.8"))
        self.assertFalse(_is_public_address("127.0.0.1"))
        self.assertFalse(_is_public_address("10.0.0.1"))

    def test_link_metadata_is_safe_for_display_and_errors_are_actionable(self):
        self.assertEqual(
            _source_filename({"sourceTitle": "Road / Junction?"}, ".mp4"),
            "Road _ Junction_.mp4",
        )
        self.assertIn("private", _link_download_error("Video is private").lower())


if __name__ == "__main__":
    unittest.main()
