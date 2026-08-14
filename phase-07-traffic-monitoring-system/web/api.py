"""FastAPI application exposing SadakDrishti data and the live CV pipeline."""

import asyncio
import math
import os
import struct
from contextlib import asynccontextmanager, suppress
from datetime import datetime, timezone
from pathlib import Path
from typing import Annotated, Literal

import cv2
import numpy as np
from fastapi import Depends, FastAPI, HTTPException, Query, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, StreamingResponse
from pydantic import BaseModel, Field

from config.settings import (
    ALLOWED_ORIGINS, AUTH_COOKIE_NAME, CAMERA_ID, PROJECT_ROOT,
)
from src.database import (
    alert_summary, analytics, assign_alert, create_database, dashboard_summary,
    get_alert, get_vehicle, get_vehicle_plate_image_path, get_vehicle_snapshot_path,
    get_violation_evidence_path,
    list_operators, list_plate_reads, list_vehicles, plate_reads_total, query_alerts,
    query_violations, save_camera_calibration, save_camera_lane_rules,
    update_alert_status, violation_summary,
)
from web.runtime import LiveRoadProfile, broker, next_event, runtime
from web.violations import parse_lane_rules
from web.auth import current_user_from_token, require_user, router as auth_router
from web.video_analysis import router as video_analysis_router
from web.reports import process_due_reports, router as reports_router


async def report_scheduler_loop():
    while True:
        await asyncio.sleep(60)
        try:
            await asyncio.to_thread(process_due_reports)
        except Exception:
            # A failed scheduled run is persisted; the API and live pipeline remain available.
            continue


@asynccontextmanager
async def lifespan(_: FastAPI):
    create_database()
    runtime.load_lane_rules()
    runtime.load_road_profile()
    if os.getenv("TRAFFIC_AUTOSTART", "true").lower() == "true":
        runtime.start()
    report_scheduler = asyncio.create_task(report_scheduler_loop())
    yield
    report_scheduler.cancel()
    with suppress(asyncio.CancelledError):
        await report_scheduler
    runtime.stop()


app = FastAPI(
    title="SadakDrishti API",
    version="1.0.0",
    description="REST, MJPEG, and WebSocket API for the AI traffic-monitoring pipeline.",
    lifespan=lifespan,
)
app.add_middleware(
    CORSMiddleware,
    allow_origins=ALLOWED_ORIGINS,
    allow_credentials=True,
    allow_methods=["GET", "POST"],
    allow_headers=["*"],
)
app.include_router(auth_router)
app.include_router(video_analysis_router, dependencies=[Depends(require_user)])
app.include_router(reports_router)


class CameraSettingsRequest(BaseModel):
    confidence: float | None = Field(default=None, ge=0.05, le=0.9)
    showOverlays: bool | None = None
    overlayFilters: list[Literal[
        "all", "car", "bike", "bus", "truck", "person", "violation",
        "no_helmet", "wrong_lane", "overspeed",
    ]] | None = None


class LaneRuleRequest(BaseModel):
    laneId: int = Field(ge=1, le=20)
    minX: float = Field(ge=0, le=1)
    maxX: float = Field(ge=0, le=1)
    allowedDirection: Literal[
        "both", "approaching", "moving_away", "left_to_right", "right_to_left"
    ] = "both"
    allowedVehicleTypes: list[
        Literal["bicycle", "car", "motorcycle", "bus", "truck"]
    ] = Field(default_factory=list)
    boundaryTolerance: float = Field(default=0.03, ge=0, lt=0.5)


class CameraLaneRulesRequest(BaseModel):
    rules: list[LaneRuleRequest] = Field(default_factory=list, max_length=20)


class BrowserCameraStartRequest(BaseModel):
    name: str = Field(default="Browser Webcam", min_length=1, max_length=80)


class CalibrationPointRequest(BaseModel):
    x: float = Field(ge=0, le=1)
    y: float = Field(ge=0, le=1)


