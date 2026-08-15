"""SQLite persistence and read models for the desktop and web applications."""

import json
import sqlite3
from contextlib import contextmanager
from datetime import datetime, timedelta, timezone
from typing import Any

from pathlib import Path

from config.settings import (
    ALERT_COOLDOWN_SECONDS, CAMERA_ID, CAMERA_NAME, DATABASE_PATH, SPEED_LIMIT,
)
SQLITE_BUSY_TIMEOUT_MS = 30_000


@contextmanager
def _connect():
    connection = sqlite3.connect(DATABASE_PATH, timeout=SQLITE_BUSY_TIMEOUT_MS / 1_000)
    connection.row_factory = sqlite3.Row
    connection.execute("PRAGMA foreign_keys = ON")
    connection.execute(f"PRAGMA busy_timeout = {SQLITE_BUSY_TIMEOUT_MS}")
    connection.execute("PRAGMA synchronous = NORMAL")
    try:
        yield connection
        connection.commit()
    except Exception:
        connection.rollback()
        raise
    finally:
        connection.close()


def create_database() -> None:
    Path(DATABASE_PATH).parent.mkdir(parents=True, exist_ok=True)
    with _connect() as connection:
        # Live detections and browser sessions share this database. WAL lets
        # authentication reads continue while the pipeline is saving events.
        connection.execute("PRAGMA journal_mode = WAL")
        connection.execute("""
            CREATE TABLE IF NOT EXISTS vehicles(
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                plate TEXT,
                speed REAL,
                status TEXT,
                time TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)
        existing = {row["name"] for row in connection.execute("PRAGMA table_info(vehicles)")}
        additions = {
            "tracking_id": "INTEGER",
            "vehicle_type": "TEXT DEFAULT 'unknown'",
            "camera_id": f"TEXT DEFAULT '{CAMERA_ID}'",
            "snapshot_url": "TEXT",
            "plate_confidence": "REAL",
            "plate_status": "TEXT DEFAULT 'NOT_DETECTED'",
            "plate_image_path": "TEXT",
        }
        for column, definition in additions.items():
            if column not in existing:
                connection.execute(f"ALTER TABLE vehicles ADD COLUMN {column} {definition}")
        connection.execute("CREATE INDEX IF NOT EXISTS idx_vehicles_time ON vehicles(time)")
        connection.execute("CREATE INDEX IF NOT EXISTS idx_vehicles_status ON vehicles(status)")
        connection.execute("""
            CREATE TABLE IF NOT EXISTS users(
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                name TEXT NOT NULL,
                email TEXT NOT NULL COLLATE NOCASE UNIQUE,
                password_hash TEXT NOT NULL,
                created_at TEXT NOT NULL
            )
        """)
        connection.execute("""
            CREATE TABLE IF NOT EXISTS auth_sessions(
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER NOT NULL,
                token_hash TEXT NOT NULL UNIQUE,
                expires_at TEXT NOT NULL,
                created_at TEXT NOT NULL,
                FOREIGN KEY(user_id) REFERENCES users(id) ON DELETE CASCADE
            )
        """)
        connection.execute("CREATE INDEX IF NOT EXISTS idx_auth_sessions_token ON auth_sessions(token_hash)")
        connection.execute("CREATE INDEX IF NOT EXISTS idx_auth_sessions_expiry ON auth_sessions(expires_at)")
        connection.execute("""
            CREATE TABLE IF NOT EXISTS violations(
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                vehicle_id INTEGER,
                tracking_id INTEGER NOT NULL,
                violation_type TEXT NOT NULL,
                confidence REAL NOT NULL,
                camera_id TEXT NOT NULL,
                vehicle_type TEXT NOT NULL,
                lane_id INTEGER,
                direction TEXT,
                evidence_path TEXT,
                session_key TEXT NOT NULL,
                source_generation INTEGER NOT NULL DEFAULT 0,
                speed REAL,
                speed_limit REAL,
                detected_at TEXT NOT NULL,
                FOREIGN KEY(vehicle_id) REFERENCES vehicles(id) ON DELETE SET NULL,
                UNIQUE(session_key, tracking_id, violation_type)
            )
        """)
        violation_columns = {
            row["name"] for row in connection.execute("PRAGMA table_info(violations)")
        }
        for column, definition in {"speed": "REAL", "speed_limit": "REAL"}.items():
            if column not in violation_columns:
                connection.execute(f"ALTER TABLE violations ADD COLUMN {column} {definition}")
        connection.execute(
            "CREATE INDEX IF NOT EXISTS idx_violations_detected_at ON violations(detected_at)"
        )
        connection.execute(
            "CREATE INDEX IF NOT EXISTS idx_violations_type ON violations(violation_type)"
        )
        connection.execute("""
            CREATE TABLE IF NOT EXISTS alerts(
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                primary_violation_id INTEGER NOT NULL UNIQUE,
                latest_violation_id INTEGER NOT NULL,
                tracking_id INTEGER NOT NULL,
                camera_id TEXT NOT NULL,
                violation_type TEXT NOT NULL,
                severity TEXT NOT NULL,
                status TEXT NOT NULL DEFAULT 'NEW',
                assigned_user_id INTEGER,
                occurrence_count INTEGER NOT NULL DEFAULT 1,
                first_occurrence_at TEXT NOT NULL,
                last_occurrence_at TEXT NOT NULL,
                acknowledged_at TEXT,
                acknowledged_by INTEGER,
                resolved_at TEXT,
                resolved_by INTEGER,
                resolution_note TEXT,
                false_positive_reason TEXT,
                version INTEGER NOT NULL DEFAULT 1,
                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL,
                FOREIGN KEY(primary_violation_id) REFERENCES violations(id) ON DELETE CASCADE,
                FOREIGN KEY(latest_violation_id) REFERENCES violations(id) ON DELETE CASCADE,
                FOREIGN KEY(assigned_user_id) REFERENCES users(id) ON DELETE SET NULL,
                FOREIGN KEY(acknowledged_by) REFERENCES users(id) ON DELETE SET NULL,
                FOREIGN KEY(resolved_by) REFERENCES users(id) ON DELETE SET NULL
            )
        """)
        connection.execute("""
            CREATE TABLE IF NOT EXISTS alert_occurrences(
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                alert_id INTEGER NOT NULL,
                violation_id INTEGER NOT NULL UNIQUE,
                occurred_at TEXT NOT NULL,
                FOREIGN KEY(alert_id) REFERENCES alerts(id) ON DELETE CASCADE,
                FOREIGN KEY(violation_id) REFERENCES violations(id) ON DELETE CASCADE
            )
        """)
        connection.execute("""
            CREATE TABLE IF NOT EXISTS alert_activity(
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                alert_id INTEGER NOT NULL,
                action TEXT NOT NULL,
                from_status TEXT,
                to_status TEXT,
                actor_user_id INTEGER,
                actor_name TEXT,
                note TEXT,
                alert_version INTEGER NOT NULL,
                created_at TEXT NOT NULL,
                FOREIGN KEY(alert_id) REFERENCES alerts(id) ON DELETE CASCADE,
                FOREIGN KEY(actor_user_id) REFERENCES users(id) ON DELETE SET NULL
            )
        """)
        connection.execute(
            "CREATE INDEX IF NOT EXISTS idx_alerts_status_severity ON alerts(status, severity)"
        )
        connection.execute(
            "CREATE INDEX IF NOT EXISTS idx_alerts_last_occurrence ON alerts(last_occurrence_at)"
        )
        connection.execute(
            "CREATE INDEX IF NOT EXISTS idx_alert_occurrences_alert ON alert_occurrences(alert_id)"
        )
        connection.execute(
            "CREATE INDEX IF NOT EXISTS idx_alert_activity_alert ON alert_activity(alert_id, created_at)"
        )
        connection.execute("""
            CREATE TABLE IF NOT EXISTS report_definitions(
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                name TEXT NOT NULL,
                report_type TEXT NOT NULL,
                filters_json TEXT NOT NULL,
                sections_json TEXT NOT NULL,
                creator_user_id INTEGER NOT NULL,
                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL,
                FOREIGN KEY(creator_user_id) REFERENCES users(id) ON DELETE RESTRICT
            )
        """)
        connection.execute("""
            CREATE TABLE IF NOT EXISTS report_runs(
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                definition_id INTEGER,
                name TEXT NOT NULL,
                report_type TEXT NOT NULL,
                status TEXT NOT NULL DEFAULT 'GENERATING',
                filters_json TEXT NOT NULL,
                sections_json TEXT NOT NULL,
                creator_user_id INTEGER NOT NULL,
                created_at TEXT NOT NULL,
                completed_at TEXT,
                snapshot_json TEXT,
                pdf_path TEXT,
                csv_path TEXT,
                failure_reason TEXT,
                source_counts_json TEXT NOT NULL DEFAULT '{}',
                version INTEGER NOT NULL DEFAULT 1,
                FOREIGN KEY(definition_id) REFERENCES report_definitions(id) ON DELETE SET NULL,
                FOREIGN KEY(creator_user_id) REFERENCES users(id) ON DELETE RESTRICT
            )
        """)
        connection.execute("""
            CREATE TABLE IF NOT EXISTS report_schedules(
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                name TEXT NOT NULL,
                report_type TEXT NOT NULL,
                frequency TEXT NOT NULL,
                generation_time TEXT NOT NULL,
                timezone TEXT NOT NULL,
                filters_json TEXT NOT NULL,
                sections_json TEXT NOT NULL,
                enabled INTEGER NOT NULL DEFAULT 1,
                last_run_at TEXT,
                next_run_at TEXT NOT NULL,
                creator_user_id INTEGER NOT NULL,
                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL,
                FOREIGN KEY(creator_user_id) REFERENCES users(id) ON DELETE RESTRICT
            )
        """)
        connection.execute(
            "CREATE INDEX IF NOT EXISTS idx_report_runs_type ON report_runs(report_type)"
        )
        connection.execute(
            "CREATE INDEX IF NOT EXISTS idx_report_runs_status ON report_runs(status)"
        )
        connection.execute(
            "CREATE INDEX IF NOT EXISTS idx_report_runs_creator ON report_runs(creator_user_id)"
        )
        connection.execute(
            "CREATE INDEX IF NOT EXISTS idx_report_runs_created ON report_runs(created_at)"
        )
        connection.execute(
            "CREATE INDEX IF NOT EXISTS idx_report_schedules_next ON report_schedules(enabled, next_run_at)"
        )
        connection.execute("""
            CREATE TABLE IF NOT EXISTS camera_lane_settings(
                camera_id TEXT PRIMARY KEY,
                rules_json TEXT NOT NULL,
                updated_at TEXT NOT NULL
            )
        """)
        connection.execute("""
            CREATE TABLE IF NOT EXISTS camera_calibration_settings(
                camera_id TEXT PRIMARY KEY,
                calibration_json TEXT NOT NULL,
                updated_at TEXT NOT NULL
            )
        """)
        connection.execute("""
            CREATE TABLE IF NOT EXISTS junctions(
                id TEXT PRIMARY KEY,
                name TEXT NOT NULL,
                location TEXT NOT NULL DEFAULT '',
                description TEXT NOT NULL DEFAULT '',
                speed_limit REAL,
                enabled INTEGER NOT NULL DEFAULT 1,
                sort_order INTEGER NOT NULL DEFAULT 0
            )
        """)
        connection.execute("""
            CREATE TABLE IF NOT EXISTS cameras(
                id TEXT PRIMARY KEY,
                junction_id TEXT NOT NULL,
                name TEXT NOT NULL,
                source_type TEXT NOT NULL DEFAULT 'live',
                video_url TEXT NOT NULL DEFAULT '',
                speed_limit REAL,
                enabled INTEGER NOT NULL DEFAULT 1,
                sort_order INTEGER NOT NULL DEFAULT 0,
                FOREIGN KEY(junction_id) REFERENCES junctions(id) ON DELETE CASCADE
            )
        """)
        connection.execute(
            "CREATE INDEX IF NOT EXISTS idx_cameras_junction ON cameras(junction_id)"
        )
        connection.execute("""
            CREATE TABLE IF NOT EXISTS demo_videos(
                id TEXT PRIMARY KEY,
                junction_id TEXT NOT NULL,
                camera_id TEXT,
                title TEXT NOT NULL,
                description TEXT NOT NULL DEFAULT '',
                filename TEXT NOT NULL,
                scenario TEXT NOT NULL DEFAULT 'normal',
                duration_seconds REAL,
                enabled INTEGER NOT NULL DEFAULT 1,
                sort_order INTEGER NOT NULL DEFAULT 0,
                FOREIGN KEY(junction_id) REFERENCES junctions(id) ON DELETE CASCADE,
                FOREIGN KEY(camera_id) REFERENCES cameras(id) ON DELETE SET NULL
            )
        """)
        connection.execute(
            "CREATE INDEX IF NOT EXISTS idx_demo_videos_junction ON demo_videos(junction_id)"
        )
        connection.execute(
            "CREATE INDEX IF NOT EXISTS idx_demo_videos_camera ON demo_videos(camera_id)"
        )
        _seed_junction_configuration(connection)
        # Preserve historical overspeed records in the new violation read model.
        connection.execute("""
            INSERT OR IGNORE INTO violations(
                vehicle_id, tracking_id, violation_type, confidence, camera_id,
                vehicle_type, session_key, source_generation, speed, speed_limit, detected_at
            )
            SELECT id, COALESCE(tracking_id, id), 'OVERSPEED', 1.0,
                   COALESCE(camera_id, ?), COALESCE(vehicle_type, 'unknown'),
                   'legacy:' || id, 0, speed, ?, REPLACE(time, ' ', 'T') || 'Z'
            FROM vehicles WHERE status = 'OVERSPEED'
        """, (CAMERA_ID, SPEED_LIMIT))


def _seed_junction_configuration(connection: sqlite3.Connection) -> None:
    """Seed instance configuration only when the junction tables are empty."""
    seeded = connection.execute("SELECT COUNT(*) FROM junctions").fetchone()[0]
    if seeded:
        return
    junction_rows = [
        ("north", "North Junction", "Birendranagar, Surkhet", "Main city entry point with highest mixed-traffic volume.", 50, 1, 0),
        ("bus-park", "Surkhet Bus Park", "Bus Park Road, Birendranagar", "Bus and tempo loading zone with heavy pedestrian flow.", 30, 1, 1),
        ("airport-chowk", "Airport Chowk", "Surkhet Airport Road", "Junction near Surkhet airport access road.", 50, 1, 2),
        ("demo", "Demo Junction", "Showcase", "Pre-recorded scenarios for presentations and testing.", 50, 1, 3),
    ]
    connection.executemany(
        "INSERT INTO junctions(id, name, location, description, speed_limit, enabled, sort_order) "
        "VALUES (?, ?, ?, ?, ?, ?, ?)",
        junction_rows,
    )
    camera_rows = [
        ("north-cam-01", "north", "Camera 01", "live", "", None, 1, 0),
        ("north-cam-02", "north", "Camera 02", "live", "", None, 1, 1),
        ("bus-park-cam-01", "bus-park", "Camera 01", "live", "", None, 1, 0),
        ("bus-park-cam-02", "bus-park", "Camera 02", "live", "", None, 1, 1),
        ("airport-cam-01", "airport-chowk", "Camera 01", "live", "", None, 1, 0),
        ("airport-cam-02", "airport-chowk", "Camera 02", "live", "", None, 1, 1),
        ("demo-cam-01", "demo", "Camera 01", "demo", "", None, 1, 0),
        ("demo-cam-02", "demo", "Camera 02", "demo", "", None, 1, 1),
    ]
    connection.executemany(
        "INSERT INTO cameras(id, junction_id, name, source_type, video_url, speed_limit, enabled, sort_order) "
        "VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
        camera_rows,
    )
    demo_rows = [
        ("demo-normal", "demo", "demo-cam-01", "Normal Traffic", "Steady mixed traffic moving within the speed limit.", "normal_traffic.mp4", "normal", None, 1, 0),
        ("demo-helmet", "demo", "demo-cam-01", "Helmet Violation", "Motorcyclists riding without helmets at the junction.", "helmet_violation.mp4", "helmet", None, 1, 1),
        ("demo-overspeed", "demo", "demo-cam-01", "Overspeed Detection", "Vehicles exceeding the junction speed limit.", "overspeed.mp4", "overspeed", None, 1, 2),
        ("demo-wrong-lane", "demo", "demo-cam-02", "Wrong Lane", "Vehicles driving against the permitted lane direction.", "wrong_lane.mp4", "wrong_lane", None, 1, 3),
        ("demo-anpr", "demo", "demo-cam-02", "ANPR Demo", "Number-plate recognition of passing vehicles.", "anpr_demo.mp4", "anpr", None, 1, 4),
        ("demo-busy", "demo", "demo-cam-02", "Busy Junction", "Heavy congestion at peak evening hours.", "busy_junction.mp4", "heavy", None, 1, 5),
        ("demo-night", "demo", "demo-cam-02", "Night Traffic", "Low-light monitoring at night.", "night_traffic.mp4", "night", None, 1, 6),
    ]
    junction_demo_videos = [
        ("normal", "Normal Traffic", "Steady mixed traffic moving within the speed limit.", "normal", "cam-01"),
        ("traffic-flow", "Mixed Traffic Flow", "Mixed vehicle flow through the junction.", "normal", "cam-02"),
        ("overspeed", "Overspeed Detection", "Vehicles exceeding the junction speed limit.", "overspeed", "cam-01"),
        ("heavy", "Heavy Congestion", "Heavy congestion at peak hours.", "heavy", "cam-02"),
        ("night", "Night Traffic", "Low-light monitoring at night.", "night", "cam-01"),
    ]
    demo_files = ["traffic.mp4", "traffic1.mp4", "traffic2.mp4", "traffic3.mp4", "traffic4.mp4"]
    junction_cameras = {
        "north": ("north-cam-01", "north-cam-02"),
        "bus-park": ("bus-park-cam-01", "bus-park-cam-02"),
        "airport-chowk": ("airport-cam-01", "airport-cam-02"),
    }
    for junction_index, (junction_id, (camera_01, camera_02)) in enumerate(junction_cameras.items()):
        for sort, (key, title, description, scenario, camera_role) in enumerate(junction_demo_videos):
            camera_id = camera_01 if camera_role == "cam-01" else camera_02
            filename = demo_files[(sort + junction_index) % len(demo_files)]
            demo_rows.append(
                (f"{junction_id}-{key}", junction_id, camera_id, title, description, filename, scenario, None, 1, sort)
            )
    connection.executemany(
        "INSERT INTO demo_videos(id, junction_id, camera_id, title, description, filename, scenario, duration_seconds, enabled, sort_order) "
        "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
        demo_rows,
    )


def _serialize_user(row: sqlite3.Row) -> dict[str, Any]:
    return {
        "id": int(row["id"]),
        "name": row["name"],
        "email": row["email"],
        "createdAt": row["created_at"],
    }


def create_user(name: str, email: str, password_hash: str) -> dict[str, Any] | None:
    """Create a user, returning None when the normalized email already exists."""
    now = datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")
    try:
        with _connect() as connection:
            cursor = connection.execute(
                "INSERT INTO users(name, email, password_hash, created_at) VALUES (?, ?, ?, ?)",
                (name, email, password_hash, now),
            )
            row = connection.execute("SELECT * FROM users WHERE id = ?", (cursor.lastrowid,)).fetchone()
    except sqlite3.IntegrityError:
        return None
    return _serialize_user(row)


def get_user_credentials(email: str) -> dict[str, Any] | None:
    with _connect() as connection:
        row = connection.execute(
            "SELECT id, name, email, password_hash, created_at FROM users WHERE email = ?",
            (email,),
        ).fetchone()
    if row is None:
        return None
    return {**_serialize_user(row), "passwordHash": row["password_hash"]}


def create_auth_session(user_id: int, token_hash: str, expires_at: str) -> None:
    now = datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")
    with _connect() as connection:
        connection.execute("DELETE FROM auth_sessions WHERE expires_at <= ?", (now,))
        connection.execute(
            "INSERT INTO auth_sessions(user_id, token_hash, expires_at, created_at) VALUES (?, ?, ?, ?)",
            (user_id, token_hash, expires_at, now),
        )


def get_user_by_session(token_hash: str) -> dict[str, Any] | None:
    now = datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")
    with _connect() as connection:
        row = connection.execute(
            """SELECT users.* FROM auth_sessions
               JOIN users ON users.id = auth_sessions.user_id
               WHERE auth_sessions.token_hash = ? AND auth_sessions.expires_at > ?""",
            (token_hash, now),
        ).fetchone()
    return _serialize_user(row) if row else None


def delete_auth_session(token_hash: str) -> None:
    with _connect() as connection:
        connection.execute("DELETE FROM auth_sessions WHERE token_hash = ?", (token_hash,))


def save_vehicle(
    plate: str,
    speed: float | None,
    status: str,
    tracking_id: int | None = None,
    vehicle_type: str = "unknown",
    camera_id: str = CAMERA_ID,
    snapshot_url: str | None = None,
) -> int:
    with _connect() as connection:
        cursor = connection.execute(
            """INSERT INTO vehicles
               (plate, speed, status, tracking_id, vehicle_type, camera_id, snapshot_url)
               VALUES (?, ?, ?, ?, ?, ?, ?)""",
            (plate, speed, status, tracking_id, vehicle_type, camera_id, snapshot_url),
        )
        return int(cursor.lastrowid)


def update_vehicle_measurement(record_id: int, speed: float, status: str) -> None:
    with _connect() as connection:
        connection.execute(
            "UPDATE vehicles SET speed = ?, status = ? WHERE id = ?",
            (speed, status, record_id),
        )


def get_vehicle_snapshot_path(vehicle_id: int) -> str | None:
    with _connect() as connection:
        row = connection.execute(
            "SELECT snapshot_url FROM vehicles WHERE id = ?", (vehicle_id,)
        ).fetchone()
    return row["snapshot_url"] if row else None


def update_vehicle_plate(
    record_id: int,
    plate: str,
    confidence: float,
    plate_status: str,
    plate_image_path: str | None = None,
) -> None:
    with _connect() as connection:
        connection.execute(
            """UPDATE vehicles SET plate = ?, plate_confidence = ?, plate_status = ?,
               plate_image_path = COALESCE(?, plate_image_path) WHERE id = ?""",
            (plate, confidence, plate_status, plate_image_path, record_id),
        )


def save_violation(
    vehicle_id: int | None,
    tracking_id: int,
    violation_type: str,
    confidence: float,
    camera_id: str,
    vehicle_type: str,
    session_key: str,
    source_generation: int = 0,
    lane_id: int | None = None,
    direction: str | None = None,
    evidence_path: str | None = None,
    detected_at: str | None = None,
    speed: float | None = None,
    speed_limit: float | None = None,
) -> dict[str, Any] | None:
    """Insert one violation per track/session/type and return it when newly created."""
    timestamp = detected_at or datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")
    with _connect() as connection:
        cursor = connection.execute(
            """INSERT OR IGNORE INTO violations(
                   vehicle_id, tracking_id, violation_type, confidence, camera_id,
                   vehicle_type, lane_id, direction, evidence_path, session_key,
                   source_generation, speed, speed_limit, detected_at
               ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            (
                vehicle_id, tracking_id, violation_type, confidence, camera_id,
                vehicle_type, lane_id, direction, evidence_path, session_key,
                source_generation, speed, speed_limit, timestamp,
            ),
        )
        if cursor.rowcount == 0:
            return None
        row = connection.execute(
            "SELECT * FROM violations WHERE id = ?", (cursor.lastrowid,)
        ).fetchone()
        _create_alert_for_violation(connection, row)
    return _serialize_violation(row)


ALERT_STATUSES = ("NEW", "ACKNOWLEDGED", "INVESTIGATING", "RESOLVED", "FALSE_POSITIVE")
ALERT_SEVERITIES = ("LOW", "MEDIUM", "HIGH", "CRITICAL")
_SEVERITY_RANK = {severity: index for index, severity in enumerate(ALERT_SEVERITIES)}


def alert_severity(
    violation_type: str, speed: float | None = None, speed_limit: float | None = None,
) -> str:
    """Return a deterministic operational severity for one confirmed violation."""
    if violation_type == "OVERSPEED":
        if speed is None or speed_limit is None:
            return "MEDIUM"
        excess = float(speed) - float(speed_limit)
        return "CRITICAL" if excess >= 30 else "HIGH" if excess >= 15 else "MEDIUM"
    if violation_type == "WRONG_DIRECTION":
        return "HIGH"
    if violation_type in {"WRONG_LANE", "NO_HELMET"}:
        return "MEDIUM"
    return "LOW"


def _alert_activity(
    connection: sqlite3.Connection,
    alert_id: int,
    action: str,
    version: int,
    created_at: str,
    from_status: str | None = None,
    to_status: str | None = None,
    actor: dict[str, Any] | None = None,
    note: str | None = None,
) -> None:
    connection.execute(
        """INSERT INTO alert_activity(
               alert_id, action, from_status, to_status, actor_user_id,
               actor_name, note, alert_version, created_at
           ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)""",
        (
            alert_id, action, from_status, to_status,
            actor["id"] if actor else None, actor["name"] if actor else "TrafficOps",
            note, version, created_at,
        ),
    )


def _create_alert_for_violation(
    connection: sqlite3.Connection, violation: sqlite3.Row,
) -> int:
    """Atomically attach a violation to one active alert, grouping short bursts."""
    violation_id = int(violation["id"])
    linked = connection.execute(
        "SELECT alert_id FROM alert_occurrences WHERE violation_id = ?", (violation_id,),
    ).fetchone()
    if linked:
        return int(linked["alert_id"])
    detected_at = violation["detected_at"]
    try:
        detected = datetime.fromisoformat(str(detected_at).replace("Z", "+00:00"))
    except ValueError:
        detected = datetime.now(timezone.utc)
    cutoff = (detected - timedelta(seconds=ALERT_COOLDOWN_SECONDS)).isoformat().replace("+00:00", "Z")
    existing = connection.execute(
        """SELECT alerts.* FROM alerts
           JOIN violations existing_latest ON existing_latest.id = alerts.latest_violation_id
           WHERE alerts.camera_id = ? AND alerts.tracking_id = ? AND alerts.violation_type = ?
             AND alerts.status NOT IN ('RESOLVED', 'FALSE_POSITIVE')
             AND alerts.last_occurrence_at >= ?
             AND (existing_latest.vehicle_id = ? OR (? IS NULL AND existing_latest.vehicle_id IS NULL))
           ORDER BY alerts.last_occurrence_at DESC, alerts.id DESC LIMIT 1""",
        (
            violation["camera_id"], violation["tracking_id"],
            violation["violation_type"], cutoff, violation["vehicle_id"], violation["vehicle_id"],
        ),
    ).fetchone()
    severity = alert_severity(
        violation["violation_type"], violation["speed"], violation["speed_limit"],
    )
    if existing:
        alert_id = int(existing["id"])
        severity = max(
            (existing["severity"], severity), key=lambda value: _SEVERITY_RANK[value],
        )
        version = int(existing["version"]) + 1
        connection.execute(
            """UPDATE alerts SET latest_violation_id = ?, severity = ?,
                   occurrence_count = occurrence_count + 1, last_occurrence_at = ?,
                   version = ?, updated_at = ? WHERE id = ?""",
            (violation_id, severity, detected_at, version, detected_at, alert_id),
        )
        connection.execute(
            "INSERT INTO alert_occurrences(alert_id, violation_id, occurred_at) VALUES (?, ?, ?)",
            (alert_id, violation_id, detected_at),
        )
        _alert_activity(
            connection, alert_id, "OCCURRENCE_ADDED", version, detected_at,
            from_status=existing["status"], to_status=existing["status"],
            note=f"Grouped violation #{violation_id}",
        )
        return alert_id
    cursor = connection.execute(
        """INSERT INTO alerts(
               primary_violation_id, latest_violation_id, tracking_id, camera_id,
               violation_type, severity, first_occurrence_at, last_occurrence_at,
               created_at, updated_at
           ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
        (
            violation_id, violation_id, violation["tracking_id"], violation["camera_id"],
            violation["violation_type"], severity, detected_at, detected_at,
            detected_at, detected_at,
        ),
    )
    alert_id = int(cursor.lastrowid)
    connection.execute(
        "INSERT INTO alert_occurrences(alert_id, violation_id, occurred_at) VALUES (?, ?, ?)",
        (alert_id, violation_id, detected_at),
    )
    _alert_activity(
        connection, alert_id, "CREATED", 1, detected_at,
        to_status="NEW", note=f"Created from violation #{violation_id}",
    )
    return alert_id


def _serialize_violation(row: sqlite3.Row) -> dict[str, Any]:
    columns = set(row.keys())
    event_speed = row["speed"] if "speed" in columns else None
    vehicle_speed = row["vehicle_speed"] if "vehicle_speed" in columns else None
    recorded_speed = event_speed if event_speed is not None else vehicle_speed
    speed_available = recorded_speed is not None
    camera_id = row["camera_id"]
    return {
        "id": int(row["id"]),
        "vehicleId": row["vehicle_id"],
        "trackingId": int(row["tracking_id"]),
        "type": row["violation_type"],
        "confidence": round(float(row["confidence"]), 3),
        "cameraId": camera_id,
        "cameraName": CAMERA_NAME if camera_id == CAMERA_ID else camera_id,
        "vehicleType": row["vehicle_type"],
        "laneId": row["lane_id"],
        "direction": row["direction"],
        "snapshotUrl": f"/api/violations/{row['id']}/evidence" if row["evidence_path"] else None,
        "detectedAt": row["detected_at"],
        "plate": (
            None if "vehicle_plate" not in columns or not row["vehicle_plate"]
            or row["vehicle_plate"] == "UNKNOWN" else row["vehicle_plate"]
        ),
        "plateConfidence": (
            round(float(row["vehicle_plate_confidence"]), 3)
            if "vehicle_plate_confidence" in columns
            and row["vehicle_plate_confidence"] is not None else None
        ),
        "plateStatus": (
            row["vehicle_plate_status"]
            if "vehicle_plate_status" in columns else None
        ),
        "speed": float(recorded_speed) if speed_available else None,
        "speedAvailable": speed_available,
        "speedLimit": (
            float(row["speed_limit"])
            if "speed_limit" in columns and row["speed_limit"] is not None else SPEED_LIMIT
        ),
        "vehicleStatus": (
            row["vehicle_status"] if "vehicle_status" in columns else None
        ),
        "vehicleSnapshotUrl": (
            f"/api/vehicles/{row['vehicle_id']}/snapshot"
            if "vehicle_snapshot_url" in columns and row["vehicle_snapshot_url"]
            and row["vehicle_id"] is not None else None
        ),
    }


def _violation_where(
    violation_type: str = "",
    vehicle_type: str = "",
    search: str = "",
    date_filter: str = "",
    camera_id: str = "",
    since: str | None = None,
) -> tuple[str, list[Any]]:
    clauses: list[str] = []
    values: list[Any] = []
    if violation_type:
        clauses.append("violations.violation_type = ?")
        values.append(violation_type)
    if vehicle_type:
        clauses.append("violations.vehicle_type = ?")
        values.append(vehicle_type)
    if search:
        needle = f"%{search.strip().lower()}%"
        clauses.append(
            "(LOWER(COALESCE(vehicles.plate, '')) LIKE ? "
            "OR CAST(violations.tracking_id AS TEXT) LIKE ? "
            "OR CAST(COALESCE(violations.vehicle_id, '') AS TEXT) LIKE ?)"
        )
        values.extend([needle, needle, needle])
    if camera_id:
        clauses.append("violations.camera_id = ?")
        values.append(camera_id)
    if since:
        clauses.append("violations.detected_at >= ?")
        values.append(since)
    elif date_filter:
        now = datetime.now(timezone.utc)
        start = now - (timedelta(days=7) if date_filter == "week" else timedelta(days=1))
        clauses.append("violations.detected_at >= ?")
        values.append(start.isoformat().replace("+00:00", "Z"))
    return (f"WHERE {' AND '.join(clauses)}" if clauses else "", values)


def query_violations(
    page: int = 1,
    page_size: int = 20,
    violation_type: str = "",
    vehicle_type: str = "",
    search: str = "",
    date_filter: str = "",
    camera_id: str = "",
    sort: str = "time_desc",
    since: str | None = None,
) -> dict[str, Any]:
    """Return a filtered violation page enriched with its matching vehicle record."""
    where, values = _violation_where(
        violation_type, vehicle_type, search, date_filter, camera_id, since,
    )
    orders = {
        "time_desc": "violations.detected_at DESC, violations.id DESC",
        "time_asc": "violations.detected_at ASC, violations.id ASC",
        "speed_desc": "COALESCE(violations.speed, vehicles.speed) IS NULL, COALESCE(violations.speed, vehicles.speed) DESC, violations.detected_at DESC",
        "confidence_desc": "violations.confidence DESC, violations.detected_at DESC",
    }
    order = orders.get(sort, orders["time_desc"])
    offset = (page - 1) * page_size
    join = "LEFT JOIN vehicles ON vehicles.id = violations.vehicle_id"
    select = """SELECT violations.*,
                       vehicles.plate AS vehicle_plate,
                       vehicles.plate_confidence AS vehicle_plate_confidence,
                       vehicles.plate_status AS vehicle_plate_status,
                       vehicles.speed AS vehicle_speed,
                       vehicles.status AS vehicle_status,
                       vehicles.snapshot_url AS vehicle_snapshot_url
                FROM violations"""
    with _connect() as connection:
        total = int(connection.execute(
            f"SELECT COUNT(*) FROM violations {join} {where}", values,
        ).fetchone()[0])
        rows = connection.execute(
            f"{select} {join} {where} ORDER BY {order} LIMIT ? OFFSET ?",
            [*values, page_size, offset],
        ).fetchall()
    return {
        "items": [_serialize_violation(row) for row in rows],
        "total": total,
        "page": page,
        "pageSize": page_size,
    }


def list_violations(
    limit: int = 50,
    violation_type: str = "",
    since: str | None = None,
) -> list[dict[str, Any]]:
    return query_violations(
        page=1, page_size=limit, violation_type=violation_type, since=since,
    )["items"]


def violation_summary(since: str | None = None) -> dict[str, Any]:
    where = "WHERE detected_at >= ?" if since else ""
    values = (since,) if since else ()
    with _connect() as connection:
        rows = connection.execute(
            f"SELECT violation_type, COUNT(*) count FROM violations {where} GROUP BY violation_type",
            values,
        ).fetchall()
        latest = connection.execute(
            f"SELECT * FROM violations {where} ORDER BY detected_at DESC, id DESC LIMIT 1",
            values,
        ).fetchone()
    counts = {row["violation_type"]: int(row["count"]) for row in rows}
    return {
        "total": sum(counts.values()),
        "counts": counts,
        "latest": _serialize_violation(latest) if latest else None,
    }


def get_violation_evidence_path(violation_id: int) -> str | None:
    with _connect() as connection:
        row = connection.execute(
            "SELECT evidence_path FROM violations WHERE id = ?", (violation_id,)
        ).fetchone()
    return row["evidence_path"] if row else None


_ALERT_SELECT = """SELECT alerts.*,
       latest.vehicle_id AS latest_vehicle_id,
       latest.confidence AS latest_confidence,
       latest.vehicle_type AS latest_vehicle_type,
       latest.lane_id AS latest_lane_id,
       latest.direction AS latest_direction,
       latest.evidence_path AS latest_evidence_path,
       latest.speed AS latest_speed,
       latest.speed_limit AS latest_speed_limit,
       latest.detected_at AS latest_detected_at,
       vehicles.plate AS vehicle_plate,
       vehicles.plate_confidence AS vehicle_plate_confidence,
       assigned.id AS assigned_id,
       assigned.name AS assigned_name,
       assigned.email AS assigned_email
FROM alerts
JOIN violations latest ON latest.id = alerts.latest_violation_id
LEFT JOIN vehicles ON vehicles.id = latest.vehicle_id
LEFT JOIN users assigned ON assigned.id = alerts.assigned_user_id"""


def _serialize_alert(row: sqlite3.Row) -> dict[str, Any]:
    speed = row["latest_speed"]
    speed_limit = row["latest_speed_limit"]
    return {
        "id": int(row["id"]),
        "primaryViolationId": int(row["primary_violation_id"]),
        "violationId": int(row["latest_violation_id"]),
        "trackingId": int(row["tracking_id"]),
        "cameraId": row["camera_id"],
        "cameraName": CAMERA_NAME if row["camera_id"] == CAMERA_ID else row["camera_id"],
        "type": row["violation_type"],
        "severity": row["severity"],
        "status": row["status"],
        "assignedTo": ({
            "id": int(row["assigned_id"]),
            "name": row["assigned_name"],
            "email": row["assigned_email"],
        } if row["assigned_id"] is not None else None),
        "occurrenceCount": int(row["occurrence_count"]),
        "firstOccurrenceAt": row["first_occurrence_at"],
        "lastOccurrenceAt": row["last_occurrence_at"],
        "acknowledgedAt": row["acknowledged_at"],
        "resolvedAt": row["resolved_at"],
        "resolutionNote": row["resolution_note"],
        "falsePositiveReason": row["false_positive_reason"],
        "version": int(row["version"]),
        "createdAt": row["created_at"],
        "updatedAt": row["updated_at"],
        "vehicleId": row["latest_vehicle_id"],
        "vehicleType": row["latest_vehicle_type"],
        "plate": (
            None if not row["vehicle_plate"] or row["vehicle_plate"] == "UNKNOWN"
            else row["vehicle_plate"]
        ),
        "plateConfidence": (
            round(float(row["vehicle_plate_confidence"]), 3)
            if row["vehicle_plate_confidence"] is not None else None
        ),
        "confidence": round(float(row["latest_confidence"]), 3),
        "laneId": row["latest_lane_id"],
        "direction": row["latest_direction"],
        "speed": float(speed) if speed is not None else None,
        "speedAvailable": speed is not None,
        "speedLimit": float(speed_limit) if speed_limit is not None else SPEED_LIMIT,
        "snapshotUrl": (
            f"/api/violations/{row['latest_violation_id']}/evidence"
            if row["latest_evidence_path"] else None
        ),
        "detectedAt": row["latest_detected_at"],
    }


def _alert_where(
    status_filter: str = "",
    severity: str = "",
    violation_type: str = "",
    vehicle_type: str = "",
    camera_id: str = "",
    assigned_to: str = "",
    search: str = "",
    date_filter: str = "",
    since: str | None = None,
) -> tuple[str, list[Any]]:
    clauses: list[str] = []
    values: list[Any] = []
    statuses = [item.strip().upper() for item in status_filter.split(",") if item.strip()]
    statuses = [item for item in statuses if item in ALERT_STATUSES]
    if statuses:
        clauses.append(f"alerts.status IN ({','.join('?' for _ in statuses)})")
        values.extend(statuses)
    if severity:
        clauses.append("alerts.severity = ?")
        values.append(severity)
    if violation_type:
        clauses.append("alerts.violation_type = ?")
        values.append(violation_type)
    if vehicle_type:
        clauses.append("latest.vehicle_type = ?")
        values.append(vehicle_type)
    if camera_id:
        clauses.append("alerts.camera_id = ?")
        values.append(camera_id)
    if assigned_to == "unassigned":
        clauses.append("alerts.assigned_user_id IS NULL")
    elif assigned_to:
        clauses.append("alerts.assigned_user_id = ?")
        values.append(int(assigned_to))
    if search:
        needle = f"%{search.strip().lower()}%"
        clauses.append(
            "(LOWER(COALESCE(vehicles.plate, '')) LIKE ? "
            "OR CAST(alerts.id AS TEXT) LIKE ? "
            "OR CAST(alerts.tracking_id AS TEXT) LIKE ? "
            "OR CAST(COALESCE(latest.vehicle_id, '') AS TEXT) LIKE ?)"
        )
        values.extend([needle, needle, needle, needle])
    if since:
        clauses.append("alerts.last_occurrence_at >= ?")
        values.append(since)
    elif date_filter:
        now = datetime.now(timezone.utc)
        if date_filter == "today":
            start = now.replace(hour=0, minute=0, second=0, microsecond=0)
        else:
            start = now - timedelta(days=7)
        clauses.append("alerts.last_occurrence_at >= ?")
        values.append(start.isoformat().replace("+00:00", "Z"))
    return (f"WHERE {' AND '.join(clauses)}" if clauses else "", values)


def query_alerts(
    page: int = 1,
    page_size: int = 20,
    status_filter: str = "",
    severity: str = "",
    violation_type: str = "",
    vehicle_type: str = "",
    camera_id: str = "",
    assigned_to: str = "",
    search: str = "",
    date_filter: str = "",
    sort: str = "newest",
    since: str | None = None,
) -> dict[str, Any]:
    """Return an operational alert queue without per-row database queries."""
    where, values = _alert_where(
        status_filter, severity, violation_type, vehicle_type, camera_id,
        assigned_to, search, date_filter, since,
    )
    orders = {
        "newest": "alerts.last_occurrence_at DESC, alerts.id DESC",
        "oldest": "alerts.last_occurrence_at ASC, alerts.id ASC",
        "severity": "CASE alerts.severity WHEN 'CRITICAL' THEN 4 WHEN 'HIGH' THEN 3 WHEN 'MEDIUM' THEN 2 ELSE 1 END DESC, alerts.last_occurrence_at DESC",
    }
    order = orders.get(sort, orders["newest"])
    offset = (page - 1) * page_size
    with _connect() as connection:
        total = int(connection.execute(
            f"SELECT COUNT(*) FROM alerts JOIN violations latest ON latest.id = alerts.latest_violation_id LEFT JOIN vehicles ON vehicles.id = latest.vehicle_id {where}",
            values,
        ).fetchone()[0])
        rows = connection.execute(
            f"{_ALERT_SELECT} {where} ORDER BY {order} LIMIT ? OFFSET ?",
            [*values, page_size, offset],
        ).fetchall()
    return {
        "items": [_serialize_alert(row) for row in rows],
        "total": total,
        "page": page,
        "pageSize": page_size,
    }


def alert_summary(since: str | None = None) -> dict[str, Any]:
    where, values = _alert_where(since=since)
    today = datetime.now(timezone.utc).replace(
        hour=0, minute=0, second=0, microsecond=0,
    ).isoformat().replace("+00:00", "Z")
    with _connect() as connection:
        row = connection.execute(
            f"""SELECT COUNT(*) AS total,
                       SUM(CASE WHEN alerts.status = 'NEW' THEN 1 ELSE 0 END) AS new_count,
                       SUM(CASE WHEN alerts.status NOT IN ('RESOLVED', 'FALSE_POSITIVE') THEN 1 ELSE 0 END) AS unresolved,
                       SUM(CASE WHEN alerts.severity = 'CRITICAL' AND alerts.status NOT IN ('RESOLVED', 'FALSE_POSITIVE') THEN 1 ELSE 0 END) AS critical,
                       SUM(CASE WHEN alerts.status = 'RESOLVED' AND alerts.resolved_at >= ? THEN 1 ELSE 0 END) AS resolved_today,
                       AVG(CASE WHEN alerts.acknowledged_at IS NOT NULL
                           THEN (julianday(alerts.acknowledged_at) - julianday(alerts.created_at)) * 86400 END) AS average_response
                FROM alerts
                JOIN violations latest ON latest.id = alerts.latest_violation_id
                LEFT JOIN vehicles ON vehicles.id = latest.vehicle_id
                {where}""",
            [today, *values],
        ).fetchone()
        severity_rows = connection.execute(
            f"""SELECT alerts.severity, COUNT(*) AS count FROM alerts
                JOIN violations latest ON latest.id = alerts.latest_violation_id
                LEFT JOIN vehicles ON vehicles.id = latest.vehicle_id
                {where} GROUP BY alerts.severity""",
            values,
        ).fetchall()
    return {
        "total": int(row["total"] or 0),
        "new": int(row["new_count"] or 0),
        "unresolved": int(row["unresolved"] or 0),
        "critical": int(row["critical"] or 0),
        "resolvedToday": int(row["resolved_today"] or 0),
        "averageResponseSeconds": (
            round(float(row["average_response"]), 1)
            if row["average_response"] is not None else None
        ),
        "bySeverity": {item["severity"]: int(item["count"]) for item in severity_rows},
    }


def _get_alert_row(connection: sqlite3.Connection, alert_id: int) -> sqlite3.Row | None:
    return connection.execute(
        f"{_ALERT_SELECT} WHERE alerts.id = ?", (alert_id,),
    ).fetchone()


def get_alert(alert_id: int) -> dict[str, Any] | None:
    with _connect() as connection:
        row = _get_alert_row(connection, alert_id)
        if row is None:
            return None
        activity = connection.execute(
            """SELECT id, action, from_status, to_status, actor_user_id,
                      actor_name, note, alert_version, created_at
               FROM alert_activity WHERE alert_id = ? ORDER BY created_at DESC, id DESC""",
            (alert_id,),
        ).fetchall()
        occurrences = connection.execute(
            """SELECT violation_id, occurred_at FROM alert_occurrences
               WHERE alert_id = ? ORDER BY occurred_at DESC, id DESC""",
            (alert_id,),
        ).fetchall()
    result = _serialize_alert(row)
    result["activity"] = [{
        "id": int(item["id"]),
        "action": item["action"],
        "fromStatus": item["from_status"],
        "toStatus": item["to_status"],
        "actorUserId": item["actor_user_id"],
        "actorName": item["actor_name"],
        "note": item["note"],
        "alertVersion": int(item["alert_version"]),
        "createdAt": item["created_at"],
    } for item in activity]
    result["occurrences"] = [{
        "violationId": int(item["violation_id"]), "occurredAt": item["occurred_at"],
    } for item in occurrences]
    return result


def get_alert_for_violation(violation_id: int) -> dict[str, Any] | None:
    with _connect() as connection:
        linked = connection.execute(
            "SELECT alert_id FROM alert_occurrences WHERE violation_id = ?", (violation_id,),
        ).fetchone()
    return get_alert(int(linked["alert_id"])) if linked else None


def list_operators() -> list[dict[str, Any]]:
    with _connect() as connection:
        rows = connection.execute(
            "SELECT id, name, email, created_at FROM users ORDER BY name, id",
        ).fetchall()
    return [_serialize_user(row) for row in rows]


def update_alert_status(
    alert_id: int,
    target_status: str,
    actor: dict[str, Any],
    note: str | None = None,
    expected_version: int | None = None,
) -> dict[str, Any]:
    transitions = {
        "ACKNOWLEDGED": {"NEW"},
        "INVESTIGATING": {"NEW", "ACKNOWLEDGED"},
        "RESOLVED": {"NEW", "ACKNOWLEDGED", "INVESTIGATING"},
        "FALSE_POSITIVE": {"NEW", "ACKNOWLEDGED", "INVESTIGATING"},
    }
    if target_status not in transitions:
        raise ValueError("Unsupported alert status")
    cleaned_note = " ".join((note or "").split()) or None
    if target_status == "RESOLVED" and not cleaned_note:
        raise ValueError("A resolution note is required")
    if target_status == "FALSE_POSITIVE" and not cleaned_note:
        raise ValueError("A false-positive reason is required")
    now = datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")
    with _connect() as connection:
        row = connection.execute("SELECT * FROM alerts WHERE id = ?", (alert_id,)).fetchone()
        if row is None:
            raise LookupError("Alert not found")
        if expected_version is not None and int(row["version"]) != expected_version:
            raise RuntimeError("Alert was updated by another operator. Refresh and try again.")
        current = row["status"]
        if current == target_status:
            pass
        elif current not in transitions[target_status]:
            raise ValueError(f"Cannot move an alert from {current} to {target_status}")
        else:
            version = int(row["version"]) + 1
            acknowledged_at = row["acknowledged_at"]
            acknowledged_by = row["acknowledged_by"]
            if target_status in {"ACKNOWLEDGED", "INVESTIGATING", "RESOLVED"} and not acknowledged_at:
                acknowledged_at, acknowledged_by = now, actor["id"]
            connection.execute(
                """UPDATE alerts SET status = ?, acknowledged_at = ?, acknowledged_by = ?,
                       resolved_at = CASE WHEN ? IN ('RESOLVED', 'FALSE_POSITIVE') THEN ? ELSE resolved_at END,
                       resolved_by = CASE WHEN ? IN ('RESOLVED', 'FALSE_POSITIVE') THEN ? ELSE resolved_by END,
                       resolution_note = CASE WHEN ? = 'RESOLVED' THEN ? ELSE resolution_note END,
                       false_positive_reason = CASE WHEN ? = 'FALSE_POSITIVE' THEN ? ELSE false_positive_reason END,
                       version = ?, updated_at = ? WHERE id = ?""",
                (
                    target_status, acknowledged_at, acknowledged_by,
                    target_status, now, target_status, actor["id"],
                    target_status, cleaned_note, target_status, cleaned_note,
                    version, now, alert_id,
                ),
            )
            _alert_activity(
                connection, alert_id, target_status, version, now,
                from_status=current, to_status=target_status, actor=actor, note=cleaned_note,
            )
    result = get_alert(alert_id)
    if result is None:
        raise LookupError("Alert not found")
    return result


def assign_alert(
    alert_id: int,
    assigned_user_id: int | None,
    actor: dict[str, Any],
    expected_version: int | None = None,
) -> dict[str, Any]:
    now = datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")
    with _connect() as connection:
        row = connection.execute("SELECT * FROM alerts WHERE id = ?", (alert_id,)).fetchone()
        if row is None:
            raise LookupError("Alert not found")
        if expected_version is not None and int(row["version"]) != expected_version:
            raise RuntimeError("Alert was updated by another operator. Refresh and try again.")
        assignee = None
        if assigned_user_id is not None:
            assignee = connection.execute(
                "SELECT id, name, email, created_at FROM users WHERE id = ?", (assigned_user_id,),
            ).fetchone()
            if assignee is None:
                raise ValueError("Assigned operator does not exist")
        if row["assigned_user_id"] != assigned_user_id:
            version = int(row["version"]) + 1
            connection.execute(
                "UPDATE alerts SET assigned_user_id = ?, version = ?, updated_at = ? WHERE id = ?",
                (assigned_user_id, version, now, alert_id),
            )
            assignment_note = f"Assigned to {assignee['name']}" if assignee else "Assignment cleared"
            _alert_activity(
                connection, alert_id, "ASSIGNED" if assignee else "UNASSIGNED",
                version, now, from_status=row["status"], to_status=row["status"],
                actor=actor, note=assignment_note,
            )
    result = get_alert(alert_id)
    if result is None:
        raise LookupError("Alert not found")
    return result


def save_camera_lane_rules(camera_id: str, rules: list[dict[str, Any]]) -> None:
    now = datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")
    payload = json.dumps(rules, separators=(",", ":"))
    with _connect() as connection:
        connection.execute(
            """INSERT INTO camera_lane_settings(camera_id, rules_json, updated_at)
               VALUES (?, ?, ?)
               ON CONFLICT(camera_id) DO UPDATE SET
                   rules_json = excluded.rules_json, updated_at = excluded.updated_at""",
            (camera_id, payload, now),
        )


def get_camera_lane_rules(camera_id: str) -> list[dict[str, Any]]:
    with _connect() as connection:
        row = connection.execute(
            "SELECT rules_json FROM camera_lane_settings WHERE camera_id = ?", (camera_id,)
        ).fetchone()
    if row is None:
        return []
    try:
        payload = json.loads(row["rules_json"])
    except (TypeError, json.JSONDecodeError):
        return []
    return payload if isinstance(payload, list) else []


def save_camera_calibration(camera_id: str, calibration: dict[str, Any]) -> None:
    now = datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")
    payload = json.dumps(calibration, separators=(",", ":"))
    with _connect() as connection:
        connection.execute(
            """INSERT INTO camera_calibration_settings(camera_id, calibration_json, updated_at)
               VALUES (?, ?, ?)
               ON CONFLICT(camera_id) DO UPDATE SET
                   calibration_json = excluded.calibration_json,
                   updated_at = excluded.updated_at""",
            (camera_id, payload, now),
        )


def get_camera_calibration(camera_id: str) -> dict[str, Any] | None:
    with _connect() as connection:
        row = connection.execute(
            "SELECT calibration_json FROM camera_calibration_settings WHERE camera_id = ?",
            (camera_id,),
        ).fetchone()
    if row is None:
        return None
    try:
        payload = json.loads(row["calibration_json"])
    except (TypeError, json.JSONDecodeError):
        return None
    return payload if isinstance(payload, dict) else None


def _serialize(row: sqlite3.Row) -> dict[str, Any]:
    detected = str(row["time"]).replace(" ", "T")
    if not detected.endswith("Z") and "+" not in detected:
        detected += "Z"
    speed_available = row["speed"] is not None
    return {
        "id": row["id"],
        "trackingId": row["tracking_id"] if row["tracking_id"] is not None else row["id"],
        "vehicleType": row["vehicle_type"] or "unknown",
        "plate": None if not row["plate"] or row["plate"] == "UNKNOWN" else row["plate"],
        "plateConfidence": (
            round(float(row["plate_confidence"]), 3)
            if row["plate_confidence"] is not None else None
        ),
        "plateStatus": row["plate_status"] or "NOT_DETECTED",
        "plateSnapshotUrl": (
            f"/api/vehicles/{row['id']}/plate-image" if row["plate_image_path"] else None
        ),
        "speed": float(row["speed"]) if speed_available else 0.0,
        "speedAvailable": speed_available,
        "speedLimit": SPEED_LIMIT,
        "status": row["status"],
        "detectedAt": detected,
        "cameraId": row["camera_id"] or CAMERA_ID,
        "snapshotUrl": (
            f"/api/vehicles/{row['id']}/snapshot" if row["snapshot_url"] else None
        ),
    }


def list_vehicles(
    page: int = 1,
    page_size: int = 20,
    status: str = "",
    vehicle_type: str = "",
    search: str = "",
    sort: str = "time_desc",
    speed_filter: str = "",
    date_filter: str = "",
    violation_filter: str = "",
) -> dict[str, Any]:
    clauses: list[str] = []
    values: list[Any] = []
    if status:
        clauses.append("status = ?")
        values.append(status)
    if vehicle_type:
        clauses.append("vehicle_type = ?")
        values.append(vehicle_type)
    if search:
        clauses.append("(LOWER(COALESCE(plate, '')) LIKE ? OR CAST(COALESCE(tracking_id, id) AS TEXT) LIKE ?)")
        needle = f"%{search.lower()}%"
        values.extend([needle, needle])
    if speed_filter == "over_limit":
        clauses.append("speed > ?")
        values.append(SPEED_LIMIT)
    elif speed_filter == "under_limit":
        clauses.append("speed <= ?")
        values.append(SPEED_LIMIT)
    if violation_filter:
        clauses.append(
            "EXISTS (SELECT 1 FROM violations WHERE violations.vehicle_id = vehicles.id "
            "AND violations.violation_type = ?)"
        )
        values.append(violation_filter)
    if date_filter:
        now = datetime.now(timezone.utc)
        start = now - (timedelta(days=7) if date_filter == "week" else timedelta(days=1))
        clauses.append("time >= ?")
        values.append(start.strftime("%Y-%m-%d %H:%M:%S"))
    where = f"WHERE {' AND '.join(clauses)}" if clauses else ""
    orders = {
        "time_desc": "time DESC, id DESC", "time_asc": "time ASC, id ASC",
        "speed_desc": "speed DESC", "speed_asc": "speed ASC",
    }
    order = orders.get(sort, orders["time_desc"])
    offset = (page - 1) * page_size
    with _connect() as connection:
        total = connection.execute(f"SELECT COUNT(*) FROM vehicles {where}", values).fetchone()[0]
        rows = connection.execute(
            f"SELECT * FROM vehicles {where} ORDER BY {order} LIMIT ? OFFSET ?",
            [*values, page_size, offset],
        ).fetchall()
    items = [_serialize(row) for row in rows]
    _attach_vehicle_violations(items)
    return {"items": items, "total": total, "page": page, "pageSize": page_size}


def get_vehicle(vehicle_id: int) -> dict[str, Any] | None:
    with _connect() as connection:
        row = connection.execute("SELECT * FROM vehicles WHERE id = ?", (vehicle_id,)).fetchone()
    if row is None:
        return None
    item = _serialize(row)
    _attach_vehicle_violations([item])
    return item


def list_plate_reads(limit: int = 20) -> list[dict[str, Any]]:
    with _connect() as connection:
        rows = connection.execute(
            """SELECT * FROM vehicles
               WHERE plate IS NOT NULL AND plate != '' AND plate != 'UNKNOWN'
                 AND plate_status = 'CONFIRMED'
               ORDER BY time DESC, id DESC LIMIT ?""",
            (limit,),
        ).fetchall()
    items = [_serialize(row) for row in rows]
    _attach_vehicle_violations(items)
    return items


def plate_reads_total() -> int:
    with _connect() as connection:
        row = connection.execute(
            """SELECT COUNT(*) AS total FROM vehicles
               WHERE plate IS NOT NULL AND plate != '' AND plate != 'UNKNOWN'
                 AND plate_status = 'CONFIRMED'"""
        ).fetchone()
    return int(row["total"])


def get_vehicle_plate_image_path(vehicle_id: int) -> str | None:
    with _connect() as connection:
        row = connection.execute(
            "SELECT plate_image_path FROM vehicles WHERE id = ?", (vehicle_id,)
        ).fetchone()
    return row["plate_image_path"] if row else None


def _attach_vehicle_violations(items: list[dict[str, Any]]) -> None:
    vehicle_ids = [int(item["id"]) for item in items]
    if not vehicle_ids:
        return
    placeholders = ",".join("?" for _ in vehicle_ids)
    with _connect() as connection:
        rows = connection.execute(
            f"""SELECT vehicle_id, violation_type FROM violations
                WHERE vehicle_id IN ({placeholders}) ORDER BY detected_at""",
            vehicle_ids,
        ).fetchall()
    by_vehicle: dict[int, list[str]] = {vehicle_id: [] for vehicle_id in vehicle_ids}
    for row in rows:
        values = by_vehicle[int(row["vehicle_id"])]
        if row["violation_type"] not in values:
            values.append(row["violation_type"])
    for item in items:
        item["violations"] = by_vehicle[int(item["id"])]


def dashboard_summary(
    current_fps: float = 0,
    since: str | None = None,
    speed_limit: float | None = None,
) -> dict[str, Any]:
    where = "WHERE time >= datetime(?)" if since else ""
    parameters = (since,) if since else ()
    with _connect() as connection:
        row = connection.execute(f"""
            SELECT COUNT(*) total,
                   SUM(CASE WHEN status = 'OVERSPEED' THEN 1 ELSE 0 END) overspeed,
                   COALESCE(AVG(speed), 0) average_speed,
                   COALESCE(MAX(speed), 0) max_speed
            FROM vehicles
            {where}
        """, parameters).fetchone()
    return {
        "totalVehicles": row["total"], "overspeedVehicles": row["overspeed"] or 0,
        "averageSpeed": round(row["average_speed"], 2), "maxSpeed": round(row["max_speed"], 2),
        "currentFps": round(current_fps, 1),
        "speedLimit": float(speed_limit) if speed_limit is not None else SPEED_LIMIT,
    }


def analytics(range_name: str) -> dict[str, Any]:
    now = datetime.now(timezone.utc)
    start = now - (timedelta(hours=1) if range_name == "hour" else timedelta(days=7) if range_name == "week" else timedelta(days=1))
    with _connect() as connection:
        rows = connection.execute("SELECT * FROM vehicles WHERE time >= ? ORDER BY time", (start.strftime("%Y-%m-%d %H:%M:%S"),)).fetchall()
    serialized = [_serialize(row) for row in rows]
    bucket_format = "%a" if range_name == "week" else "%H:00"
    buckets: dict[str, dict[str, int]] = {}
    for item in serialized:
        label = datetime.fromisoformat(item["detectedAt"].replace("Z", "+00:00")).strftime(bucket_format)
        bucket = buckets.setdefault(label, {"label": label, "detections": 0, "overspeed": 0})
        bucket["detections"] += 1
        bucket["overspeed"] += item["status"] == "OVERSPEED"
    by_type: dict[str, int] = {}
    for item in serialized:
        by_type[item["vehicleType"]] = by_type.get(item["vehicleType"], 0) + 1
    speeds = [item["speed"] for item in serialized if item["speedAvailable"]]
    return {
        "timeline": list(buckets.values()),
        "byType": [{"name": key, "value": value} for key, value in by_type.items()],
        "byStatus": [
            {"name": "NORMAL", "value": sum(item["status"] == "NORMAL" for item in serialized)},
            {"name": "OVERSPEED", "value": sum(item["status"] == "OVERSPEED" for item in serialized)},
        ],
        "averageSpeed": round(sum(speeds) / len(speeds), 2) if speeds else 0,
        "maxSpeed": max(speeds, default=0),
    }


def _row_to_dict(row: sqlite3.Row) -> dict[str, Any]:
    return {key: row[key] for key in row.keys()}


def list_junctions() -> list[dict[str, Any]]:
    with _connect() as connection:
        rows = connection.execute(
            "SELECT * FROM junctions ORDER BY sort_order, name"
        ).fetchall()
    return [_serialize_junction(row) for row in rows]


def get_junction(junction_id: str) -> dict[str, Any] | None:
    with _connect() as connection:
        row = connection.execute(
            "SELECT * FROM junctions WHERE id = ?", (junction_id,)
        ).fetchone()
    return _serialize_junction(row) if row else None


def create_junction(
    junction_id: str,
    name: str,
    location: str = "",
    description: str = "",
    speed_limit: float | None = None,
    enabled: bool = True,
) -> dict[str, Any] | None:
    with _connect() as connection:
        try:
            connection.execute(
                "INSERT INTO junctions(id, name, location, description, speed_limit, enabled) "
                "VALUES (?, ?, ?, ?, ?, ?)",
                (junction_id, name, location, description, speed_limit, int(enabled)),
            )
        except sqlite3.IntegrityError:
            return None
        row = connection.execute(
            "SELECT * FROM junctions WHERE id = ?", (junction_id,)
        ).fetchone()
    return _serialize_junction(row) if row else None


def update_junction(
    junction_id: str,
    name: str | None = None,
    location: str | None = None,
    description: str | None = None,
    speed_limit: float | None = None,
    enabled: bool | None = None,
) -> dict[str, Any] | None:
    updates: list[str] = []
    values: list[Any] = []
    if name is not None:
        updates.append("name = ?")
        values.append(name)
    if location is not None:
        updates.append("location = ?")
        values.append(location)
    if description is not None:
        updates.append("description = ?")
        values.append(description)
    if speed_limit is not None:
        updates.append("speed_limit = ?")
        values.append(speed_limit)
    if enabled is not None:
        updates.append("enabled = ?")
        values.append(int(enabled))
    if not updates:
        return get_junction(junction_id)
    values.append(junction_id)
    with _connect() as connection:
        connection.execute(
            f"UPDATE junctions SET {', '.join(updates)} WHERE id = ?", values,
        )
        row = connection.execute(
            "SELECT * FROM junctions WHERE id = ?", (junction_id,)
        ).fetchone()
    return _serialize_junction(row) if row else None


def delete_junction(junction_id: str) -> bool:
    with _connect() as connection:
        cursor = connection.execute("DELETE FROM junctions WHERE id = ?", (junction_id,))
        return cursor.rowcount > 0


def list_cameras(junction_id: str | None = None) -> list[dict[str, Any]]:
    where = "WHERE junction_id = ?" if junction_id else ""
    values = (junction_id,) if junction_id else ()
    with _connect() as connection:
        rows = connection.execute(
            f"SELECT * FROM cameras {where} ORDER BY junction_id, sort_order, name",
            values,
        ).fetchall()
    return [_serialize_camera(row) for row in rows]


def get_camera(camera_id: str) -> dict[str, Any] | None:
    with _connect() as connection:
        row = connection.execute(
            "SELECT * FROM cameras WHERE id = ?", (camera_id,)
        ).fetchone()
    return _serialize_camera(row) if row else None


def camera_exists(camera_id: str) -> bool:
    with _connect() as connection:
        row = connection.execute(
            "SELECT 1 FROM cameras WHERE id = ?", (camera_id,)
        ).fetchone()
    return row is not None


def create_camera(
    camera_id: str,
    junction_id: str,
    name: str,
    source_type: str = "live",
    video_url: str = "",
    speed_limit: float | None = None,
    enabled: bool = True,
) -> dict[str, Any] | None:
    if source_type not in {"live", "demo"}:
        raise ValueError("source_type must be 'live' or 'demo'")
    with _connect() as connection:
        junction = connection.execute(
            "SELECT 1 FROM junctions WHERE id = ?", (junction_id,)
        ).fetchone()
        if junction is None:
            raise LookupError("Junction not found")
        try:
            connection.execute(
                "INSERT INTO cameras(id, junction_id, name, source_type, video_url, speed_limit, enabled) "
                "VALUES (?, ?, ?, ?, ?, ?, ?)",
                (camera_id, junction_id, name, source_type, video_url, speed_limit, int(enabled)),
            )
        except sqlite3.IntegrityError:
            return None
        row = connection.execute(
            "SELECT * FROM cameras WHERE id = ?", (camera_id,)
        ).fetchone()
    return _serialize_camera(row) if row else None


def update_camera(
    camera_id: str,
    junction_id: str | None = None,
    name: str | None = None,
    source_type: str | None = None,
    video_url: str | None = None,
    speed_limit: float | None = None,
    enabled: bool | None = None,
) -> dict[str, Any] | None:
    if source_type is not None and source_type not in {"live", "demo"}:
        raise ValueError("source_type must be 'live' or 'demo'")
    updates: list[str] = []
    values: list[Any] = []
    if junction_id is not None:
        updates.append("junction_id = ?")
        values.append(junction_id)
    if name is not None:
        updates.append("name = ?")
        values.append(name)
    if source_type is not None:
        updates.append("source_type = ?")
        values.append(source_type)
    if video_url is not None:
        updates.append("video_url = ?")
        values.append(video_url)
    if speed_limit is not None:
        updates.append("speed_limit = ?")
        values.append(speed_limit)
    if enabled is not None:
        updates.append("enabled = ?")
        values.append(int(enabled))
    if not updates:
        return get_camera(camera_id)
    values.append(camera_id)
    with _connect() as connection:
        connection.execute(
            f"UPDATE cameras SET {', '.join(updates)} WHERE id = ?", values,
        )
        row = connection.execute(
            "SELECT * FROM cameras WHERE id = ?", (camera_id,)
        ).fetchone()
    return _serialize_camera(row) if row else None


def delete_camera(camera_id: str) -> bool:
    with _connect() as connection:
        cursor = connection.execute("DELETE FROM cameras WHERE id = ?", (camera_id,))
        return cursor.rowcount > 0


DEMO_SCENARIOS = (
    "normal",
    "helmet",
    "overspeed",
    "wrong_lane",
    "anpr",
    "heavy",
    "night",
)


def list_demo_videos(
    junction_id: str | None = None,
    camera_id: str | None = None,
    scenario: str | None = None,
    enabled_only: bool = True,
) -> list[dict[str, Any]]:
    clauses: list[str] = []
    values: list[Any] = []
    if junction_id:
        clauses.append("demo_videos.junction_id = ?")
        values.append(junction_id)
    if camera_id:
        clauses.append("demo_videos.camera_id = ?")
        values.append(camera_id)
    if scenario and scenario != "all":
        clauses.append("demo_videos.scenario = ?")
        values.append(scenario)
    if enabled_only:
        clauses.append("demo_videos.enabled = 1")
    where = f"WHERE {' AND '.join(clauses)}" if clauses else ""
    with _connect() as connection:
        rows = connection.execute(
            f"SELECT * FROM demo_videos {where} ORDER BY demo_videos.sort_order, demo_videos.title",
            values,
        ).fetchall()
    return [_serialize_demo_video(row) for row in rows]


def get_demo_video(video_id: str) -> dict[str, Any] | None:
    with _connect() as connection:
        row = connection.execute(
            "SELECT * FROM demo_videos WHERE id = ?", (video_id,)
        ).fetchone()
    return _serialize_demo_video(row) if row else None


def create_demo_video(
    video_id: str,
    junction_id: str,
    title: str,
    filename: str,
    description: str = "",
    scenario: str = "normal",
    camera_id: str | None = None,
    duration_seconds: float | None = None,
    enabled: bool = True,
) -> dict[str, Any] | None:
    if scenario not in DEMO_SCENARIOS:
        raise ValueError(f"Unsupported demo scenario: {scenario}")
    with _connect() as connection:
        junction = connection.execute(
            "SELECT 1 FROM junctions WHERE id = ?", (junction_id,)
        ).fetchone()
        if junction is None:
            raise LookupError("Junction not found")
        if camera_id is not None:
            camera = connection.execute(
                "SELECT 1 FROM cameras WHERE id = ?", (camera_id,)
            ).fetchone()
            if camera is None:
                raise LookupError("Camera not found")
        try:
            connection.execute(
                "INSERT INTO demo_videos(id, junction_id, camera_id, title, description, filename, scenario, duration_seconds, enabled) "
                "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)",
                (video_id, junction_id, camera_id, title, description, filename, scenario, duration_seconds, int(enabled)),
            )
        except sqlite3.IntegrityError:
            return None
        row = connection.execute(
            "SELECT * FROM demo_videos WHERE id = ?", (video_id,)
        ).fetchone()
    return _serialize_demo_video(row) if row else None


def update_demo_video(
    video_id: str,
    junction_id: str | None = None,
    camera_id: str | None = None,
    title: str | None = None,
    description: str | None = None,
    filename: str | None = None,
    scenario: str | None = None,
    duration_seconds: float | None = None,
    enabled: bool | None = None,
) -> dict[str, Any] | None:
    if scenario is not None and scenario not in DEMO_SCENARIOS:
        raise ValueError(f"Unsupported demo scenario: {scenario}")
    updates: list[str] = []
    values: list[Any] = []
    if junction_id is not None:
        updates.append("junction_id = ?")
        values.append(junction_id)
    if camera_id is not None:
        updates.append("camera_id = ?")
        values.append(camera_id)
    if title is not None:
        updates.append("title = ?")
        values.append(title)
    if description is not None:
        updates.append("description = ?")
        values.append(description)
    if filename is not None:
        updates.append("filename = ?")
        values.append(filename)
    if scenario is not None:
        updates.append("scenario = ?")
        values.append(scenario)
    if duration_seconds is not None:
        updates.append("duration_seconds = ?")
        values.append(duration_seconds)
    if enabled is not None:
        updates.append("enabled = ?")
        values.append(int(enabled))
    if not updates:
        return get_demo_video(video_id)
    values.append(video_id)
    with _connect() as connection:
        connection.execute(
            f"UPDATE demo_videos SET {', '.join(updates)} WHERE id = ?", values,
        )
        row = connection.execute(
            "SELECT * FROM demo_videos WHERE id = ?", (video_id,)
        ).fetchone()
    return _serialize_demo_video(row) if row else None


def delete_demo_video(video_id: str) -> bool:
    with _connect() as connection:
        cursor = connection.execute("DELETE FROM demo_videos WHERE id = ?", (video_id,))
        return cursor.rowcount > 0


def _serialize_junction(row: sqlite3.Row) -> dict[str, Any]:
    junction_id = str(row["id"])
    with _connect() as connection:
        camera_count = int(connection.execute(
            "SELECT COUNT(*) FROM cameras WHERE junction_id = ?", (junction_id,)
        ).fetchone()[0])
        demo_count = int(connection.execute(
            "SELECT COUNT(*) FROM demo_videos WHERE junction_id = ?", (junction_id,)
        ).fetchone()[0])
    speed_limit = row["speed_limit"]
    return {
        "id": junction_id,
        "name": row["name"],
        "location": row["location"] or "",
        "description": row["description"] or "",
        "status": "ACTIVE" if row["enabled"] else "DISABLED",
        "enabled": bool(row["enabled"]),
        "speedLimit": float(speed_limit) if speed_limit is not None else SPEED_LIMIT,
        "cameraCount": camera_count,
        "demoVideoCount": demo_count,
    }


def _serialize_camera(row: sqlite3.Row) -> dict[str, Any]:
    speed_limit = row["speed_limit"]
    junction = get_junction(str(row["junction_id"]))
    return {
        "id": str(row["id"]),
        "junctionId": str(row["junction_id"]),
        "junctionName": junction["name"] if junction else None,
        "name": row["name"],
        "sourceType": row["source_type"],
        "videoUrl": row["video_url"] or "",
        "speedLimit": float(speed_limit) if speed_limit is not None else None,
        "enabled": bool(row["enabled"]),
    }


def _serialize_demo_video(row: sqlite3.Row) -> dict[str, Any]:
    junction = get_junction(str(row["junction_id"]))
    speed_limit = junction["speedLimit"] if junction else SPEED_LIMIT
    return {
        "id": str(row["id"]),
        "junctionId": str(row["junction_id"]),
        "cameraId": str(row["camera_id"]) if row["camera_id"] else None,
        "title": row["title"],
        "description": row["description"] or "",
        "filename": row["filename"],
        "scenario": row["scenario"],
        "duration": float(row["duration_seconds"]) if row["duration_seconds"] is not None else None,
        "speedLimit": speed_limit,
        "enabled": bool(row["enabled"]),
    }
