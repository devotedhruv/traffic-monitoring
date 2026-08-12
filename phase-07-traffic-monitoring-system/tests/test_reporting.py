import csv
import os
import tempfile
import unittest
from datetime import datetime, timedelta, timezone
from pathlib import Path
from unittest.mock import patch

os.environ["TRAFFIC_AUTOSTART"] = "false"

from services import reporting
from src import database


class ReportingTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.original_database = database.DATABASE_PATH
        self.original_report_root = reporting.REPORT_ROOT
        database.DATABASE_PATH = str(Path(self.temp.name) / "traffic.db")
        reporting.REPORT_ROOT = Path(self.temp.name) / "reports"
        database.create_database()
        self.user = database.create_user(
            "Report Operator", "reports@example.com", "test-password-hash",
        )
        self.now = datetime.now(timezone.utc)
        self.filters = {
            "startAt": (self.now - timedelta(days=1)).isoformat(),
            "endAt": (self.now + timedelta(minutes=1)).isoformat(),
            "timezone": "Asia/Kathmandu",
        }

    def tearDown(self):
        database.DATABASE_PATH = self.original_database
        reporting.REPORT_ROOT = self.original_report_root
        self.temp.cleanup()

    def _report(self, report_type="TRAFFIC_SUMMARY"):
        return reporting.create_report(
            "Operational Report", report_type, self.filters, ["kpis"], self.user, {},
        )

    def test_migrations_are_non_destructive_and_idempotent(self):
        database.save_vehicle("BA 12 PA 1234", 51, "OVERSPEED", 1, "car")

        database.create_database()

        self.assertEqual(database.list_vehicles()["total"], 1)
        with database._connect() as connection:
            tables = {row["name"] for row in connection.execute(
                "SELECT name FROM sqlite_master WHERE type='table'"
            )}
        self.assertTrue({"report_definitions", "report_runs", "report_schedules"}.issubset(tables))

    def test_range_validation_rejects_invalid_future_and_oversized_ranges(self):
        with self.assertRaises(ValueError):
            reporting.validate_report_filters({
                **self.filters, "startAt": self.filters["endAt"],
                "endAt": self.filters["startAt"],
            })
        with self.assertRaises(ValueError):
            reporting.validate_report_filters({
                **self.filters,
                "startAt": (self.now - timedelta(days=367)).isoformat(),
            })
        with self.assertRaises(ValueError):
            reporting.validate_report_filters({
                **self.filters,
                "endAt": (self.now + timedelta(hours=1)).isoformat(),
            })

    def test_vehicle_aggregation_excludes_null_speed_and_combines_filters(self):
        measured_id = database.save_vehicle("BA 1 PA 1", 60, "OVERSPEED", 1, "car", "camera-01")
        database.save_vehicle("UNKNOWN", None, "NORMAL", 2, "car", "camera-01")
        database.save_vehicle("BA 2 PA 2", 25, "NORMAL", 3, "bus", "camera-02")
        database.save_violation(
            measured_id, 1, "OVERSPEED", 0.9, "camera-01", "car", "reporting",
            speed=60, speed_limit=50,
        )
        snapshot = reporting.build_report_snapshot(
            "TRAFFIC_SUMMARY",
            {**self.filters, "camera": "camera-01", "vehicleType": "car", "violationType": "OVERSPEED"},
            ["kpis"], {},
        )

        self.assertEqual(snapshot["traffic"]["totalDetections"], 2)
        self.assertEqual(snapshot["traffic"]["measuredSpeedCount"], 1)
        self.assertEqual(snapshot["traffic"]["averageSpeed"], 60.0)
        self.assertEqual(snapshot["violations"]["total"], 1)

    def test_alert_response_calculations_use_persisted_workflow(self):
        vehicle_id = database.save_vehicle("UNKNOWN", 40, "NORMAL", 4, "motorcycle")
        violation = database.save_violation(
            vehicle_id, 4, "NO_HELMET", 0.88, "camera-01", "motorcycle", "alerts",
        )
        alert = database.get_alert_for_violation(violation["id"])
        acknowledged = database.update_alert_status(
            alert["id"], "ACKNOWLEDGED", self.user, expected_version=alert["version"],
        )
        database.update_alert_status(
            alert["id"], "RESOLVED", self.user, "Verified and closed",
            expected_version=acknowledged["version"],
        )

        snapshot = reporting.build_report_snapshot(
            "ALERT_RESPONSE", self.filters, ["alertRecords"], {},
        )

        self.assertEqual(snapshot["alerts"]["total"], 1)
        self.assertIsNotNone(snapshot["alerts"]["averageAcknowledgementSeconds"])
        self.assertIsNotNone(snapshot["alerts"]["averageResolutionSeconds"])
        self.assertEqual(snapshot["alerts"]["records"][0]["resolutionNote"], "Verified and closed")

    def test_snapshot_is_immutable_and_exports_are_real(self):
        database.save_vehicle("BA 3 PA 3", 45, "NORMAL", 5, "car")
        report = self._report()
        original = reporting.get_report(report["id"])["snapshot"]

        database.save_vehicle("BA 4 PA 4", 55, "OVERSPEED", 6, "car")
        loaded = reporting.get_report(report["id"])
        pdf = reporting.get_report_export_path(report["id"], "pdf")
        csv_path = reporting.get_report_export_path(report["id"], "csv")

        self.assertEqual(original, loaded["snapshot"])
        self.assertEqual(loaded["sourceCounts"]["vehicles"], 1)
        self.assertTrue(pdf.read_bytes().startswith(b"%PDF-"))
        with csv_path.open(newline="", encoding="utf-8") as handle:
            self.assertEqual(next(csv.reader(handle)), ["period", "detections", "overspeed"])

    def test_csv_formula_injection_is_escaped(self):
        for value in ("=SUM(A1:A2)", "+cmd", "-10", "@import"):
            self.assertTrue(reporting.csv_safe_for_test(value).startswith("'"))
        self.assertEqual(reporting.csv_safe_for_test("BA 12 PA 1234"), "BA 12 PA 1234")

    def test_safe_download_path_missing_report_and_missing_export(self):
        with self.assertRaises(LookupError):
            reporting.get_report_export_path(999, "pdf")
        report = self._report()
        with database._connect() as connection:
            connection.execute(
                "UPDATE report_runs SET pdf_path=? WHERE id=?",
                (str(Path(self.temp.name).parent / "outside.pdf"), report["id"]),
            )
        with self.assertRaises(FileNotFoundError):
            reporting.get_report_export_path(report["id"], "pdf")

    def test_generation_failure_is_persisted(self):
        with patch("services.reporting.write_pdf_export", side_effect=OSError("disk unavailable")):
            with self.assertRaises(OSError):
                self._report()

        failed = reporting.list_reports(status="FAILED")
        self.assertEqual(failed["total"], 1)
        self.assertEqual(
            failed["items"][0]["failureReason"],
            "Report export storage is unavailable.",
        )

    def test_report_schedule_next_run_and_toggle(self):
        schedule = reporting.create_report_schedule(
            "Daily Summary", "TRAFFIC_SUMMARY", "DAILY", "06:00",
            "Asia/Kathmandu", {}, ["kpis"], self.user,
        )

        self.assertTrue(schedule["enabled"])
        self.assertGreater(
            datetime.fromisoformat(schedule["nextRunAt"].replace("Z", "+00:00")),
            datetime.now(timezone.utc),
        )
        disabled = reporting.toggle_report_schedule(schedule["id"])
        self.assertFalse(disabled["enabled"])
        start, end = reporting.schedule_period("WEEKLY", self.now)
        self.assertEqual(
            datetime.fromisoformat(end.replace("Z", "+00:00")) - datetime.fromisoformat(start.replace("Z", "+00:00")),
            timedelta(days=7),
        )

    def test_report_api_requires_authentication_and_generates_for_signed_in_user(self):
        from fastapi import HTTPException
        from web import auth, reports as report_api

        with self.assertRaises(HTTPException) as unauthenticated:
            auth.require_user(None)
        generated = report_api.generate_report(report_api.GenerateReportRequest(
            name="Authenticated API Report",
            type="TRAFFIC_SUMMARY",
            filters=report_api.ReportFiltersRequest(**self.filters),
            sections=["kpis", "trafficTrend"],
        ), self.user)

        self.assertEqual(unauthenticated.exception.status_code, 401)
        self.assertEqual(generated["creator"]["email"], self.user["email"])
        self.assertEqual(generated["status"], "READY")


if __name__ == "__main__":
    unittest.main()
