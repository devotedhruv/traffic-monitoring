import { config, endpoints } from "../lib/config";
import { getMockAnalytics, getMockSummary, getMockVehicles, mockVehicles } from "../mocks/data";
import type { AnalyticsData, AnalyticsRange, AuthResponse, Camera, CameraSettings, DashboardSummary, LaneRule, LiveCameraCalibration, PaginatedVehicles, VehicleDetection, VehicleQuery, VideoAnalysisJob, VideoAnalysisOptions, ViolationCapabilities, ViolationEvent, ViolationType } from "../types";

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
    config.useMocks ? Promise.resolve({ items: [], total: 0 }) :
      request<{ items: ViolationEvent[]; total: number }>(`${endpoints.violations}?limit=${limit}&type=${type}`),
  getPlates: (limit = 20) => config.useMocks
    ? Promise.resolve({ items: [] as VehicleDetection[], total: 0 })
    : request<{ items: VehicleDetection[]; total: number }>(`${endpoints.plates}?limit=${limit}`),
  getViolationSummary: () => config.useMocks ? Promise.resolve({ total: 0, counts: {}, latest: null }) :
    request<{ total: number; counts: Partial<Record<ViolationType, number>>; latest: ViolationEvent | null }>(endpoints.violationsSummary),
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
