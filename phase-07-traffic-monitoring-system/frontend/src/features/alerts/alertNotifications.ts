import type { AlertRecord } from "../../types";

export const ALERT_PREFERENCES_KEY = "trafficops-alert-preferences";

export interface AlertPreferences {
  sound: boolean;
  browser: boolean;
  criticalOnly: boolean;
}

export const defaultAlertPreferences: AlertPreferences = {
  sound: false,
  browser: false,
  criticalOnly: false
};

export function readAlertPreferences(): AlertPreferences {
  try {
    return { ...defaultAlertPreferences, ...JSON.parse(window.localStorage.getItem(ALERT_PREFERENCES_KEY) ?? "{}") };
  } catch {
    return defaultAlertPreferences;
  }
}

export function saveAlertPreferences(preferences: AlertPreferences) {
  window.localStorage.setItem(ALERT_PREFERENCES_KEY, JSON.stringify(preferences));
}

export function playAlertTone() {
  const Context = window.AudioContext ?? (window as typeof window & { webkitAudioContext?: typeof AudioContext }).webkitAudioContext;
  if (!Context) return;
  const context = new Context();
  const oscillator = context.createOscillator();
  const gain = context.createGain();
  oscillator.frequency.value = 720;
  gain.gain.setValueAtTime(0.06, context.currentTime);
  gain.gain.exponentialRampToValueAtTime(0.001, context.currentTime + 0.18);
  oscillator.connect(gain);
  gain.connect(context.destination);
  oscillator.start();
  oscillator.stop(context.currentTime + 0.18);
  oscillator.addEventListener("ended", () => { void context.close(); });
}

export function showAlertNotification(alert: AlertRecord) {
  if (!("Notification" in window) || Notification.permission !== "granted") return;
  const plate = alert.plate || `Track #${alert.trackingId}`;
  new Notification(`${alert.severity}: ${alert.type.replaceAll("_", " ")}`, {
    body: `${plate} · ${alert.cameraName} · ${alert.occurrenceCount} occurrence${alert.occurrenceCount === 1 ? "" : "s"}`,
    tag: `trafficops-alert-${alert.id}`
  });
}
