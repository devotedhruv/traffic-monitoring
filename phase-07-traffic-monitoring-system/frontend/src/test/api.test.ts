import { describe, expect, it, vi } from "vitest";
import { config, endpoints } from "../lib/config";
import { getMockVehicles } from "../mocks/data";
import { api } from "../services/api";

describe("API configuration", () => {
  it("uses real API mode for the connected local environment", () => {
    expect(config.useMocks).toBe(false);
  });

  it("keeps endpoint paths centralized", () => {
    expect(endpoints.vehicle(12)).toBe("/api/vehicles/12");
    expect(endpoints.stream("camera-01")).toContain("camera-01");
    expect(endpoints.videoAnalysisLink).toBe("/api/video-analysis/link");
    expect(endpoints.videoAnalysisJob("job 12")).toBe("/api/video-analysis/job%2012");
  });

  it("returns deterministic filtered mock data", async () => {
    const data = await getMockVehicles({ page: 1, pageSize: 20, status: "OVERSPEED", type: "", search: "", sort: "time_desc" });
    expect(data.items.length).toBeGreaterThan(0);
    expect(data.items.every((item) => item.status === "OVERSPEED")).toBe(true);
  });

  it("sends an uploaded video as the analysis request body", async () => {
    const fetchMock = vi.fn().mockResolvedValue({
      ok: true,
      json: () => Promise.resolve({ id: "job-1", status: "queued" })
    });
    vi.stubGlobal("fetch", fetchMock);
    const file = new File(["video-bytes"], "road clip.mp4", { type: "video/mp4" });

    await api.startVideoAnalysis(file, {
      location: "Ring Road",
      speedLimit: 50,
      metersPerPixel: 0.05,
      calibration: {
        enabled: true,
        sourcePoints: [{ x: 0.3, y: 0.3 }, { x: 0.7, y: 0.3 }, { x: 0.9, y: 0.9 }, { x: 0.1, y: 0.9 }],
        roadWidthMeters: 8,
        roadLengthMeters: 30,
        laneCount: 2,
        countingLinePosition: 0.62,
        stabilize: true,
        analysisFps: 15,
        tracker: "botsort.yaml",
        allowedDirection: "both"
      }
    });

    expect(fetchMock).toHaveBeenCalledWith(
      expect.stringContaining("/api/video-analysis?"),
      expect.objectContaining({ method: "POST", body: file })
    );
    expect(fetchMock.mock.calls[0][0]).toContain("filename=road+clip.mp4");
    expect(fetchMock.mock.calls[0][0]).toContain("calibration=");
    vi.unstubAllGlobals();
  });

  it("queues a public video link with rights confirmation", async () => {
    const fetchMock = vi.fn().mockResolvedValue({
      ok: true,
      json: () => Promise.resolve({ id: "job-link", status: "queued", sourceType: "link" })
    });
    vi.stubGlobal("fetch", fetchMock);

    await api.startLinkVideoAnalysis({
      videoUrl: "https://www.youtube.com/watch?v=road",
      location: "Ring Road",
      speedLimit: 50,
      metersPerPixel: 0.05,
      confirmedRights: true
    });

    expect(fetchMock).toHaveBeenCalledWith(
      expect.stringContaining("/api/video-analysis/link"),
      expect.objectContaining({ method: "POST" })
    );
    expect(fetchMock.mock.calls[0][1]?.body).toContain("\"confirmedRights\":true");
    vi.unstubAllGlobals();
  });
});
