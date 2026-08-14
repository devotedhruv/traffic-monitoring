export type VehicleStatus = "NORMAL" | "OVERSPEED";
export type ViolationType = "OVERSPEED" | "NO_HELMET" | "WRONG_LANE" | "WRONG_DIRECTION";
export type ConnectionStatus = "connected" | "reconnecting" | "offline";
export type LiveOverlayFilter = "all" | "car" | "bike" | "bus" | "truck" | "person" | "violation" | "no_helmet" | "wrong_lane" | "overspeed";
export type VehicleType = "bicycle" | "car" | "motorcycle" | "bus" | "truck" | "unknown";
export type AnalyticsRange = "hour" | "today" | "week";
export type VideoAnalysisStatus = "queued" | "processing" | "completed" | "failed";
export type AlertSeverity = "LOW" | "MEDIUM" | "HIGH" | "CRITICAL";
export type AlertStatus = "NEW" | "ACKNOWLEDGED" | "INVESTIGATING" | "RESOLVED" | "FALSE_POSITIVE";
export type ReportType = "TRAFFIC_SUMMARY" | "VIOLATION_ENFORCEMENT" | "ALERT_RESPONSE" | "VEHICLE_FLOW" | "CAMERA_PERFORMANCE" | "CUSTOM";
export type ReportStatus = "GENERATING" | "READY" | "FAILED";
export type ReportFrequency = "DAILY" | "WEEKLY" | "MONTHLY";

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
  plateConfidence?: number | null;
  plateStatus?: "NOT_CONFIGURED" | "NOT_DETECTED" | "POSSIBLE" | "CONFIRMED";
  plateSnapshotUrl?: string | null;
  speed: number;
  speedLimit: number;
  status: VehicleStatus;
  detectedAt: string;
  cameraId: string;
  cameraName?: string;
  snapshotUrl?: string | null;
  confidence?: number | null;
  speedConfidence?: number | null;
  speedSamples?: number;
  speedCalibration?: "PERSPECTIVE_ESTIMATED" | "FALLBACK_PIXEL_SCALE" | "OUTSIDE_CALIBRATED_ZONE";
  speedAvailable?: boolean;
  violations?: ViolationType[];
}

export interface DashboardSummary {
  totalVehicles: number;
  overspeedVehicles: number;
  averageSpeed: number;
  maxSpeed: number;
  currentFps: number;
  speedLimit: number;
}

export interface SystemHealth {
  status: "healthy" | "degraded" | string;
  pipelineRunning: boolean;
  fps: number;
  analysisFps: number;
  sourceFps: number;
  loopCount: number;
  confidence: number;
  showOverlays: boolean;
  activeTracks: number;
  activeDetections: number;
  speedCalibration: string;
  speedProcessingMode: string;
  speedCalibrationQuality: number;
  roadWidthMeters: number | null;
  roadLengthMeters: number | null;
  sourceMode: string;
  browserConnected: boolean;
  capabilities: Record<string, unknown>;
  error: string | null;
}

export interface Camera {
  id: string;
  name: string;
  streamAvailable: boolean;
  sourceType?: "configured" | "browser";
  browserConnected?: boolean;
}

export interface LiveCameraCalibration {
  sourcePoints: NormalizedPoint[];
  roadWidthMeters: number;
  roadLengthMeters: number;
  laneCount: number;
  quality: number;
}

export interface CameraSettings {
  confidence: number;
  showOverlays: boolean;
  overlayFilters: LiveOverlayFilter[];
}

export interface LaneRule {
  laneId: number;
  minX: number;
  maxX: number;
  allowedDirection: "both" | "approaching" | "moving_away" | "left_to_right" | "right_to_left";
  allowedVehicleTypes: Exclude<VehicleType, "unknown">[];
  boundaryTolerance: number;
}

export interface ViolationEvent {
  id: number;
  vehicleId: number | null;
  trackingId: number;
  type: ViolationType;
  confidence: number;
  cameraId: string;
  cameraName?: string;
  vehicleType: VehicleType;
  laneId: number | null;
  direction: string | null;
  snapshotUrl: string | null;
  detectedAt: string;
  plate?: string | null;
  plateConfidence?: number | null;
  plateStatus?: "NOT_CONFIGURED" | "NOT_DETECTED" | "POSSIBLE" | "CONFIRMED" | null;
  speed?: number | null;
  speedAvailable?: boolean;
  speedLimit?: number;
  vehicleStatus?: VehicleStatus | null;
  vehicleSnapshotUrl?: string | null;
}

