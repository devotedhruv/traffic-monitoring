const apiBaseUrl = (import.meta.env.VITE_API_BASE_URL ?? "http://localhost:8000").replace(/\/$/, "");

function webSocketUrlFromApiBase() {
  if (!apiBaseUrl && typeof window !== "undefined") {
    return `${window.location.protocol === "https:" ? "wss:" : "ws:"}//${window.location.host}/ws/live`;
  }
  const base = apiBaseUrl || "http://localhost:8000";
  return `${base.replace(/^http/, "ws")}/ws/live`;
}

export const config = {
  apiBaseUrl,
  wsUrl: import.meta.env.VITE_WS_URL || webSocketUrlFromApiBase(),
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
