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
  alerts: "/api/alerts",
  alertsSummary: "/api/alerts/summary",
  alertOperators: "/api/alerts/operators",
  alert: (alertId: number) => `/api/alerts/${alertId}`,
  alertAction: (alertId: number, action: string) => `/api/alerts/${alertId}/${action}`,
  reportTemplates: "/api/reports/templates",
  reports: "/api/reports",
  reportsSummary: "/api/reports/summary",
  generateReport: "/api/reports/generate",
  report: (reportId: number) => `/api/reports/${reportId}`,
  reportAction: (reportId: number, action: string) => `/api/reports/${reportId}/${action}`,
  reportDownload: (reportId: number, format: "pdf" | "csv") => `/api/reports/${reportId}/download?format=${format}`,
  reportSchedules: "/api/report-schedules",
  reportScheduleToggle: (scheduleId: number) => `/api/report-schedules/${scheduleId}/toggle`,
  cameraSettings: (cameraId: string) => `/api/cameras/${encodeURIComponent(cameraId)}/settings`,
  startBrowserCamera: "/api/cameras/browser/start",
  stopCamera: (cameraId: string) => `/api/cameras/${encodeURIComponent(cameraId)}/stop`,
  cameraCalibration: (cameraId: string) => `/api/cameras/${encodeURIComponent(cameraId)}/calibration`,
  cameraLanes: (cameraId: string) => `/api/cameras/${encodeURIComponent(cameraId)}/lanes`,
  stream: (cameraId: string) => `/api/cameras/${encodeURIComponent(cameraId)}/stream`,
  videoAnalysis: "/api/video-analysis",
  videoAnalysisJob: (jobId: string) => `/api/video-analysis/${encodeURIComponent(jobId)}`,
  junctions: "/api/junctions",
  junctionCameras: (junctionId: string) => `/api/junctions/${encodeURIComponent(junctionId)}/cameras`,
  cameraConfig: (cameraId: string) => `/api/cameras/${encodeURIComponent(cameraId)}`,
  addJunction: "/api/junctions",
  updateJunction: (junctionId: string) => `/api/junctions/${encodeURIComponent(junctionId)}/update`,
  deleteJunction: (junctionId: string) => `/api/junctions/${encodeURIComponent(junctionId)}/delete`,
  addCamera: (junctionId: string) => `/api/junctions/${encodeURIComponent(junctionId)}/cameras`,
  updateCamera: (cameraId: string) => `/api/cameras/${encodeURIComponent(cameraId)}/update`,
  deleteCamera: (cameraId: string) => `/api/cameras/${encodeURIComponent(cameraId)}/delete`,
  demoVideos: "/api/demo-videos",
  addDemoVideo: "/api/demo-videos",
  updateDemoVideo: (videoId: string) => `/api/demo-videos/${encodeURIComponent(videoId)}/update`,
  deleteDemoVideo: (videoId: string) => `/api/demo-videos/${encodeURIComponent(videoId)}/delete`,
  demoScenarios: "/api/demo/scenarios",
  demoStatus: "/api/demo/status",
  demoStart: "/api/demo/start",
  demoStop: "/api/demo/stop",
  demoPause: "/api/demo/pause",
  demoResume: "/api/demo/resume",
  demoRestart: "/api/demo/restart"
};
