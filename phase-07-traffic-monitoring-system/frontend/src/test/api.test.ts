import { describe, expect, it } from "vitest";
import { config, endpoints } from "../lib/config";
import { getMockVehicles } from "../mocks/data";

describe("API configuration", () => {
  it("uses real API mode for the connected local environment", () => {
    expect(config.useMocks).toBe(false);
  });

  it("keeps endpoint paths centralized", () => {
    expect(endpoints.vehicle(12)).toBe("/api/vehicles/12");
    expect(endpoints.stream("camera-01")).toContain("camera-01");
  });

  it("returns deterministic filtered mock data", async () => {
    const data = await getMockVehicles({ page: 1, pageSize: 20, status: "OVERSPEED", type: "", search: "", sort: "time_desc" });
    expect(data.items.length).toBeGreaterThan(0);
    expect(data.items.every((item) => item.status === "OVERSPEED")).toBe(true);
  });
});
