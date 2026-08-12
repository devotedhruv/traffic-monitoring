"""Persistent, reproducible operational reports and safe export generation."""

from __future__ import annotations

import csv
import io
import json
import sqlite3
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from fpdf import FPDF

from config.settings import CAMERA_ID, CAMERA_NAME, PROJECT_ROOT, SPEED_LIMIT
from src.database import _connect

REPORT_TYPES = (
    "TRAFFIC_SUMMARY", "VIOLATION_ENFORCEMENT", "ALERT_RESPONSE",
    "VEHICLE_FLOW", "CAMERA_PERFORMANCE", "CUSTOM",
)
REPORT_STATUSES = ("GENERATING", "READY", "FAILED")
REPORT_FREQUENCIES = ("DAILY", "WEEKLY", "MONTHLY")
MAX_REPORT_RANGE_DAYS = 366
MAX_DETAIL_ROWS = 5_000
REPORT_ROOT = PROJECT_ROOT / "output" / "reports"
REPORT_TIMEZONE = "Asia/Kathmandu"

REPORT_TEMPLATES: list[dict[str, Any]] = [
    {
        "type": "TRAFFIC_SUMMARY", "name": "Traffic Summary",
        "description": "Vehicle totals, speed statistics, peak periods, distribution, and previous-period comparison.",
        "sections": ["kpis", "trafficTrend", "vehicleDistribution", "comparison"],
    },
    {
        "type": "VIOLATION_ENFORCEMENT", "name": "Violation Enforcement",
        "description": "Confirmed traffic-rule violations with matching vehicle and evidence metadata.",
        "sections": ["kpis", "violationDistribution", "violationRecords"],
    },
    {
        "type": "ALERT_RESPONSE", "name": "Alert Response",
        "description": "Alert severity, workflow status, response times, assignments, and resolution outcomes.",
        "sections": ["kpis", "alertDistribution", "alertRecords", "auditSummary"],
    },
    {
        "type": "VEHICLE_FLOW", "name": "Vehicle Flow",
        "description": "Traffic volume, peak and quiet periods, vehicle types, lanes, and directions.",
        "sections": ["kpis", "trafficTrend", "vehicleDistribution", "laneDirection"],
    },
    {
        "type": "CAMERA_PERFORMANCE", "name": "Camera Performance",
        "description": "Truthful camera detection volume, configuration, capability, and evidence availability.",
        "sections": ["kpis", "cameraSummary", "capabilities"],
    },
    {
        "type": "CUSTOM", "name": "Custom Report",
        "description": "Choose the operational sections that should appear in the report.",
        "sections": ["kpis"],
    },
]


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


def _json(value: Any) -> str:
    return json.dumps(value, separators=(",", ":"), ensure_ascii=False)


def _loads(value: str | None, fallback: Any) -> Any:
    if not value:
        return fallback
    try:
        return json.loads(value)
    except (TypeError, json.JSONDecodeError):
        return fallback


def _iso(value: str) -> datetime:
    parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    if parsed.tzinfo is None:
        raise ValueError("Report timestamps must include a timezone")
    return parsed.astimezone(timezone.utc)


def validate_report_filters(filters: dict[str, Any]) -> dict[str, Any]:
    start_raw, end_raw = filters.get("startAt"), filters.get("endAt")
    if not isinstance(start_raw, str) or not isinstance(end_raw, str):
        raise ValueError("A start and end date are required")
    start, end = _iso(start_raw), _iso(end_raw)
    if start >= end:
        raise ValueError("The report start time must be before the end time")
    if end - start > timedelta(days=MAX_REPORT_RANGE_DAYS):
        raise ValueError(f"Report ranges cannot exceed {MAX_REPORT_RANGE_DAYS} days")
    if end > datetime.now(timezone.utc) + timedelta(minutes=5):
        raise ValueError("The report end time cannot be in the future")
    normalized = {
        "startAt": start.isoformat().replace("+00:00", "Z"),
        "endAt": end.isoformat().replace("+00:00", "Z"),
        "timezone": str(filters.get("timezone") or REPORT_TIMEZONE),
        "camera": str(filters.get("camera") or ""),
        "vehicleType": str(filters.get("vehicleType") or ""),
        "violationType": str(filters.get("violationType") or ""),
        "alertSeverity": str(filters.get("alertSeverity") or ""),
        "alertStatus": str(filters.get("alertStatus") or ""),
        "assignedTo": filters.get("assignedTo") if filters.get("assignedTo") not in ("", None) else None,
    }
    try:
        ZoneInfo(normalized["timezone"])
    except ZoneInfoNotFoundError as error:
        raise ValueError("Unknown report timezone") from error
    allowed_vehicle_types = {"", "bicycle", "car", "motorcycle", "bus", "truck", "unknown"}
    allowed_violations = {"", "OVERSPEED", "NO_HELMET", "WRONG_LANE", "WRONG_DIRECTION"}
    allowed_severities = {"", "LOW", "MEDIUM", "HIGH", "CRITICAL"}
    allowed_statuses = {"", "NEW", "ACKNOWLEDGED", "INVESTIGATING", "RESOLVED", "FALSE_POSITIVE"}
    if normalized["vehicleType"] not in allowed_vehicle_types:
        raise ValueError("Invalid vehicle type filter")
    if normalized["violationType"] not in allowed_violations:
        raise ValueError("Invalid violation type filter")
    if normalized["alertSeverity"] not in allowed_severities:
        raise ValueError("Invalid alert severity filter")
    if normalized["alertStatus"] not in allowed_statuses:
        raise ValueError("Invalid alert status filter")
    assigned = normalized["assignedTo"]
    if assigned is not None:
        try:
            normalized["assignedTo"] = int(assigned)
        except (TypeError, ValueError) as error:
            raise ValueError("Invalid assigned operator filter") from error
    return normalized


