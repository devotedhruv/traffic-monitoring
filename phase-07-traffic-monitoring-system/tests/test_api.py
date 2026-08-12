import os
import sqlite3
import struct
import tempfile
import unittest
from http.cookies import SimpleCookie
from pathlib import Path
from unittest.mock import patch

import cv2
import numpy as np

os.environ["TRAFFIC_AUTOSTART"] = "false"

from src import database
from fastapi import HTTPException
from starlette.requests import Request
from starlette.responses import Response
from web import api
from web import auth
from config.settings import AUTH_COOKIE_NAME


class TrafficApiTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        database.DATABASE_PATH = str(Path(self.temp.name) / "traffic.db")
        api.runtime.set_overlays_visible(True)
        api.runtime.set_lane_rules(())
        database.create_database()
        database.save_vehicle("BA 12 PA 1234", 68.5, "OVERSPEED", 42, "car")
        database.save_vehicle("UNKNOWN", 35.0, "NORMAL", 43, "motorcycle")

    def tearDown(self):
        self.temp.cleanup()

    def test_health_and_summary(self):
        health = api.health()
        self.assertIn(health["status"], {"healthy", "degraded"})
        self.assertIn("analysisFps", health)
        self.assertIn("sourceFps", health)
        self.assertIn("loopCount", health)
        self.assertIn("activeTracks", health)
        self.assertIn("activeDetections", health)
        self.assertEqual(health["speedCalibration"], "PERSPECTIVE_ESTIMATED")
        self.assertIn(health["speedProcessingMode"], {"REAL_TIME", "ORDERED_FILE_ANALYSIS"})
        summary = api.summary()
        self.assertEqual(summary["totalVehicles"], 2)
        self.assertEqual(summary["overspeedVehicles"], 1)
        helmet = api.capabilities()["helmetDetection"]
        self.assertFalse(helmet["available"])
        self.assertIn("not configured", helmet["reason"].lower())

    def test_dashboard_summary_can_be_scoped_to_current_session(self):
        with database._connect() as connection:
            connection.execute(
                "UPDATE vehicles SET time = '2026-08-12 05:00:00' WHERE plate = ?",
                ("BA 12 PA 1234",),
            )

        summary = database.dashboard_summary(
            current_fps=12.5,
            since="2026-08-12T05:30:00Z",
        )

        self.assertEqual(summary["totalVehicles"], 1)
        self.assertEqual(summary["overspeedVehicles"], 0)
        self.assertEqual(summary["averageSpeed"], 35.0)
        self.assertEqual(summary["currentFps"], 12.5)

    def test_database_is_configured_for_concurrent_pipeline_and_auth_access(self):
        with database._connect() as connection:
            journal_mode = connection.execute("PRAGMA journal_mode").fetchone()[0]
            busy_timeout = connection.execute("PRAGMA busy_timeout").fetchone()[0]

        self.assertEqual(journal_mode, "wal")
        self.assertGreaterEqual(busy_timeout, 30_000)

    def test_vehicle_filter_and_serialization(self):
        payload = api.vehicles(status="OVERSPEED")
        self.assertEqual(payload["total"], 1)
        self.assertEqual(payload["items"][0]["trackingId"], 42)
        self.assertEqual(payload["items"][0]["vehicleType"], "car")

    def test_unmeasured_vehicle_is_counted_without_lowering_speed_statistics(self):
        database.save_vehicle("UNKNOWN", None, "NORMAL", 44, "bicycle")

        summary = database.dashboard_summary()
        self.assertEqual(summary["totalVehicles"], 3)
        self.assertEqual(summary["averageSpeed"], 51.75)
        self.assertEqual(summary["maxSpeed"], 68.5)

        bicycle = database.list_vehicles(vehicle_type="bicycle")["items"][0]
        self.assertFalse(bicycle["speedAvailable"])
        self.assertEqual(bicycle["speed"], 0.0)

        analytics = database.analytics("today")
        self.assertEqual(analytics["averageSpeed"], 51.75)
        self.assertEqual(analytics["maxSpeed"], 68.5)

    def test_vehicle_detail_and_not_found(self):
        vehicles = api.vehicles()["items"]
        self.assertEqual(api.vehicle(vehicles[0]["id"])["id"], vehicles[0]["id"])
        with self.assertRaises(HTTPException) as error:
            api.vehicle(99999)
        self.assertEqual(error.exception.status_code, 404)

    def test_confirmed_plate_is_correlated_with_the_saved_vehicle(self):
        vehicle_id = database.save_vehicle("UNKNOWN", 41.5, "NORMAL", 88, "car")
        database.update_vehicle_plate(
            vehicle_id, "BA 20 PA 7788", 0.91, "CONFIRMED", None,
        )

        result = api.plates(limit=20)

        self.assertEqual(result["total"], 1)
        self.assertEqual(result["items"][0]["id"], vehicle_id)
        self.assertEqual(result["items"][0]["trackingId"], 88)
        self.assertEqual(result["items"][0]["plate"], "BA 20 PA 7788")
        self.assertEqual(result["items"][0]["plateConfidence"], 0.91)

    def test_camera_calibration_is_validated_and_persisted_per_source(self):
        original_source = api.runtime.source_mode
        original_profile = api.runtime.road_profile
        api.runtime.source_mode = "browser"
        payload = api.CameraCalibrationRequest(
            sourcePoints=[
                api.CalibrationPointRequest(x=0.25, y=0.35),
                api.CalibrationPointRequest(x=0.75, y=0.35),
                api.CalibrationPointRequest(x=0.9, y=0.9),
                api.CalibrationPointRequest(x=0.1, y=0.9),
            ],
            roadWidthMeters=8,
            roadLengthMeters=45,
            laneCount=2,
            quality=0.85,
        )
        try:
            updated = api.update_camera_calibration("camera-01", payload)
            stored = database.get_camera_calibration("camera-01:browser")

            self.assertTrue(updated["configured"])
            self.assertEqual(updated["calibration"]["roadLengthMeters"], 45)
            self.assertEqual(stored["laneCount"], 2)
            with self.assertRaises(HTTPException) as too_small:
                api.update_camera_calibration("camera-01", api.CameraCalibrationRequest(
                    sourcePoints=[
                        api.CalibrationPointRequest(x=0.10, y=0.10),
                        api.CalibrationPointRequest(x=0.11, y=0.10),
                        api.CalibrationPointRequest(x=0.11, y=0.11),
                        api.CalibrationPointRequest(x=0.10, y=0.11),
                    ],
                    roadWidthMeters=8,
                    roadLengthMeters=45,
                    laneCount=2,
                ))
            self.assertEqual(too_small.exception.status_code, 422)
        finally:
            api.runtime.source_mode = original_source
            api.runtime.set_road_profile(original_profile)

    def test_browser_ingest_decodes_timestamped_jpeg_and_rejects_invalid_data(self):
        frame = np.zeros((24, 32, 3), dtype=np.uint8)
        encoded, jpeg = cv2.imencode(".jpg", frame)
        self.assertTrue(encoded)

        decoded = api.decode_browser_frame(struct.pack(">d", 1.25) + jpeg.tobytes())

        self.assertIsNotNone(decoded)
        timestamp, decoded_frame = decoded
        self.assertEqual(timestamp, 1.25)
        self.assertEqual(decoded_frame.shape[:2], (24, 32))
        self.assertIsNone(api.decode_browser_frame(b"invalid"))

    def test_violation_persistence_filter_summary_and_loop_deduplication(self):
        vehicle_id = database.list_vehicles(vehicle_type="motorcycle")["items"][0]["id"]
        created = database.save_violation(
            vehicle_id, 43, "NO_HELMET", 0.87, "camera-01", "motorcycle",
            "session-one", source_generation=0,
        )
        duplicate = database.save_violation(
            vehicle_id, 43, "NO_HELMET", 0.92, "camera-01", "motorcycle",
            "session-one", source_generation=1,
        )

        self.assertIsNotNone(created)
        self.assertIsNone(duplicate)
        self.assertEqual(api.violations(type="NO_HELMET")["items"][0]["trackingId"], 43)
        self.assertEqual(database.violation_summary()["counts"]["NO_HELMET"], 1)
        filtered = api.vehicles(violation="NO_HELMET")
        self.assertEqual(filtered["total"], 1)
        self.assertIn("NO_HELMET", filtered["items"][0]["violations"])

    def test_camera_lane_rules_validate_persist_and_update_capability(self):
        payload = api.CameraLaneRulesRequest(rules=[api.LaneRuleRequest(
            laneId=1, minX=0, maxX=0.5, allowedDirection="approaching",
            allowedVehicleTypes=["car", "motorcycle"], boundaryTolerance=0.03,
        )])

        updated = api.update_camera_lanes("camera-01", payload)

        self.assertEqual(updated["rules"][0]["laneId"], 1)
        self.assertEqual(api.camera_lanes("camera-01")["rules"], updated["rules"])
        self.assertTrue(api.capabilities()["wrongLaneDetection"]["available"])

        with self.assertRaises(HTTPException) as invalid:
            api.update_camera_lanes("camera-01", api.CameraLaneRulesRequest(rules=[
                api.LaneRuleRequest(laneId=2, minX=0.7, maxX=0.3)
            ]))
        self.assertEqual(invalid.exception.status_code, 422)

    def test_analytics_and_camera(self):
        analytics = api.analytics_endpoint("today")
        self.assertIn("byStatus", analytics)
        cameras = api.cameras()
        self.assertEqual(cameras[0]["id"], "camera-01")

        updated = api.camera_settings(
            "camera-01", api.CameraSettingsRequest(confidence=0.2, showOverlays=False)
        )
        self.assertEqual(updated["confidence"], 0.2)
        self.assertFalse(updated["showOverlays"])
        self.assertFalse(api.get_camera_settings("camera-01")["showOverlays"])
        with self.assertRaises(HTTPException) as missing:
            api.camera_settings("missing", api.CameraSettingsRequest(confidence=0.2))
        self.assertEqual(missing.exception.status_code, 404)

    def test_routes_are_registered(self):
        paths = {
            route.path for route in api.app.routes
            if getattr(route, "path", None)
        }
        paths.update(api.app.openapi()["paths"])
        self.assertIn("/api/vehicles", paths)
        self.assertIn("/api/cameras/{camera_id}/stream", paths)
        self.assertIn("/api/cameras/{camera_id}/settings", paths)
        self.assertIn("/api/cameras/{camera_id}/lanes", paths)
        self.assertIn("/api/cameras/browser/start", paths)
        self.assertIn("/api/cameras/{camera_id}/stop", paths)
        self.assertIn("/api/cameras/{camera_id}/calibration", paths)
        self.assertIn("/api/plates", paths)
        self.assertIn("/api/vehicles/{vehicle_id}/plate-image", paths)
        self.assertIn("/api/capabilities", paths)
        self.assertIn("/api/violations", paths)
        self.assertIn("/api/violations/summary", paths)
        self.assertIn("/api/video-analysis", paths)
        self.assertNotIn("/api/video-analysis/link", paths)
        self.assertIn("/api/video-analysis/{job_id}", paths)
        self.assertIn("/api/video-analysis/{job_id}/video", paths)
        self.assertIn("/ws/live", paths)
        self.assertIn("/ws/cameras/{camera_id}/ingest", paths)
        self.assertIn("/api/auth/signup", paths)
        self.assertIn("/api/auth/signin", paths)
        self.assertIn("/api/auth/me", paths)
        self.assertIn("/api/auth/signout", paths)

    def test_authentication_session_lifecycle_and_protected_api(self):
        with self.assertRaises(HTTPException) as unauthenticated:
            auth.require_user(None)
        self.assertEqual(unauthenticated.exception.status_code, 401)

        response = Response()
        signup = auth.signup(auth.SignUpRequest(
            name="Traffic Operator", email="operator@example.com", password="strong-pass-123"
        ), response)
        self.assertEqual(signup["user"]["email"], "operator@example.com")
        self.assertNotIn("passwordHash", signup["user"])
        self.assertIn("httponly", response.headers["set-cookie"].lower())

        cookie = SimpleCookie()
        cookie.load(response.headers["set-cookie"])
        token = cookie[AUTH_COOKIE_NAME].value
        user = auth.require_user(token)
        self.assertEqual(auth.me(user)["user"]["name"], "Traffic Operator")

        request = Request({
            "type": "http",
            "headers": [(b"cookie", f"{AUTH_COOKIE_NAME}={token}".encode("ascii"))],
        })
        auth.signout(request, Response())
        with self.assertRaises(HTTPException) as signed_out:
            auth.require_user(token)
        self.assertEqual(signed_out.exception.status_code, 401)

    def test_duplicate_signup_and_invalid_login_are_rejected(self):
        payload = auth.SignUpRequest(
            name="Traffic Operator", email="operator@example.com", password="strong-pass-123"
        )
        auth.signup(payload, Response())
        with self.assertRaises(HTTPException) as duplicate:
            auth.signup(payload, Response())
        self.assertEqual(duplicate.exception.status_code, 409)
        with self.assertRaises(HTTPException) as invalid:
            auth.signin(auth.SignInRequest(
                email=payload.email, password="wrong-password"
            ), Response())
        self.assertEqual(invalid.exception.status_code, 401)

    def test_auth_database_failure_returns_service_unavailable(self):
        with patch("web.auth.get_user_credentials", side_effect=sqlite3.OperationalError("database is locked")):
            with self.assertRaises(HTTPException) as unavailable:
                auth.signin(auth.SignInRequest(
                    email="operator@example.com", password="strong-pass-123"
                ), Response())

        self.assertEqual(unavailable.exception.status_code, 503)

    def test_user_can_sign_in_again_with_signup_credentials(self):
        password = "strong-pass-123"
        signup_response = Response()
        signup = auth.signup(auth.SignUpRequest(
            name="Traffic Operator", email=" Operator@Example.com ", password=password
        ), signup_response)

        cookie = SimpleCookie()
        cookie.load(signup_response.headers["set-cookie"])
        token = cookie[AUTH_COOKIE_NAME].value
        auth.signout(Request({
            "type": "http",
            "headers": [(b"cookie", f"{AUTH_COOKIE_NAME}={token}".encode("ascii"))],
        }), Response())

        signin_response = Response()
        signin = auth.signin(auth.SignInRequest(
            email=" OPERATOR@example.com ", password=password
        ), signin_response)

        self.assertEqual(signin["user"]["id"], signup["user"]["id"])
        self.assertEqual(signin["user"]["email"], "operator@example.com")
        self.assertIn("httponly", signin_response.headers["set-cookie"].lower())

    def test_signup_rejects_common_gmail_domain_typo(self):
        with self.assertRaises(ValueError) as invalid:
            auth.SignUpRequest(
                name="Traffic Operator",
                email="operator@gmaiil.com",
                password="strong-pass-123",
            )
        self.assertIn("operator@gmail.com", str(invalid.exception))


if __name__ == "__main__":
    unittest.main()