export interface ViolationQuery {
  page: number;
  pageSize: number;
  type?: ViolationType | "";
  vehicleType?: VehicleType | "";
  search?: string;
  date?: "" | "today" | "week";
  camera?: string;
  sort?: "time_desc" | "time_asc" | "speed_desc" | "confidence_desc";
}

export interface PaginatedViolations {
  items: ViolationEvent[];
  total: number;
  page: number;
  pageSize: number;
}

export interface ViolationSummary {
  total: number;
  counts: Partial<Record<ViolationType, number>>;
  latest: ViolationEvent | null;
}

export interface AlertAssignee {
  id: number;
  name: string;
  email: string;
}

export interface AlertActivity {
  id: number;
  action: string;
  fromStatus: AlertStatus | null;
  toStatus: AlertStatus | null;
  actorUserId: number | null;
  actorName: string;
  note: string | null;
  alertVersion: number;
  createdAt: string;
}

export interface AlertRecord {
  id: number;
  primaryViolationId: number;
  violationId: number;
  trackingId: number;
  cameraId: string;
  cameraName: string;
  type: ViolationType;
  severity: AlertSeverity;
  status: AlertStatus;
  assignedTo: AlertAssignee | null;
  occurrenceCount: number;
  firstOccurrenceAt: string;
  lastOccurrenceAt: string;
  acknowledgedAt: string | null;
  resolvedAt: string | null;
  resolutionNote: string | null;
  falsePositiveReason: string | null;
  version: number;
  createdAt: string;
  updatedAt: string;
  vehicleId: number | null;
  vehicleType: VehicleType;
  plate: string | null;
  plateConfidence: number | null;
  confidence: number;
  laneId: number | null;
  direction: string | null;
  speed: number | null;
  speedAvailable: boolean;
  speedLimit: number;
  snapshotUrl: string | null;
  detectedAt: string;
}

export interface AlertDetail extends AlertRecord {
  activity: AlertActivity[];
  occurrences: { violationId: number; occurredAt: string }[];
}

export interface AlertQuery {
  page: number;
  pageSize: number;
  status?: AlertStatus | "";
  severity?: AlertSeverity | "";
  type?: ViolationType | "";
  vehicleType?: VehicleType | "";
  camera?: string;
  assignedTo?: "" | "me" | "unassigned" | `${number}`;
  search?: string;
  date?: "" | "today" | "week";
  sort?: "newest" | "oldest" | "severity";
}

export interface PaginatedAlerts {
  items: AlertRecord[];
  total: number;
  page: number;
  pageSize: number;
}

export interface AlertSummary {
  total: number;
  new: number;
  unresolved: number;
  critical: number;
  resolvedToday: number;
  averageResponseSeconds: number | null;
  bySeverity: Partial<Record<AlertSeverity, number>>;
}

export interface ReportFilters {
  startAt: string;
  endAt: string;
  timezone: string;
  camera: string;
  vehicleType: VehicleType | "";
  violationType: ViolationType | "";
  alertSeverity: AlertSeverity | "";
  alertStatus: AlertStatus | "";
  assignedTo: number | null;
}

export interface ReportTemplate {
  type: ReportType;
  name: string;
  description: string;
  sections: string[];
}

export interface ReportSnapshot {
  schemaVersion: number;
  reportType: ReportType;
  generatedAt: string;
  timezone: string;
  filters: ReportFilters;
  sections: string[];
  speedLimit: number;
  dataNote: string;
  warnings: string[];
  sourceCounts: { vehicles: number; measuredSpeeds: number; violations: number; alerts: number };
  traffic: {
    totalDetections: number;
    measuredSpeedCount: number;
    averageSpeed: number | null;
    maximumSpeed: number | null;
    overspeedCount: number;
    overspeedPercentage: number;
    vehicleDistribution: { name: string; value: number }[];
    trafficTrend: { period: string; detections: number; overspeed: number }[];
    busiestPeriod: { period: string; detections: number; overspeed: number } | null;
    quietestPeriod: { period: string; detections: number; overspeed: number } | null;
    laneDirection: { laneId: number | null; direction: string | null; events: number }[];
  };
  comparison: { previousTotal: number; currentTotal: number; percentageChange: number | null };
  violations: { total: number; distribution: { type: ViolationType; count: number }[]; records: Record<string, unknown>[]; recordsTruncated: boolean };
  alerts: {
    total: number;
    criticalUnresolved: number;
    averageAcknowledgementSeconds: number | null;
    averageResolutionSeconds: number | null;
    byStatus: { name: AlertStatus; value: number }[];
    bySeverity: { name: AlertSeverity; value: number }[];
    records: Record<string, unknown>[];
    auditSummary: { action: string; count: number }[];
    recordsTruncated: boolean;
  };
  camera: {
    cameraId: string;
    cameraName: string;
    runtimeStatus: string;
    analysisFps: number | null;
    analysisFpsHistorical: boolean;
    calibrationConfigured: boolean | null;
    evidenceCaptures: number;
    capabilities: Record<string, Capability>;
  };
}