def _vehicle_where(filters: dict[str, Any], alias: str = "vehicles") -> tuple[str, list[Any]]:
    # julianday preserves the fractional boundary of ISO request timestamps;
    # SQLite's datetime() truncates it and can otherwise exclude same-second rows.
    clauses = [f"julianday({alias}.time) >= julianday(?)", f"julianday({alias}.time) < julianday(?)"]
    values: list[Any] = [filters["startAt"], filters["endAt"]]
    if filters["camera"]:
        clauses.append(f"{alias}.camera_id = ?")
        values.append(filters["camera"])
    if filters["vehicleType"]:
        clauses.append(f"{alias}.vehicle_type = ?")
        values.append(filters["vehicleType"])
    return " AND ".join(clauses), values


def _violation_where(filters: dict[str, Any], alias: str = "violations") -> tuple[str, list[Any]]:
    clauses = [f"{alias}.detected_at >= ?", f"{alias}.detected_at < ?"]
    values: list[Any] = [filters["startAt"], filters["endAt"]]
    if filters["camera"]:
        clauses.append(f"{alias}.camera_id = ?")
        values.append(filters["camera"])
    if filters["vehicleType"]:
        clauses.append(f"{alias}.vehicle_type = ?")
        values.append(filters["vehicleType"])
    if filters["violationType"]:
        clauses.append(f"{alias}.violation_type = ?")
        values.append(filters["violationType"])
    return " AND ".join(clauses), values


def _alert_where(filters: dict[str, Any]) -> tuple[str, list[Any]]:
    clauses = ["alerts.last_occurrence_at >= ?", "alerts.last_occurrence_at < ?"]
    values: list[Any] = [filters["startAt"], filters["endAt"]]
    if filters["camera"]:
        clauses.append("alerts.camera_id = ?")
        values.append(filters["camera"])
    if filters["vehicleType"]:
        clauses.append("latest.vehicle_type = ?")
        values.append(filters["vehicleType"])
    if filters["violationType"]:
        clauses.append("alerts.violation_type = ?")
        values.append(filters["violationType"])
    if filters["alertSeverity"]:
        clauses.append("alerts.severity = ?")
        values.append(filters["alertSeverity"])
    if filters["alertStatus"]:
        clauses.append("alerts.status = ?")
        values.append(filters["alertStatus"])
    if filters["assignedTo"] is not None:
        clauses.append("alerts.assigned_user_id = ?")
        values.append(filters["assignedTo"])
    return " AND ".join(clauses), values


def _rows_as_dicts(rows: list[sqlite3.Row]) -> list[dict[str, Any]]:
    return [{key: row[key] for key in row.keys()} for row in rows]


def _aggregate_traffic(connection: sqlite3.Connection, filters: dict[str, Any]) -> dict[str, Any]:
    where, values = _vehicle_where(filters)
    aggregate = connection.execute(
        f"""SELECT COUNT(*) AS total,
                   COUNT(speed) AS measured,
                   AVG(speed) AS average_speed,
                   MAX(speed) AS maximum_speed,
                   SUM(CASE WHEN status = 'OVERSPEED' THEN 1 ELSE 0 END) AS overspeed
            FROM vehicles WHERE {where}""",
        values,
    ).fetchone()
    by_type = connection.execute(
        f"""SELECT COALESCE(vehicle_type, 'unknown') AS name, COUNT(*) AS value
            FROM vehicles WHERE {where} GROUP BY COALESCE(vehicle_type, 'unknown')
            ORDER BY value DESC""",
        values,
    ).fetchall()
    trend = connection.execute(
        f"""SELECT strftime('%Y-%m-%dT%H:00:00Z', time) AS period,
                   COUNT(*) AS detections,
                   SUM(CASE WHEN status = 'OVERSPEED' THEN 1 ELSE 0 END) AS overspeed
            FROM vehicles WHERE {where} GROUP BY period ORDER BY period""",
        values,
    ).fetchall()
    lane_direction = connection.execute(
        f"""SELECT violations.lane_id AS laneId, violations.direction,
                   COUNT(*) AS events
            FROM violations
            WHERE violations.detected_at >= ? AND violations.detected_at < ?
              AND (violations.lane_id IS NOT NULL OR violations.direction IS NOT NULL)
            GROUP BY violations.lane_id, violations.direction ORDER BY events DESC""",
        (filters["startAt"], filters["endAt"]),
    ).fetchall()
    total = int(aggregate["total"] or 0)
    overspeed = int(aggregate["overspeed"] or 0)
    timeline = _rows_as_dicts(trend)
    busiest = max(timeline, key=lambda row: row["detections"], default=None)
    quietest = min(timeline, key=lambda row: row["detections"], default=None)
    return {
        "totalDetections": total,
        "measuredSpeedCount": int(aggregate["measured"] or 0),
        "averageSpeed": round(float(aggregate["average_speed"]), 2) if aggregate["average_speed"] is not None else None,
        "maximumSpeed": round(float(aggregate["maximum_speed"]), 2) if aggregate["maximum_speed"] is not None else None,
        "overspeedCount": overspeed,
        "overspeedPercentage": round(overspeed / total * 100, 2) if total else 0,
        "vehicleDistribution": _rows_as_dicts(by_type),
        "trafficTrend": timeline,
        "busiestPeriod": busiest,
        "quietestPeriod": quietest,
        "laneDirection": _rows_as_dicts(lane_direction),
    }


