"""Junction, camera, and demo-video configuration with the demo processing API.

Demo videos are processed by the *existing* live CV pipeline: switching a demo
video restarts the single TrafficRuntime with the demo file as its source, so
YOLO detection, ByteTrack tracking, speed estimation, and violation logic are
reused unchanged.  The operator-facing stream is the same MJPEG endpoint.
"""

from pathlib import Path
from typing import Annotated, Any

import cv2
from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel, Field

from config.settings import (
    CAMERA_ID, DEMO_VIDEO_BASE_URL, DEMO_VIDEO_DIR, PROJECT_ROOT, SPEED_LIMIT,
)
from src.database import (
    camera_exists, create_camera, create_demo_video, create_junction,
    delete_camera, delete_demo_video, delete_junction, get_camera,
    get_camera_calibration, get_demo_video, get_junction, list_cameras,
    list_demo_videos, list_junctions, update_camera, update_demo_video,
    update_junction,
)
from web.runtime import LiveRoadProfile, runtime

router = APIRouter(prefix="/api", tags=["junctions"])

SCENARIO_LABELS: dict[str, str] = {
    "normal": "Normal Traffic",
    "helmet": "Helmet Violation",
    "overspeed": "Overspeed",
    "wrong_lane": "Wrong Lane",
    "anpr": "ANPR",
    "heavy": "Heavy Traffic",
    "night": "Night Traffic",
}


def _demo_directory() -> Path:
    configured = Path(DEMO_VIDEO_DIR).expanduser()
    if not configured.is_absolute():
        configured = PROJECT_ROOT / configured
    return configured


def _resolve_demo_path(filename: str) -> Path:
    return _demo_directory() / Path(filename).name


def _probe_duration(filename: str) -> float | None:
    path = _resolve_demo_path(filename)
    if not path.is_file():
        return None
    try:
        capture = cv2.VideoCapture(str(path))
        try:
            fps = float(capture.get(cv2.CAP_PROP_FPS) or 0)
            frames = int(capture.get(cv2.CAP_PROP_FRAME_COUNT) or 0)
        finally:
            capture.release()
        if frames > 0 and fps > 0:
            return round(frames / fps, 1)
    except Exception:
        return None
    return None


def _demo_video_payload(video: dict[str, Any]) -> dict[str, Any]:
    payload = dict(video)
    payload["available"] = _resolve_demo_path(video["filename"]).is_file()
    if payload["duration"] is None and payload["available"]:
        payload["duration"] = _probe_duration(video["filename"])
    preview = None
    if DEMO_VIDEO_BASE_URL:
        preview = f"{DEMO_VIDEO_BASE_URL}/{video['filename']}"
    payload["previewUrl"] = preview
    return payload


def _camera_profile(camera_id: str) -> LiveRoadProfile | None:
    saved = get_camera_calibration(camera_id)
    if not saved:
        return None
    try:
        points = tuple(
            (float(point["x"]), float(point["y"]))
            for point in saved.get("sourcePoints", [])
        )
        if len(points) != 4:
            return None
        return LiveRoadProfile(
            points,
            float(saved["roadWidthMeters"]),
            float(saved["roadLengthMeters"]),
            int(saved.get("laneCount", 2)),
            float(saved.get("quality", 0.6)),
        )
    except (KeyError, TypeError, ValueError):
        return None


def _camera_stream_available(camera_id: str) -> bool:
    if not runtime.running:
        return False
    if camera_id != CAMERA_ID and not camera_exists(camera_id):
        return False
    return runtime.error is None


# --------------------------------------------------------------------------- #
# Junction and camera configuration
# --------------------------------------------------------------------------- #


@router.get("/junctions")
def junctions():
    return {"items": list_junctions()}


@router.get("/junctions/{junction_id}")
def junction_detail(junction_id: str):
    junction = get_junction(junction_id)
    if junction is None:
        raise HTTPException(status_code=404, detail="Junction not found")
    junction["cameras"] = list_cameras(junction_id)
    return junction