export interface ReportRecord {
  id: number;
  definitionId: number | null;
  name: string;
  type: ReportType;
  status: ReportStatus;
  filters: ReportFilters;
  sections: string[];
  creator: AuthUser;
  createdAt: string;
  completedAt: string | null;
  failureReason: string | null;
  sourceCounts: Partial<ReportSnapshot["sourceCounts"]>;
  version: number;
  availableFormats: Array<"pdf" | "csv">;
  snapshot?: ReportSnapshot | null;
}

export interface ReportQuery {
  page: number;
  pageSize: number;
  search?: string;
  type?: ReportType | "";
  status?: ReportStatus | "";
  creator?: number | null;
  date?: "" | "today" | "week";
  sort?: "newest" | "oldest";
}

export interface ReportSummary {
  total: number;
  ready: number;
  failed: number;
  scheduled: number;
  thisMonth: number;
}

export interface ReportSchedule {
  id: number;
  name: string;
  type: ReportType;
  frequency: ReportFrequency;
  generationTime: string;
  timezone: string;
  filters: Omit<ReportFilters, "startAt" | "endAt" | "timezone">;
  sections: string[];
  enabled: boolean;
  lastRunAt: string | null;
  nextRunAt: string;
  creator: AuthUser;
  createdAt: string;
  updatedAt: string;
  delivery: "Not configured";
}

export interface Capability {
  available: boolean;
  reason: string | null;
  model?: string | null;
  method?: string | null;
}

export interface ViolationCapabilities {
  plateRecognition: Capability;
  helmetDetection: Capability;
  wrongLaneDetection: Capability;
  wrongDirectionDetection: Capability;
}

export interface VehicleQuery {
  page: number;
  pageSize: number;
  status?: VehicleStatus | "";
  type?: VehicleType | "";
  search?: string;
  speed?: "" | "under_limit" | "over_limit";
  date?: "" | "today" | "week";
  violation?: ViolationType | "";
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

export interface LiveViolationEvent {
  type: "violation_event";
  data: ViolationEvent;
}

export interface LiveAlertEvent {
  type: "alert_event";
  data: AlertRecord;
}

export interface SystemStatusEvent {
  type: "system_status";
  data: {
    connection: ConnectionStatus;
    fps: number;
    analysisFps?: number;
    activeTracks?: number;
    activeDetections?: number;
    speedCalibration?: string;
    cameraId: string;
    timestamp: string;
  };
}

export type LiveEvent = LiveDetectionEvent | LiveViolationEvent | LiveAlertEvent | SystemStatusEvent;

export interface VideoAnalysisOptions {
  location: string;
  speedLimit: number;
  metersPerPixel: number;
  calibration?: RoadCalibration;
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
  speedSamples: number;
  estimatedSpeed: number | null;
  peakSpeed: number | null;
  speedConfidence: "LOW" | "MEDIUM" | "HIGH";
  speedLimit: number;
  status: "NORMAL" | "OVERSPEED" | "INSUFFICIENT_DATA";
  direction: string;
  violations: VideoAnalysisViolationType[];
}

export type VideoAnalysisViolationType = "OVERSPEED" | "NO_HELMET" | "WRONG_DIRECTION" | "WRONG_LANE";

export interface VideoAnalysisViolation {
  id: string;
  trackingId: number;
  type: VideoAnalysisViolationType;
  vehicleType: string;
  plate: string | null;
  lane: number | null;
  direction: string;
  speed: number | null;
  speedLimit: number;
  confidence: number;
  detectedAtSeconds: number;
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
    totalViolations?: number;
    violationCounts?: Partial<Record<VideoAnalysisViolationType, number>>;
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
  violations?: VideoAnalysisViolation[];
  artifacts: {
    annotatedVideoUrl: string | null;
    frameRate: number;
    containsSampledFrames: boolean;
  };
  capabilities: Record<string, {
    available: boolean;
    model?: string;
    method?: string | null;
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
