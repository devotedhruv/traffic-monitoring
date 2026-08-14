import type { ThemePreference } from "../../app/ThemeContext";

export type SettingsSectionId =
  | "general"
  | "cameras"
  | "detection"
  | "alerts"
  | "users"
  | "recording"
  | "integrations"
  | "privacy"
  | "health"
  | "account"
  | "danger";

export type UserRole = "Admin" | "Operator" | "Viewer";
export type UserStatus = "Active" | "Suspended";

export interface ManagedCamera {
  id: string;
  name: string;
  junction: string;
  streamUrl: string;
  resolution: "1280x720" | "1920x1080" | "2560x1440" | "3840x2160";
  fps: number;
  enabled: boolean;
}

export interface ManagedUser {
  id: string;
  name: string;
  email: string;
  role: UserRole;
  status: UserStatus;
  junctionAccess: string[];
}

export interface TrafficOpsSettings {
  general: {
    systemName: string;
    language: "en" | "ne";
    timezone: string;
    dateFormat: "MMM d, yyyy" | "dd/MM/yyyy" | "yyyy-MM-dd";
    timeFormat: "12h" | "24h";
    theme: ThemePreference;
    refreshInterval: number;
  };
  cameras: ManagedCamera[];
  detection: {
    objects: Record<"car" | "bike" | "bus" | "truck" | "pedestrian", boolean>;
    confidence: number;
    speedLimit: number;
    violations: Record<"overspeed" | "redLight" | "wrongLane" | "noHelmet", boolean>;
    plateRecognition: boolean;
    junctionOverrides: boolean;
  };
  alerts: {
    alertTypes: Record<"violation" | "cameraOffline" | "systemHealth", boolean>;
    minimumSeverity: "Low" | "Medium" | "High" | "Critical";
    email: boolean;
    sms: boolean;
    push: boolean;
    quietHoursEnabled: boolean;
    quietFrom: string;
    quietTo: string;
    cooldownMinutes: number;
    emergencyContactName: string;
    emergencyContactPhone: string;
  };
  users: ManagedUser[];
  recording: {
    retentionDays: number;
    evidenceClipSeconds: number;
    autoCleanup: boolean;
    exportFormat: "MP4" | "AVI" | "WebM";
    backupFrequency: "Never" | "Daily" | "Weekly" | "Monthly";
  };
  integrations: {
    trafficPoliceEnabled: boolean;
    webhookUrl: string;
    emailProvider: "Not configured" | "SMTP" | "SendGrid" | "Mailgun";
    smsProvider: "Not configured" | "Twilio" | "Sparrow SMS" | "Custom";
    mapProvider: "OpenStreetMap" | "Google Maps" | "Mapbox";
    gpsEnabled: boolean;
  };
  privacy: {
    blurFaces: boolean;
    blurPlates: boolean;
    sessionTimeoutMinutes: number;
    twoFactorPreferred: boolean;
    auditLogging: boolean;
    restrictUnknownDevices: boolean;
  };
  account: {
    name: string;
    email: string;
    phone: string;
    notifyAssignments: boolean;
    notifyReports: boolean;
  };
}

export const sectionCatalog: Array<{ id: SettingsSectionId; label: string; description: string; keywords: string }> = [
  { id: "general", label: "General", description: "Workspace, language and time", keywords: "site system language timezone date time refresh" },
  { id: "cameras", label: "Cameras & Junctions", description: "Video sources and monitored locations", keywords: "camera junction rtsp ip stream resolution fps connection location" },
  { id: "detection", label: "AI Detection", description: "Objects, confidence and violation rules", keywords: "ai car bike bus truck pedestrian confidence speed overspeed red light lane helmet plate recognition" },
  { id: "alerts", label: "Alerts & Notifications", description: "Severity, channels and quiet hours", keywords: "alert notification email sms push severity quiet emergency cooldown offline health" },
  { id: "users", label: "Users & Permissions", description: "Operators, roles and access", keywords: "user admin operator viewer permission role access account" },
  { id: "recording", label: "Recording & Data", description: "Retention, evidence and backups", keywords: "recording storage retention evidence clip cleanup export backup" },
  { id: "integrations", label: "Integrations", description: "Police, webhook, messaging and maps", keywords: "traffic police api webhook email sms provider map gps integration" },
  { id: "privacy", label: "Privacy & Security", description: "Blurring, sessions and audit controls", keywords: "privacy security blur face plate session two factor audit device" },
  { id: "health", label: "System Health", description: "Runtime status and diagnostics", keywords: "system health camera ai model cpu gpu storage connectivity diagnostic restart fps" },
  { id: "account", label: "Account", description: "Profile and personal preferences", keywords: "profile contact password logout devices notification account" },
  { id: "danger", label: "Danger Zone", description: "Reset locally stored configuration", keywords: "danger reset remove clear configuration delete" }
];

export function createDefaultSettings(theme: ThemePreference = "system"): TrafficOpsSettings {
  const detectedTimezone = Intl.DateTimeFormat().resolvedOptions().timeZone || "Asia/Kathmandu";
  return {
    general: {
      systemName: "SadakDrishti",
      language: "en",
      timezone: detectedTimezone,
      dateFormat: "MMM d, yyyy",
      timeFormat: "12h",
      theme,
      refreshInterval: 15
    },
    cameras: [],
    detection: {
      objects: { car: true, bike: true, bus: true, truck: true, pedestrian: true },
      confidence: 65,
      speedLimit: 50,
      violations: { overspeed: true, redLight: false, wrongLane: false, noHelmet: false },
      plateRecognition: false,
      junctionOverrides: false
    },
    alerts: {
      alertTypes: { violation: true, cameraOffline: true, systemHealth: true },
      minimumSeverity: "Medium",
      email: true,
      sms: false,
      push: true,
      quietHoursEnabled: false,
      quietFrom: "22:00",
      quietTo: "06:00",
      cooldownMinutes: 5,
      emergencyContactName: "",
      emergencyContactPhone: ""
    },
    users: [],
    recording: {
      retentionDays: 30,
      evidenceClipSeconds: 15,
      autoCleanup: true,
      exportFormat: "MP4",
      backupFrequency: "Weekly"
    },
    integrations: {
      trafficPoliceEnabled: false,
      webhookUrl: "",
      emailProvider: "Not configured",
      smsProvider: "Not configured",
      mapProvider: "OpenStreetMap",
      gpsEnabled: false
    },
    privacy: {
      blurFaces: true,
      blurPlates: false,
      sessionTimeoutMinutes: 30,
      twoFactorPreferred: false,
      auditLogging: true,
      restrictUnknownDevices: false
    },
    account: {
      name: "",
      email: "",
      phone: "",
      notifyAssignments: true,
      notifyReports: true
    }
  };
}