class CameraCalibrationRequest(BaseModel):
    sourcePoints: list[CalibrationPointRequest] = Field(min_length=4, max_length=4)
    roadWidthMeters: float = Field(ge=2, le=80)
    roadLengthMeters: float = Field(ge=5, le=1000)
    laneCount: int = Field(ge=1, le=8)
    quality: float = Field(default=0.8, ge=0.1, le=1)


class AlertActionRequest(BaseModel):
    note: str | None = Field(default=None, max_length=500)
    expectedVersion: int = Field(ge=1)


class AlertAssignmentRequest(BaseModel):
    userId: int | None = Field(default=None, ge=1)
    expectedVersion: int = Field(ge=1)


@app.get("/api/health")
def health():
    profile = runtime.road_profile
    return {
        "status": "healthy" if runtime.running else "degraded",
        "pipelineRunning": runtime.running,
        "fps": round(runtime.fps, 1),
        "analysisFps": round(runtime.analysis_fps, 1),
        "sourceFps": round(runtime.source_fps, 1),
        "loopCount": runtime.loop_count,
        "confidence": runtime.confidence_threshold,
        "showOverlays": runtime.show_overlays,
        "activeTracks": runtime.active_tracks,
        "activeDetections": runtime.active_detections,
        "speedCalibration": runtime.speed_calibration,
        "speedProcessingMode": runtime.speed_processing_mode,
        "speedCalibrationQuality": profile.quality if profile else 0.0,
        "roadWidthMeters": profile.road_width_meters if profile else None,
        "roadLengthMeters": profile.road_length_meters if profile else None,
        "sourceMode": runtime.source_mode,
        "browserConnected": runtime.browser_connected,
        "capabilities": runtime.capabilities(),
        "error": runtime.error,
    }


@app.get("/api/dashboard/summary", dependencies=[Depends(require_user)])
def summary():
    return dashboard_summary(runtime.fps, runtime.session_started_at)


@app.get("/api/vehicles", dependencies=[Depends(require_user)])
def vehicles(
    page: Annotated[int, Query(ge=1)] = 1,
    pageSize: Annotated[int, Query(ge=1, le=100)] = 20,
    status: Literal["", "NORMAL", "OVERSPEED"] = "",
    type: Literal["", "bicycle", "car", "motorcycle", "bus", "truck", "unknown"] = "",
    search: Annotated[str, Query(max_length=100)] = "",
    sort: Literal["time_desc", "time_asc", "speed_desc", "speed_asc"] = "time_desc",
    speed: Literal["", "under_limit", "over_limit"] = "",
    date: Literal["", "today", "week"] = "",
    violation: Literal["", "OVERSPEED", "NO_HELMET", "WRONG_LANE", "WRONG_DIRECTION"] = "",
):
    return list_vehicles(page, pageSize, status, type, search, sort, speed, date, violation)


@app.get("/api/vehicles/{vehicle_id}", dependencies=[Depends(require_user)])
def vehicle(vehicle_id: int):
    result = get_vehicle(vehicle_id)
    if result is None:
        raise HTTPException(status_code=404, detail="Vehicle detection not found")
    return result


@app.get("/api/vehicles/{vehicle_id}/snapshot", dependencies=[Depends(require_user)])
def vehicle_snapshot(vehicle_id: int):
    snapshot_path = get_vehicle_snapshot_path(vehicle_id)
    if not snapshot_path:
        raise HTTPException(status_code=404, detail="Detection snapshot not found")
    resolved = Path(snapshot_path).resolve()
    snapshot_root = (PROJECT_ROOT / "output" / "detections").resolve()
    if not resolved.is_file() or not resolved.is_relative_to(snapshot_root):
        raise HTTPException(status_code=404, detail="Detection snapshot not found")
    return FileResponse(resolved, media_type="image/jpeg")


@app.get("/api/plates", dependencies=[Depends(require_user)])
def plates(limit: Annotated[int, Query(ge=1, le=100)] = 20):
    return {"items": list_plate_reads(limit), "total": plate_reads_total()}


