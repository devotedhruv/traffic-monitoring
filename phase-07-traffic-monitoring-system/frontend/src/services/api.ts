import { config, endpoints } from "../lib/config";
import { getMockAnalytics, getMockSummary, getMockVehicles, mockVehicles } from "../mocks/data";
import type { AnalyticsData, AnalyticsRange, Camera, DashboardSummary, PaginatedVehicles, VehicleDetection, VehicleQuery, VideoAnalysisJob, VideoAnalysisOptions, VideoLinkAnalysisOptions } from "../types";

async function request<T>(path: string, init?: RequestInit): Promise<T> {
  const response = await fetch(`${config.apiBaseUrl}${path}`, {
    ...init,
    headers: { Accept: "application/json", ...init?.headers }
  });
  if (!response.ok) throw new Error(`Request failed (${response.status})`);
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
    headers: {
      Accept: "application/json",
      "Content-Type": file.type || "application/octet-stream"
    },
    body: file
  });
  if (!response.ok) {
    const payload = await response.json().catch(() => null) as { detail?: string } | null;
    throw new Error(payload?.detail || `Video upload failed (${response.status})`);
  }
  return response.json() as Promise<VideoAnalysisJob>;
}

async function startLinkVideoAnalysis(options: VideoLinkAnalysisOptions) {
  const response = await fetch(`${config.apiBaseUrl}${endpoints.videoAnalysisLink}`, {
    method: "POST",
    headers: {
      Accept: "application/json",
      "Content-Type": "application/json"
    },
    body: JSON.stringify(options)
  });
  if (!response.ok) {
    const payload = await response.json().catch(() => null) as { detail?: string | { msg?: string }[] } | null;
    const detail = Array.isArray(payload?.detail)
      ? payload.detail.map((item) => item.msg).filter(Boolean).join(", ")
      : payload?.detail;
    throw new Error(detail || `Video link could not be queued (${response.status})`);
  }
  return response.json() as Promise<VideoAnalysisJob>;
}

export const api = {
  getSummary: () => config.useMocks ? getMockSummary() : request<DashboardSummary>(endpoints.summary),
  getVehicles: (query: VehicleQuery) => config.useMocks ? getMockVehicles(query) : request<PaginatedVehicles>(`${endpoints.vehicles}?${queryString(query)}`),
  getVehicle: (id: number) => config.useMocks
    ? Promise.resolve(mockVehicles.find((vehicle) => vehicle.id === id) ?? null)
    : request<VehicleDetection>(endpoints.vehicle(id)),
  getAnalytics: (range: AnalyticsRange) => config.useMocks
    ? getMockAnalytics(range)
    : request<AnalyticsData>(`${endpoints.analytics}?range=${range}`),
  getCameras: () => config.useMocks
    ? Promise.resolve<Camera[]>([{ id: "camera-01", name: "North Junction", streamAvailable: false }])
    : request<Camera[]>(endpoints.cameras),
  getStreamUrl: (cameraId: string) => `${config.apiBaseUrl}${endpoints.stream(cameraId)}`,
  startVideoAnalysis,
  startLinkVideoAnalysis,
  getVideoAnalysis: (jobId: string) =>
    request<VideoAnalysisJob>(endpoints.videoAnalysisJob(jobId)),
  resolveApiUrl: (path: string) => path.startsWith("http") ? path : `${config.apiBaseUrl}${path}`
};