@router.get("/junctions/{junction_id}/cameras")
def junction_cameras(junction_id: str):
    if get_junction(junction_id) is None:
        raise HTTPException(status_code=404, detail="Junction not found")
    return {"items": list_cameras(junction_id)}


@router.get("/cameras/{camera_id}")
def camera_detail(camera_id: str):
    camera = get_camera(camera_id)
    if camera is None:
        raise HTTPException(status_code=404, detail="Camera not found")
    return camera


class JunctionRequest(BaseModel):
    id: Annotated[str, Field(min_length=2, max_length=80, pattern=r"^[a-z0-9][a-z0-9-]*$")]
    name: Annotated[str, Field(min_length=1, max_length=120)]
    location: Annotated[str, Field(max_length=200)] = ""
    description: Annotated[str, Field(max_length=500)] = ""
    speedLimit: Annotated[float, Field(ge=5, le=200)] = SPEED_LIMIT
    enabled: bool = True


@router.post("/junctions")
def add_junction(payload: JunctionRequest):
    junction = create_junction(
        payload.id, payload.name, payload.location, payload.description,
        payload.speedLimit, payload.enabled,
    )
    if junction is None:
        raise HTTPException(status_code=409, detail="A junction with this id already exists")
    return junction


class JunctionUpdateRequest(BaseModel):
    name: Annotated[str, Field(min_length=1, max_length=120)] | None = None
    location: Annotated[str, Field(max_length=200)] | None = None
    description: Annotated[str, Field(max_length=500)] | None = None
    speedLimit: Annotated[float, Field(ge=5, le=200)] | None = None
    enabled: bool | None = None


@router.post("/junctions/{junction_id}/update")
def edit_junction(junction_id: str, payload: JunctionUpdateRequest):
    junction = update_junction(
        junction_id, payload.name, payload.location, payload.description,
        payload.speedLimit, payload.enabled,
    )
    if junction is None:
        raise HTTPException(status_code=404, detail="Junction not found")
    return junction


@router.post("/junctions/{junction_id}/delete")
def remove_junction(junction_id: str):
    if junction_id == "north":
        raise HTTPException(status_code=422, detail="The primary North Junction cannot be removed")
    if not delete_junction(junction_id):
        raise HTTPException(status_code=404, detail="Junction not found")
    return {"deleted": True}


class CameraRequest(BaseModel):
    id: Annotated[str, Field(min_length=2, max_length=80, pattern=r"^[a-z0-9][a-z0-9-]*$")]
    name: Annotated[str, Field(min_length=1, max_length=120)]
    sourceType: Annotated[str, Field(pattern=r"^(live|demo)$")] = "live"
    videoUrl: Annotated[str, Field(max_length=500)] = ""
    speedLimit: Annotated[float, Field(ge=5, le=200)] | None = None
    enabled: bool = True


@router.post("/junctions/{junction_id}/cameras")
def add_camera(junction_id: str, payload: CameraRequest):
    try:
        camera = create_camera(
            payload.id, junction_id, payload.name, payload.sourceType,
            payload.videoUrl, payload.speedLimit, payload.enabled,
        )
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    except LookupError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    if camera is None:
        raise HTTPException(status_code=409, detail="A camera with this id already exists")
    return camera


class CameraUpdateRequest(BaseModel):
    name: Annotated[str, Field(min_length=1, max_length=120)] | None = None
    sourceType: Annotated[str, Field(pattern=r"^(live|demo)$")] | None = None
    videoUrl: Annotated[str, Field(max_length=500)] | None = None
    speedLimit: Annotated[float, Field(ge=5, le=200)] | None = None
    enabled: bool | None = None


