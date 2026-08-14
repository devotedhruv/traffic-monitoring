import { beforeEach, describe, expect, it } from "vitest";
import { settingsStorage, validateSettings } from "../features/settings/settingsStorage";
import { createDefaultSettings } from "../features/settings/types";

describe("settings persistence", () => {
  beforeEach(() => window.localStorage.clear());

  it("stores and restores non-sensitive preferences", () => {
    const settings = createDefaultSettings("dark");
    settings.general.systemName = "Kathmandu Traffic Centre";
    settings.detection.confidence = 72;
    settingsStorage.save(settings);

    const restored = settingsStorage.load("system");
    expect(restored.general.systemName).toBe("Kathmandu Traffic Centre");
    expect(restored.general.theme).toBe("dark");
    expect(restored.detection.confidence).toBe(72);
  });

  it("rejects stream URLs with embedded credentials", () => {
    const settings = createDefaultSettings();
    settings.cameras.push({ id: "cam-1", name: "North", junction: "North Junction", streamUrl: "rtsp://admin:secret@camera.local/live", resolution: "1920x1080", fps: 25, enabled: true });
    expect(validateSettings(settings)).toContain("North has an invalid stream URL or embedded credentials.");
  });
});
