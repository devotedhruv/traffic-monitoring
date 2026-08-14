import { config, endpoints } from "../lib/config";
import { getMockAnalytics, getMockSummary, getMockVehicles, mockVehicles } from "../mocks/data";
import type { AlertDetail, AlertQuery, AlertSummary, AnalyticsData, AnalyticsRange, AuthResponse, AuthUser, Camera, CameraSettings, DashboardSummary, LaneRule, LiveCameraCalibration, PaginatedAlerts, PaginatedVehicles, PaginatedViolations, ReportFilters, ReportFrequency, ReportQuery, ReportRecord, ReportSchedule, ReportSummary, ReportTemplate, ReportType, SystemHealth, VehicleDetection, VehicleQuery, VideoAnalysisJob, VideoAnalysisOptions, ViolationCapabilities, ViolationQuery, ViolationSummary, ViolationType } from "../types";

export class ApiError extends Error {
  status: number;

  constructor(message: string, status: number) {
    super(message);
    this.name = "ApiError";
    this.status = status;
  }
}

async function request<T>(path: string, init?: RequestInit): Promise<T> {
  const response = await fetch(`${config.apiBaseUrl}${path}`, {
    ...init,
    credentials: "include",
    headers: { Accept: "application/json", ...init?.headers }
  });
  if (!response.ok) {
    const payload = await response.json().catch(() => null) as { detail?: string | { msg?: string }[] } | null;
    const detail = Array.isArray(payload?.detail)
      ? payload.detail.map((item) => item.msg).filter(Boolean).join(", ")
      : payload?.detail;
    if (response.status === 401) window.dispatchEvent(new Event("trafficops:unauthorized"));
    throw new ApiError(detail || `Request failed (${response.status})`, response.status);
  }
  if (response.status === 204) return undefined as T;
  return response.json() as Promise<T>;
}

function queryString(query: VehicleQuery) {
  const params = new URLSearchParams({
    page: String(query.page),
    pageSize: String(query.pageSize),
    status: query.status ?? "",
    type: query.type ?? "",
    search: query.search ?? "",
    speed: query.speed ?? "",
    date: query.date ?? "",
    violation: query.violation ?? "",
    sort: query.sort ?? "time_desc"
  });
  return params.toString();
}

function violationQueryString(query: ViolationQuery) {
  return new URLSearchParams({
    page: String(query.page),
    pageSize: String(query.pageSize),
    type: query.type ?? "",
    vehicleType: query.vehicleType ?? "",
    search: query.search ?? "",
    date: query.date ?? "",
    camera: query.camera ?? "",
    sort: query.sort ?? "time_desc"
  }).toString();
}

function alertQueryString(query: AlertQuery) {
  return new URLSearchParams({
    page: String(query.page),
    pageSize: String(query.pageSize),
    status: query.status ?? "",
    severity: query.severity ?? "",
    type: query.type ?? "",
    vehicleType: query.vehicleType ?? "",
    camera: query.camera ?? "",
    assignedTo: query.assignedTo ?? "",
    search: query.search ?? "",
    date: query.date ?? "",
    sort: query.sort ?? "newest"
  }).toString();
}

function reportQueryString(query: ReportQuery) {
  return new URLSearchParams({
    page: String(query.page),
    pageSize: String(query.pageSize),
    search: query.search ?? "",
    type: query.type ?? "",
    status: query.status ?? "",
    creator: query.creator ? String(query.creator) : "",
    date: query.date ?? "",
    sort: query.sort ?? "newest"
  }).toString();
}

async function startVideoAnalysis(file: File, options: VideoAnalysisOptions) {
  const params = new URLSearchParams({
    filename: file.name,
    location: options.location,
    speedLimit: String(options.speedLimit),
    metersPerPixel: String(options.metersPerPixel)
  });
  if (options.calibration) params.set("calibration", JSON.stringify(options.calibration));
  const response = await fetch(`${config.apiBaseUrl}${endpoints.videoAnalysis}?${params}`, {
    method: "POST",
    credentials: "include",
    headers: {
      Accept: "application/json",
      "Content-Type": file.type || "application/octet-stream"
    },
    body: file
  });
  if (!response.ok) {
    if (response.status === 401) window.dispatchEvent(new Event("trafficops:unauthorized"));
    const payload = await response.json().catch(() => null) as { detail?: string } | null;
    throw new Error(payload?.detail || `Video upload failed (${response.status})`);
  }
  return response.json() as Promise<VideoAnalysisJob>;
}