@router.post("/cameras/{camera_id}/update")
def edit_camera(camera_id: str, payload: CameraUpdateRequest):
    try:
        camera = update_camera(
            camera_id,
            name=payload.name,
            source_type=payload.sourceType,
            video_url=payload.videoUrl,
            speed_limit=payload.speedLimit,
            enabled=payload.enabled,
        )
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    if camera is None:
        raise HTTPException(status_code=404, detail="Camera not found")
    return camera


@router.post("/cameras/{camera_id}/delete")
def remove_camera(camera_id: str):
    if camera_id == CAMERA_ID:
        raise HTTPException(status_code=422, detail="The primary configured camera cannot be removed")
    if not delete_camera(camera_id):
        raise HTTPException(status_code=404, detail="Camera not found")
    return {"deleted": True}


# --------------------------------------------------------------------------- #
# Demo video library
# --------------------------------------------------------------------------- #


@router.get("/demo/scenarios")
def demo_scenarios():
    return {"items": [{"id": key, "label": label} for key, label in SCENARIO_LABELS.items()]}


@router.get("/demo-videos")
def demo_videos(
    junction_id: Annotated[str, Query()] = "",
    camera_id: Annotated[str, Query()] = "",
    scenario: Annotated[str, Query()] = "",
    includeDisabled: bool = False,
):
    videos = list_demo_videos(
        junction_id or None,
        camera_id or None,
        scenario or None,
        enabled_only=not includeDisabled,
    )
    return {"items": [_demo_video_payload(video) for video in videos]}


class DemoVideoRequest(BaseModel):
    id: Annotated[str, Field(min_length=2, max_length=80, pattern=r"^[a-z0-9][a-z0-9-]*$")]
    junctionId: Annotated[str, Field(min_length=1, max_length=80)]
    title: Annotated[str, Field(min_length=1, max_length=120)]
    filename: Annotated[str, Field(min_length=1, max_length=240)]
    description: Annotated[str, Field(max_length=500)] = ""
    scenario: Annotated[str, Field(pattern=r"^(normal|helmet|overspeed|wrong_lane|anpr|heavy|night)$")] = "normal"
    cameraId: Annotated[str, Field(max_length=80)] | None = None
    duration: Annotated[float, Field(ge=1, le=36000)] | None = None
    enabled: bool = True


@router.post("/demo-videos")
def add_demo_video(payload: DemoVideoRequest):
    try:
        video = create_demo_video(
            payload.id, payload.junctionId, payload.title, payload.filename,
            payload.description, payload.scenario, payload.cameraId,
            payload.duration, payload.enabled,
        )
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    except LookupError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    if video is None:
        raise HTTPException(status_code=409, detail="A demo video with this id already exists")
    return _demo_video_payload(video)


class DemoVideoUpdateRequest(BaseModel):
    title: Annotated[str, Field(min_length=1, max_length=120)] | None = None
    filename: Annotated[str, Field(min_length=1, max_length=240)] | None = None
    description: Annotated[str, Field(max_length=500)] | None = None
    scenario: Annotated[str, Field(pattern=r"^(normal|helmet|overspeed|wrong_lane|anpr|heavy|night)$")] | None = None
    cameraId: Annotated[str, Field(max_length=80)] | None = None
    duration: Annotated[float, Field(ge=1, le=36000)] | None = None
    enabled: bool | None = None


@router.post("/demo-videos/{video_id}/update")
def edit_demo_video(video_id: str, payload: DemoVideoUpdateRequest):
    try:
        video = update_demo_video(
            video_id,
            title=payload.title,
            filename=payload.filename,
            description=payload.description,
            scenario=payload.scenario,
            camera_id=payload.cameraId,
            duration_seconds=payload.duration,
            enabled=payload.enabled,
        )
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    if video is None:
        raise HTTPException(status_code=404, detail="Demo video not found")
    return _demo_video_payload(video)


@router.post("/demo-videos/{video_id}/delete")
def remove_demo_video(video_id: str):
    if not delete_demo_video(video_id):
        raise HTTPException(status_code=404, detail="Demo video not found")
    return {"deleted": True}


