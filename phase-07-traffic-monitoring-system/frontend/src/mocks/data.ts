import type { AnalyticsData, AnalyticsRange, CameraConfig, DashboardSummary, DemoVideo, Junction, PaginatedVehicles, VehicleDetection, VehicleQuery, VehicleStatus, VehicleType } from "../types";

const types: VehicleType[] = ["car", "motorcycle", "bicycle", "bus", "truck"];
const plates = ["BA 12 PA 1234", "BA 08 CHA 4421", "GA 03 PA 9022", null, "NA 05 KHA 7810"];
const baseTime = Date.now();

export const mockVehicles: VehicleDetection[] = Array.from({ length: 53 }, (_, index) => {
  const speed = 24 + ((index * 17) % 69);
  return {
    id: 1000 + index,
    trackingId: 220 + index,
    vehicleType: types[index % types.length],
    plate: plates[index % plates.length],
    speed,
    speedLimit: 50,
    status: speed > 50 ? "OVERSPEED" : "NORMAL",
    detectedAt: new Date(baseTime - index * 72_000).toISOString(),
    cameraId: "camera-01",
    cameraName: "North Junction"
  };
});

const delay = <T>(value: T, ms = 140) => new Promise<T>((resolve) => setTimeout(() => resolve(value), ms));

export async function getMockVehicles(query: VehicleQuery): Promise<PaginatedVehicles> {
  const needle = query.search?.trim().toLowerCase();
  let items = mockVehicles.filter((vehicle) =>
    (!query.status || vehicle.status === query.status) &&
    (!query.type || vehicle.vehicleType === query.type) &&
    (!query.speed || (query.speed === "over_limit" ? vehicle.speed > vehicle.speedLimit : vehicle.speed <= vehicle.speedLimit)) &&
    (!query.violation || vehicle.violations?.includes(query.violation)) &&
    (!query.date || Date.now() - new Date(vehicle.detectedAt).getTime() <= (query.date === "today" ? 86_400_000 : 604_800_000)) &&
    (!needle || (vehicle.plate ?? "unknown").toLowerCase().includes(needle) || String(vehicle.trackingId).includes(needle))
  );
  items = [...items].sort((a, b) => {
    if (query.sort === "speed_desc") return b.speed - a.speed;
    if (query.sort === "speed_asc") return a.speed - b.speed;
    if (query.sort === "time_asc") return a.detectedAt.localeCompare(b.detectedAt);
    return b.detectedAt.localeCompare(a.detectedAt);
  });
  const start = (query.page - 1) * query.pageSize;
  return delay({ items: items.slice(start, start + query.pageSize), total: items.length, page: query.page, pageSize: query.pageSize });
}

export async function getMockSummary(): Promise<DashboardSummary> {
  const overspeed = mockVehicles.filter((v) => v.status === "OVERSPEED");
  return delay({
    totalVehicles: mockVehicles.length,
    overspeedVehicles: overspeed.length,
    averageSpeed: mockVehicles.reduce((sum, v) => sum + v.speed, 0) / mockVehicles.length,
    maxSpeed: Math.max(...mockVehicles.map((v) => v.speed)),
    currentFps: 27.4,
    speedLimit: 50
  });
}

export async function getMockAnalytics(range: AnalyticsRange): Promise<AnalyticsData> {
  const count = range === "hour" ? 6 : range === "today" ? 8 : 7;
  const labels = range === "week"
    ? ["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"]
    : Array.from({ length: count }, (_, i) => `${String(8 + i * 2).padStart(2, "0")}:00`);
  return delay({
    timeline: labels.map((label, i) => ({ label, detections: 18 + ((i * 13) % 26), overspeed: 3 + ((i * 5) % 11) })),
    byType: types.map((name, i) => ({ name, value: [25, 13, 4, 6, 5][i] })),
    byStatus: [
      { name: "NORMAL" as VehicleStatus, value: 31 },
      { name: "OVERSPEED" as VehicleStatus, value: 22 }
    ],
    averageSpeed: 55.8,
    maxSpeed: 92
  });
}

let liveSequence = 0;
export function nextMockDetection(): VehicleDetection {
  liveSequence += 1;
  const speed = 32 + ((liveSequence * 19) % 61);
  return {
    id: 2000 + liveSequence,
    trackingId: 500 + liveSequence,
    vehicleType: types[liveSequence % types.length],
    plate: plates[liveSequence % plates.length],
    speed,
    speedLimit: 50,
    status: speed > 50 ? "OVERSPEED" : "NORMAL",
    detectedAt: new Date().toISOString(),
    cameraId: "camera-01",
    cameraName: "North Junction"
  };
}

