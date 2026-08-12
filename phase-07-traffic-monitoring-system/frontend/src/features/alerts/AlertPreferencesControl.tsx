import { BellRing, Volume2, VolumeX } from "lucide-react";
import { useState } from "react";
import { playAlertTone, readAlertPreferences, saveAlertPreferences, type AlertPreferences } from "./alertNotifications";

export function AlertPreferencesControl() {
  const [preferences, setPreferences] = useState<AlertPreferences>(readAlertPreferences);
  const [permissionMessage, setPermissionMessage] = useState("");
  const update = (next: AlertPreferences) => {
    setPreferences(next);
    saveAlertPreferences(next);
  };
  const toggleSound = () => {
    const sound = !preferences.sound;
    update({ ...preferences, sound });
    if (sound) playAlertTone();
  };
  const toggleBrowser = async () => {
    if (!("Notification" in window)) {
      setPermissionMessage("Browser notifications are not supported here.");
      return;
    }
    if (!preferences.browser && Notification.permission !== "granted") {
      const permission = await Notification.requestPermission();
      if (permission !== "granted") {
        setPermissionMessage("Notification permission was not granted.");
        return;
      }
    }
    setPermissionMessage("");
    update({ ...preferences, browser: !preferences.browser });
  };
  return <div className="flex flex-wrap items-center gap-2">
    <button type="button" onClick={toggleSound} aria-pressed={preferences.sound} className="secondary-button h-9">{preferences.sound ? <Volume2 size={14} /> : <VolumeX size={14} />}Sound {preferences.sound ? "on" : "off"}</button>
    <button type="button" onClick={() => void toggleBrowser()} aria-pressed={preferences.browser} className="secondary-button h-9"><BellRing size={14} />Browser {preferences.browser ? "on" : "off"}</button>
    <label className="flex h-9 items-center gap-2 rounded-xl border border-border bg-surface px-3 text-[11px] text-muted"><input type="checkbox" checked={preferences.criticalOnly} onChange={(event) => update({ ...preferences, criticalOnly: event.target.checked })} className="accent-primary" />Critical only</label>
    {permissionMessage && <span role="status" className="text-[10px] text-warning">{permissionMessage}</span>}
  </div>;
}
