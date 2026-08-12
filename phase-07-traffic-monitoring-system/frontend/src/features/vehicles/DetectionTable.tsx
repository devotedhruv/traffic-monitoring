import { Bus, CarFront, ChevronLeft, ChevronRight, ChevronsLeft, ChevronsRight, Eye, MoreVertical, Bike } from "lucide-react";
import { EmptyState, ErrorState, LoadingSkeleton } from "../../components/ui/States";
import { StatusBadge } from "../../components/ui/StatusBadge";
import { cx, formatDateTime, formatSpeed, titleCase } from "../../lib/format";
import type { PaginatedVehicles, VehicleDetection, VehicleQuery } from "../../types";

function VehicleIcon({ type }: { type: VehicleDetection["vehicleType"] }) {
  const Icon = type === "bus" ? Bus : type === "motorcycle" || type === "bicycle" ? Bike : CarFront;
  return <Icon size={18} className="text-primary" aria-hidden="true" />;
}

export function DetectionTable({ data, query, loading, error, onQueryChange, onSelect, selectedId }: { data?: PaginatedVehicles; query: VehicleQuery; loading?: boolean; error?: boolean; onQueryChange: (next: VehicleQuery) => void; onSelect: (vehicle: VehicleDetection) => void; selectedId?: number }) {
  if (loading) return <div className="space-y-3 p-4"><LoadingSkeleton className="h-12" /><LoadingSkeleton className="h-12" /><LoadingSkeleton className="h-12" /><LoadingSkeleton className="h-12" /></div>;
  if (error) return <ErrorState message="Detection history could not be loaded. Check the API connection and try again." />;
  if (!data?.items.length) return <EmptyState title={query.search || query.status || query.type || query.speed || query.date ? "No matching detections" : "No detections yet"} message="Adjust or clear the current filters and try again." />;
  const pages = Math.max(1, Math.ceil(data.total / query.pageSize));
  const visiblePages = Array.from(new Set([1, query.page - 1, query.page, query.page + 1, pages].filter((page) => page >= 1 && page <= pages)));
  const go = (page: number) => onQueryChange({ ...query, page });
  return (
    <>
      <div className="max-h-[590px] overflow-auto scrollbar-thin">
        <table className="w-full min-w-[1110px] border-collapse text-left text-[12px]">
          <thead className="sticky top-0 z-10 bg-surface-secondary text-[9px] uppercase tracking-[0.08em] text-muted"><tr>{["ID", "Vehicle type", "Plate / Tracking ID", "Speed", "Speed limit", "Status", "Detection time", "Confidence", "Actions"].map((heading) => <th key={heading} scope="col" className="border-b border-border px-4 py-3 font-bold">{heading}</th>)}</tr></thead>
          <tbody className="divide-y divide-border">{data.items.map((vehicle) => {
            const confidence = vehicle.confidence;
            return <tr key={vehicle.id} tabIndex={0} role="button" aria-label={`View details for vehicle ${vehicle.trackingId}`} aria-selected={selectedId === vehicle.id} onClick={() => onSelect(vehicle)} onKeyDown={(e) => { if (e.key === "Enter" || e.key === " ") onSelect(vehicle); }} className={cx("cursor-pointer bg-card hover:bg-primary-soft/45 focus:bg-primary-soft/45", selectedId === vehicle.id && "bg-primary-soft")}>
              <td className="px-4 py-3 font-bold tabular-nums text-primary">#{vehicle.trackingId}</td>
              <td className="px-4 py-3"><span className="flex items-center gap-2.5"><VehicleIcon type={vehicle.vehicleType} /><span>{titleCase(vehicle.vehicleType)}</span></span></td>
              <td className="px-4 py-3"><span className="inline-flex rounded-lg border border-border bg-surface-secondary px-2.5 py-1 font-semibold tabular-nums">{vehicle.plate || "UNKNOWN"}</span></td>
              <td className="px-4 py-3 font-semibold tabular-nums">{vehicle.speedAvailable === false ? <span className="text-muted">Not measured</span> : `${formatSpeed(vehicle.speed)} km/h`}</td><td className="px-4 py-3 tabular-nums text-muted">{vehicle.speedLimit} km/h</td><td className="px-4 py-3"><StatusBadge status={vehicle.status} />{vehicle.violations?.filter((type) => type !== "OVERSPEED").map((type) => <span key={type} className="mt-1 block rounded bg-danger/10 px-1.5 py-0.5 text-[8px] font-bold text-danger">{type.replaceAll("_", " ")}</span>)}</td><td className="px-4 py-3 tabular-nums text-muted">{formatDateTime(vehicle.detectedAt)}</td>
              <td className="px-4 py-3">{typeof confidence === "number" ? <div className="w-20"><span className="font-semibold tabular-nums">{Math.round(confidence * 100)}%</span><div className="mt-1 h-1 overflow-hidden rounded-full bg-elevated"><div className="h-full rounded-full bg-primary" style={{ width: `${confidence * 100}%` }} /></div></div> : <span className="text-muted" title="Confidence was not stored for this detection">Not recorded</span>}</td>
              <td className="px-4 py-3"><span className="flex gap-2"><button type="button" className="grid h-9 w-9 place-items-center rounded-lg border border-border bg-surface hover:bg-elevated hover:text-primary" onClick={(event) => { event.stopPropagation(); onSelect(vehicle); }} aria-label={`View detection ${vehicle.trackingId}`}><Eye size={15} /></button><button type="button" className="grid h-9 w-9 place-items-center rounded-lg border border-border bg-surface hover:bg-elevated hover:text-primary" onClick={(event) => { event.stopPropagation(); onSelect(vehicle); }} aria-label={`More actions for detection ${vehicle.trackingId}`}><MoreVertical size={15} /></button></span></td>
            </tr>})}</tbody>
        </table>
      </div>
      <footer className="flex flex-wrap items-center justify-between gap-3 border-t border-border p-3 text-[11px] text-muted"><span>Showing {(query.page - 1) * query.pageSize + 1}–{Math.min(query.page * query.pageSize, data.total)} of {data.total.toLocaleString()} detections</span><div className="flex flex-wrap items-center gap-2"><label className="mr-2">Rows per page <select value={query.pageSize} onChange={(e) => onQueryChange({ ...query, pageSize: Number(e.target.value), page: 1 })} className="ml-2 h-9 rounded-lg border border-border bg-surface px-2 text-ink"><option>10</option><option>20</option><option>50</option><option>100</option></select></label><button disabled={query.page <= 1} onClick={() => go(1)} className="pagination-button" aria-label="First page"><ChevronsLeft size={15} /></button><button disabled={query.page <= 1} onClick={() => go(query.page - 1)} className="pagination-button" aria-label="Previous page"><ChevronLeft size={15} /></button>{visiblePages.map((page, index) => <span key={page} className="contents">{index > 0 && page - visiblePages[index - 1] > 1 && <span className="px-1">…</span>}<button onClick={() => go(page)} aria-current={page === query.page ? "page" : undefined} className={cx("pagination-button", page === query.page && "border-primary/30 bg-primary-soft text-primary")}>{page}</button></span>)}<button disabled={query.page >= pages} onClick={() => go(query.page + 1)} className="pagination-button" aria-label="Next page"><ChevronRight size={15} /></button><button disabled={query.page >= pages} onClick={() => go(pages)} className="pagination-button" aria-label="Last page"><ChevronsRight size={15} /></button></div></footer>
    </>
  );
}
