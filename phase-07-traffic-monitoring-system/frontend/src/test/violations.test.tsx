import { cleanup, fireEvent, render, screen } from "@testing-library/react";
import { afterEach, describe, expect, it } from "vitest";
import { ViolationDetailsDrawer } from "../features/violations/ViolationDetailsDrawer";
import { ViolationFilters } from "../features/violations/ViolationFilters";
import { ViolationTable } from "../features/violations/ViolationTable";
import type { ViolationEvent, ViolationQuery } from "../types";

const query: ViolationQuery = { page: 1, pageSize: 20, type: "", vehicleType: "", search: "", date: "", camera: "", sort: "time_desc" };
const violation: ViolationEvent = {
  id: 17, vehicleId: 8, trackingId: 42, type: "OVERSPEED", confidence: 0.91,
  cameraId: "camera-01", cameraName: "North Junction", vehicleType: "car",
  laneId: 2, direction: "approaching", snapshotUrl: "/api/violations/17/evidence",
  detectedAt: "2026-08-12T10:00:00Z", plate: "BA 12 PA 1234", speed: 68.5,
  speedAvailable: true, speedLimit: 50, vehicleStatus: "OVERSPEED"
};

afterEach(cleanup);

describe("violation history", () => {
  it("filters violations and clears individual chips", () => {
    let current = { ...query };
    const change = (next: ViolationQuery) => { current = next; };
    const { rerender } = render(<ViolationFilters query={current} cameras={[{ id: "camera-01", name: "North Junction", streamAvailable: true }]} onChange={change} />);

    fireEvent.change(screen.getByLabelText("Filter by violation type"), { target: { value: "NO_HELMET" } });
    expect(current.type).toBe("NO_HELMET");
    rerender(<ViolationFilters query={current} cameras={[]} onChange={change} />);
    expect(screen.getByText("Violation: No helmet")).toBeInTheDocument();
    fireEvent.click(screen.getByText("Violation: No helmet"));
    expect(current.type).toBe("");
  });

  it("renders joined vehicle data, violation type, and evidence", () => {
    render(<ViolationTable data={{ items: [violation], total: 1, page: 1, pageSize: 20 }} query={query} onQueryChange={() => undefined} onSelect={() => undefined} />);

    expect(screen.getByText("BA 12 PA 1234")).toBeInTheDocument();
    expect(screen.getByText("Overspeed")).toBeInTheDocument();
    expect(screen.getByText(/68.5/)).toBeInTheDocument();
    expect(screen.getByText("Lane 2")).toBeInTheDocument();
    expect(screen.getByRole("link", { name: "Open evidence for violation 17" })).toHaveAttribute("href", "/api/violations/17/evidence");
  });

  it("shows an unavailable-capability empty state without fake records", () => {
    render(<ViolationTable data={{ items: [], total: 0, page: 1, pageSize: 20 }} query={query} capabilitiesUnavailable onQueryChange={() => undefined} onSelect={() => undefined} />);
    expect(screen.getByText("No confirmed violations yet")).toBeInTheDocument();
    expect(screen.getByText(/not configured/i)).toBeInTheDocument();
  });

  it("opens full violation details and matching vehicle history", () => {
    render(<ViolationDetailsDrawer violation={violation} onClose={() => undefined} />);

    expect(screen.getByRole("dialog")).toHaveTextContent("Event #17");
    expect(screen.getByRole("dialog")).toHaveTextContent("68.5 km/h");
    expect(screen.getByRole("link", { name: "Open full violation evidence" })).toHaveAttribute("href", "/api/violations/17/evidence");
    expect(screen.getByRole("link", { name: /open matching vehicle/i })).toHaveAttribute("href", "/app/history?search=BA%2012%20PA%201234");
  });
});
