import { useEffect, useRef } from "react";
import { Camera, X } from "lucide-react";
import { formatDateTime, formatSpeed, titleCase } from "../../lib/format";
import type { VehicleDetection } from "../../types";
import { StatusBadge } from "../../components/ui/StatusBadge";

export function VehicleDetailsDrawer({ vehicle, onClose }: { vehicle: VehicleDetection | null; onClose: () => void }) {
  const close = useRef<HTMLButtonElement>(null);
  useEffect(() => {
    if (!vehicle) return;
    close.current?.focus();
    const escape = (event: KeyboardEvent) => { if (event.key === "Escape") onClose(); };
    document.addEventListener("keydown", escape);
    return () => document.removeEventListener("keydown", escape);
  }, [vehicle, onClose]);
  if (!vehicle) return null;
  const details = [
    ["Tracking ID", `#${vehicle.trackingId}`], ["Database record", `#${vehicle.id}`],
    ["Vehicle type", titleCase(vehicle.vehicleType)], ["Plate", vehicle.plate || "UNKNOWN"],
    ["Speed", `${formatSpeed(vehicle.speed)} km/h`], ["Speed limit", `${vehicle.speedLimit} km/h`],
    ["Detected", formatDateTime(vehicle.detectedAt)], ["Camera", vehicle.cameraName || vehicle.cameraId]
  ];
  return (
    <div className="fixed inset-0 z-50 bg-black/65" onMouseDown={(e) => { if (e.target === e.currentTarget) onClose(); }}>
      <aside role="dialog" aria-modal="true" aria-labelledby="vehicle-drawer-title" className="ml-auto flex h-full w-full max-w-md flex-col border-l border-line bg-surface shadow-2xl">
        <header className="flex items-center justify-between border-b border-line p-4"><div><p className="text-xs font-bold uppercase tracking-wider text-cyan">Detection detail</p><h2 id="vehicle-drawer-title" className="mt-1 text-lg font-bold">Vehicle #{vehicle.trackingId}</h2></div><button ref={close} onClick={onClose} className="rounded p-2 text-muted hover:bg-elevated hover:text-ink" aria-label="Close vehicle details"><X /></button></header>
        <div className="scrollbar-thin flex-1 overflow-y-auto p-4">
          {vehicle.snapshotUrl ? <img src={vehicle.snapshotUrl} alt={`Vehicle ${vehicle.trackingId} detection snapshot`} className="mb-4 aspect-video w-full rounded border border-line object-cover" /> : <div className="mb-4 grid aspect-video place-items-center rounded border border-line bg-page text-muted"><div className="text-center"><Camera className="mx-auto mb-2" /><span className="text-xs">No detection snapshot available</span></div></div>}
          <StatusBadge status={vehicle.status} verbose />
          <dl className="mt-5 divide-y divide-line rounded border border-line">{details.map(([label, value]) => <div key={label} className="flex justify-between gap-4 p-3 text-sm"><dt className="text-muted">{label}</dt><dd className="text-right font-medium tabular-nums">{value}</dd></div>)}</dl>
        </div>
      </aside>
    </div>
  );
}
