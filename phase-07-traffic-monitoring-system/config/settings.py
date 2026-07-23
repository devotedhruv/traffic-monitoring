"""Runtime configuration with environment-variable overrides."""

import os
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent

SPEED_LIMIT = float(os.getenv("TRAFFIC_SPEED_LIMIT", "50"))
VIDEO_SOURCE = os.getenv("TRAFFIC_VIDEO_SOURCE", str(PROJECT_ROOT / "videos" / "traffic.mp4"))
VIDEO_PATH = VIDEO_SOURCE
MODEL_PATH = os.getenv("TRAFFIC_MODEL_PATH", str(PROJECT_ROOT / "models" / "yolov8n.pt"))
DATABASE_PATH = os.getenv("TRAFFIC_DATABASE_PATH", str(PROJECT_ROOT / "database" / "traffic.db"))
CAMERA_ID = os.getenv("TRAFFIC_CAMERA_ID", "camera-01")
CAMERA_NAME = os.getenv("TRAFFIC_CAMERA_NAME", "North Junction")
METERS_PER_PIXEL = float(os.getenv("TRAFFIC_METERS_PER_PIXEL", "0.05"))
ALLOWED_ORIGINS = [
    origin.strip()
    for origin in os.getenv(
        "TRAFFIC_ALLOWED_ORIGINS", "http://localhost:5173,http://127.0.0.1:5173"
    ).split(",")
    if origin.strip()
]
