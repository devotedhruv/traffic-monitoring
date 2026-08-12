"""Authenticated report generation, export, and scheduling API."""

from __future__ import annotations

from typing import Annotated, Literal

from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi.responses import FileResponse
from pydantic import BaseModel, Field

from services.reporting import (
    REPORT_TEMPLATES, create_report, create_report_schedule, get_report,
    get_report_export_path, list_report_schedules, list_reports, regenerate_report,
    rename_report, report_summary, run_due_report_schedules, toggle_report_schedule,
)
from web.auth import require_user
from web.runtime import runtime

router = APIRouter(prefix="/api", tags=["reports"])
CurrentUser = Annotated[dict, Depends(require_user)]


class ReportFiltersRequest(BaseModel):
    startAt: str
    endAt: str
    timezone: str = Field(default="Asia/Kathmandu", min_length=1, max_length=80)
    camera: str = Field(default="", max_length=100)
    vehicleType: Literal["", "bicycle", "car", "motorcycle", "bus", "truck", "unknown"] = ""
    violationType: Literal["", "OVERSPEED", "NO_HELMET", "WRONG_LANE", "WRONG_DIRECTION"] = ""
    alertSeverity: Literal["", "LOW", "MEDIUM", "HIGH", "CRITICAL"] = ""
    alertStatus: Literal["", "NEW", "ACKNOWLEDGED", "INVESTIGATING", "RESOLVED", "FALSE_POSITIVE"] = ""
    assignedTo: int | None = Field(default=None, ge=1)


class GenerateReportRequest(BaseModel):
    name: str = Field(min_length=2, max_length=120)
    type: Literal[
        "TRAFFIC_SUMMARY", "VIOLATION_ENFORCEMENT", "ALERT_RESPONSE",
        "VEHICLE_FLOW", "CAMERA_PERFORMANCE", "CUSTOM",
    ]
    filters: ReportFiltersRequest
    sections: list[str] = Field(min_length=1, max_length=20)


class RenameReportRequest(BaseModel):
    name: str = Field(min_length=2, max_length=120)


class ScheduleFiltersRequest(BaseModel):
    camera: str = Field(default="", max_length=100)
    vehicleType: Literal["", "bicycle", "car", "motorcycle", "bus", "truck", "unknown"] = ""
    violationType: Literal["", "OVERSPEED", "NO_HELMET", "WRONG_LANE", "WRONG_DIRECTION"] = ""
    alertSeverity: Literal["", "LOW", "MEDIUM", "HIGH", "CRITICAL"] = ""
    alertStatus: Literal["", "NEW", "ACKNOWLEDGED", "INVESTIGATING", "RESOLVED", "FALSE_POSITIVE"] = ""
    assignedTo: int | None = Field(default=None, ge=1)


class CreateScheduleRequest(BaseModel):
    name: str = Field(min_length=2, max_length=120)
    type: Literal[
        "TRAFFIC_SUMMARY", "VIOLATION_ENFORCEMENT", "ALERT_RESPONSE",
        "VEHICLE_FLOW", "CAMERA_PERFORMANCE", "CUSTOM",
    ]
    frequency: Literal["DAILY", "WEEKLY", "MONTHLY"]
    generationTime: str = Field(pattern=r"^([01]\d|2[0-3]):[0-5]\d$")
    timezone: str = Field(default="Asia/Kathmandu", min_length=1, max_length=80)
    filters: ScheduleFiltersRequest = Field(default_factory=ScheduleFiltersRequest)
    sections: list[str] = Field(min_length=1, max_length=20)


def runtime_report_info() -> dict:
    return {
        "runtimeStatus": "LIVE" if runtime.running and not runtime.error else "DEGRADED",
        "analysisFps": round(runtime.analysis_fps, 1) if runtime.analysis_fps else None,
        "calibrationConfigured": runtime.road_profile is not None,
        "capabilities": runtime.capabilities(),
    }


def _service(operation):
    try:
        return operation()
    except LookupError as error:
        raise HTTPException(status_code=404, detail=str(error)) from error
    except RuntimeError as error:
        raise HTTPException(status_code=409, detail=str(error)) from error
    except (ValueError, TypeError) as error:
        raise HTTPException(status_code=422, detail=str(error)) from error


