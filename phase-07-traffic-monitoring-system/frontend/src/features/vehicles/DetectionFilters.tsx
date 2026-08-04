import { CalendarDays, Filter, Search, SlidersHorizontal, X } from "lucide-react";
import type { VehicleQuery } from "../../types";

export function DetectionFilters({ query, onChange }: { query: VehicleQuery; onChange: (next: VehicleQuery) => void }) {
  const update = (patch: Partial<VehicleQuery>) => onChange({ ...query, ...patch, page: 1 });
  const clear = () => onChange({ page: 1, pageSize: query.pageSize, status: "", type: "", speed: "", date: "", search: "", sort: "time_desc" });
  const chips = [
    query.date && { key: "date", text: `Date: ${query.date === "today" ? "Today" : "Last 7 days"}` },
    query.status && { key: "status", text: `Status: ${query.status === "OVERSPEED" ? "Overspeed" : "Normal"}` },
    query.speed && { key: "speed", text: `Speed: ${query.speed === "over_limit" ? "Above limit" : "Within limit"}` },
    query.type && { key: "type", text: `Vehicle: ${query.type}` }
  ].filter(Boolean) as { key: keyof VehicleQuery; text: string }[];
  return (
    <div className="border-b border-border bg-surface p-3 sm:p-4">
      <div className="grid gap-2 md:grid-cols-2 xl:grid-cols-[minmax(240px,1.35fr)_155px_165px_145px_145px_150px_auto]">
        <label className="relative"><span className="sr-only">Search plate or tracking ID</span><Search className="absolute left-3 top-3.5 text-muted" size={16} /><input value={query.search ?? ""} onChange={(e) => update({ search: e.target.value })} placeholder="Search by plate number or tracking ID…" className="field pl-10" /></label>
        <select aria-label="Filter by status" value={query.status ?? ""} onChange={(e) => update({ status: e.target.value as VehicleQuery["status"] })} className="field"><option value="">All statuses</option><option value="NORMAL">Normal</option><option value="OVERSPEED">Overspeed</option></select>
        <select aria-label="Filter by vehicle type" value={query.type ?? ""} onChange={(e) => update({ type: e.target.value as VehicleQuery["type"] })} className="field"><option value="">All vehicle types</option><option value="car">Car</option><option value="motorcycle">Motorcycle</option><option value="bus">Bus</option><option value="truck">Truck</option><option value="unknown">Unknown</option></select>
        <select aria-label="Filter by speed" value={query.speed ?? ""} onChange={(e) => update({ speed: e.target.value as VehicleQuery["speed"] })} className="field"><option value="">All speeds</option><option value="under_limit">Within limit</option><option value="over_limit">Above limit</option></select>
        <label className="relative"><CalendarDays className="pointer-events-none absolute left-3 top-3.5 text-muted" size={15} /><select aria-label="Filter by date" value={query.date ?? ""} onChange={(e) => update({ date: e.target.value as VehicleQuery["date"] })} className="field appearance-none pl-9"><option value="">All time</option><option value="today">Today</option><option value="week">Last 7 days</option></select></label>
        <select aria-label="Sort detections" value={query.sort} onChange={(e) => update({ sort: e.target.value as VehicleQuery["sort"] })} className="field"><option value="time_desc">Newest first</option><option value="time_asc">Oldest first</option><option value="speed_desc">Fastest first</option><option value="speed_asc">Slowest first</option></select>
        <button type="button" onClick={clear} className="secondary-button h-11"><X size={15} />Clear all</button>
      </div>
      <div className="mt-3 flex min-h-8 flex-wrap items-center gap-2 text-[11px]"><span className="mr-1 flex items-center gap-1.5 text-muted"><Filter size={13} />Active filters:</span>{chips.length ? chips.map((chip) => <button type="button" key={chip.key} onClick={() => update({ [chip.key]: "" })} className="inline-flex h-8 items-center gap-2 rounded-lg border border-primary/10 bg-primary-soft px-3 font-semibold capitalize text-primary">{chip.text}<X size={12} /></button>) : <span className="text-muted">None</span>}<button type="button" className="inline-flex h-8 items-center gap-1.5 rounded-lg border border-border px-3 font-semibold text-muted hover:bg-elevated hover:text-ink"><SlidersHorizontal size={13} />Advanced filter</button></div>
    </div>
  );
}
