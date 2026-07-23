import { describe, expect, it } from "vitest";
import { config, endpoints } from "../lib/config";
import { api } from "../services/api";

describe("API configuration", () => {
  it("uses mock mode by default in development", () => {
    expect(config.useMocks).toBe(true);
  });

  it("keeps endpoint paths centralized", () => {
    expect(endpoints.vehicle(12)).toBe("/api/vehicles/12");
    expect(endpoints.stream("camera-01")).toContain("camera-01");
  });

  it("returns deterministic filtered mock data", async () => {
    const data = await api.getVehicles({ page: 1, pageSize: 20, status: "OVERSPEED", type: "", search: "", sort: "time_desc" });
    expect(data.items.length).toBeGreaterThan(0);
    expect(data.items.every((item) => item.status === "OVERSPEED")).toBe(true);
  });
});
