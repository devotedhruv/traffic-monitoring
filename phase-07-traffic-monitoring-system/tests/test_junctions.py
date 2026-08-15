import os
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

os.environ["TRAFFIC_AUTOSTART"] = "false"
os.environ["TRAFFIC_DEMO_VIDEO_DIR"] = "/tmp/traffic-demo-tests"

from fastapi import HTTPException
from src import database
from web import api, junctions


class JunctionConfigurationTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        database.DATABASE_PATH = str(Path(self.temp.name) / "traffic.db")
        database.create_database()

    def tearDown(self):
        self.temp.cleanup()

    def test_seeded_junctions_cameras_and_demo_videos(self):
        junction_items = junctions.junctions()["items"]
        names = {item["name"] for item in junction_items}
        self.assertTrue({"North Junction", "Demo Junction", "Surkhet Bus Park"} <= names)
        north = next(item for item in junction_items if item["id"] == "north")
        self.assertEqual(north["status"], "ACTIVE")
        self.assertEqual(north["speedLimit"], 50)
        self.assertEqual(north["cameraCount"], 2)
        demo = next(item for item in junction_items if item["id"] == "demo")
        self.assertEqual(demo["demoVideoCount"], 7)

        cameras = junctions.junction_cameras("north")["items"]
        self.assertEqual(len(cameras), 2)
        self.assertEqual({camera["sourceType"] for camera in cameras}, {"live"})

    def test_demo_videos_filtered_by_junction_camera_and_scenario(self):
        all_videos = junctions.demo_videos()["items"]
        self.assertEqual(len(all_videos), 22)
        overspeed = junctions.demo_videos(scenario="overspeed")["items"]
        self.assertEqual(len(overspeed), 4)
        self.assertEqual(overspeed[0]["title"], "Overspeed Detection")
        self.assertFalse(overspeed[0]["available"])
        self.assertEqual(overspeed[0]["duration"], None)
        camera_filtered = junctions.demo_videos(camera_id="demo-cam-02")["items"]
        self.assertEqual({video["scenario"] for video in camera_filtered}, {
            "wrong_lane", "anpr", "heavy", "night",
        })

    def test_junction_camera_and_demo_video_crud(self):
        created = junctions.add_junction(junctions.JunctionRequest(
            id="test-junction", name="Test Junction", location="Test Road",
            description="For tests", speedLimit=40, enabled=True,
        ))
        self.assertEqual(created["speedLimit"], 40)
        self.assertEqual(created["status"], "ACTIVE")

        updated = junctions.edit_junction("test-junction", junctions.JunctionUpdateRequest(
            name="Renamed Junction", enabled=False,
        ))
        self.assertEqual(updated["name"], "Renamed Junction")
        self.assertEqual(updated["status"], "DISABLED")

        camera = junctions.add_camera("test-junction", junctions.CameraRequest(
            id="test-cam-01", name="Camera 01", sourceType="demo",
        ))
        self.assertEqual(camera["junctionId"], "test-junction")

        video = junctions.add_demo_video(junctions.DemoVideoRequest(
            id="test-video", junctionId="test-junction", title="Test Video",
            filename="test.mp4", scenario="night", cameraId="test-cam-01",
        ))
        self.assertEqual(video["scenario"], "night")

        changed = junctions.edit_demo_video("test-video", junctions.DemoVideoUpdateRequest(
            scenario="anpr", enabled=False,
        ))
        self.assertEqual(changed["scenario"], "anpr")
        self.assertFalse(changed["enabled"])
        self.assertTrue(junctions.remove_demo_video("test-video")["deleted"])
        self.assertTrue(junctions.remove_camera("test-cam-01")["deleted"])
        self.assertTrue(junctions.remove_junction("test-junction")["deleted"])

        with self.assertRaises(HTTPException) as missing:
            junctions.edit_junction("test-junction", junctions.JunctionUpdateRequest(name="Nope"))
        self.assertEqual(missing.exception.status_code, 404)

    def test_primary_north_junction_cannot_be_deleted(self):
        with self.assertRaises(HTTPException) as blocked:
            junctions.remove_junction("north")
        self.assertEqual(blocked.exception.status_code, 422)

    def test_demo_video_file_endpoint_handles_missing_files(self):
        with self.assertRaises(HTTPException) as missing:
            junctions.demo_video_file("demo-overspeed")
        self.assertEqual(missing.exception.status_code, 404)

    def test_stream_and_settings_accept_configured_cameras(self):
        with self.assertRaises(HTTPException) as missing:
            api.camera_stream("not-a-camera")
        self.assertEqual(missing.exception.status_code, 404)
        with self.assertRaises(HTTPException) as unavailable:
            api.camera_stream("north-cam-01")
        self.assertEqual(unavailable.exception.status_code, 503)
        settings = api.get_camera_settings("north-cam-01")
        self.assertIn("confidence", settings)


class DemoPlaybackTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        database.DATABASE_PATH = str(Path(self.temp.name) / "traffic.db")
        database.create_database()

    def tearDown(self):
        api.runtime.stop()
        api.runtime.source_mode = "configured"
        api.runtime.demo_video_id = None
        api.runtime._source_path = None
        api.runtime._demo_paused = False
        self.temp.cleanup()

    def test_demo_start_with_missing_video_reports_unavailable(self):
        response = junctions.start_demo(junctions.DemoStartRequest(
            junctionId="demo", cameraId="demo-cam-01", videoId="demo-overspeed",
        ))
        self.assertFalse(response["started"])
        self.assertFalse(response["available"])
        self.assertEqual(response["reason"], "Demo video unavailable")

    def test_demo_start_validates_junction_camera_and_video_ownership(self):
        with self.assertRaises(HTTPException) as missing_junction:
            junctions.start_demo(junctions.DemoStartRequest(
                junctionId="nope", cameraId="demo-cam-01", videoId="demo-normal",
            ))
        self.assertEqual(missing_junction.exception.status_code, 404)

        with self.assertRaises(HTTPException) as wrong_camera:
            junctions.start_demo(junctions.DemoStartRequest(
                junctionId="demo", cameraId="north-cam-01", videoId="demo-normal",
            ))
        self.assertEqual(wrong_camera.exception.status_code, 404)

        with self.assertRaises(HTTPException) as wrong_owner:
            junctions.start_demo(junctions.DemoStartRequest(
                junctionId="north", cameraId="north-cam-01", videoId="demo-normal",
            ))
        self.assertEqual(wrong_owner.exception.status_code, 422)

    def test_demo_controls_require_active_demo(self):
        with self.assertRaises(HTTPException) as paused:
            junctions.pause_demo()
        self.assertEqual(paused.exception.status_code, 409)
        with self.assertRaises(HTTPException) as restarted:
            junctions.restart_demo()
        self.assertEqual(restarted.exception.status_code, 409)
        with self.assertRaises(HTTPException) as stopped:
            junctions.pause_demo()
        self.assertEqual(stopped.exception.status_code, 409)

    def test_use_demo_source_switches_runtime_without_duplicating_pipeline(self):
        """A demo start reconfigures the singleton runtime; the pipeline itself is reused."""
        with patch.object(api.runtime, "start"), patch.object(api.runtime, "stop"):
            api.runtime.use_demo_source(
                "/tmp/traffic-demo-tests/overspeed.mp4",
                "Camera 01 · Overspeed Detection",
                "demo-overspeed",
                speed_limit=50,
            )
            self.assertEqual(api.runtime.source_mode, "demo")
            self.assertEqual(api.runtime.demo_video_id, "demo-overspeed")
            self.assertEqual(api.runtime.speed_limit, 50)
            self.assertEqual(api.runtime.camera_name, "Camera 01 · Overspeed Detection")
            self.assertTrue(api.runtime._source_path.endswith("overspeed.mp4"))
            self.assertEqual(api.runtime.demo_status()["videoId"], "demo-overspeed")


if __name__ == "__main__":
    unittest.main()
