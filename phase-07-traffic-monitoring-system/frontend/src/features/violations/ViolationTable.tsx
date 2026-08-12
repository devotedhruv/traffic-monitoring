import { Bike, Bus, Camera, CarFront, ChevronLeft, ChevronRight, ChevronsLeft, ChevronsRight, Eye } from "lucide-react";
import { EmptyState, ErrorState, LoadingSkeleton } from "../../components/ui/States";
import { cx, formatDateTime, formatSpeed, titleCase } from "../../lib/format";
import { api } from "../../services/api";
import type { PaginatedViolations, VehicleType, ViolationEvent, ViolationQuery, ViolationType } from "../../types";
import { violationLabel } from "./violationFormat";

function VehicleIcon({ type }: { type: VehicleType }) {
  const Icon = type === "bus" ? Bus : type === "motorcycle" || type === "bicycle" ? Bike : CarFront;
  return <Icon size={17} className="text-primary" aria-hidden="true" />;
}

function ViolationBadge({ type }: { type: ViolationType }) {
  const tone = type === "OVERSPEED" ? "bg-danger/10 text-danger" : type === "NO_HELMET" ? "bg-warning/10 text-warning" : "bg-purple/10 text-purple";
  return <span className={cx("inline-flex rounded-lg px-2.5 py-1 text-[9px] font-extrabold uppercase tracking-wide", tone)}>{violationLabel(type)}</span>;
}

