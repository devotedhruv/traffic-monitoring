import os
import tempfile
import unittest
from http.cookies import SimpleCookie
from pathlib import Path

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
        self.assertIn("/api/video-analysis/{job_id}/video", paths)
        self.assertIn("/ws/live", paths)
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