@router.get("/reports/templates")
def report_templates(user: CurrentUser):
    del user
    return {"items": REPORT_TEMPLATES}


@router.get("/reports")
def reports(
    user: CurrentUser,
    page: Annotated[int, Query(ge=1)] = 1,
    pageSize: Annotated[int, Query(ge=1, le=100)] = 20,
    search: Annotated[str, Query(max_length=100)] = "",
    type: Literal["", "TRAFFIC_SUMMARY", "VIOLATION_ENFORCEMENT", "ALERT_RESPONSE", "VEHICLE_FLOW", "CAMERA_PERFORMANCE", "CUSTOM"] = "",
    status: Literal["", "GENERATING", "READY", "FAILED"] = "",
    creator: Annotated[int | None, Query(ge=1)] = None,
    date: Literal["", "today", "week"] = "",
    sort: Literal["newest", "oldest"] = "newest",
):
    del user
    return list_reports(page, pageSize, search, type, status, creator, date, sort)


@router.get("/reports/summary")
def reports_summary(user: CurrentUser):
    del user
    return report_summary()


@router.post("/reports/generate", status_code=201)
def generate_report(payload: GenerateReportRequest, user: CurrentUser):
    try:
        return create_report(
            payload.name, payload.type, payload.filters.model_dump(), payload.sections,
            user, runtime_report_info(),
        )
    except (ValueError, TypeError) as error:
        raise HTTPException(status_code=422, detail=str(error)) from error
    except Exception as error:
        raise HTTPException(status_code=500, detail="Report generation failed. The failed run was recorded.") from error


@router.get("/reports/{report_id}")
def report_detail(report_id: int, user: CurrentUser):
    del user
    result = get_report(report_id)
    if result is None:
        raise HTTPException(status_code=404, detail="Report not found")
    return result


@router.get("/reports/{report_id}/download")
def download_report(
    report_id: int, user: CurrentUser, format: Literal["pdf", "csv"] = "pdf",
):
    del user
    try:
        path = get_report_export_path(report_id, format)
    except LookupError as error:
        raise HTTPException(status_code=404, detail=str(error)) from error
    except RuntimeError as error:
        raise HTTPException(status_code=409, detail=str(error)) from error
    except (ValueError, FileNotFoundError) as error:
        raise HTTPException(status_code=404, detail=str(error)) from error
    media_type = "application/pdf" if format == "pdf" else "text/csv; charset=utf-8"
    return FileResponse(path, media_type=media_type, filename=path.name)


@router.post("/reports/{report_id}/rename")
def rename_report_endpoint(report_id: int, payload: RenameReportRequest, user: CurrentUser):
    del user
    return _service(lambda: rename_report(report_id, payload.name))


@router.post("/reports/{report_id}/regenerate", status_code=201)
def regenerate_report_endpoint(report_id: int, user: CurrentUser):
    try:
        return regenerate_report(report_id, user, runtime_report_info())
    except LookupError as error:
        raise HTTPException(status_code=404, detail=str(error)) from error
    except (ValueError, TypeError) as error:
        raise HTTPException(status_code=422, detail=str(error)) from error
    except Exception as error:
        raise HTTPException(status_code=500, detail="Report regeneration failed. The failed run was recorded.") from error


@router.get("/report-schedules")
def report_schedules(user: CurrentUser):
    del user
    return {"items": list_report_schedules()}


@router.post("/report-schedules", status_code=201)
def add_report_schedule(payload: CreateScheduleRequest, user: CurrentUser):
    return _service(lambda: create_report_schedule(
        payload.name, payload.type, payload.frequency, payload.generationTime,
        payload.timezone, payload.filters.model_dump(), payload.sections, user,
    ))


@router.post("/report-schedules/{schedule_id}/toggle")
def toggle_report_schedule_endpoint(schedule_id: int, user: CurrentUser):
    del user
    return _service(lambda: toggle_report_schedule(schedule_id))


def process_due_reports() -> int:
    return run_due_report_schedules(runtime_report_info())
