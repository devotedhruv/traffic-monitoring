import { config, endpoints } from "../lib/config";
import { getMockAnalytics, getMockSummary, getMockVehicles, mockVehicles } from "../mocks/data";
import type { AnalyticsData, AnalyticsRange, Camera, DashboardSummary, PaginatedVehicles, VehicleDetection, VehicleQuery } from "../types";

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
    sort: query.sort ?? "time_desc"
  });
  return params.toString();
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
  getStreamUrl: (cameraId: string) => `${config.apiBaseUrl}${endpoints.stream(cameraId)}`
};