export const mockJunctions: Junction[] = [
  { id: "north", name: "North Junction", location: "Birendranagar, Surkhet", description: "Main city entry point with highest mixed-traffic volume.", status: "ACTIVE", enabled: true, speedLimit: 50, cameraCount: 2, demoVideoCount: 0 },
  { id: "bus-park", name: "Surkhet Bus Park", location: "Bus Park Road, Birendranagar", description: "Bus and tempo loading zone with heavy pedestrian flow.", status: "ACTIVE", enabled: true, speedLimit: 30, cameraCount: 2, demoVideoCount: 0 },
  { id: "airport-chowk", name: "Airport Chowk", location: "Surkhet Airport Road", description: "Junction near Surkhet airport access road.", status: "ACTIVE", enabled: true, speedLimit: 50, cameraCount: 2, demoVideoCount: 0 },
  { id: "demo", name: "Demo Junction", location: "Showcase", description: "Pre-recorded scenarios for presentations and testing.", status: "ACTIVE", enabled: true, speedLimit: 50, cameraCount: 2, demoVideoCount: 7 }
];

export const mockCameras: CameraConfig[] = [
  { id: "north-cam-01", junctionId: "north", junctionName: "North Junction", name: "Camera 01", sourceType: "live", videoUrl: "", speedLimit: null, enabled: true },
  { id: "north-cam-02", junctionId: "north", junctionName: "North Junction", name: "Camera 02", sourceType: "live", videoUrl: "", speedLimit: null, enabled: true },
  { id: "bus-park-cam-01", junctionId: "bus-park", junctionName: "Surkhet Bus Park", name: "Camera 01", sourceType: "live", videoUrl: "", speedLimit: null, enabled: true },
  { id: "bus-park-cam-02", junctionId: "bus-park", junctionName: "Surkhet Bus Park", name: "Camera 02", sourceType: "live", videoUrl: "", speedLimit: null, enabled: true },
  { id: "airport-cam-01", junctionId: "airport-chowk", junctionName: "Airport Chowk", name: "Camera 01", sourceType: "live", videoUrl: "", speedLimit: null, enabled: true },
  { id: "airport-cam-02", junctionId: "airport-chowk", junctionName: "Airport Chowk", name: "Camera 02", sourceType: "live", videoUrl: "", speedLimit: null, enabled: true },
  { id: "demo-cam-01", junctionId: "demo", junctionName: "Demo Junction", name: "Camera 01", sourceType: "demo", videoUrl: "", speedLimit: null, enabled: true },
  { id: "demo-cam-02", junctionId: "demo", junctionName: "Demo Junction", name: "Camera 02", sourceType: "demo", videoUrl: "", speedLimit: null, enabled: true }
];

export const mockDemoVideos: DemoVideo[] = [
  { id: "demo-normal", junctionId: "demo", cameraId: "demo-cam-01", title: "Normal Traffic", description: "Steady mixed traffic moving within the speed limit.", filename: "normal_traffic.mp4", scenario: "normal", duration: 42, speedLimit: 50, enabled: true, available: false, previewUrl: null },
  { id: "demo-helmet", junctionId: "demo", cameraId: "demo-cam-01", title: "Helmet Violation", description: "Motorcyclists riding without helmets at the junction.", filename: "helmet_violation.mp4", scenario: "helmet", duration: 38, speedLimit: 50, enabled: true, available: false, previewUrl: null },
  { id: "demo-overspeed", junctionId: "demo", cameraId: "demo-cam-01", title: "Overspeed Detection", description: "Vehicles exceeding the junction speed limit.", filename: "overspeed.mp4", scenario: "overspeed", duration: 45, speedLimit: 50, enabled: true, available: false, previewUrl: null },
  { id: "demo-wrong-lane", junctionId: "demo", cameraId: "demo-cam-02", title: "Wrong Lane", description: "Vehicles driving against the permitted lane direction.", filename: "wrong_lane.mp4", scenario: "wrong_lane", duration: 40, speedLimit: 50, enabled: true, available: false, previewUrl: null },
  { id: "demo-anpr", junctionId: "demo", cameraId: "demo-cam-02", title: "ANPR Demo", description: "Number-plate recognition of passing vehicles.", filename: "anpr_demo.mp4", scenario: "anpr", duration: 36, speedLimit: 50, enabled: true, available: false, previewUrl: null },
  { id: "demo-busy", junctionId: "demo", cameraId: "demo-cam-02", title: "Busy Junction", description: "Heavy congestion at peak evening hours.", filename: "busy_junction.mp4", scenario: "heavy", duration: 60, speedLimit: 50, enabled: true, available: false, previewUrl: null },
  { id: "demo-night", junctionId: "demo", cameraId: "demo-cam-02", title: "Night Traffic", description: "Low-light monitoring at night.", filename: "night_traffic.mp4", scenario: "night", duration: 52, speedLimit: 50, enabled: true, available: false, previewUrl: null }
];
