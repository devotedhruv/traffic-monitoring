import { CarFront } from "lucide-react";
import { formatSpeed, formatTime, titleCase } from "../../lib/format";
import type { VehicleDetection } from "../../types";
import { StatusBadge } from "../../components/ui/StatusBadge";

export function ActiveVehicleCard({ vehicle }: { vehicle: VehicleDetection | null }) {
  if (!vehicle) return <div className="grid min-h-44 place-items-center p-5 text-center text-muted"><div><CarFront className="mx-auto mb-2 opacity-60" /><p className="text-sm">No vehicle detected yet</p><p className="mt-3 rounded bg-elevated px-3 py-2 text-[11px] font-bold">AWAITING DATA</p></div></div>;
  return (
    <div className="p-4">
      <dl className="grid grid-cols-2 gap-x-4 gap-y-3 text-sm">
        <div><dt className="text-xs text-muted">Tracking ID</dt><dd className="mt-0.5 font-semibold tabular-nums">#{vehicle.trackingId}</dd></div>
        <div><dt className="text-xs text-muted">Vehicle type</dt><dd className="mt-0.5 font-semibold">{titleCase(vehicle.vehicleType)}</dd></div>
        <div><dt className="text-xs text-muted">Plate</dt><dd className="mt-0.5 font-semibold">{vehicle.plate || "UNKNOWN"}</dd></div>
        <div><dt className="text-xs text-muted">Detected</dt><dd className="mt-0.5 tabular-nums">{formatTime(vehicle.detectedAt)}</dd></div>
        <div><dt className="text-xs text-muted">Speed</dt><dd className="mt-0.5 font-semibold tabular-nums">{formatSpeed(vehicle.speed)} km/h</dd></div>
        <div><dt className="text-xs text-muted">Limit</dt><dd className="mt-0.5 tabular-nums">{vehicle.speedLimit} km/h</dd></div>
        <div><dt className="text-xs text-muted">Speed confidence</dt><dd className="mt-0.5 font-semibold tabular-nums">{vehicle.speedConfidence == null ? "—" : `${Math.round(vehicle.speedConfidence * 100)}%`}</dd></div>
        <div><dt className="text-xs text-muted">Calibration</dt><dd className="mt-0.5 font-semibold">{vehicle.speedCalibration === "PERSPECTIVE_ESTIMATED" ? "Perspective estimate" : "Pixel-scale fallback"}</dd></div>
      </dl>
      <div className="mt-4"><StatusBadge status={vehicle.status} verbose /></div>
    </div>
  );
}