export function ViolationTable({ data, query, loading, error, capabilitiesUnavailable, onQueryChange, onSelect, selectedId }: {
  data?: PaginatedViolations;
  query: ViolationQuery;
  loading?: boolean;
  error?: boolean;
  capabilitiesUnavailable?: boolean;
  onQueryChange: (next: ViolationQuery) => void;
  onSelect: (event: ViolationEvent) => void;
  selectedId?: number;
}) {
  if (loading) return <div className="space-y-3 p-4"><LoadingSkeleton className="h-12" /><LoadingSkeleton className="h-12" /><LoadingSkeleton className="h-12" /><LoadingSkeleton className="h-12" /></div>;
  if (error) return <ErrorState message="Violation history could not be loaded. Check the API connection and try again." />;
  const filtered = Boolean(query.search || query.type || query.vehicleType || query.date || query.camera);
  if (!data?.items.length) return <EmptyState title={filtered ? "No matching violations" : "No confirmed violations yet"} message={capabilitiesUnavailable && !filtered ? "Some specialist detectors are not configured. Confirmed events will appear here when available." : filtered ? "Adjust or clear the active filters and try again." : "Confirmed traffic-rule violations will appear here automatically."} />;
  const pages = Math.max(1, Math.ceil(data.total / query.pageSize));
  const visiblePages = Array.from(new Set([1, query.page - 1, query.page, query.page + 1, pages].filter((page) => page >= 1 && page <= pages)));
  const go = (page: number) => onQueryChange({ ...query, page });
  return <>
    <div className="max-h-[590px] overflow-auto scrollbar-thin">
      <table className="w-full min-w-[1250px] border-collapse text-left text-[12px]">
        <thead className="sticky top-0 z-10 bg-surface-secondary text-[9px] uppercase tracking-[0.08em] text-muted"><tr>{["Event", "Vehicle", "Plate / Tracking ID", "Violation", "Speed / Limit", "Lane / Direction", "Camera", "Detected", "Confidence", "Evidence"].map((heading) => <th key={heading} scope="col" className="border-b border-border px-4 py-3 font-bold">{heading}</th>)}</tr></thead>
        <tbody className="divide-y divide-border">{data.items.map((item) => <tr key={item.id} tabIndex={0} role="button" aria-label={`View ${violationLabel(item.type)} violation ${item.id}`} aria-selected={selectedId === item.id} onClick={() => onSelect(item)} onKeyDown={(event) => { if (event.key === "Enter" || event.key === " ") onSelect(item); }} className={cx("cursor-pointer bg-card hover:bg-primary-soft/45 focus:bg-primary-soft/45", selectedId === item.id && "bg-primary-soft")}>
          <td className="px-4 py-3 font-bold tabular-nums text-primary">#{item.id}</td>
          <td className="px-4 py-3"><span className="flex items-center gap-2"><VehicleIcon type={item.vehicleType} />{titleCase(item.vehicleType)}{item.vehicleId != null && <small className="text-muted">DB #{item.vehicleId}</small>}</span></td>
          <td className="px-4 py-3"><span className="inline-flex rounded-lg border border-border bg-surface-secondary px-2.5 py-1 font-semibold tabular-nums">{item.plate || `Track #${item.trackingId}`}</span></td>
          <td className="px-4 py-3"><ViolationBadge type={item.type} /></td>
          <td className="px-4 py-3 font-semibold tabular-nums">{item.speedAvailable && item.speed != null ? <>{formatSpeed(item.speed)} <span className="text-muted">/ {item.speedLimit ?? "—"} km/h</span></> : <span className="text-muted">Not available</span>}</td>
          <td className="px-4 py-3 text-muted">{item.laneId != null ? `Lane ${item.laneId}` : "Not available"}{item.direction && <small className="mt-1 block">{item.direction.replaceAll("_", " ")}</small>}</td>
          <td className="px-4 py-3 text-muted">{item.cameraName || item.cameraId}</td>
          <td className="px-4 py-3 tabular-nums text-muted">{formatDateTime(item.detectedAt)}</td>
          <td className="px-4 py-3"><strong className="tabular-nums">{Math.round(item.confidence * 100)}%</strong><div className="mt-1 h-1 w-16 overflow-hidden rounded-full bg-elevated"><div className="h-full rounded-full bg-primary" style={{ width: `${item.confidence * 100}%` }} /></div></td>
          <td className="px-4 py-3">{item.snapshotUrl ? <a href={api.resolveApiUrl(item.snapshotUrl)} target="_blank" rel="noreferrer" onClick={(event) => event.stopPropagation()} className="grid h-9 w-9 place-items-center rounded-lg border border-border bg-surface hover:text-primary" aria-label={`Open evidence for violation ${item.id}`}><Camera size={15} /></a> : <button type="button" onClick={(event) => { event.stopPropagation(); onSelect(item); }} className="grid h-9 w-9 place-items-center rounded-lg border border-border bg-surface text-muted hover:text-primary" aria-label={`View violation ${item.id}`}><Eye size={15} /></button>}</td>
        </tr>)}</tbody>
      </table>
    </div>
    <footer className="flex flex-wrap items-center justify-between gap-3 border-t border-border p-3 text-[11px] text-muted"><span>Showing {(query.page - 1) * query.pageSize + 1}–{Math.min(query.page * query.pageSize, data.total)} of {data.total.toLocaleString()} violations</span><div className="flex flex-wrap items-center gap-2"><label className="mr-2">Rows per page <select value={query.pageSize} onChange={(event) => onQueryChange({ ...query, pageSize: Number(event.target.value), page: 1 })} className="ml-2 h-9 rounded-lg border border-border bg-surface px-2 text-ink"><option>10</option><option>20</option><option>50</option><option>100</option></select></label><button disabled={query.page <= 1} onClick={() => go(1)} className="pagination-button" aria-label="First violations page"><ChevronsLeft size={15} /></button><button disabled={query.page <= 1} onClick={() => go(query.page - 1)} className="pagination-button" aria-label="Previous violations page"><ChevronLeft size={15} /></button>{visiblePages.map((page, index) => <span key={page} className="contents">{index > 0 && page - visiblePages[index - 1] > 1 && <span className="px-1">…</span>}<button onClick={() => go(page)} aria-current={page === query.page ? "page" : undefined} className={cx("pagination-button", page === query.page && "border-primary/30 bg-primary-soft text-primary")}>{page}</button></span>)}<button disabled={query.page >= pages} onClick={() => go(query.page + 1)} className="pagination-button" aria-label="Next violations page"><ChevronRight size={15} /></button><button disabled={query.page >= pages} onClick={() => go(pages)} className="pagination-button" aria-label="Last violations page"><ChevronsRight size={15} /></button></div></footer>
  </>;
}
