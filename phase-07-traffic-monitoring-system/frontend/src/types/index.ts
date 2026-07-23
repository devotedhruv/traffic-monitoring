export type VehicleStatus = "NORMAL" | "OVERSPEED";
export type ConnectionStatus = "connected" | "reconnecting" | "offline";
export type VehicleType = "car" | "motorcycle" | "bus" | "truck" | "unknown";
export type AnalyticsRange = "hour" | "today" | "week";

export interface VehicleDetection {
  id: number;
  trackingId: number;
  vehicleType: VehicleType;
  plate: string | null;
  speed: number;
  speedLimit: number;
  status: VehicleStatus;
  detectedAt: string;
  cameraId: string;
  cameraName?: string;
  snapshotUrl?: string | null;
}

export interface DashboardSummary {
  totalVehicles: number;
  overspeedVehicles: number;
  averageSpeed: number;
  maxSpeed: number;
  currentFps: number;
  speedLimit: number;
}

export interface Camera {
  id: string;
  name: string;
  streamAvailable: boolean;
}

export interface VehicleQuery {
  page: number;
  pageSize: number;
  status?: VehicleStatus | "";
  type?: VehicleType | "";
  search?: string;
  sort?: "time_desc" | "time_asc" | "speed_desc" | "speed_asc";
}

export interface PaginatedVehicles {
  items: VehicleDetection[];
  total: number;
  page: number;
  pageSize: number;
}

export interface AnalyticsData {
  timeline: { label: string; detections: number; overspeed: number }[];
  byType: { name: string; value: number }[];
  byStatus: { name: VehicleStatus; value: number }[];
  averageSpeed: number;
  maxSpeed: number;
}

export interface LiveDetectionEvent {
  type: "vehicle_detection";
  data: VehicleDetection;
}

export interface SystemStatusEvent {
  type: "system_status";
  data: {
    connection: ConnectionStatus;
    fps: number;
    cameraId: string;
    timestamp: string;
  };
}

export type LiveEvent = LiveDetectionEvent | SystemStatusEvent;
