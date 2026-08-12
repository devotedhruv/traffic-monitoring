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
    expect(endpoints.cameraLanes("camera-01")).toContain("/lanes");
    expect(endpoints.cameraCalibration("camera-01")).toContain("/calibration");
    expect(endpoints.startBrowserCamera).toBe("/api/cameras/browser/start");
    expect(endpoints.plates).toBe("/api/plates");
    expect(endpoints.violations).toBe("/api/violations");
    expect(endpoints.alerts).toBe("/api/alerts");
    expect(endpoints.alertAction(12, "resolve")).toBe("/api/alerts/12/resolve");
    expect(endpoints.reports).toBe("/api/reports");
    expect(endpoints.reportDownload(7, "pdf")).toBe("/api/reports/7/download?format=pdf");
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

  it("serializes violation history filters without changing the legacy endpoint", async () => {
    const fetchMock = vi.fn().mockResolvedValue({
      ok: true,
      status: 200,
      json: () => Promise.resolve({ items: [], total: 0, page: 2, pageSize: 20 })
    });
    vi.stubGlobal("fetch", fetchMock);

    await api.getViolationRecords({
      page: 2, pageSize: 20, type: "WRONG_LANE", vehicleType: "car",
      search: "BA 12", date: "week", camera: "camera-01", sort: "confidence_desc"
    });

    const url = String(fetchMock.mock.calls[0][0]);
    expect(url).toContain("/api/violations?");
    expect(url).toContain("page=2");
    expect(url).toContain("type=WRONG_LANE");
    expect(url).toContain("vehicleType=car");
    expect(url).toContain("search=BA+12");
    expect(url).toContain("date=week");
    expect(url).toContain("camera=camera-01");
    vi.unstubAllGlobals();
  });

  it("serializes the operational alert queue and workflow version", async () => {
    const fetchMock = vi.fn().mockResolvedValue({
      ok: true,
      status: 200,
      json: () => Promise.resolve({ items: [], total: 0, page: 1, pageSize: 20 })
    });
    vi.stubGlobal("fetch", fetchMock);

    await api.getAlerts({
      page: 1, pageSize: 20, status: "NEW", severity: "CRITICAL",
      type: "OVERSPEED", assignedTo: "me", search: "BA 12", sort: "severity"
    });
    await api.updateAlertStatus(42, "resolve", 7, "Reviewed evidence");

    const queueUrl = String(fetchMock.mock.calls[0][0]);
    expect(queueUrl).toContain("/api/alerts?");
    expect(queueUrl).toContain("status=NEW");
    expect(queueUrl).toContain("severity=CRITICAL");
    expect(queueUrl).toContain("assignedTo=me");
    expect(fetchMock.mock.calls[1][0]).toContain("/api/alerts/42/resolve");
    expect(fetchMock.mock.calls[1][1]).toEqual(expect.objectContaining({
      method: "POST",
      body: JSON.stringify({ expectedVersion: 7, note: "Reviewed evidence" })
    }));
    vi.unstubAllGlobals();
  });

  it("serializes report filters and generation requests", async () => {
    const fetchMock = vi.fn().mockResolvedValue({
      ok: true,
      status: 200,
      json: () => Promise.resolve({ items: [], total: 0, page: 2, pageSize: 20 })
    });
    vi.stubGlobal("fetch", fetchMock);

    await api.getReports({ page: 2, pageSize: 20, search: "morning", type: "TRAFFIC_SUMMARY", status: "READY", date: "week", sort: "oldest" });
    await api.generateReport({
      name: "Morning report", type: "TRAFFIC_SUMMARY", sections: ["kpis"],
      filters: { startAt: "2026-08-12T00:00:00Z", endAt: "2026-08-13T00:00:00Z", timezone: "Asia/Kathmandu", camera: "", vehicleType: "", violationType: "", alertSeverity: "", alertStatus: "", assignedTo: null }
    });

    expect(String(fetchMock.mock.calls[0][0])).toContain("/api/reports?page=2");
    expect(String(fetchMock.mock.calls[0][0])).toContain("type=TRAFFIC_SUMMARY");
    expect(fetchMock.mock.calls[1][0]).toContain("/api/reports/generate");
    expect(fetchMock.mock.calls[1][1]).toEqual(expect.objectContaining({ method: "POST" }));
    vi.unstubAllGlobals();
  });

});