@app.get("/api/vehicles/{vehicle_id}/plate-image", dependencies=[Depends(require_user)])
def vehicle_plate_image(vehicle_id: int):
    image_path = get_vehicle_plate_image_path(vehicle_id)
    if not image_path:
        raise HTTPException(status_code=404, detail="Number-plate image not found")
    resolved = Path(image_path).resolve()
    plate_root = (PROJECT_ROOT / "output" / "plates").resolve()
    if not resolved.is_file() or not resolved.is_relative_to(plate_root):
        raise HTTPException(status_code=404, detail="Number-plate image not found")
    return FileResponse(resolved, media_type="image/jpeg")


@app.get("/api/analytics", dependencies=[Depends(require_user)])
def analytics_endpoint(range: Literal["hour", "today", "week"] = "today"):
    return analytics(range)


@app.get("/api/cameras", dependencies=[Depends(require_user)])
def cameras():
    return [{
        "id": CAMERA_ID, "name": runtime.camera_name,
        "streamAvailable": runtime.running and runtime.error is None,
        "sourceType": runtime.source_mode,
        "browserConnected": runtime.browser_connected,
    }]


@app.post("/api/cameras/browser/start", dependencies=[Depends(require_user)])
def start_browser_camera(payload: BrowserCameraStartRequest):
    runtime.use_browser_source(payload.name)
    return {
        "cameraId": CAMERA_ID,
        "name": runtime.camera_name,
        "sourceType": runtime.source_mode,
        "browserConnected": runtime.browser_connected,
    }


@app.post("/api/cameras/{camera_id}/stop", dependencies=[Depends(require_user)])
def stop_browser_camera(camera_id: str):
    if camera_id != CAMERA_ID:
        raise HTTPException(status_code=404, detail="Camera not found")
    if runtime.source_mode == "browser":
        runtime.restore_configured_source()
    return {"cameraId": CAMERA_ID, "sourceType": runtime.source_mode}


@app.get("/api/cameras/{camera_id}/calibration", dependencies=[Depends(require_user)])
def camera_calibration(camera_id: str):
    if camera_id != CAMERA_ID:
        raise HTTPException(status_code=404, detail="Camera not found")
    return {
        "cameraId": camera_id,
        "configured": runtime.road_profile is not None,
        "calibration": runtime.road_profile.as_dict() if runtime.road_profile else None,
    }


@app.post("/api/cameras/{camera_id}/calibration", dependencies=[Depends(require_user)])
def update_camera_calibration(camera_id: str, payload: CameraCalibrationRequest):
    if camera_id != CAMERA_ID:
        raise HTTPException(status_code=404, detail="Camera not found")
    points = tuple((point.x, point.y) for point in payload.sourcePoints)
    polygon = np.asarray(points, dtype=np.float32)
    if not cv2.isContourConvex((polygon * 1000).astype(np.int32)):
        raise HTTPException(status_code=422, detail="Calibration points must form a convex road polygon")
    if abs(cv2.contourArea(polygon)) < 0.01:
        raise HTTPException(status_code=422, detail="Calibration road polygon is too small")
    profile = LiveRoadProfile(
        points, payload.roadWidthMeters, payload.roadLengthMeters,
        payload.laneCount, payload.quality,
    )
    save_camera_calibration(runtime.calibration_storage_key(), profile.as_dict())
    runtime.set_road_profile(profile)
    return {"cameraId": camera_id, "configured": True, "calibration": profile.as_dict()}


@app.post("/api/cameras/{camera_id}/settings", dependencies=[Depends(require_user)])
def camera_settings(camera_id: str, payload: CameraSettingsRequest):
    if camera_id != CAMERA_ID:
        raise HTTPException(status_code=404, detail="Camera not found")
    if payload.confidence is not None:
        runtime.set_confidence(payload.confidence)
    if payload.showOverlays is not None:
        runtime.set_overlays_visible(payload.showOverlays)
    if payload.overlayFilters is not None:
        runtime.set_overlay_filters(payload.overlayFilters)
    return {
        "confidence": runtime.confidence_threshold,
        "showOverlays": runtime.show_overlays,
        "overlayFilters": sorted(runtime.overlay_filters),
    }


