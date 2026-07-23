import { Search, X } from "lucide-react";
import type { VehicleQuery } from "../../types";

export function DetectionFilters({ query, onChange }: { query: VehicleQuery; onChange: (next: VehicleQuery) => void }) {
  const update = (patch: Partial<VehicleQuery>) => onChange({ ...query, ...patch, page: 1 });
  const clear = () => onChange({ page: 1, pageSize: query.pageSize, status: "", type: "", search: "", sort: "time_desc" });
  return (
    <div className="grid gap-2 border-b border-line bg-card p-3 sm:grid-cols-2 xl:grid-cols-[minmax(220px,1fr)_160px_160px_170px_auto]">
      <label className="relative"><span className="sr-only">Search plate or tracking ID</span><Search className="absolute left-3 top-2.5 text-muted" size={16} /><input value={query.search ?? ""} onChange={(e) => update({ search: e.target.value })} placeholder="Search plate or tracking ID" className="h-9 w-full rounded border border-line bg-elevated pl-9 pr-3 text-sm placeholder:text-muted" /></label>
      <select aria-label="Filter by status" value={query.status ?? ""} onChange={(e) => update({ status: e.target.value as VehicleQuery["status"] })} className="h-9 rounded border border-line bg-elevated px-3 text-sm"><option value="">All statuses</option><option value="NORMAL">Normal</option><option value="OVERSPEED">Overspeed</option></select>
      <select aria-label="Filter by vehicle type" value={query.type ?? ""} onChange={(e) => update({ type: e.target.value as VehicleQuery["type"] })} className="h-9 rounded border border-line bg-elevated px-3 text-sm"><option value="">All vehicle types</option><option value="car">Car</option><option value="motorcycle">Motorcycle</option><option value="bus">Bus</option><option value="truck">Truck</option></select>
      <select aria-label="Sort detections" value={query.sort} onChange={(e) => update({ sort: e.target.value as VehicleQuery["sort"] })} className="h-9 rounded border border-line bg-elevated px-3 text-sm"><option value="time_desc">Newest first</option><option value="time_asc">Oldest first</option><option value="speed_desc">Fastest first</option><option value="speed_asc">Slowest first</option></select>
      <button onClick={clear} className="flex h-9 items-center justify-center gap-1 rounded border border-line px-3 text-sm text-muted hover:bg-elevated hover:text-ink"><X size={15} />Clear</button>
    </div>
  );
}
