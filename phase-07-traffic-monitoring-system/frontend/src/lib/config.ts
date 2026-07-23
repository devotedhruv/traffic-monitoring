export const config = {
  apiBaseUrl: (import.meta.env.VITE_API_BASE_URL ?? "http://localhost:8000").replace(/\/$/, ""),
  wsUrl: import.meta.env.VITE_WS_URL ?? "ws://localhost:8000/ws/live",
  useMocks: (import.meta.env.VITE_USE_MOCKS ?? "true").toLowerCase() === "true"
};

export const endpoints = {
  health: "/api/health",
  summary: "/api/dashboard/summary",
  vehicles: "/api/vehicles",
  vehicle: (id: number) => `/api/vehicles/${id}`,
  analytics: "/api/analytics",
  cameras: "/api/cameras",
  stream: (cameraId: string) => `/api/cameras/${encodeURIComponent(cameraId)}/stream`
};
