import os
import tempfile
import unittest
from pathlib import Path

os.environ["TRAFFIC_AUTOSTART"] = "false"

from src import database
from fastapi import HTTPException
from web import api


class TrafficApiTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        database.DATABASE_PATH = str(Path(self.temp.name) / "traffic.db")
        database.create_database()
        database.save_vehicle("BA 12 PA 1234", 68.5, "OVERSPEED", 42, "car")
        database.save_vehicle("UNKNOWN", 35.0, "NORMAL", 43, "motorcycle")

    def tearDown(self):
        self.temp.cleanup()

    def test_health_and_summary(self):
        health = api.health()
        self.assertIn(health["status"], {"healthy", "degraded"})
        summary = api.summary()
        self.assertEqual(summary["totalVehicles"], 2)
        self.assertEqual(summary["overspeedVehicles"], 1)

    def test_vehicle_filter_and_serialization(self):
        payload = api.vehicles(status="OVERSPEED")
        self.assertEqual(payload["total"], 1)
        self.assertEqual(payload["items"][0]["trackingId"], 42)
        self.assertEqual(payload["items"][0]["vehicleType"], "car")

    def test_vehicle_detail_and_not_found(self):
        vehicles = api.vehicles()["items"]
        self.assertEqual(api.vehicle(vehicles[0]["id"])["id"], vehicles[0]["id"])
        with self.assertRaises(HTTPException) as error:
            api.vehicle(99999)
        self.assertEqual(error.exception.status_code, 404)

    def test_analytics_and_camera(self):
        analytics = api.analytics_endpoint("today")
        self.assertIn("byStatus", analytics)
        cameras = api.cameras()
        self.assertEqual(cameras[0]["id"], "camera-01")

    def test_routes_are_registered(self):
        paths = {
            route.path for route in api.app.routes
            if getattr(route, "path", None)
        }
        paths.update(api.app.openapi()["paths"])
        self.assertIn("/api/vehicles", paths)
        self.assertIn("/api/cameras/{camera_id}/stream", paths)
        self.assertIn("/api/video-analysis", paths)
        self.assertIn("/api/video-analysis/link", paths)
        self.assertIn("/api/video-analysis/{job_id}", paths)
        self.assertIn("/ws/live", paths)


if __name__ == "__main__":
    unittest.main()
