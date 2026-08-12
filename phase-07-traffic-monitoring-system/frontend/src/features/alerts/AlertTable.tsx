import { ChevronLeft, ChevronRight, ChevronsLeft, ChevronsRight, Eye, Layers3 } from "lucide-react";
import { EmptyState, ErrorState, LoadingSkeleton } from "../../components/ui/States";
import { cx, formatDateTime, formatSpeed, titleCase } from "../../lib/format";
import type { AlertQuery, AlertRecord, PaginatedAlerts } from "../../types";
import { alertStatusLabel, alertTypeLabel, severityTone, statusTone } from "./alertFormat";

export function AlertTable({ data, query, loading, error, selectedId, onQueryChange, onSelect }: {
  data?: PaginatedAlerts;
  query: AlertQuery;
  loading?: boolean;
  error?: boolean;
  selectedId?: number;
  onQueryChange: (next: AlertQuery) => void;
  onSelect: (alert: AlertRecord) => void;
}) {
  if (loading) return <div className="space-y-3 p-4"><LoadingSkeleton className="h-14" /><LoadingSkeleton className="h-14" /><LoadingSkeleton className="h-14" /><LoadingSkeleton className="h-14" /></div>;
  if (error) return <ErrorState message="The alert queue could not be loaded. Check the API connection and try again." />;
  const filtered = Boolean(query.search || query.status || query.severity || query.type || query.vehicleType || query.camera || query.assignedTo || query.date);
  if (!data?.items.length) return <EmptyState title={filtered ? "No alerts match these filters" : "No operational alerts"} message={filtered ? "Clear or adjust the active filters to see more alerts." : "Confirmed live violations will create alerts automatically. Historical violations are not activated retroactively."} />;
  const pages = Math.max(1, Math.ceil(data.total / query.pageSize));
  const visiblePages = Array.from(new Set([1, query.page - 1, query.page, query.page + 1, pages].filter((page) => page >= 1 && page <= pages)));
  const go = (page: number) => onQueryChange({ ...query, page });
  return <>
    <div className="max-h-[610px] overflow-auto scrollbar-thin">
      <table className="w-full min-w-[1270px] border-collapse text-left text-[12px]">
        <thead className="sticky top-0 z-10 bg-surface-secondary text-[9px] uppercase tracking-[0.08em] text-muted"><tr>{["Alert", "Severity", "Status", "Violation", "Vehicle / tracking", "Speed / limit", "Occurrences", "Assigned to", "Camera", "Last detected", "Details"].map((heading) => <th key={heading} scope="col" className="border-b border-border px-4 py-3 font-bold">{heading}</th>)}</tr></thead>
        <tbody className="divide-y divide-border">{data.items.map((item) => <tr key={item.id} tabIndex={0} role="button" aria-label={`Open alert ${item.id}`} aria-selected={selectedId === item.id} onClick={() => onSelect(item)} onKeyDown={(event) => { if (event.key === "Enter" || event.key === " ") onSelect(item); }} className={cx("cursor-pointer bg-card hover:bg-primary-soft/40 focus:bg-primary-soft/40", item.status === "NEW" && "border-l-2 border-l-danger", selectedId === item.id && "bg-primary-soft")}>
          <td className="px-4 py-3"><strong className="block tabular-nums text-primary">#{item.id}</strong><small className="text-muted">v{item.version}</small></td>
          <td className="px-4 py-3"><span className={cx("inline-flex rounded-lg border px-2.5 py-1 text-[9px] font-extrabold tracking-wide", severityTone(item.severity))}>{item.severity}</span></td>
          <td className="px-4 py-3"><span className={cx("inline-flex rounded-lg px-2.5 py-1 text-[9px] font-bold uppercase tracking-wide", statusTone(item.status))}>{alertStatusLabel(item.status)}</span></td>
          <td className="px-4 py-3"><strong>{alertTypeLabel(item.type)}</strong><small className="mt-1 block text-muted">Violation #{item.violationId}</small></td>
          <td className="px-4 py-3"><strong className="block capitalize">{titleCase(item.vehicleType)}</strong><span className="text-muted">{item.plate || `Track #${item.trackingId}`}</span></td>
          <td className="px-4 py-3 font-semibold tabular-nums">{item.speedAvailable && item.speed != null ? <>{formatSpeed(item.speed)} <span className="text-muted">/ {item.speedLimit} km/h</span></> : <span className="font-normal text-muted">Not available</span>}</td>
          <td className="px-4 py-3"><span className="inline-flex items-center gap-1.5 rounded-lg bg-elevated px-2.5 py-1 tabular-nums"><Layers3 size={13} />{item.occurrenceCount}</span></td>
          <td className="px-4 py-3 text-muted">{item.assignedTo?.name || "Unassigned"}</td>
          <td className="px-4 py-3 text-muted">{item.cameraName}</td>
          <td className="px-4 py-3 tabular-nums text-muted">{formatDateTime(item.lastOccurrenceAt)}</td>
          <td className="px-4 py-3"><button type="button" onClick={(event) => { event.stopPropagation(); onSelect(item); }} className="grid h-9 w-9 place-items-center rounded-lg border border-border bg-surface text-muted hover:text-primary" aria-label={`View alert ${item.id}`}><Eye size={15} /></button></td>
        </tr>)}</tbody>
      </table>
    </div>
    <footer className="flex flex-wrap items-center justify-between gap-3 border-t border-border p-3 text-[11px] text-muted"><span>Showing {(query.page - 1) * query.pageSize + 1}–{Math.min(query.page * query.pageSize, data.total)} of {data.total.toLocaleString()} alerts</span><div className="flex flex-wrap items-center gap-2"><label className="mr-2">Rows per page <select value={query.pageSize} onChange={(event) => onQueryChange({ ...query, pageSize: Number(event.target.value), page: 1 })} className="ml-2 h-9 rounded-lg border border-border bg-surface px-2 text-ink"><option>10</option><option>20</option><option>50</option><option>100</option></select></label><button disabled={query.page <= 1} onClick={() => go(1)} className="pagination-button" aria-label="First alerts page"><ChevronsLeft size={15} /></button><button disabled={query.page <= 1} onClick={() => go(query.page - 1)} className="pagination-button" aria-label="Previous alerts page"><ChevronLeft size={15} /></button>{visiblePages.map((page, index) => <span key={page} className="contents">{index > 0 && page - visiblePages[index - 1] > 1 && <span className="px-1">…</span>}<button onClick={() => go(page)} aria-current={page === query.page ? "page" : undefined} className={cx("pagination-button", page === query.page && "border-primary/30 bg-primary-soft text-primary")}>{page}</button></span>)}<button disabled={query.page >= pages} onClick={() => go(query.page + 1)} className="pagination-button" aria-label="Next alerts page"><ChevronRight size={15} /></button><button disabled={query.page >= pages} onClick={() => go(pages)} className="pagination-button" aria-label="Last alerts page"><ChevronsRight size={15} /></button></div></footer>
  </>;
}
