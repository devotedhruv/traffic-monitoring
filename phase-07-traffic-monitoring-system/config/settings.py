"""Runtime configuration with environment-variable overrides."""

import os
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent

SPEED_LIMIT = float(os.getenv("TRAFFIC_SPEED_LIMIT", "50"))
VIDEO_SOURCE = os.getenv("TRAFFIC_VIDEO_SOURCE", str(PROJECT_ROOT / "videos" / "traffic.mp4"))
VIDEO_PATH = VIDEO_SOURCE
MODEL_PATH = os.getenv("TRAFFIC_MODEL_PATH", str(PROJECT_ROOT / "models" / "yolo11s.pt"))
PLATE_MODEL_PATH = os.getenv("TRAFFIC_PLATE_MODEL_PATH", "")
HELMET_MODEL_PATH = os.getenv("TRAFFIC_HELMET_MODEL_PATH", "")
TESSERACT_CMD = os.getenv("TRAFFIC_TESSERACT_CMD", "tesseract")
TRACKER_CONFIG = os.getenv("TRAFFIC_TRACKER", "botsort.yaml")
if TRACKER_CONFIG not in {"botsort.yaml", "bytetrack.yaml"}:
    TRACKER_CONFIG = "botsort.yaml"
ANALYSIS_FPS = min(30.0, max(5.0, float(os.getenv("TRAFFIC_ANALYSIS_FPS", "15"))))
DETECTOR_IMAGE_SIZE = min(1280, max(640, int(os.getenv("TRAFFIC_DETECTOR_IMAGE_SIZE", "960"))))
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
AUTH_COOKIE_NAME = os.getenv("TRAFFIC_AUTH_COOKIE_NAME", "trafficops_session")
AUTH_SESSION_HOURS = min(24 * 30, max(1, int(os.getenv("TRAFFIC_AUTH_SESSION_HOURS", "168"))))
AUTH_COOKIE_SECURE = os.getenv("TRAFFIC_AUTH_COOKIE_SECURE", "false").lower() == "true"
