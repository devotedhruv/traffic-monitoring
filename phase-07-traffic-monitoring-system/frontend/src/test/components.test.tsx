import { cleanup, fireEvent, render, screen, waitFor } from "@testing-library/react";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { afterEach, describe, expect, it, vi } from "vitest";
import { ActiveVehicleCard } from "../features/dashboard/ActiveVehicleCard";
import { AlertsPanel } from "../features/dashboard/AlertsPanel";
import { LiveCamera } from "../features/dashboard/LiveCamera";
import { NumberPlatePanel } from "../features/dashboard/NumberPlatePanel";
import { SpeedGauge } from "../features/dashboard/SpeedGauge";
import { DetectionTable } from "../features/vehicles/DetectionTable";
import { VehicleDetailsDrawer } from "../features/vehicles/VehicleDetailsDrawer";
import { StatusBadge } from "../components/ui/StatusBadge";
import { UploadAnalysisPage } from "../pages/UploadAnalysisPage";
import type { VehicleDetection, VehicleQuery } from "../types";
import { api } from "../services/api";

const vehicle: VehicleDetection = {
  id: 1, trackingId: 42, vehicleType: "car", plate: "BA 12 PA 1234",
  speed: 68, speedLimit: 50, status: "OVERSPEED",
  detectedAt: "2026-07-23T10:00:00.000Z", cameraId: "camera-01"
};
const query: VehicleQuery = { page: 1, pageSize: 10, status: "", type: "", search: "", sort: "time_desc" };