export const api = {
  signUp: (name: string, email: string, password: string) => request<AuthResponse>(endpoints.signUp, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ name, email, password })
  }),
  signIn: (email: string, password: string) => request<AuthResponse>(endpoints.signIn, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ email, password })
  }),
  signOut: () => request<void>(endpoints.signOut, { method: "POST" }),
  getMe: () => request<AuthResponse>(endpoints.me),
  getHealth: () => config.useMocks ? Promise.resolve<SystemHealth>({
    status: "healthy", pipelineRunning: true, fps: 29.8, analysisFps: 12, sourceFps: 30,
    loopCount: 0, confidence: 0.65, showOverlays: true, activeTracks: 7, activeDetections: 57,
    speedCalibration: "DEMO", speedProcessingMode: "DEMO", speedCalibrationQuality: 0,
    roadWidthMeters: null, roadLengthMeters: null, sourceMode: "demo", browserConnected: false,
    capabilities: {}, error: null
  }) : request<SystemHealth>(endpoints.health),
  getSummary: () => config.useMocks ? getMockSummary() : request<DashboardSummary>(endpoints.summary),
  getVehicles: (query: VehicleQuery) => config.useMocks ? getMockVehicles(query) : request<PaginatedVehicles>(`${endpoints.vehicles}?${queryString(query)}`),
  getVehicle: (id: number) => config.useMocks
    ? Promise.resolve(mockVehicles.find((vehicle) => vehicle.id === id) ?? null)
    : request<VehicleDetection>(endpoints.vehicle(id)),
  getAnalytics: (range: AnalyticsRange) => config.useMocks
    ? getMockAnalytics(range)
    : request<AnalyticsData>(`${endpoints.analytics}?range=${range}`),
  getCameras: () => config.useMocks
    ? Promise.resolve<Camera[]>([{ id: "camera-01", name: "North Junction", streamAvailable: false, sourceType: "configured", browserConnected: false }])
    : request<Camera[]>(endpoints.cameras),
  getCapabilities: () => config.useMocks ? Promise.resolve<ViolationCapabilities>({
    plateRecognition: { available: false, reason: "Dedicated number-plate detector weights are not configured" },
    helmetDetection: { available: false, reason: "Dedicated helmet weights are not configured" },
    wrongLaneDetection: { available: false, reason: "Camera lane rules are not configured" },
    wrongDirectionDetection: { available: false, reason: "A global allowed direction is not configured" }
  }) : request<ViolationCapabilities>(endpoints.capabilities),
  getViolations: (limit = 50, type: ViolationType | "" = "") =>
    config.useMocks ? Promise.resolve({ items: [], total: 0, page: 1, pageSize: limit }) :
      request<PaginatedViolations>(`${endpoints.violations}?limit=${limit}&type=${type}`),
  getViolationRecords: (query: ViolationQuery) => config.useMocks
    ? Promise.resolve<PaginatedViolations>({ items: [], total: 0, page: query.page, pageSize: query.pageSize })
    : request<PaginatedViolations>(`${endpoints.violations}?${violationQueryString(query)}`),
  getPlates: (limit = 20) => config.useMocks
    ? Promise.resolve({ items: [] as VehicleDetection[], total: 0 })
    : request<{ items: VehicleDetection[]; total: number }>(`${endpoints.plates}?limit=${limit}`),
  getViolationSummary: (scope: "session" | "all" = "session") => config.useMocks ? Promise.resolve<ViolationSummary>({ total: 0, counts: {}, latest: null }) :
    request<ViolationSummary>(`${endpoints.violationsSummary}?scope=${scope}`),
  getAlerts: (query: AlertQuery) => config.useMocks
    ? Promise.resolve<PaginatedAlerts>({ items: [], total: 0, page: query.page, pageSize: query.pageSize })
    : request<PaginatedAlerts>(`${endpoints.alerts}?${alertQueryString(query)}`),
  getAlertSummary: (scope: "session" | "today" | "all" = "session") => config.useMocks
    ? Promise.resolve<AlertSummary>({ total: 0, new: 0, unresolved: 0, critical: 0, resolvedToday: 0, averageResponseSeconds: null, bySeverity: {} })
    : request<AlertSummary>(`${endpoints.alertsSummary}?scope=${scope}`),
  getAlert: (alertId: number) => request<AlertDetail>(endpoints.alert(alertId)),
  getAlertOperators: () => request<{ items: AuthUser[] }>(endpoints.alertOperators),
  updateAlertStatus: (alertId: number, action: "acknowledge" | "investigate" | "resolve" | "false-positive", expectedVersion: number, note?: string) => request<AlertDetail>(endpoints.alertAction(alertId, action), {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ expectedVersion, note })
  }),
  assignAlert: (alertId: number, userId: number | null, expectedVersion: number) => request<AlertDetail>(endpoints.alertAction(alertId, "assign"), {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ userId, expectedVersion })
  }),
  getReportTemplates: () => config.useMocks
    ? Promise.resolve<{ items: ReportTemplate[] }>({ items: [] })
    : request<{ items: ReportTemplate[] }>(endpoints.reportTemplates),
  getReports: (query: ReportQuery) => config.useMocks
    ? Promise.resolve({ items: [] as ReportRecord[], total: 0, page: query.page, pageSize: query.pageSize })
    : request<{ items: ReportRecord[]; total: number; page: number; pageSize: number }>(`${endpoints.reports}?${reportQueryString(query)}`),
  getReportSummary: () => config.useMocks
    ? Promise.resolve<ReportSummary>({ total: 0, ready: 0, failed: 0, scheduled: 0, thisMonth: 0 })
    : request<ReportSummary>(endpoints.reportsSummary),
  getReport: (reportId: number) => request<ReportRecord>(endpoints.report(reportId)),
  generateReport: (payload: { name: string; type: ReportType; filters: ReportFilters; sections: string[] }) => request<ReportRecord>(endpoints.generateReport, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(payload)
  }),
  renameReport: (reportId: number, name: string) => request<ReportRecord>(endpoints.reportAction(reportId, "rename"), {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ name })
  }),
  regenerateReport: (reportId: number) => request<ReportRecord>(endpoints.reportAction(reportId, "regenerate"), { method: "POST" }),
  getReportSchedules: () => config.useMocks
    ? Promise.resolve<{ items: ReportSchedule[] }>({ items: [] })
    : request<{ items: ReportSchedule[] }>(endpoints.reportSchedules),
  createReportSchedule: (payload: { name: string; type: ReportType; frequency: ReportFrequency; generationTime: string; timezone: string; filters: Omit<ReportFilters, "startAt" | "endAt" | "timezone">; sections: string[] }) => request<ReportSchedule>(endpoints.reportSchedules, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(payload)
  }),
  toggleReportSchedule: (scheduleId: number) => request<ReportSchedule>(endpoints.reportScheduleToggle(scheduleId), { method: "POST" }),
  getReportDownloadUrl: (reportId: number, format: "pdf" | "csv") => `${config.apiBaseUrl}${endpoints.reportDownload(reportId, format)}`,
  getCameraSettings: (cameraId: string) => request<CameraSettings>(endpoints.cameraSettings(cameraId)),
  updateCameraSettings: (cameraId: string, settings: Partial<CameraSettings>) => request<CameraSettings>(endpoints.cameraSettings(cameraId), {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(settings)
  }),
  startBrowserCamera: (name: string) => request<{ cameraId: string; name: string; sourceType: "browser"; browserConnected: boolean }>(endpoints.startBrowserCamera, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ name })
  }),
  stopCamera: (cameraId: string) => request<{ cameraId: string; sourceType: "configured" }>(endpoints.stopCamera(cameraId), { method: "POST" }),
  getCameraCalibration: (cameraId: string) => request<{ cameraId: string; configured: boolean; calibration: LiveCameraCalibration | null }>(endpoints.cameraCalibration(cameraId)),
  updateCameraCalibration: (cameraId: string, calibration: LiveCameraCalibration) => request<{ cameraId: string; configured: true; calibration: LiveCameraCalibration }>(endpoints.cameraCalibration(cameraId), {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(calibration)
  }),
  getCameraLanes: (cameraId: string) => request<{ cameraId: string; rules: LaneRule[] }>(endpoints.cameraLanes(cameraId)),
  updateCameraLanes: (cameraId: string, rules: LaneRule[]) => request<{ cameraId: string; rules: LaneRule[] }>(endpoints.cameraLanes(cameraId), {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ rules })
  }),
  getStreamUrl: (cameraId: string) => `${config.apiBaseUrl}${endpoints.stream(cameraId)}`,
  startVideoAnalysis,
  getVideoAnalysis: (jobId: string) =>
    request<VideoAnalysisJob>(endpoints.videoAnalysisJob(jobId)),
  resolveApiUrl: (path: string) => path.startsWith("http") ? path : `${config.apiBaseUrl}${path}`
};
