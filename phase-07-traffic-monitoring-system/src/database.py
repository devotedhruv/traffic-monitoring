"""SQLite persistence and read models for the desktop and web applications."""

import sqlite3
from contextlib import contextmanager
from datetime import datetime, timedelta, timezone
from typing import Any

from config.settings import CAMERA_ID, DATABASE_PATH, SPEED_LIMIT


@contextmanager
def _connect():
    connection = sqlite3.connect(DATABASE_PATH, timeout=10)
    connection.row_factory = sqlite3.Row
    connection.execute("PRAGMA foreign_keys = ON")
    try:
        yield connection
        connection.commit()
    except Exception:
        connection.rollback()
        raise
    finally:
        connection.close()


def create_database() -> None:
    with _connect() as connection:
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
    speed: float,
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


def _serialize(row: sqlite3.Row) -> dict[str, Any]:
    detected = str(row["time"]).replace(" ", "T")
    if not detected.endswith("Z") and "+" not in detected:
        detected += "Z"
    return {
        "id": row["id"],
        "trackingId": row["tracking_id"] if row["tracking_id"] is not None else row["id"],
        "vehicleType": row["vehicle_type"] or "unknown",
        "plate": None if not row["plate"] or row["plate"] == "UNKNOWN" else row["plate"],
        "speed": float(row["speed"] or 0),
        "speedLimit": SPEED_LIMIT,
        "status": row["status"],
        "detectedAt": detected,
        "cameraId": row["camera_id"] or CAMERA_ID,
        "snapshotUrl": row["snapshot_url"],
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
    return {"items": [_serialize(row) for row in rows], "total": total, "page": page, "pageSize": page_size}


def get_vehicle(vehicle_id: int) -> dict[str, Any] | None:
    with _connect() as connection:
        row = connection.execute("SELECT * FROM vehicles WHERE id = ?", (vehicle_id,)).fetchone()
    return _serialize(row) if row else None


def dashboard_summary(current_fps: float = 0) -> dict[str, Any]:
    with _connect() as connection:
        row = connection.execute("""
            SELECT COUNT(*) total,
                   SUM(CASE WHEN status = 'OVERSPEED' THEN 1 ELSE 0 END) overspeed,
                   COALESCE(AVG(speed), 0) average_speed,
                   COALESCE(MAX(speed), 0) max_speed
            FROM vehicles
        """).fetchone()
    return {
        "totalVehicles": row["total"], "overspeedVehicles": row["overspeed"] or 0,
        "averageSpeed": round(row["average_speed"], 2), "maxSpeed": round(row["max_speed"], 2),
        "currentFps": round(current_fps, 1), "speedLimit": SPEED_LIMIT,
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
    speeds = [item["speed"] for item in serialized]
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
