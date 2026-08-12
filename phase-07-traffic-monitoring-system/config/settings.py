"""Runtime configuration with environment-variable overrides."""

import os
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent

SPEED_LIMIT = float(os.getenv("TRAFFIC_SPEED_LIMIT", "50"))
VIDEO_SOURCE = os.getenv("TRAFFIC_VIDEO_SOURCE", str(PROJECT_ROOT / "videos" / "traffic.mp4"))
VIDEO_PATH = VIDEO_SOURCE
MODEL_PATH = os.getenv("TRAFFIC_MODEL_PATH", str(PROJECT_ROOT / "models" / "yolo11s.pt"))
_DEFAULT_LIVE_MODEL = PROJECT_ROOT / "models" / "yolov8n.pt"
LIVE_MODEL_PATH = os.getenv(
    "TRAFFIC_LIVE_MODEL_PATH",
    str(_DEFAULT_LIVE_MODEL if _DEFAULT_LIVE_MODEL.exists() else Path(MODEL_PATH)),
)
PLATE_MODEL_PATH = os.getenv("TRAFFIC_PLATE_MODEL_PATH", "")
PLATE_OCR_ENGINE = os.getenv("TRAFFIC_PLATE_OCR_ENGINE", "tesseract").strip().lower()
if PLATE_OCR_ENGINE not in {"tesseract", "easyocr", "none"}:
    PLATE_OCR_ENGINE = "none"
PLATE_OCR_LANGUAGES = os.getenv("TRAFFIC_PLATE_OCR_LANGUAGES", "eng").strip() or "eng"
PLATE_CONFIDENCE = min(
    0.95, max(0.05, float(os.getenv("TRAFFIC_PLATE_CONFIDENCE", "0.35")))
)
PLATE_MIN_QUALITY = min(
    1.0, max(0.0, float(os.getenv("TRAFFIC_PLATE_MIN_QUALITY", "0.18")))
)
PLATE_SAMPLE_SECONDS = min(
    10.0, max(0.25, float(os.getenv("TRAFFIC_PLATE_SAMPLE_SECONDS", "0.75")))
)
HELMET_MODEL_PATH = os.getenv("TRAFFIC_HELMET_MODEL_PATH", "")
LIVE_HELMET_CONFIDENCE = min(
    0.95, max(0.05, float(os.getenv("TRAFFIC_LIVE_HELMET_CONFIDENCE", "0.35")))
)
LIVE_HELMET_CONFIRMATIONS = min(
    12, max(2, int(os.getenv("TRAFFIC_LIVE_HELMET_CONFIRMATIONS", "3")))
)
LIVE_HELMET_SAMPLE_SECONDS = min(
    10.0, max(0.25, float(os.getenv("TRAFFIC_LIVE_HELMET_SAMPLE_SECONDS", "0.75")))
)
LIVE_LANE_RULES_JSON = os.getenv("TRAFFIC_LIVE_LANE_RULES", "").strip()
LIVE_ALLOWED_DIRECTION = os.getenv("TRAFFIC_LIVE_ALLOWED_DIRECTION", "both").strip().lower()
if LIVE_ALLOWED_DIRECTION not in {
    "both", "approaching", "moving_away", "left_to_right", "right_to_left",
}:
    LIVE_ALLOWED_DIRECTION = "both"
LIVE_LANE_CONFIRMATIONS = min(
    20, max(3, int(os.getenv("TRAFFIC_LIVE_LANE_CONFIRMATIONS", "5")))
)
LIVE_LANE_GRACE_SECONDS = min(
    10.0, max(0.25, float(os.getenv("TRAFFIC_LIVE_LANE_GRACE_SECONDS", "1.0")))
)
LIVE_LANE_MIN_TRAJECTORY_SECONDS = min(
    10.0, max(0.25, float(os.getenv("TRAFFIC_LIVE_LANE_MIN_TRAJECTORY_SECONDS", "0.75")))
)
LIVE_LANE_MIN_DISTANCE_METERS = min(
    50.0, max(0.25, float(os.getenv("TRAFFIC_LIVE_LANE_MIN_DISTANCE_METERS", "1.0")))
)
TESSERACT_CMD = os.getenv("TRAFFIC_TESSERACT_CMD", "tesseract")
TRACKER_CONFIG = os.getenv("TRAFFIC_TRACKER", "botsort.yaml")
if TRACKER_CONFIG not in {"botsort.yaml", "bytetrack.yaml"}:
    TRACKER_CONFIG = "botsort.yaml"
