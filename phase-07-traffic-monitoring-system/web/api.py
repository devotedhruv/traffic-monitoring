"""FastAPI application exposing TrafficOps data and the live CV pipeline."""

import os
from contextlib import asynccontextmanager
from datetime import datetime, timezone
from typing import Annotated, Literal

from fastapi import FastAPI, HTTPException, Query, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse

from config.settings import ALLOWED_ORIGINS, CAMERA_ID, CAMERA_NAME
from src.database import (
    analytics, create_database, dashboard_summary, get_vehicle, list_vehicles,
)
from web.runtime import broker, next_event, runtime


@asynccontextmanager
async def lifespan(_: FastAPI):
    create_database()
    if os.getenv("TRAFFIC_AUTOSTART", "true").lower() == "true":
        runtime.start()
    yield
    runtime.stop()


app = FastAPI(
    title="TrafficOps API",
    version="1.0.0",
    description="REST, MJPEG, and WebSocket API for the AI traffic-monitoring pipeline.",
    lifespan=lifespan,
)
app.add_middleware(
    CORSMiddleware,
    allow_origins=ALLOWED_ORIGINS,
    allow_credentials=True,
    allow_methods=["GET"],
    allow_headers=["*"],
)


@app.get("/api/health")
def health():
    return {
        "status": "healthy" if runtime.running else "degraded",
        "pipelineRunning": runtime.running,
        "fps": round(runtime.fps, 1),
        "error": runtime.error,
    }


@app.get("/api/dashboard/summary")
def summary():
    return dashboard_summary(runtime.fps)


@app.get("/api/vehicles")
def vehicles(
    page: Annotated[int, Query(ge=1)] = 1,
    pageSize: Annotated[int, Query(ge=1, le=100)] = 20,
    status: Literal["", "NORMAL", "OVERSPEED"] = "",
    type: Literal["", "car", "motorcycle", "bus", "truck", "unknown"] = "",
    search: Annotated[str, Query(max_length=100)] = "",
    sort: Literal["time_desc", "time_asc", "speed_desc", "speed_asc"] = "time_desc",
):
    return list_vehicles(page, pageSize, status, type, search, sort)


@app.get("/api/vehicles/{vehicle_id}")
def vehicle(vehicle_id: int):
    result = get_vehicle(vehicle_id)
    if result is None:
        raise HTTPException(status_code=404, detail="Vehicle detection not found")
    return result


@app.get("/api/analytics")
def analytics_endpoint(range: Literal["hour", "today", "week"] = "today"):
    return analytics(range)


@app.get("/api/cameras")
def cameras():
    return [{
        "id": CAMERA_ID, "name": CAMERA_NAME,
        "streamAvailable": runtime.running and runtime.error is None,
    }]


def mjpeg_frames():
    version = -1
    while runtime.running:
        version, frame = runtime.wait_for_frame(version)
        if frame:
            yield b"--frame\r\nContent-Type: image/jpeg\r\n\r\n" + frame + b"\r\n"


@app.get("/api/cameras/{camera_id}/stream")
def camera_stream(camera_id: str):
    if camera_id != CAMERA_ID:
        raise HTTPException(status_code=404, detail="Camera not found")
    if not runtime.running:
        raise HTTPException(status_code=503, detail=runtime.error or "Pipeline is not running")
    return StreamingResponse(mjpeg_frames(), media_type="multipart/x-mixed-replace; boundary=frame")


@app.websocket("/ws/live")
async def live_socket(websocket: WebSocket):
    await websocket.accept()
    await websocket.send_json({"type": "system_status", "data": {
        "connection": "connected" if runtime.running else "offline",
        "fps": round(runtime.fps, 1),
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
