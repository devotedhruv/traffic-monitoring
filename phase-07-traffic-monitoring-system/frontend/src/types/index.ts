export type VehicleStatus = "NORMAL" | "OVERSPEED";
export type ConnectionStatus = "connected" | "reconnecting" | "offline";
export type VehicleType = "car" | "motorcycle" | "bus" | "truck" | "unknown";
export type AnalyticsRange = "hour" | "today" | "week";
export type VideoAnalysisStatus = "queued" | "processing" | "completed" | "failed";

export interface AuthUser {
  id: number;
  name: string;
  email: string;
  createdAt: string;
}

export interface AuthResponse {
  user: AuthUser;
}

export interface NormalizedPoint {
  x: number;
  y: number;
}

export interface RoadCalibration {
  enabled: boolean;
  sourcePoints: NormalizedPoint[];
  roadWidthMeters: number;
  roadLengthMeters: number;
  laneCount: number;
  countingLinePosition: number;
  stabilize: boolean;
  analysisFps: number;
  tracker: "botsort.yaml" | "bytetrack.yaml";
  allowedDirection: "both" | "approaching" | "moving_away" | "left_to_right" | "right_to_left";
}

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
  confidence?: number | null;
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
  speed?: "" | "under_limit" | "over_limit";
  date?: "" | "today" | "week";
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

export interface VideoAnalysisOptions {
  location: string;
  speedLimit: number;
  metersPerPixel: number;
  calibration?: RoadCalibration;
}

export interface VideoLinkAnalysisOptions extends VideoAnalysisOptions {
  videoUrl: string;
  confirmedRights: boolean;
}

export interface AnalyzedVehicle {
  trackingId: number;
  vehicleType: string;
  color: string;
  plate: string | null;
  plateStatus: "NOT_AVAILABLE" | "RECOGNIZED";
  plateConfidence: number | null;
  lane: number | null;
  confidence: number;
  firstSeenSeconds: number;
  lastSeenSeconds: number;
  countedAtSeconds: number | null;
  trackedForSeconds: number;
  framesTracked: number;
  estimatedSpeed: number | null;
  peakSpeed: number | null;
  speedConfidence: "LOW" | "MEDIUM" | "HIGH";
  speedLimit: number;
  status: "NORMAL" | "OVERSPEED" | "INSUFFICIENT_DATA";
  direction: string;
  violations: string[];
}

export interface VideoAnalysisResult {
  video: {
    filename: string;
    mimeType: string;
    sizeBytes: number;
    durationSeconds: number;
    fps: number;
    width: number;
    height: number;
    totalFrames: number;
    analyzedFrames: number;
    location: string;
    sourceType: "upload" | "link";
    sourceUrl: string | null;
    sourcePlatform: string | null;
    sourceTitle: string | null;
    sourceUploader: string | null;
  };
  summary: {
    totalVehicles: number;
    lineCrossingVehicles: number;
    overspeedVehicles: number;
    averageSpeed: number | null;
    maxSpeed: number | null;
    speedLimit: number;
    peakTrafficAtSeconds: number | null;
  };
  vehicleTypes: { name: string; value: number }[];
  vehicleColors: { name: string; value: number }[];
  timeline: {
    label: string;
    startSeconds: number;
    detections: number;
    overspeed: number;
  }[];
  vehicles: AnalyzedVehicle[];
  artifacts: {
    annotatedVideoUrl: string | null;
    frameRate: number;
    containsSampledFrames: boolean;
  };
  capabilities: Record<string, {
    available: boolean;
    model?: string;
    method?: string;
    reason?: string | null;
  }>;
  analysis: {
    completedAt: string;
    processingSeconds: number;
    model: string;
    tracker: string;
    sampleEveryFrames: number;
    analysisFps: number;
    calibrationMetersPerPixel: number;
    perspectiveCalibrated: boolean;
    roadWidthMeters: number | null;
    roadLengthMeters: number | null;
    laneCount: number | null;
    speedMethod: string;
    speedIsEstimated: true;
    stabilizationEnabled: boolean;
    stabilizedFrames: number;
    plateRecognitionAvailable: boolean;
    note: string;
  };
}

export interface VideoAnalysisJob {
  id: string;
  filename: string;
  sourceType: "upload" | "link";
  status: VideoAnalysisStatus;
  progress: number;
  stage: string;
  result: VideoAnalysisResult | null;
  error: string | null;
  createdAt: string;
  updatedAt: string;
}