def _previous_comparison(connection: sqlite3.Connection, filters: dict[str, Any], current_total: int) -> dict[str, Any]:
    start, end = _iso(filters["startAt"]), _iso(filters["endAt"])
    duration = end - start
    previous = {**filters,
        "startAt": (start - duration).isoformat().replace("+00:00", "Z"),
        "endAt": start.isoformat().replace("+00:00", "Z"),
    }
    where, values = _vehicle_where(previous)
    count = int(connection.execute(f"SELECT COUNT(*) FROM vehicles WHERE {where}", values).fetchone()[0])
    change = None if count == 0 else round((current_total - count) / count * 100, 2)
    return {"previousTotal": count, "currentTotal": current_total, "percentageChange": change}


def _aggregate_violations(connection: sqlite3.Connection, filters: dict[str, Any]) -> dict[str, Any]:
    where, values = _violation_where(filters)
    counts = connection.execute(
        f"""SELECT violation_type AS type, COUNT(*) AS count
            FROM violations WHERE {where} GROUP BY violation_type ORDER BY count DESC""",
        values,
    ).fetchall()
    rows = connection.execute(
        f"""SELECT violations.id, violations.vehicle_id AS vehicleId,
                   violations.tracking_id AS trackingId,
                   violations.violation_type AS type,
                   violations.vehicle_type AS vehicleType,
                   NULLIF(vehicles.plate, 'UNKNOWN') AS plate,
                   COALESCE(violations.speed, vehicles.speed) AS speed,
                   violations.speed_limit AS speedLimit,
                   violations.lane_id AS laneId, violations.direction,
                   violations.camera_id AS cameraId,
                   violations.confidence, violations.detected_at AS detectedAt,
                   CASE WHEN violations.evidence_path IS NULL THEN 0 ELSE 1 END AS evidenceAvailable
            FROM violations LEFT JOIN vehicles ON vehicles.id = violations.vehicle_id
            WHERE {where} ORDER BY violations.detected_at DESC, violations.id DESC LIMIT ?""",
        [*values, MAX_DETAIL_ROWS],
    ).fetchall()
    total = sum(int(row["count"]) for row in counts)
    return {
        "total": total,
        "distribution": _rows_as_dicts(counts),
        "records": _rows_as_dicts(rows),
        "recordsTruncated": total > MAX_DETAIL_ROWS,
    }


def _aggregate_alerts(connection: sqlite3.Connection, filters: dict[str, Any]) -> dict[str, Any]:
    where, values = _alert_where(filters)
    join = "JOIN violations latest ON latest.id = alerts.latest_violation_id LEFT JOIN users assigned ON assigned.id = alerts.assigned_user_id"
    aggregate = connection.execute(
        f"""SELECT COUNT(*) AS total,
                   AVG(CASE WHEN acknowledged_at IS NOT NULL THEN
                       (julianday(acknowledged_at)-julianday(alerts.created_at))*86400 END) AS average_ack,
                   AVG(CASE WHEN resolved_at IS NOT NULL THEN
                       (julianday(resolved_at)-julianday(alerts.created_at))*86400 END) AS average_resolve,
                   SUM(CASE WHEN severity='CRITICAL' AND status NOT IN ('RESOLVED','FALSE_POSITIVE') THEN 1 ELSE 0 END) AS critical_unresolved
            FROM alerts {join} WHERE {where}""",
        values,
    ).fetchone()
    by_status = connection.execute(
        f"SELECT alerts.status AS name, COUNT(*) AS value FROM alerts {join} WHERE {where} GROUP BY alerts.status",
        values,
    ).fetchall()
    by_severity = connection.execute(
        f"SELECT alerts.severity AS name, COUNT(*) AS value FROM alerts {join} WHERE {where} GROUP BY alerts.severity",
        values,
    ).fetchall()
    rows = connection.execute(
        f"""SELECT alerts.id, alerts.violation_type AS type, alerts.severity,
                   alerts.status, alerts.tracking_id AS trackingId,
                   latest.vehicle_type AS vehicleType, alerts.camera_id AS cameraId,
                   assigned.name AS assignedTo, alerts.occurrence_count AS occurrenceCount,
                   alerts.created_at AS createdAt, alerts.acknowledged_at AS acknowledgedAt,
                   alerts.resolved_at AS resolvedAt, alerts.resolution_note AS resolutionNote,
                   alerts.false_positive_reason AS falsePositiveReason
            FROM alerts {join} WHERE {where}
            ORDER BY alerts.last_occurrence_at DESC, alerts.id DESC LIMIT ?""",
        [*values, MAX_DETAIL_ROWS],
    ).fetchall()
    audit = connection.execute(
        f"""SELECT activity.action, COUNT(*) AS count
            FROM alert_activity activity JOIN alerts ON alerts.id = activity.alert_id
            {join} WHERE {where} GROUP BY activity.action ORDER BY count DESC""",
        values,
    ).fetchall()
    total = int(aggregate["total"] or 0)
    return {
        "total": total,
        "criticalUnresolved": int(aggregate["critical_unresolved"] or 0),
        "averageAcknowledgementSeconds": round(float(aggregate["average_ack"]), 1) if aggregate["average_ack"] is not None else None,
        "averageResolutionSeconds": round(float(aggregate["average_resolve"]), 1) if aggregate["average_resolve"] is not None else None,
        "byStatus": _rows_as_dicts(by_status),
        "bySeverity": _rows_as_dicts(by_severity),
        "records": _rows_as_dicts(rows),
        "auditSummary": _rows_as_dicts(audit),
        "recordsTruncated": total > MAX_DETAIL_ROWS,
    }