ANALYSIS_FPS = min(30.0, max(5.0, float(os.getenv("TRAFFIC_ANALYSIS_FPS", "15"))))
DETECTOR_IMAGE_SIZE = min(1280, max(640, int(os.getenv("TRAFFIC_DETECTOR_IMAGE_SIZE", "960"))))
LIVE_IMAGE_SIZE = min(960, max(320, int(os.getenv("TRAFFIC_LIVE_IMAGE_SIZE", "640"))))
LIVE_CONFIDENCE = min(0.9, max(0.05, float(os.getenv("TRAFFIC_LIVE_CONFIDENCE", "0.10"))))
LIVE_STREAM_FPS = min(60.0, max(5.0, float(os.getenv("TRAFFIC_LIVE_STREAM_FPS", "15"))))
LIVE_STREAM_WIDTH = min(1920, max(640, int(os.getenv("TRAFFIC_LIVE_STREAM_WIDTH", "960"))))
_DEFAULT_LIVE_TRACKER = PROJECT_ROOT / "config" / "live_bytetrack.yaml"
LIVE_TRACKER_CONFIG = os.getenv("TRAFFIC_LIVE_TRACKER", str(_DEFAULT_LIVE_TRACKER))
if (
    LIVE_TRACKER_CONFIG not in {"botsort.yaml", "bytetrack.yaml"}
    and not Path(LIVE_TRACKER_CONFIG).is_file()
):
    LIVE_TRACKER_CONFIG = str(_DEFAULT_LIVE_TRACKER)
LIVE_PREPROCESS_FILES = os.getenv("TRAFFIC_LIVE_PREPROCESS_FILES", "true").lower() == "true"
LIVE_ACCURATE_FILE_MODE = os.getenv("TRAFFIC_LIVE_ACCURATE_FILE_MODE", "true").lower() == "true"
LIVE_FILE_ANALYSIS_FPS = min(
    5.0, max(0.5, float(os.getenv("TRAFFIC_LIVE_FILE_ANALYSIS_FPS", "2")))
)
LIVE_ROAD_PROFILE = os.getenv("TRAFFIC_LIVE_ROAD_PROFILE", "auto").strip().lower()
_BUNDLED_ROAD_POINTS = "0.27,0.50;0.69,0.50;0.88,0.98;0.06,0.98"
_live_road_points_value = os.getenv("TRAFFIC_LIVE_ROAD_POINTS")
if not (_live_road_points_value or "").strip():
    use_bundled_profile = LIVE_ROAD_PROFILE == "bundled" or (
        LIVE_ROAD_PROFILE == "auto" and Path(VIDEO_SOURCE).name == "traffic.mp4"
    )
    _live_road_points_value = _BUNDLED_ROAD_POINTS if use_bundled_profile else ""


def _parse_live_road_points(value: str) -> tuple[tuple[float, float], ...]:
    try:
        points = tuple(
            tuple(float(coordinate.strip()) for coordinate in pair.split(",", 1))
            for pair in value.split(";") if pair.strip()
        )
    except ValueError:
        return ()
    if len(points) != 4 or any(len(point) != 2 for point in points):
        return ()
    if any(not 0 <= coordinate <= 1 for point in points for coordinate in point):
        return ()
    return points


LIVE_ROAD_POINTS = _parse_live_road_points(_live_road_points_value)
LIVE_ROAD_WIDTH_METERS = min(80.0, max(2.0, float(os.getenv("TRAFFIC_LIVE_ROAD_WIDTH_METERS", "13"))))
LIVE_ROAD_LENGTH_METERS = min(1000.0, max(5.0, float(os.getenv("TRAFFIC_LIVE_ROAD_LENGTH_METERS", "50"))))
LIVE_ROAD_CALIBRATION_QUALITY = min(
    1.0, max(0.1, float(os.getenv("TRAFFIC_LIVE_ROAD_CALIBRATION_QUALITY", "0.60")))
)
LIVE_MIN_SPEED_SAMPLES = min(20, max(2, int(os.getenv("TRAFFIC_LIVE_MIN_SPEED_SAMPLES", "2"))))
LIVE_MIN_SPEED_CONFIDENCE = min(
    1.0, max(0.1, float(os.getenv("TRAFFIC_LIVE_MIN_SPEED_CONFIDENCE", "0.45")))
)
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