@router.get("/demo-videos/{video_id}/file")
def demo_video_file(video_id: str):
    video = get_demo_video(video_id)
    if video is None:
        raise HTTPException(status_code=404, detail="Demo video not found")
    resolved = _resolve_demo_path(video["filename"]).resolve()
    demo_root = _demo_directory().resolve()
    if not resolved.is_file() or not resolved.is_relative_to(demo_root):
        raise HTTPException(status_code=404, detail="Demo video unavailable")
    from fastapi.responses import FileResponse
    return FileResponse(resolved, media_type="video/mp4", filename=resolved.name)


# --------------------------------------------------------------------------- #
# Demo playback: reuse the live CV pipeline with the selected file
# --------------------------------------------------------------------------- #


class DemoStartRequest(BaseModel):
    junctionId: Annotated[str, Field(min_length=1, max_length=80)]
    cameraId: Annotated[str, Field(min_length=1, max_length=80)]
    videoId: Annotated[str, Field(min_length=1, max_length=80)]


@router.get("/demo/status")
def demo_status():
    status = runtime.demo_status()
    status["video"] = None
    if status["videoId"]:
        video = get_demo_video(status["videoId"])
        if video is not None:
            status["video"] = _demo_video_payload(video)
    return status


@router.post("/demo/start")
def start_demo(payload: DemoStartRequest):
    junction = get_junction(payload.junctionId)
    if junction is None:
        raise HTTPException(status_code=404, detail="Junction not found")
    if not junction["enabled"]:
        raise HTTPException(status_code=422, detail="Junction is disabled")
    camera = get_camera(payload.cameraId)
    if camera is None or camera["junctionId"] != payload.junctionId:
        raise HTTPException(status_code=404, detail="Camera not found for this junction")
    if not camera["enabled"]:
        raise HTTPException(status_code=422, detail="Camera is disabled")
    video = get_demo_video(payload.videoId)
    if video is None:
        raise HTTPException(status_code=404, detail="Demo video not found")
    if video["junctionId"] != payload.junctionId:
        raise HTTPException(status_code=422, detail="Demo video does not belong to this junction")
    if video["cameraId"] and video["cameraId"] != payload.cameraId:
        raise HTTPException(status_code=422, detail="Demo video is assigned to a different camera")
    if not video["enabled"]:
        raise HTTPException(status_code=422, detail="Demo video is disabled")

    resolved = _resolve_demo_path(video["filename"])
    if not resolved.is_file() or resolved.stat().st_size == 0:
        runtime.demo_available = False
        runtime.demo_error = "Demo video unavailable"
        return {
            "started": False,
            "available": False,
            "reason": "Demo video unavailable",
            "video": _demo_video_payload(video),
        }

    speed_limit = camera["speedLimit"] or video["speedLimit"] or SPEED_LIMIT
    profile = _camera_profile(payload.cameraId)
    runtime.use_demo_source(
        str(resolved),
        f"{camera['name']} · {video['title']}",
        video["id"],
        speed_limit=speed_limit,
        road_profile=profile,
    )
    return {
        "started": True,
        "available": True,
        "status": runtime.demo_status(),
    }


@router.post("/demo/stop")
def stop_demo():
    if runtime.source_mode == "demo":
        runtime.restore_configured_source()
    return {"status": runtime.demo_status()}


@router.post("/demo/pause")
def pause_demo():
    if runtime.source_mode != "demo":
        raise HTTPException(status_code=409, detail="No demo video is playing")
    return {"paused": runtime.set_demo_paused(True)}


@router.post("/demo/resume")
def resume_demo():
    if runtime.source_mode != "demo":
        raise HTTPException(status_code=409, detail="No demo video is playing")
    return {"paused": runtime.set_demo_paused(False)}


@router.post("/demo/restart")
def restart_demo():
    if runtime.source_mode != "demo":
        raise HTTPException(status_code=409, detail="No demo video is playing")
    return {"restarted": runtime.restart_demo()}
