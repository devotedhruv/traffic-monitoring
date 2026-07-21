"""
AI Traffic Monitoring System — Main Pipeline
=============================================
Detects & tracks vehicles with YOLO + ByteTrack, estimates speed,
flags overspeed violations, logs to the database, and drives the
live dashboard UI.

Run:
    python main.py
Quit:
    close the dashboard window, press 'q', or use Ctrl+C in the terminal.
"""

import os
import sys
import time
import logging

sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

import cv2
from ultralytics import YOLO

from camera_stream import Camera
from speed_manager import SpeedManager
from alert_system import check_speed
from dashboard import Dashboard
from database import create_database, save_vehicle

from config.settings import MODEL_PATH, VIDEO_PATH, SPEED_LIMIT


logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    datefmt="%H:%M:%S",
)
log = logging.getLogger("traffic_monitor")


# --------------------------------------------------------------------------
# Constants
# --------------------------------------------------------------------------
PLATE_PLACEHOLDER = "UNKNOWN"      # TODO: wire in ANPR module (Phase 6)
ALERT_COLOR_OVER = (0, 0, 255)     # red   (BGR)
ALERT_COLOR_OK = (0, 255, 0)       # green (BGR)
FPS_COLOR = (0, 220, 255)
QUIT_KEY = "q"


def draw_status_overlay(frame, status: str, position=(50, 50)):
    """Draw a simple OVERSPEED / NORMAL banner on the annotated frame."""
    text = "OVERSPEED" if status == "OVERSPEED" else "NORMAL"
    color = ALERT_COLOR_OVER if status == "OVERSPEED" else ALERT_COLOR_OK
    cv2.putText(frame, text, position, cv2.FONT_HERSHEY_SIMPLEX, 1, color, 3)


def draw_fps(frame, fps: float, position=(50, 90)):
    cv2.putText(frame, f"FPS: {fps:.1f}", position,
                cv2.FONT_HERSHEY_SIMPLEX, 0.7, FPS_COLOR, 2)


def process_frame(frame, model, speed_manager, dashboard, saved_vehicles):
    """Run detection/tracking on a single frame, update UI + DB, return the
    annotated frame ready for display."""
    results = model.track(frame, persist=True, tracker="bytetrack.yaml")
    output = results[0].plot()

    boxes = results[0].boxes
    if boxes is None or boxes.id is None:
        return output

    ids = boxes.id.tolist()
    classes = boxes.cls.tolist()

    for vehicle_id_raw, class_id_raw in zip(ids, classes):
        vehicle_id = int(vehicle_id_raw)
        vehicle_type = model.names[int(class_id_raw)]

        speed = speed_manager.calculate(vehicle_id) or 0
        status = check_speed(speed)
        plate = PLATE_PLACEHOLDER

        dashboard.update_vehicle(
            vehicle_id, vehicle_type, plate, speed, SPEED_LIMIT, status
        )

        if vehicle_id not in saved_vehicles:
            try:
                save_vehicle(plate, speed, status)
            except Exception:
                log.exception("Failed to save vehicle %s to database", vehicle_id)
            saved_vehicles.add(vehicle_id)

        draw_status_overlay(output, status)

    return output


def run():
    log.info("Initializing database...")
    create_database()

    log.info("Loading YOLO model from %s", MODEL_PATH)
    model = YOLO(MODEL_PATH)

    log.info("Opening video source: %s", VIDEO_PATH)
    camera = Camera(VIDEO_PATH)

    speed_manager = SpeedManager()
    dashboard = Dashboard()
    saved_vehicles = set()

    frame_count = 0
    fps = 0.0
    fps_timer = time.time()

    try:
        while dashboard.running:
            ret, frame = camera.read()
            if not ret:
                log.info("Video finished or camera disconnected.")
                break

            try:
                output = process_frame(frame, model, speed_manager, dashboard, saved_vehicles)
            except Exception:
                log.exception("Error while processing frame %d — skipping frame", frame_count)
                output = frame

            # FPS calculation (updated once per second)
            frame_count += 1
            elapsed = time.time() - fps_timer
            if elapsed >= 1.0:
                fps = frame_count / elapsed
                frame_count = 0
                fps_timer = time.time()
            draw_fps(output, fps)

            dashboard.update_video(output)
            if not dashboard.update():
                log.info("Dashboard closed, shutting down.")
                break

            if cv2.waitKey(1) & 0xFF == ord(QUIT_KEY):
                log.info("Quit key pressed, shutting down.")
                break

    except KeyboardInterrupt:
        log.info("Interrupted by user (Ctrl+C).")

    finally:
        log.info("Releasing camera and closing windows...")
        dashboard.close()
        camera.release()
        cv2.destroyAllWindows()
        log.info("Shutdown complete.")


if __name__ == "__main__":
    run()
