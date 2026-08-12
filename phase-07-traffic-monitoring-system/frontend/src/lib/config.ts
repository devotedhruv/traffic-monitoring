const apiBaseUrl = (import.meta.env.VITE_API_BASE_URL ?? "").replace(/\/$/, "");

function webSocketUrlFromApiBase(path = "/ws/live") {
  if (!apiBaseUrl && typeof window !== "undefined") {
    return `${window.location.protocol === "https:" ? "wss:" : "ws:"}//${window.location.host}${path}`;
  }
  const base = apiBaseUrl || "http://localhost:8000";
  return `${base.replace(/^http/, "ws")}${path}`;
}

export const config = {
  apiBaseUrl,
  wsUrl: import.meta.env.VITE_WS_URL || webSocketUrlFromApiBase(),
  useMocks: (import.meta.env.VITE_USE_MOCKS ?? "true").toLowerCase() === "true"
};

export function cameraIngestWebSocketUrl(cameraId: string) {
  const path = `/ws/cameras/${encodeURIComponent(cameraId)}/ingest`;
  try {
    const url = new URL(config.wsUrl);
    url.pathname = path;
    url.search = "";
    url.hash = "";
    return url.toString();
  } catch {
    return webSocketUrlFromApiBase(path);
  }
}

export const endpoints = {
  signUp: "/api/auth/signup",
  signIn: "/api/auth/signin",
  signOut: "/api/auth/signout",
  me: "/api/auth/me",
  health: "/api/health",
  summary: "/api/dashboard/summary",
  vehicles: "/api/vehicles",
  plates: "/api/plates",
  vehicle: (id: number) => `/api/vehicles/${id}`,
  analytics: "/api/analytics",
  cameras: "/api/cameras",
  capabilities: "/api/capabilities",
  violations: "/api/violations",
  violationsSummary: "/api/violations/summary",
  cameraSettings: (cameraId: string) => `/api/cameras/${encodeURIComponent(cameraId)}/settings`,
  startBrowserCamera: "/api/cameras/browser/start",
  stopCamera: (cameraId: string) => `/api/cameras/${encodeURIComponent(cameraId)}/stop`,
  cameraCalibration: (cameraId: string) => `/api/cameras/${encodeURIComponent(cameraId)}/calibration`,
  cameraLanes: (cameraId: string) => `/api/cameras/${encodeURIComponent(cameraId)}/lanes`,
  stream: (cameraId: string) => `/api/cameras/${encodeURIComponent(cameraId)}/stream`,
  videoAnalysis: "/api/video-analysis",
  videoAnalysisJob: (jobId: string) => `/api/video-analysis/${encodeURIComponent(jobId)}`
};