afterEach(() => {
  cleanup();
  vi.restoreAllMocks();
});

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

  it("shows the snapshot captured for a detection record", () => {
    render(<VehicleDetailsDrawer vehicle={{ ...vehicle, snapshotUrl: "/api/vehicles/1/snapshot" }} onClose={vi.fn()} />);

    expect(screen.getByRole("img", { name: /at the moment it was detected/i })).toHaveAttribute("src", "/api/vehicles/1/snapshot");
    expect(screen.getByRole("link", { name: /open vehicle 42 detection snapshot/i })).toHaveAttribute("href", "/api/vehicles/1/snapshot");
  });

  it("labels a tracked vehicle whose speed is not ready yet", () => {
    const unmeasured = { ...vehicle, id: 2, speed: 0, speedAvailable: false };
    render(<DetectionTable data={{ items: [unmeasured], total: 1, page: 1, pageSize: 10 }} query={query} onQueryChange={vi.fn()} onSelect={vi.fn()} />);
    expect(screen.getByText("Not measured")).toBeInTheDocument();
  });

  it("updates active vehicle content", () => {
    const { rerender, container } = render(<ActiveVehicleCard vehicle={null} />);
    expect(container).toHaveTextContent("AWAITING DATA");
    rerender(<ActiveVehicleCard vehicle={vehicle} />);
    expect(container).toHaveTextContent("#42");
    expect(container).toHaveTextContent("BA 12 PA 1234");
  });

  it("shows a confirmed plate with its corresponding vehicle data", () => {
    render(<NumberPlatePanel vehicles={[{
      ...vehicle,
      plateConfidence: 0.91,
      plateStatus: "CONFIRMED",
      plateSnapshotUrl: "/api/vehicles/1/plate-image"
    }]} total={1} capability={{ available: true, reason: null }} />);

    expect(screen.getByText("BA 12 PA 1234")).toBeInTheDocument();
    expect(screen.getByText(/car · ID #42/i)).toBeInTheDocument();
    expect(screen.getByText("91%")).toBeInTheDocument();
    expect(screen.getByRole("link", { name: "Matching vehicle data" })).toHaveAttribute("href", "/app/history?search=BA%2012%20PA%201234");
  });

  it("does not fabricate number plates when the specialist is unavailable", () => {
    render(<NumberPlatePanel vehicles={[]} capability={{ available: false, reason: "Dedicated plate weights are missing" }} />);

    expect(screen.getByText("Plate recognition not configured")).toBeInTheDocument();
    expect(screen.getByText(/never guessed/i)).toBeInTheDocument();
  });

  it("reports unavailable specialists and renders a confirmed violation", () => {
    const unavailable = { available: false, reason: "Dedicated weights are not configured" };
    const { rerender } = render(<AlertsPanel latest={null} violations={[]} capabilities={{ helmetDetection: unavailable, wrongLaneDetection: unavailable }} />);
    expect(screen.getAllByText("Not configured")).toHaveLength(2);
    expect(screen.getByRole("link", { name: /view all/i })).toHaveAttribute("href", "/app/history");
    expect(screen.getAllByRole("link", { name: "View history" })[0]).toHaveAttribute("href", "/app/history?violation=NO_HELMET");
    expect(screen.getAllByRole("link", { name: "View history" })[1]).toHaveAttribute("href", "/app/history?violation=WRONG_LANE");

    rerender(<AlertsPanel latest={null} violations={[{
      id: 7, vehicleId: 1, trackingId: 42, type: "NO_HELMET", confidence: 0.88,
      cameraId: "camera-01", cameraName: "North Junction", vehicleType: "motorcycle",
      laneId: 1, direction: "approaching", snapshotUrl: "/api/violations/7/evidence",
      detectedAt: "2026-07-23T10:00:00.000Z"
    }]} capabilities={{ helmetDetection: { available: true, reason: null }, wrongLaneDetection: unavailable }} />);
    expect(screen.getByText("No helmet detected")).toBeInTheDocument();
    expect(screen.getByText(/88% confidence/)).toBeInTheDocument();
    expect(screen.getByRole("link", { name: "Evidence" })).toHaveAttribute("href", "/api/violations/7/evidence");
  });

  it("toggles a clean feed without changing detection settings", async () => {
    const getSettings = vi.spyOn(api, "getCameraSettings").mockResolvedValue({ confidence: 0.1, showOverlays: true, overlayFilters: ["all"] });
    const update = vi.spyOn(api, "updateCameraSettings").mockResolvedValue({ confidence: 0.1, showOverlays: false, overlayFilters: ["all"] });
    render(<LiveCamera cameraId="camera-01" cameraName="North Junction" connection="connected" fps={25} analysisFps={3} activeTracks={42} activeDetections={38} />);

    await waitFor(() => expect(getSettings).toHaveBeenCalledWith("camera-01"));
    fireEvent.click(screen.getByRole("button", { name: "Hide vehicle IDs and boxes" }));

    await waitFor(() => expect(update).toHaveBeenCalledWith("camera-01", { showOverlays: false }));
    expect(await screen.findByRole("button", { name: "Show vehicle IDs and boxes" })).toBeInTheDocument();
    expect(screen.getByText(/clean view enabled/i)).toHaveTextContent(/tracking remain/i);
  });

  it("applies selected object and violation filters to the live stream", async () => {
    vi.spyOn(api, "getCameraSettings").mockResolvedValue({ confidence: 0.25, showOverlays: true, overlayFilters: ["all"] });
    const update = vi.spyOn(api, "updateCameraSettings").mockResolvedValue({ confidence: 0.25, showOverlays: true, overlayFilters: ["car"] });
    render(<LiveCamera cameraId="camera-01" cameraName="North Junction" connection="connected" fps={25} analysisFps={3} activeTracks={42} activeDetections={38} />);

    await waitFor(() => expect(screen.getByRole("button", { name: "Filter live detections by All" })).toHaveAttribute("aria-pressed", "true"));
    fireEvent.click(screen.getByRole("button", { name: "Filter live detections by Car" }));

    await waitFor(() => expect(update).toHaveBeenCalledWith("camera-01", { overlayFilters: ["car"] }));
    expect(screen.getByRole("button", { name: "Filter live detections by Car" })).toHaveAttribute("aria-pressed", "true");
    expect(screen.getByText(/filtered to Car/i)).toHaveTextContent(/monitoring remains active/i);
  });

  it("offers bus and truck live overlay filters", async () => {
    vi.spyOn(api, "getCameraSettings").mockResolvedValue({ confidence: 0.25, showOverlays: true, overlayFilters: ["all"] });
    const update = vi.spyOn(api, "updateCameraSettings").mockResolvedValue({ confidence: 0.25, showOverlays: true, overlayFilters: ["bus"] });
    render(<LiveCamera cameraId="camera-01" cameraName="North Junction" connection="connected" fps={25} analysisFps={3} activeTracks={42} activeDetections={38} />);

    await waitFor(() => expect(screen.getByRole("button", { name: "Filter live detections by Bus" })).toBeInTheDocument());
    expect(screen.getByRole("button", { name: "Filter live detections by Truck" })).toBeInTheDocument();
    fireEvent.click(screen.getByRole("button", { name: "Filter live detections by Bus" }));

    await waitFor(() => expect(update).toHaveBeenCalledWith("camera-01", { overlayFilters: ["bus"] }));
    expect(screen.getByRole("button", { name: "Filter live detections by Bus" })).toHaveAttribute("aria-pressed", "true");
  });

  it("renders the manual video analysis workflow", () => {
    const client = new QueryClient({ defaultOptions: { queries: { retry: false } } });
    render(<QueryClientProvider client={client}><UploadAnalysisPage /></QueryClientProvider>);
    expect(screen.getByRole("heading", { name: /turn any road video/i })).toBeInTheDocument();
    expect(screen.getByRole("button", { name: /drop your video here/i })).toBeInTheDocument();
    expect(screen.getByRole("button", { name: /analyze traffic video/i })).toBeDisabled();
    expect(screen.queryByRole("button", { name: /video link/i })).not.toBeInTheDocument();
    expect(screen.queryByRole("textbox", { name: /public video url/i })).not.toBeInTheDocument();
    expect(screen.getByText(/four-point calibration required/i)).toBeInTheDocument();
  });
});