@app.get("/api/cameras/{camera_id}/settings", dependencies=[Depends(require_user)])
def get_camera_settings(camera_id: str):
    if camera_id != CAMERA_ID:
        raise HTTPException(status_code=404, detail="Camera not found")
    return {
        "confidence": runtime.confidence_threshold,
        "showOverlays": runtime.show_overlays,
        "overlayFilters": sorted(runtime.overlay_filters),
    }


@app.get("/api/capabilities", dependencies=[Depends(require_user)])
def capabilities():
    return runtime.capabilities()


@app.get("/api/violations", dependencies=[Depends(require_user)])
def violations(
    page: Annotated[int, Query(ge=1)] = 1,
    pageSize: Annotated[int, Query(ge=1, le=100)] = 20,
    limit: Annotated[int | None, Query(ge=1, le=200)] = None,
    type: Literal["", "OVERSPEED", "NO_HELMET", "WRONG_LANE", "WRONG_DIRECTION"] = "",
    vehicleType: Literal["", "bicycle", "car", "motorcycle", "bus", "truck", "unknown"] = "",
    search: Annotated[str, Query(max_length=100)] = "",
    date: Literal["", "today", "week"] = "",
    camera: Annotated[str, Query(max_length=100)] = "",
    sort: Literal["time_desc", "time_asc", "speed_desc", "confidence_desc"] = "time_desc",
):
    return query_violations(
        page=page,
        page_size=limit or pageSize,
        violation_type=type,
        vehicle_type=vehicleType,
        search=search,
        date_filter=date,
        camera_id=camera,
        sort=sort,
    )


@app.get("/api/violations/summary", dependencies=[Depends(require_user)])
def violations_summary(scope: Literal["session", "all"] = "session"):
    return violation_summary(runtime.session_started_at if scope == "session" else None)


@app.get("/api/violations/{violation_id}/evidence", dependencies=[Depends(require_user)])
def violation_evidence(violation_id: int):
    evidence_path = get_violation_evidence_path(violation_id)
    if not evidence_path:
        raise HTTPException(status_code=404, detail="Violation evidence not found")
    resolved = Path(evidence_path).resolve()
    evidence_root = (PROJECT_ROOT / "output" / "violations").resolve()
    if not resolved.is_file() or not resolved.is_relative_to(evidence_root):
        raise HTTPException(status_code=404, detail="Violation evidence not found")
    return FileResponse(resolved, media_type="image/jpeg")


@app.get("/api/alerts")
def alerts(
    user: Annotated[dict, Depends(require_user)],
    page: Annotated[int, Query(ge=1)] = 1,
    pageSize: Annotated[int, Query(ge=1, le=100)] = 20,
    status: Annotated[str, Query(max_length=120)] = "",
    severity: Literal["", "LOW", "MEDIUM", "HIGH", "CRITICAL"] = "",
    type: Literal["", "OVERSPEED", "NO_HELMET", "WRONG_LANE", "WRONG_DIRECTION"] = "",
    vehicleType: Literal["", "bicycle", "car", "motorcycle", "bus", "truck", "unknown"] = "",
    camera: Annotated[str, Query(max_length=100)] = "",
    assignedTo: Annotated[str, Query(max_length=40)] = "",
    search: Annotated[str, Query(max_length=100)] = "",
    date: Literal["", "today", "week"] = "",
    sort: Literal["newest", "oldest", "severity"] = "newest",
):
    requested_statuses = [item.strip().upper() for item in status.split(",") if item.strip()]
    if any(item not in {"NEW", "ACKNOWLEDGED", "INVESTIGATING", "RESOLVED", "FALSE_POSITIVE"} for item in requested_statuses):
        raise HTTPException(status_code=422, detail="Invalid alert status filter")
    assignment = str(user["id"]) if assignedTo == "me" else assignedTo
    if assignment and assignment != "unassigned" and not assignment.isdigit():
        raise HTTPException(status_code=422, detail="Invalid assignedTo filter")
    return query_alerts(
        page, pageSize, status, severity, type, vehicleType, camera,
        assignment, search, date, sort,
    )


