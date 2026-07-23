import { fireEvent, render, screen } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";
import { ActiveVehicleCard } from "../features/dashboard/ActiveVehicleCard";
import { SpeedGauge } from "../features/dashboard/SpeedGauge";
import { DetectionTable } from "../features/vehicles/DetectionTable";
import { StatusBadge } from "../components/ui/StatusBadge";
import type { VehicleDetection, VehicleQuery } from "../types";

const vehicle: VehicleDetection = {
  id: 1, trackingId: 42, vehicleType: "car", plate: "BA 12 PA 1234",
  speed: 68, speedLimit: 50, status: "OVERSPEED",
  detectedAt: "2026-07-23T10:00:00.000Z", cameraId: "camera-01"
};
const query: VehicleQuery = { page: 1, pageSize: 10, status: "", type: "", search: "", sort: "time_desc" };

describe("operational UI", () => {
  it("marks gauge state below and above the limit", () => {
    const { rerender, container } = render(<SpeedGauge speed={45} limit={50} />);
    expect(container.firstChild).toHaveAttribute("data-state", "normal");
    rerender(<SpeedGauge speed={70} limit={50} />);
    expect(container.firstChild).toHaveAttribute("data-state", "overspeed");
  });

  it("shows both status variants", () => {
    const { rerender } = render(<StatusBadge status="NORMAL" />);
    expect(screen.getByText("NORMAL")).toBeInTheDocument();
    rerender(<StatusBadge status="OVERSPEED" />);
    expect(screen.getByText("OVERSPEED")).toBeInTheDocument();
  });

  it("renders an empty history state", () => {
    render(<DetectionTable data={{ items: [], total: 0, page: 1, pageSize: 10 }} query={query} onQueryChange={vi.fn()} onSelect={vi.fn()} />);
    expect(screen.getByText("No detections yet")).toBeInTheDocument();
  });

  it("opens a detection through accessible keyboard interaction", () => {
    const select = vi.fn();
    render(<DetectionTable data={{ items: [vehicle], total: 1, page: 1, pageSize: 10 }} query={query} onQueryChange={vi.fn()} onSelect={select} />);
    fireEvent.keyDown(screen.getByRole("button", { name: /view details/i }), { key: "Enter" });
    expect(select).toHaveBeenCalledWith(vehicle);
  });

  it("updates active vehicle content", () => {
    const { rerender, container } = render(<ActiveVehicleCard vehicle={null} />);
    expect(container).toHaveTextContent("AWAITING DATA");
    rerender(<ActiveVehicleCard vehicle={vehicle} />);
    expect(container).toHaveTextContent("#42");
    expect(container).toHaveTextContent("BA 12 PA 1234");
  });
});