def build_report_snapshot(
    report_type: str,
    filters: dict[str, Any],
    sections: list[str],
    runtime_info: dict[str, Any] | None = None,
) -> dict[str, Any]:
    if report_type not in REPORT_TYPES:
        raise ValueError("Invalid report type")
    normalized = validate_report_filters(filters)
    generated_at = utc_now()
    with _connect() as connection:
        traffic = _aggregate_traffic(connection, normalized)
        violations = _aggregate_violations(connection, normalized)
        alerts = _aggregate_alerts(connection, normalized)
        comparison = _previous_comparison(connection, normalized, traffic["totalDetections"])
    capabilities = (runtime_info or {}).get("capabilities", {})
    warnings: list[str] = []
    for name, capability in capabilities.items():
        if isinstance(capability, dict) and capability.get("available") is False:
            warnings.append(f"{name}: {capability.get('reason') or 'Not configured'}")
    camera_summary = {
        "cameraId": normalized["camera"] or CAMERA_ID,
        "cameraName": CAMERA_NAME if not normalized["camera"] or normalized["camera"] == CAMERA_ID else normalized["camera"],
        "runtimeStatus": (runtime_info or {}).get("runtimeStatus", "Not available"),
        "analysisFps": (runtime_info or {}).get("analysisFps"),
        "analysisFpsHistorical": False,
        "calibrationConfigured": (runtime_info or {}).get("calibrationConfigured"),
        "evidenceCaptures": sum(int(row["evidenceAvailable"]) for row in violations["records"]),
        "capabilities": capabilities,
    }
    return {
        "schemaVersion": 1,
        "reportType": report_type,
        "generatedAt": generated_at,
        "timezone": normalized["timezone"],
        "filters": normalized,
        "sections": sections,
        "speedLimit": SPEED_LIMIT,
        "dataNote": "Generated from confirmed recorded events. Missing measurements are not represented as zero.",
        "warnings": warnings,
        "traffic": traffic,
        "comparison": comparison,
        "violations": violations,
        "alerts": alerts,
        "camera": camera_summary,
        "sourceCounts": {
            "vehicles": traffic["totalDetections"],
            "measuredSpeeds": traffic["measuredSpeedCount"],
            "violations": violations["total"],
            "alerts": alerts["total"],
        },
    }


def _csv_safe(value: Any) -> str:
    text = "" if value is None else str(value)
    return f"'{text}" if text.lstrip().startswith(("=", "+", "-", "@")) else text


def _csv_rows(snapshot: dict[str, Any]) -> tuple[list[str], list[list[Any]]]:
    report_type = snapshot["reportType"]
    if report_type == "VIOLATION_ENFORCEMENT":
        records = snapshot["violations"]["records"]
        headers = ["id", "type", "vehicleType", "plate", "trackingId", "speed", "speedLimit", "laneId", "direction", "cameraId", "confidence", "detectedAt", "evidenceAvailable"]
    elif report_type == "ALERT_RESPONSE":
        records = snapshot["alerts"]["records"]
        headers = ["id", "type", "severity", "status", "trackingId", "vehicleType", "cameraId", "assignedTo", "occurrenceCount", "createdAt", "acknowledgedAt", "resolvedAt", "resolutionNote", "falsePositiveReason"]
    else:
        records = snapshot["traffic"]["trafficTrend"]
        headers = ["period", "detections", "overspeed"]
    return headers, [[record.get(header) for header in headers] for record in records]