@app.get("/api/alerts/summary")
def alerts_summary(
    user: Annotated[dict, Depends(require_user)],
    scope: Literal["session", "today", "all"] = "session",
):
    del user
    since = runtime.session_started_at if scope == "session" else None
    if scope == "today":
        since = datetime.now(timezone.utc).replace(
            hour=0, minute=0, second=0, microsecond=0,
        ).isoformat().replace("+00:00", "Z")
    return alert_summary(since)


@app.get("/api/alerts/operators")
def alert_operators(user: Annotated[dict, Depends(require_user)]):
    del user
    return {"items": list_operators()}


def _alert_result(operation):
    try:
        return operation()
    except LookupError as error:
        raise HTTPException(status_code=404, detail=str(error)) from error
    except RuntimeError as error:
        raise HTTPException(status_code=409, detail=str(error)) from error
    except ValueError as error:
        raise HTTPException(status_code=422, detail=str(error)) from error


@app.get("/api/alerts/{alert_id}")
def alert_detail(alert_id: int, user: Annotated[dict, Depends(require_user)]):
    del user
    result = get_alert(alert_id)
    if result is None:
        raise HTTPException(status_code=404, detail="Alert not found")
    return result


@app.post("/api/alerts/{alert_id}/acknowledge")
def acknowledge_alert(
    alert_id: int, payload: AlertActionRequest,
    user: Annotated[dict, Depends(require_user)],
):
    return _alert_result(lambda: update_alert_status(
        alert_id, "ACKNOWLEDGED", user, payload.note, payload.expectedVersion,
    ))


@app.post("/api/alerts/{alert_id}/investigate")
def investigate_alert(
    alert_id: int, payload: AlertActionRequest,
    user: Annotated[dict, Depends(require_user)],
):
    return _alert_result(lambda: update_alert_status(
        alert_id, "INVESTIGATING", user, payload.note, payload.expectedVersion,
    ))


@app.post("/api/alerts/{alert_id}/resolve")
def resolve_alert(
    alert_id: int, payload: AlertActionRequest,
    user: Annotated[dict, Depends(require_user)],
):
    return _alert_result(lambda: update_alert_status(
        alert_id, "RESOLVED", user, payload.note, payload.expectedVersion,
    ))


@app.post("/api/alerts/{alert_id}/false-positive")
def false_positive_alert(
    alert_id: int, payload: AlertActionRequest,
    user: Annotated[dict, Depends(require_user)],
):
    return _alert_result(lambda: update_alert_status(
        alert_id, "FALSE_POSITIVE", user, payload.note, payload.expectedVersion,
    ))


@app.post("/api/alerts/{alert_id}/assign")
def assign_alert_operator(
    alert_id: int, payload: AlertAssignmentRequest,
    user: Annotated[dict, Depends(require_user)],
):
    return _alert_result(lambda: assign_alert(
        alert_id, payload.userId, user, payload.expectedVersion,
    ))


@app.get("/api/cameras/{camera_id}/lanes", dependencies=[Depends(require_user)])
def camera_lanes(camera_id: str):
    if camera_id != CAMERA_ID:
        raise HTTPException(status_code=404, detail="Camera not found")
    return {"cameraId": camera_id, "rules": [rule.as_dict() for rule in runtime.lane_rules]}


@app.post("/api/cameras/{camera_id}/lanes", dependencies=[Depends(require_user)])
def update_camera_lanes(camera_id: str, payload: CameraLaneRulesRequest):
    if camera_id != CAMERA_ID:
        raise HTTPException(status_code=404, detail="Camera not found")
    raw_rules = [rule.model_dump() for rule in payload.rules]
    try:
        parsed = parse_lane_rules(raw_rules)
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    save_camera_lane_rules(camera_id, [rule.as_dict() for rule in parsed])
    runtime.set_lane_rules(parsed)
    return {"cameraId": camera_id, "rules": [rule.as_dict() for rule in parsed]}


