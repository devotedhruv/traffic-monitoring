import { ChevronLeft, ChevronRight } from "lucide-react";
import { EmptyState, ErrorState, LoadingSkeleton } from "../../components/ui/States";
import { StatusBadge } from "../../components/ui/StatusBadge";
import { formatDateTime, formatSpeed, titleCase } from "../../lib/format";
import type { PaginatedVehicles, VehicleDetection, VehicleQuery } from "../../types";

export function DetectionTable({ data, query, loading, error, onQueryChange, onSelect }: { data?: PaginatedVehicles; query: VehicleQuery; loading?: boolean; error?: boolean; onQueryChange: (next: VehicleQuery) => void; onSelect: (vehicle: VehicleDetection) => void }) {
  if (loading) return <div className="space-y-2 p-4"><LoadingSkeleton /><LoadingSkeleton /><LoadingSkeleton /></div>;
  if (error) return <ErrorState message="Detection history could not be loaded. Check the API connection and try again." />;
  if (!data?.items.length) return <EmptyState title={query.search || query.status || query.type ? "No matching detections" : "No detections yet"} message={query.search || query.status || query.type ? "Adjust or clear the current filters." : undefined} />;
  const pages = Math.max(1, Math.ceil(data.total / query.pageSize));
  return (
    <>
      <div className="hidden max-h-[520px] overflow-auto md:block scrollbar-thin">
        <table className="w-full min-w-[820px] border-collapse text-left text-sm">
          <thead className="sticky top-0 z-10 bg-elevated text-[11px] uppercase tracking-wider text-muted"><tr>{["ID", "Vehicle type", "Plate", "Speed", "Limit", "Status", "Detection time"].map((heading) => <th key={heading} className="border-b border-line px-4 py-3 font-semibold">{heading}</th>)}</tr></thead>
          <tbody className="divide-y divide-line">{data.items.map((vehicle) => <tr key={vehicle.id} tabIndex={0} role="button" aria-label={`View details for vehicle ${vehicle.trackingId}`} onClick={() => onSelect(vehicle)} onKeyDown={(e) => { if (e.key === "Enter" || e.key === " ") onSelect(vehicle); }} className="cursor-pointer hover:bg-elevated/60 focus:bg-elevated">
            <td className="px-4 py-3 font-semibold tabular-nums text-cyan">#{vehicle.trackingId}</td><td className="px-4 py-3">{titleCase(vehicle.vehicleType)}</td><td className="px-4 py-3 font-medium">{vehicle.plate || "UNKNOWN"}</td><td className="px-4 py-3 tabular-nums">{formatSpeed(vehicle.speed)} km/h</td><td className="px-4 py-3 tabular-nums text-muted">{vehicle.speedLimit} km/h</td><td className="px-4 py-3"><StatusBadge status={vehicle.status} /></td><td className="px-4 py-3 tabular-nums text-muted">{formatDateTime(vehicle.detectedAt)}</td>
          </tr>)}</tbody>
        </table>
      </div>
      <div className="divide-y divide-line md:hidden">{data.items.map((vehicle) => <button key={vehicle.id} onClick={() => onSelect(vehicle)} className="block w-full p-4 text-left hover:bg-elevated"><span className="flex items-start justify-between gap-2"><span><span className="font-bold text-cyan">#{vehicle.trackingId}</span><span className="ml-2 text-sm">{titleCase(vehicle.vehicleType)}</span></span><StatusBadge status={vehicle.status} /></span><span className="mt-3 grid grid-cols-2 gap-2 text-xs text-muted"><span>{vehicle.plate || "UNKNOWN"}</span><span className="text-right tabular-nums">{formatSpeed(vehicle.speed)} / {vehicle.speedLimit} km/h</span><span className="col-span-2 tabular-nums">{formatDateTime(vehicle.detectedAt)}</span></span></button>)}</div>
      <footer className="flex flex-wrap items-center justify-between gap-3 border-t border-line p-3 text-xs text-muted">
        <span>{data.total} detections · Page {query.page} of {pages}</span>
        <div className="flex items-center gap-2"><label>Rows <select value={query.pageSize} onChange={(e) => onQueryChange({ ...query, pageSize: Number(e.target.value), page: 1 })} className="ml-1 rounded border border-line bg-elevated px-2 py-1 text-ink"><option>10</option><option>20</option><option>50</option></select></label><button disabled={query.page <= 1} onClick={() => onQueryChange({ ...query, page: query.page - 1 })} className="rounded border border-line p-1.5 disabled:opacity-30" aria-label="Previous page"><ChevronLeft size={16} /></button><button disabled={query.page >= pages} onClick={() => onQueryChange({ ...query, page: query.page + 1 })} className="rounded border border-line p-1.5 disabled:opacity-30" aria-label="Next page"><ChevronRight size={16} /></button></div>
      </footer>
    </>
  );
}