def write_csv_export(path: Path, snapshot: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    headers, rows = _csv_rows(snapshot)
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.writer(handle)
        writer.writerow(headers)
        writer.writerows([[_csv_safe(value) for value in row] for row in rows])


def _pdf_text(value: Any) -> str:
    return str(value).encode("latin-1", "replace").decode("latin-1")


def write_pdf_export(path: Path, name: str, report_id: int, version: int, snapshot: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    pdf = FPDF()
    pdf.set_auto_page_break(auto=True, margin=15)
    pdf.add_page()
    pdf.set_font("Helvetica", "B", 18)
    pdf.set_text_color(15, 170, 91)
    pdf.cell(0, 10, "TrafficOps AI", new_x="LMARGIN", new_y="NEXT")
    pdf.set_text_color(20, 30, 25)
    pdf.set_font("Helvetica", "B", 16)
    pdf.multi_cell(0, 9, _pdf_text(name), new_x="LMARGIN", new_y="NEXT")
    pdf.set_font("Helvetica", size=9)
    pdf.set_text_color(90, 100, 95)
    metadata = [
        f"Report ID: {report_id} | Version: {version}",
        f"Type: {snapshot['reportType'].replace('_', ' ').title()}",
        f"Generated: {snapshot['generatedAt']} | Timezone: {snapshot['timezone']}",
        f"Period: {snapshot['filters']['startAt']} to {snapshot['filters']['endAt']}",
        f"Camera: {snapshot['camera']['cameraName']} | Speed limit: {snapshot['speedLimit']} km/h",
    ]
    for line in metadata:
        pdf.multi_cell(0, 5, _pdf_text(line), new_x="LMARGIN", new_y="NEXT")
    pdf.ln(3)
    pdf.set_font("Helvetica", "B", 12)
    pdf.set_text_color(20, 30, 25)
    pdf.cell(0, 8, "Source summary", new_x="LMARGIN", new_y="NEXT")
    pdf.set_font("Helvetica", size=10)
    for label, value in snapshot["sourceCounts"].items():
        pdf.cell(0, 6, _pdf_text(f"{label.replace('_', ' ').title()}: {value}"), new_x="LMARGIN", new_y="NEXT")
    traffic = snapshot["traffic"]
    pdf.ln(2)
    pdf.set_font("Helvetica", "B", 12)
    pdf.cell(0, 8, "Traffic metrics", new_x="LMARGIN", new_y="NEXT")
    pdf.set_font("Helvetica", size=10)
    metrics = {
        "Total detections": traffic["totalDetections"],
        "Average measured speed": f"{traffic['averageSpeed']} km/h" if traffic["averageSpeed"] is not None else "Not measured",
        "Maximum measured speed": f"{traffic['maximumSpeed']} km/h" if traffic["maximumSpeed"] is not None else "Not measured",
        "Overspeed events": traffic["overspeedCount"],
        "Confirmed violations": snapshot["violations"]["total"],
        "Operational alerts": snapshot["alerts"]["total"],
    }
    for label, value in metrics.items():
        pdf.cell(0, 6, _pdf_text(f"{label}: {value}"), new_x="LMARGIN", new_y="NEXT")
    if "vehicleDistribution" in snapshot["sections"]:
        pdf.ln(2)
        pdf.set_font("Helvetica", "B", 11)
        pdf.cell(0, 7, "Vehicle distribution", new_x="LMARGIN", new_y="NEXT")
        pdf.set_font("Helvetica", size=9)
        for item in traffic["vehicleDistribution"]:
            pdf.cell(0, 5, _pdf_text(f"{str(item['name']).title()}: {item['value']}"), new_x="LMARGIN", new_y="NEXT")
    if "trafficTrend" in snapshot["sections"] and traffic["trafficTrend"]:
        pdf.ln(2)
        pdf.set_font("Helvetica", "B", 11)
        pdf.cell(0, 7, "Traffic trend", new_x="LMARGIN", new_y="NEXT")
        pdf.set_font("Helvetica", size=8)
        for item in traffic["trafficTrend"][:200]:
            pdf.cell(0, 5, _pdf_text(
                f"{item['period']} | detections {item['detections']} | overspeed {item['overspeed']}"
            ), new_x="LMARGIN", new_y="NEXT")
    if "violationDistribution" in snapshot["sections"]:
        pdf.ln(2)
        pdf.set_font("Helvetica", "B", 11)
        pdf.cell(0, 7, "Violation distribution", new_x="LMARGIN", new_y="NEXT")
        pdf.set_font("Helvetica", size=9)
        for item in snapshot["violations"]["distribution"]:
            pdf.cell(0, 5, _pdf_text(
                f"{item['type'].replace('_', ' ').title()}: {item['count']}"
            ), new_x="LMARGIN", new_y="NEXT")
    if "violationRecords" in snapshot["sections"] and snapshot["violations"]["records"]:
        pdf.ln(2)
        pdf.set_font("Helvetica", "B", 11)
        pdf.cell(0, 7, "Confirmed violation records", new_x="LMARGIN", new_y="NEXT")
        pdf.set_font("Helvetica", size=8)
        for item in snapshot["violations"]["records"][:200]:
            speed = f"{item['speed']} / {item['speedLimit']} km/h" if item["speed"] is not None else "Not measured"
            identity = item["plate"] or f"Track #{item['trackingId']}"
            evidence = "Evidence available" if item["evidenceAvailable"] else "No evidence"
            pdf.multi_cell(0, 5, _pdf_text(
                f"#{item['id']} {item['type'].replace('_', ' ').title()} | "
                f"{identity} | {speed} | "
                f"{item['cameraId']} | {evidence} | {item['detectedAt']}"
            ), new_x="LMARGIN", new_y="NEXT")
    if "alertDistribution" in snapshot["sections"]:
        pdf.ln(2)
        pdf.set_font("Helvetica", "B", 11)
        pdf.cell(0, 7, "Alert workflow", new_x="LMARGIN", new_y="NEXT")
        pdf.set_font("Helvetica", size=9)
        for item in snapshot["alerts"]["byStatus"]:
            pdf.cell(0, 5, _pdf_text(
                f"{item['name'].replace('_', ' ').title()}: {item['value']}"
            ), new_x="LMARGIN", new_y="NEXT")
    if "alertRecords" in snapshot["sections"] and snapshot["alerts"]["records"]:
        pdf.ln(2)
        pdf.set_font("Helvetica", "B", 11)
        pdf.cell(0, 7, "Operational alert records", new_x="LMARGIN", new_y="NEXT")
        pdf.set_font("Helvetica", size=8)
        for item in snapshot["alerts"]["records"][:200]:
            pdf.multi_cell(0, 5, _pdf_text(
                f"#{item['id']} {item['severity']} {item['type'].replace('_', ' ').title()} | "
                f"{item['status'].replace('_', ' ').title()} | "
                f"{item['assignedTo'] or 'Unassigned'} | occurrences {item['occurrenceCount']}"
            ), new_x="LMARGIN", new_y="NEXT")
    if "auditSummary" in snapshot["sections"] and snapshot["alerts"]["auditSummary"]:
        pdf.ln(2)
        pdf.set_font("Helvetica", "B", 11)
        pdf.cell(0, 7, "Alert activity summary", new_x="LMARGIN", new_y="NEXT")
        pdf.set_font("Helvetica", size=9)
        for item in snapshot["alerts"]["auditSummary"]:
            pdf.cell(0, 5, _pdf_text(
                f"{item['action'].replace('_', ' ').title()}: {item['count']}"
            ), new_x="LMARGIN", new_y="NEXT")
    if "cameraSummary" in snapshot["sections"]:
        camera = snapshot["camera"]
        pdf.ln(2)
        pdf.set_font("Helvetica", "B", 11)
        pdf.cell(0, 7, "Camera performance and availability", new_x="LMARGIN", new_y="NEXT")
        pdf.set_font("Helvetica", size=9)
        camera_lines = [
            f"Camera: {camera['cameraName']} ({camera['cameraId']})",
            f"Current runtime status: {camera['runtimeStatus']}",
            f"Current analysis FPS: {camera['analysisFps'] if camera['analysisFps'] is not None else 'Not measured'}",
            "Historical FPS: Not measured",
            f"Calibration: {'Configured' if camera['calibrationConfigured'] else 'Not configured'}",
            f"Evidence captures in period: {camera['evidenceCaptures']}",
        ]
        for line in camera_lines:
            pdf.cell(0, 5, _pdf_text(line), new_x="LMARGIN", new_y="NEXT")
    if snapshot["warnings"]:
        pdf.ln(2)
        pdf.set_font("Helvetica", "B", 11)
        pdf.cell(0, 7, "Configuration notes", new_x="LMARGIN", new_y="NEXT")
        pdf.set_font("Helvetica", size=9)
        for warning in snapshot["warnings"]:
            pdf.multi_cell(0, 5, _pdf_text(f"- {warning}"), new_x="LMARGIN", new_y="NEXT")
    pdf.ln(3)
    pdf.set_font("Helvetica", "I", 8)
    pdf.set_text_color(90, 100, 95)
    pdf.multi_cell(0, 5, _pdf_text(snapshot["dataNote"]), new_x="LMARGIN", new_y="NEXT")
    pdf.output(path)


def _serialize_report(row: sqlite3.Row, include_snapshot: bool = False) -> dict[str, Any]:
    item = {
        "id": int(row["id"]), "definitionId": row["definition_id"],
        "name": row["name"], "type": row["report_type"], "status": row["status"],
        "filters": _loads(row["filters_json"], {}), "sections": _loads(row["sections_json"], []),
        "creator": {"id": int(row["creator_user_id"]), "name": row["creator_name"], "email": row["creator_email"]},
        "createdAt": row["created_at"], "completedAt": row["completed_at"],
        "failureReason": row["failure_reason"],
        "sourceCounts": _loads(row["source_counts_json"], {}), "version": int(row["version"]),
        "availableFormats": [name for name, column in (("pdf", "pdf_path"), ("csv", "csv_path")) if row[column]],
    }
    if include_snapshot:
        item["snapshot"] = _loads(row["snapshot_json"], None)
    return item


_REPORT_SELECT = """SELECT report_runs.*, users.name AS creator_name, users.email AS creator_email
FROM report_runs JOIN users ON users.id = report_runs.creator_user_id"""


def create_report(
    name: str, report_type: str, filters: dict[str, Any], sections: list[str],
    creator: dict[str, Any], runtime_info: dict[str, Any] | None = None,
    definition_id: int | None = None, version: int = 1,
) -> dict[str, Any]:
    cleaned_name = " ".join(name.split())
    if not 2 <= len(cleaned_name) <= 120:
        raise ValueError("Report name must contain 2 to 120 characters")
    normalized = validate_report_filters(filters)
    if report_type not in REPORT_TYPES:
        raise ValueError("Invalid report type")
    if not sections:
        raise ValueError("Select at least one report section")
    created_at = utc_now()
    with _connect() as connection:
        if definition_id is None:
            definition_cursor = connection.execute(
                """INSERT INTO report_definitions(
                       name, report_type, filters_json, sections_json,
                       creator_user_id, created_at, updated_at
                   ) VALUES (?, ?, ?, ?, ?, ?, ?)""",
                (
                    cleaned_name, report_type, _json(normalized), _json(sections),
                    creator["id"], created_at, created_at,
                ),
            )
            definition_id = int(definition_cursor.lastrowid)
        cursor = connection.execute(
            """INSERT INTO report_runs(
                   definition_id, name, report_type, filters_json, sections_json,
                   creator_user_id, created_at, version
               ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)""",
            (definition_id, cleaned_name, report_type, _json(normalized), _json(sections), creator["id"], created_at, version),
        )
        report_id = int(cursor.lastrowid)
    try:
        snapshot = build_report_snapshot(report_type, normalized, sections, runtime_info)
        export_stem = f"report-{report_id}-v{version}"
        pdf_path = REPORT_ROOT / f"{export_stem}.pdf"
        csv_path = REPORT_ROOT / f"{export_stem}.csv"
        write_pdf_export(pdf_path, cleaned_name, report_id, version, snapshot)
        write_csv_export(csv_path, snapshot)
        completed_at = utc_now()
        with _connect() as connection:
            connection.execute(
                """UPDATE report_runs SET status='READY', completed_at=?, snapshot_json=?,
                       pdf_path=?, csv_path=?, source_counts_json=? WHERE id=?""",
                (completed_at, _json(snapshot), str(pdf_path), str(csv_path), _json(snapshot["sourceCounts"]), report_id),
            )
    except Exception as error:
        if isinstance(error, OSError):
            failure_reason = "Report export storage is unavailable."
        elif isinstance(error, sqlite3.Error):
            failure_reason = "Report source data could not be read."
        else:
            failure_reason = "Report generation failed."
        with _connect() as connection:
            connection.execute(
                "UPDATE report_runs SET status='FAILED', completed_at=?, failure_reason=? WHERE id=?",
                (utc_now(), failure_reason, report_id),
            )
        raise
    result = get_report(report_id)
    if result is None:
        raise RuntimeError("Generated report could not be loaded")
    return result


def get_report(report_id: int) -> dict[str, Any] | None:
    with _connect() as connection:
        row = connection.execute(f"{_REPORT_SELECT} WHERE report_runs.id=?", (report_id,)).fetchone()
    return _serialize_report(row, include_snapshot=True) if row else None


def list_reports(
    page: int = 1, page_size: int = 20, search: str = "", report_type: str = "",
    status: str = "", creator_id: int | None = None, date_filter: str = "", sort: str = "newest",
) -> dict[str, Any]:
    clauses: list[str] = []
    values: list[Any] = []
    if search:
        needle = f"%{search.strip().lower()}%"
        clauses.append("(LOWER(report_runs.name) LIKE ? OR CAST(report_runs.id AS TEXT) LIKE ?)")
        values.extend([needle, needle])
    if report_type:
        clauses.append("report_runs.report_type=?")
        values.append(report_type)
    if status:
        clauses.append("report_runs.status=?")
        values.append(status)
    if creator_id is not None:
        clauses.append("report_runs.creator_user_id=?")
        values.append(creator_id)
    if date_filter:
        now = datetime.now(timezone.utc)
        start = now.replace(hour=0, minute=0, second=0, microsecond=0) if date_filter == "today" else now - timedelta(days=7)
        clauses.append("report_runs.created_at>=?")
        values.append(start.isoformat().replace("+00:00", "Z"))
    where = f"WHERE {' AND '.join(clauses)}" if clauses else ""
    order = "report_runs.created_at ASC, report_runs.id ASC" if sort == "oldest" else "report_runs.created_at DESC, report_runs.id DESC"
    offset = (page - 1) * page_size
    with _connect() as connection:
        total = int(connection.execute(f"SELECT COUNT(*) FROM report_runs {where}", values).fetchone()[0])
        rows = connection.execute(
            f"{_REPORT_SELECT} {where} ORDER BY {order} LIMIT ? OFFSET ?", [*values, page_size, offset],
        ).fetchall()
    return {"items": [_serialize_report(row) for row in rows], "total": total, "page": page, "pageSize": page_size}


def report_summary() -> dict[str, int]:
    month = datetime.now(timezone.utc).replace(day=1, hour=0, minute=0, second=0, microsecond=0).isoformat().replace("+00:00", "Z")
    with _connect() as connection:
        row = connection.execute(
            """SELECT COUNT(*) AS total,
                      SUM(CASE WHEN status='READY' THEN 1 ELSE 0 END) AS ready,
                      SUM(CASE WHEN status='FAILED' THEN 1 ELSE 0 END) AS failed,
                      SUM(CASE WHEN created_at>=? THEN 1 ELSE 0 END) AS this_month
               FROM report_runs""", (month,),
        ).fetchone()
        scheduled = int(connection.execute("SELECT COUNT(*) FROM report_schedules WHERE enabled=1").fetchone()[0])
    return {"total": int(row["total"] or 0), "ready": int(row["ready"] or 0), "failed": int(row["failed"] or 0), "scheduled": scheduled, "thisMonth": int(row["this_month"] or 0)}


def rename_report(report_id: int, name: str) -> dict[str, Any]:
    cleaned = " ".join(name.split())
    if not 2 <= len(cleaned) <= 120:
        raise ValueError("Report name must contain 2 to 120 characters")
    with _connect() as connection:
        cursor = connection.execute("UPDATE report_runs SET name=? WHERE id=?", (cleaned, report_id))
        if cursor.rowcount == 0:
            raise LookupError("Report not found")
    result = get_report(report_id)
    if result is None:
        raise LookupError("Report not found")
    return result


def regenerate_report(report_id: int, creator: dict[str, Any], runtime_info: dict[str, Any] | None = None) -> dict[str, Any]:
    existing = get_report(report_id)
    if existing is None:
        raise LookupError("Report not found")
    return create_report(
        existing["name"], existing["type"], existing["filters"], existing["sections"], creator,
        runtime_info, existing["definitionId"], existing["version"] + 1,
    )


def get_report_export_path(report_id: int, export_format: str) -> Path:
    if export_format not in {"pdf", "csv"}:
        raise ValueError("Unsupported report format")
    with _connect() as connection:
        row = connection.execute(
            f"SELECT status, {export_format}_path AS path FROM report_runs WHERE id=?", (report_id,),
        ).fetchone()
    if row is None:
        raise LookupError("Report not found")
    if row["status"] == "GENERATING":
        raise RuntimeError("Report is still generating")
    if not row["path"]:
        raise FileNotFoundError("Report export is unavailable")
    path = Path(row["path"]).resolve()
    root = REPORT_ROOT.resolve()
    if not path.is_relative_to(root) or not path.is_file():
        raise FileNotFoundError("Report export is unavailable")
    return path


def calculate_next_run(frequency: str, generation_time: str, timezone_name: str, after: datetime | None = None) -> str:
    if frequency not in REPORT_FREQUENCIES:
        raise ValueError("Invalid report frequency")
    try:
        hour, minute = (int(part) for part in generation_time.split(":"))
        if hour not in range(24) or minute not in range(60):
            raise ValueError
    except (ValueError, TypeError) as error:
        raise ValueError("Generation time must use HH:MM") from error
    try:
        zone = ZoneInfo(timezone_name)
    except ZoneInfoNotFoundError as error:
        raise ValueError("Unknown schedule timezone") from error
    now = (after or datetime.now(timezone.utc)).astimezone(zone)
    candidate = now.replace(hour=hour, minute=minute, second=0, microsecond=0)
    if candidate <= now:
        if frequency == "DAILY":
            candidate += timedelta(days=1)
        elif frequency == "WEEKLY":
            candidate += timedelta(days=7)
        else:
            year = candidate.year + (candidate.month == 12)
            month = 1 if candidate.month == 12 else candidate.month + 1
            candidate = candidate.replace(year=year, month=month, day=1)
    elif frequency == "WEEKLY":
        candidate += timedelta(days=(7 - candidate.weekday()) % 7)
    elif frequency == "MONTHLY":
        candidate = candidate.replace(day=1)
        if candidate <= now:
            year = candidate.year + (candidate.month == 12)
            month = 1 if candidate.month == 12 else candidate.month + 1
            candidate = candidate.replace(year=year, month=month, day=1)
    return candidate.astimezone(timezone.utc).isoformat().replace("+00:00", "Z")


def _serialize_schedule(row: sqlite3.Row) -> dict[str, Any]:
    return {
        "id": int(row["id"]), "name": row["name"], "type": row["report_type"],
        "frequency": row["frequency"], "generationTime": row["generation_time"],
        "timezone": row["timezone"], "filters": _loads(row["filters_json"], {}),
        "sections": _loads(row["sections_json"], []), "enabled": bool(row["enabled"]),
        "lastRunAt": row["last_run_at"], "nextRunAt": row["next_run_at"],
        "creator": {"id": int(row["creator_user_id"]), "name": row["creator_name"], "email": row["creator_email"]},
        "createdAt": row["created_at"], "updatedAt": row["updated_at"],
        "delivery": "Not configured",
    }


def list_report_schedules() -> list[dict[str, Any]]:
    with _connect() as connection:
        rows = connection.execute(
            """SELECT report_schedules.*, users.name AS creator_name, users.email AS creator_email
               FROM report_schedules JOIN users ON users.id=report_schedules.creator_user_id
               ORDER BY report_schedules.created_at DESC""",
        ).fetchall()
    return [_serialize_schedule(row) for row in rows]


def create_report_schedule(
    name: str, report_type: str, frequency: str, generation_time: str,
    timezone_name: str, filters: dict[str, Any], sections: list[str], creator: dict[str, Any],
) -> dict[str, Any]:
    cleaned = " ".join(name.split())
    if not 2 <= len(cleaned) <= 120:
        raise ValueError("Schedule name must contain 2 to 120 characters")
    if report_type not in REPORT_TYPES:
        raise ValueError("Invalid report type")
    next_run = calculate_next_run(frequency, generation_time, timezone_name)
    now = utc_now()
    with _connect() as connection:
        cursor = connection.execute(
            """INSERT INTO report_schedules(
                   name, report_type, frequency, generation_time, timezone,
                   filters_json, sections_json, next_run_at, creator_user_id,
                   created_at, updated_at
               ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            (cleaned, report_type, frequency, generation_time, timezone_name, _json(filters), _json(sections), next_run, creator["id"], now, now),
        )
        schedule_id = int(cursor.lastrowid)
    return next(item for item in list_report_schedules() if item["id"] == schedule_id)


def toggle_report_schedule(schedule_id: int) -> dict[str, Any]:
    now = utc_now()
    with _connect() as connection:
        row = connection.execute("SELECT * FROM report_schedules WHERE id=?", (schedule_id,)).fetchone()
        if row is None:
            raise LookupError("Report schedule not found")
        enabled = not bool(row["enabled"])
        next_run = calculate_next_run(row["frequency"], row["generation_time"], row["timezone"]) if enabled else row["next_run_at"]
        connection.execute(
            "UPDATE report_schedules SET enabled=?, next_run_at=?, updated_at=? WHERE id=?",
            (int(enabled), next_run, now, schedule_id),
        )
    return next(item for item in list_report_schedules() if item["id"] == schedule_id)


def schedule_period(frequency: str, end: datetime | None = None) -> tuple[str, str]:
    current = (end or datetime.now(timezone.utc)).astimezone(timezone.utc)
    if frequency == "DAILY":
        start = current - timedelta(days=1)
    elif frequency == "WEEKLY":
        start = current - timedelta(days=7)
    else:
        start = current - timedelta(days=30)
    return start.isoformat().replace("+00:00", "Z"), current.isoformat().replace("+00:00", "Z")


def run_due_report_schedules(runtime_info: dict[str, Any] | None = None) -> int:
    now = utc_now()
    with _connect() as connection:
        rows = connection.execute(
            """SELECT report_schedules.*, users.name AS creator_name,
                      users.email AS creator_email, users.created_at AS user_created_at
               FROM report_schedules JOIN users ON users.id=report_schedules.creator_user_id
               WHERE enabled=1 AND next_run_at<=? ORDER BY next_run_at LIMIT 20""", (now,),
        ).fetchall()
    completed = 0
    for row in rows:
        start_at, end_at = schedule_period(row["frequency"])
        filters = _loads(row["filters_json"], {})
        filters.update({"startAt": start_at, "endAt": end_at, "timezone": row["timezone"]})
        creator = {"id": int(row["creator_user_id"]), "name": row["creator_name"], "email": row["creator_email"], "createdAt": row["user_created_at"]}
        try:
            create_report(row["name"], row["report_type"], filters, _loads(row["sections_json"], ["kpis"]), creator, runtime_info)
        except Exception:
            # create_report persists the failed run; continue so one bad schedule
            # cannot prevent other due schedules from being processed.
            pass
        finally:
            next_run = calculate_next_run(row["frequency"], row["generation_time"], row["timezone"])
            with _connect() as connection:
                connection.execute(
                    "UPDATE report_schedules SET last_run_at=?, next_run_at=?, updated_at=? WHERE id=?",
                    (now, next_run, now, row["id"]),
                )
        completed += 1
    return completed


def csv_safe_for_test(value: Any) -> str:
    """Expose the CSV security boundary for focused regression tests."""
    return _csv_safe(value)


def render_csv_for_test(snapshot: dict[str, Any]) -> str:
    headers, rows = _csv_rows(snapshot)
    stream = io.StringIO()
    writer = csv.writer(stream)
    writer.writerow(headers)
    writer.writerows([[_csv_safe(value) for value in row] for row in rows])
    return stream.getvalue()
