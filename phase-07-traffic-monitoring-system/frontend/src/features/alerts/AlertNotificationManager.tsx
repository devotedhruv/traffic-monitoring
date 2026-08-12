import { useEffect } from "react";
import type { AlertRecord } from "../../types";
import { playAlertTone, readAlertPreferences, showAlertNotification } from "./alertNotifications";

export function AlertNotificationManager() {
  useEffect(() => {
    const notify = (event: Event) => {
      const alert = (event as CustomEvent<AlertRecord>).detail;
      if (!alert) return;
      const preferences = readAlertPreferences();
      if (preferences.criticalOnly && alert.severity !== "CRITICAL") return;
      if (preferences.sound) playAlertTone();
      if (preferences.browser) showAlertNotification(alert);
    };
    window.addEventListener("trafficops:new-alert", notify);
    return () => window.removeEventListener("trafficops:new-alert", notify);
  }, []);
  return null;
}
