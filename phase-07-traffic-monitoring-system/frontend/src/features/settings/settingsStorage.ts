import type { ThemePreference } from "../../app/ThemeContext";
import { createDefaultSettings, type TrafficOpsSettings } from "./types";

const STORAGE_KEY = "trafficops-settings-v1";

function isRecord(value: unknown): value is Record<string, unknown> {
  return Boolean(value) && typeof value === "object" && !Array.isArray(value);
}

function mergeSettings(defaults: TrafficOpsSettings, stored: unknown): TrafficOpsSettings {
  if (!isRecord(stored)) return defaults;
  const merged = structuredClone(defaults);
  const source = stored as Partial<TrafficOpsSettings>;

  for (const key of ["general", "recording", "integrations", "privacy", "account"] as const) {
    if (isRecord(source[key])) Object.assign(merged[key], source[key]);
  }
  if (isRecord(source.detection)) {
    const { objects, violations, ...detection } = source.detection;
    Object.assign(merged.detection, detection);
    if (isRecord(objects)) Object.assign(merged.detection.objects, objects);
    if (isRecord(violations)) Object.assign(merged.detection.violations, violations);
  }
  if (isRecord(source.alerts)) {
    const { alertTypes, ...alerts } = source.alerts;
    Object.assign(merged.alerts, alerts);
    if (isRecord(alertTypes)) Object.assign(merged.alerts.alertTypes, alertTypes);
  }
  merged.general.language = merged.general.language === "ne" ? "ne" : "en";
  if (merged.general.systemName === "TrafficOps AI") merged.general.systemName = "SadakDrishti";
  if (Array.isArray(source.cameras)) merged.cameras = source.cameras.filter((camera): camera is TrafficOpsSettings["cameras"][number] => isRecord(camera) && typeof camera.id === "string" && typeof camera.name === "string" && typeof camera.junction === "string" && typeof camera.streamUrl === "string" && typeof camera.fps === "number" && typeof camera.enabled === "boolean" && typeof camera.resolution === "string");
  if (Array.isArray(source.users)) merged.users = source.users.filter((user): user is TrafficOpsSettings["users"][number] => isRecord(user) && typeof user.id === "string" && typeof user.name === "string" && typeof user.email === "string" && typeof user.role === "string" && typeof user.status === "string" && Array.isArray(user.junctionAccess));
  return merged;
}

export const settingsStorage = {
  hasSavedSettings: () => window.localStorage.getItem(STORAGE_KEY) !== null,
  load(theme: ThemePreference = "system") {
    const defaults = createDefaultSettings(theme);
    try {
      const stored = window.localStorage.getItem(STORAGE_KEY);
      return stored ? mergeSettings(defaults, JSON.parse(stored) as unknown) : defaults;
    } catch {
      return defaults;
    }
  },
  save(settings: TrafficOpsSettings) {
    window.localStorage.setItem(STORAGE_KEY, JSON.stringify(settings));
  },
  reset() {
    window.localStorage.removeItem(STORAGE_KEY);
  }
};

function validEndpoint(value: string, protocols: string[]) {
  if (!value.trim()) return true;
  try {
    const parsed = new URL(value);
    return protocols.includes(parsed.protocol) && !parsed.username && !parsed.password;
  } catch {
    return false;
  }
}

export function validateSettings(settings: TrafficOpsSettings): string[] {
  const errors: string[] = [];
  if (!settings.general.systemName.trim()) errors.push("System name is required.");
  if (!settings.account.name.trim()) errors.push("Account display name is required.");
  if (!/^\S+@\S+\.\S+$/.test(settings.account.email)) errors.push("Account email address is invalid.");
  if (settings.general.refreshInterval < 5 || settings.general.refreshInterval > 300) errors.push("Refresh interval must be between 5 and 300 seconds.");
  if (settings.detection.confidence < 1 || settings.detection.confidence > 100) errors.push("Detection confidence must be between 1 and 100 percent.");
  if (settings.detection.speedLimit < 5 || settings.detection.speedLimit > 200) errors.push("Speed limit must be between 5 and 200 km/h.");
  if (settings.alerts.cooldownMinutes < 0 || settings.alerts.cooldownMinutes > 1440) errors.push("Alert cooldown must be between 0 and 1,440 minutes.");
  if (settings.recording.retentionDays < 1 || settings.recording.retentionDays > 3650) errors.push("Retention must be between 1 and 3,650 days.");
  if (settings.recording.evidenceClipSeconds < 5 || settings.recording.evidenceClipSeconds > 300) errors.push("Evidence clips must be between 5 and 300 seconds.");
  if (settings.privacy.sessionTimeoutMinutes < 5 || settings.privacy.sessionTimeoutMinutes > 1440) errors.push("Session timeout must be between 5 and 1,440 minutes.");
  if (settings.integrations.webhookUrl && !validEndpoint(settings.integrations.webhookUrl, ["http:", "https:"])) errors.push("Webhook must be a valid HTTP(S) URL without embedded credentials.");
  settings.cameras.forEach((camera) => {
    if (!camera.name.trim() || !camera.junction.trim()) errors.push(`Camera ${camera.name || camera.id} needs a name and junction.`);
    if (camera.streamUrl && !validEndpoint(camera.streamUrl, ["rtsp:", "rtsps:", "http:", "https:"])) errors.push(`${camera.name || camera.id} has an invalid stream URL or embedded credentials.`);
    if (camera.fps < 1 || camera.fps > 120) errors.push(`${camera.name || camera.id} FPS must be between 1 and 120.`);
  });
  settings.users.forEach((user) => {
    if (!user.name.trim() || !/^\S+@\S+\.\S+$/.test(user.email)) errors.push(`${user.name || "A user"} needs a valid name and email address.`);
  });
  return [...new Set(errors)];
}
