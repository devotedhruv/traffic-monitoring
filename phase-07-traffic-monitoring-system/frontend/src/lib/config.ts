const apiBaseUrl = (import.meta.env.VITE_API_BASE_URL ?? "http://localhost:8000").replace(/\/$/, "");
const defaultWebSocketUrl = typeof window === "undefined"
  ? "ws://localhost:8000/ws/live"
  : `${window.location.protocol === "https:" ? "wss:" : "ws:"}//${window.location.host}/ws/live`;

export const config = {
  apiBaseUrl,
  wsUrl: import.meta.env.VITE_WS_URL || defaultWebSocketUrl,
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