def mjpeg_frames():
    version = -1
    while runtime.running:
        version, frame = runtime.wait_for_frame(version)
        if frame:
            yield b"--frame\r\nContent-Type: image/jpeg\r\n\r\n" + frame + b"\r\n"


@app.get("/api/cameras/{camera_id}/stream", dependencies=[Depends(require_user)])
def camera_stream(camera_id: str):
    if camera_id != CAMERA_ID:
        raise HTTPException(status_code=404, detail="Camera not found")
    if not runtime.running:
        raise HTTPException(status_code=503, detail=runtime.error or "Pipeline is not running")
    return StreamingResponse(mjpeg_frames(), media_type="multipart/x-mixed-replace; boundary=frame")


@app.websocket("/ws/live")
async def live_socket(websocket: WebSocket):
    if current_user_from_token(websocket.cookies.get(AUTH_COOKIE_NAME)) is None:
        await websocket.close(code=4401, reason="Authentication required")
        return
    await websocket.accept()
    await websocket.send_json({"type": "system_status", "data": {
        "connection": "connected" if runtime.running else "offline",
        "fps": round(runtime.fps, 1),
        "analysisFps": round(runtime.analysis_fps, 1),
        "activeTracks": runtime.active_tracks,
        "activeDetections": runtime.active_detections,
        "speedCalibration": runtime.speed_calibration,
        "cameraId": CAMERA_ID,
        "timestamp": datetime.now(timezone.utc).isoformat().replace("+00:00", "Z"),
    }})
    events = broker.subscribe()
    try:
        while True:
            await websocket.send_json(await next_event(events))
    except (WebSocketDisconnect, RuntimeError):
        return
    finally:
        broker.unsubscribe(events)


def decode_browser_frame(payload: bytes) -> tuple[float, np.ndarray] | None:
    if len(payload) <= 8 or len(payload) > 2_000_000:
        return None
    timestamp = struct.unpack(">d", payload[:8])[0]
    if not math.isfinite(timestamp) or timestamp < 0:
        return None
    encoded = np.frombuffer(payload, dtype=np.uint8, offset=8)
    frame = cv2.imdecode(encoded, cv2.IMREAD_COLOR)
    if frame is None:
        return None
    height, width = frame.shape[:2]
    if width > 1280 or height > 720:
        scale = min(1280 / width, 720 / height)
        frame = cv2.resize(
            frame,
            (max(1, round(width * scale)), max(1, round(height * scale))),
            interpolation=cv2.INTER_AREA,
        )
    return timestamp, frame


@app.websocket("/ws/cameras/{camera_id}/ingest")
async def browser_camera_ingest(websocket: WebSocket, camera_id: str):
    """Accept timestamped JPEG frames from a browser webcam.

    Each binary message is an eight-byte, big-endian float64 timestamp in
    seconds followed by one JPEG image.  At most one queued frame is retained,
    so slow inference cannot build a stale-video backlog.
    """
    if current_user_from_token(websocket.cookies.get(AUTH_COOKIE_NAME)) is None:
        await websocket.close(code=4401, reason="Authentication required")
        return
    if camera_id != CAMERA_ID:
        await websocket.close(code=4404, reason="Camera not found")
        return
    if runtime.source_mode != "browser":
        await websocket.close(code=4409, reason="Start browser camera first")
        return

    await websocket.accept()
    runtime.set_browser_connected(True)
    last_accepted = 0.0
    try:
        while True:
            payload = await websocket.receive_bytes()
            now = asyncio.get_running_loop().time()
            if now - last_accepted < 1 / 15:
                await websocket.send_json({"type": "frame_ack", "accepted": False})
                continue
            decoded = await asyncio.to_thread(decode_browser_frame, payload)
            if decoded is None:
                await websocket.send_json({"type": "frame_ack", "accepted": False})
                continue
            timestamp, frame = decoded
            accepted = runtime.offer_browser_frame(timestamp, frame)
            if accepted:
                last_accepted = now
            await websocket.send_json({"type": "frame_ack", "accepted": accepted})
    except (WebSocketDisconnect, RuntimeError):
        return
    finally:
        runtime.set_browser_connected(False)
