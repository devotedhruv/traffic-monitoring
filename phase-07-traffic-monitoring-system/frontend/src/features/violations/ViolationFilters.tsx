import { CalendarDays, Filter, Search, X } from "lucide-react";
import type { Camera, ViolationQuery } from "../../types";

const typeLabels = {
  OVERSPEED: "Overspeed",
  NO_HELMET: "No helmet",
  WRONG_LANE: "Wrong lane",
  WRONG_DIRECTION: "Wrong direction"
} as const;

export function ViolationFilters({ query, cameras, onChange }: {
  query: ViolationQuery;
  cameras: Camera[];
  onChange: (next: ViolationQuery) => void;
}) {
  const update = (patch: Partial<ViolationQuery>) => onChange({ ...query, ...patch, page: 1 });
  const clear = () => onChange({ page: 1, pageSize: query.pageSize, type: "", vehicleType: "", search: "", date: "", camera: "", sort: "time_desc" });
  const chips = [
    query.date && { key: "date", text: `Date: ${query.date === "today" ? "Today" : "Last 7 days"}` },
    query.type && { key: "type", text: `Violation: ${typeLabels[query.type]}` },
    query.vehicleType && { key: "vehicleType", text: `Vehicle: ${query.vehicleType}` },
    query.camera && { key: "camera", text: `Camera: ${cameras.find((item) => item.id === query.camera)?.name ?? query.camera}` },
    query.search && { key: "search", text: `Search: ${query.search}` }
  ].filter(Boolean) as { key: keyof ViolationQuery; text: string }[];

  return <div className="border-b border-border bg-surface p-3 sm:p-4">
    <div className="grid gap-2 md:grid-cols-2 xl:grid-cols-[minmax(220px,1.25fr)_155px_155px_145px_155px_170px_auto]">
      <label className="relative"><span className="sr-only">Search violations</span><Search className="absolute left-3 top-3.5 text-muted" size={16} /><input value={query.search ?? ""} onChange={(event) => update({ search: event.target.value.slice(0, 100) })} placeholder="Plate, tracking ID, or vehicle ID…" className="field pl-10" /></label>
      <select aria-label="Filter by violation type" value={query.type ?? ""} onChange={(event) => update({ type: event.target.value as ViolationQuery["type"] })} className="field"><option value="">All violations</option><option value="OVERSPEED">Overspeed</option><option value="WRONG_LANE">Wrong lane</option><option value="NO_HELMET">No helmet</option><option value="WRONG_DIRECTION">Wrong direction</option></select>
      <select aria-label="Filter violations by vehicle type" value={query.vehicleType ?? ""} onChange={(event) => update({ vehicleType: event.target.value as ViolationQuery["vehicleType"] })} className="field"><option value="">All vehicle types</option><option value="bicycle">Bicycle</option><option value="car">Car</option><option value="motorcycle">Motorcycle</option><option value="bus">Bus</option><option value="truck">Truck</option><option value="unknown">Unknown</option></select>
      <label className="relative"><CalendarDays className="pointer-events-none absolute left-3 top-3.5 text-muted" size={15} /><select aria-label="Filter violations by date" value={query.date ?? ""} onChange={(event) => update({ date: event.target.value as ViolationQuery["date"] })} className="field appearance-none pl-9"><option value="">All time</option><option value="today">Today</option><option value="week">Last 7 days</option></select></label>
      <select aria-label="Filter violations by camera" value={query.camera ?? ""} onChange={(event) => update({ camera: event.target.value })} className="field"><option value="">All cameras</option>{cameras.map((camera) => <option key={camera.id} value={camera.id}>{camera.name}</option>)}</select>
      <select aria-label="Sort violations" value={query.sort ?? "time_desc"} onChange={(event) => update({ sort: event.target.value as ViolationQuery["sort"] })} className="field"><option value="time_desc">Newest first</option><option value="time_asc">Oldest first</option><option value="speed_desc">Highest speed</option><option value="confidence_desc">Highest confidence</option></select>
      <button type="button" onClick={clear} className="secondary-button h-11"><X size={15} />Clear all</button>
    </div>
    <div className="mt-3 flex min-h-8 flex-wrap items-center gap-2 text-[11px]"><span className="mr-1 flex items-center gap-1.5 text-muted"><Filter size={13} />Active filters:</span>{chips.length ? chips.map((chip) => <button type="button" key={chip.key} onClick={() => update({ [chip.key]: "" })} className="inline-flex h-8 items-center gap-2 rounded-lg border border-primary/10 bg-primary-soft px-3 font-semibold capitalize text-primary">{chip.text}<X size={12} /></button>) : <span className="text-muted">None</span>}</div>
  </div>;
}
