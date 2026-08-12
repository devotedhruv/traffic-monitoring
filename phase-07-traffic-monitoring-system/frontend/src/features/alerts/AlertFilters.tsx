import { CalendarDays, Filter, Search, X } from "lucide-react";
import type { AlertQuery, AuthUser, Camera } from "../../types";
import { alertStatusLabel, alertTypeLabel } from "./alertFormat";

export function AlertFilters({ query, cameras, operators, onChange }: {
  query: AlertQuery;
  cameras: Camera[];
  operators: AuthUser[];
  onChange: (next: AlertQuery) => void;
}) {
  const update = (patch: Partial<AlertQuery>) => onChange({ ...query, ...patch, page: 1 });
  const clear = () => onChange({ page: 1, pageSize: query.pageSize, status: "", severity: "", type: "", vehicleType: "", camera: "", assignedTo: "", search: "", date: "", sort: "newest" });
  const chips = [
    query.status && { key: "status", text: `Status: ${alertStatusLabel(query.status)}` },
    query.severity && { key: "severity", text: `Severity: ${query.severity.toLowerCase()}` },
    query.type && { key: "type", text: `Type: ${alertTypeLabel(query.type)}` },
    query.vehicleType && { key: "vehicleType", text: `Vehicle: ${query.vehicleType}` },
    query.assignedTo && { key: "assignedTo", text: `Assigned: ${query.assignedTo === "me" ? "Me" : query.assignedTo === "unassigned" ? "Unassigned" : operators.find((item) => String(item.id) === query.assignedTo)?.name ?? query.assignedTo}` },
    query.camera && { key: "camera", text: `Camera: ${cameras.find((item) => item.id === query.camera)?.name ?? query.camera}` },
    query.date && { key: "date", text: `Date: ${query.date === "today" ? "Today" : "Last 7 days"}` },
    query.search && { key: "search", text: `Search: ${query.search}` }
  ].filter(Boolean) as { key: keyof AlertQuery; text: string }[];

  return <div className="border-b border-border bg-surface p-3 sm:p-4">
    <div className="grid gap-2 md:grid-cols-2 xl:grid-cols-[minmax(210px,1.2fr)_145px_135px_145px_150px_155px_150px_150px_auto]">
      <label className="relative"><span className="sr-only">Search alerts</span><Search className="absolute left-3 top-3.5 text-muted" size={16} /><input value={query.search ?? ""} onChange={(event) => update({ search: event.target.value.slice(0, 100) })} placeholder="Alert, plate, tracking, vehicle…" className="field pl-10" /></label>
      <select aria-label="Filter alerts by status" value={query.status ?? ""} onChange={(event) => update({ status: event.target.value as AlertQuery["status"] })} className="field"><option value="">All statuses</option><option value="NEW">New</option><option value="ACKNOWLEDGED">Acknowledged</option><option value="INVESTIGATING">Investigating</option><option value="RESOLVED">Resolved</option><option value="FALSE_POSITIVE">False positive</option></select>
      <select aria-label="Filter alerts by severity" value={query.severity ?? ""} onChange={(event) => update({ severity: event.target.value as AlertQuery["severity"] })} className="field"><option value="">All severities</option><option value="CRITICAL">Critical</option><option value="HIGH">High</option><option value="MEDIUM">Medium</option><option value="LOW">Low</option></select>
      <select aria-label="Filter alerts by violation type" value={query.type ?? ""} onChange={(event) => update({ type: event.target.value as AlertQuery["type"] })} className="field"><option value="">All violations</option><option value="OVERSPEED">Overspeed</option><option value="WRONG_LANE">Wrong lane</option><option value="NO_HELMET">No helmet</option><option value="WRONG_DIRECTION">Wrong direction</option></select>
      <select aria-label="Filter alerts by vehicle type" value={query.vehicleType ?? ""} onChange={(event) => update({ vehicleType: event.target.value as AlertQuery["vehicleType"] })} className="field"><option value="">All vehicles</option><option value="bicycle">Bicycle</option><option value="car">Car</option><option value="motorcycle">Motorcycle</option><option value="bus">Bus</option><option value="truck">Truck</option><option value="unknown">Unknown</option></select>
      <select aria-label="Filter alerts by assignment" value={query.assignedTo ?? ""} onChange={(event) => update({ assignedTo: event.target.value as AlertQuery["assignedTo"] })} className="field"><option value="">All operators</option><option value="me">Assigned to me</option><option value="unassigned">Unassigned</option>{operators.map((operator) => <option key={operator.id} value={operator.id}>{operator.name}</option>)}</select>
      <select aria-label="Filter alerts by camera" value={query.camera ?? ""} onChange={(event) => update({ camera: event.target.value })} className="field"><option value="">All cameras</option>{cameras.map((camera) => <option key={camera.id} value={camera.id}>{camera.name}</option>)}</select>
      <label className="relative"><CalendarDays className="pointer-events-none absolute left-3 top-3.5 text-muted" size={15} /><select aria-label="Filter alerts by date" value={query.date ?? ""} onChange={(event) => update({ date: event.target.value as AlertQuery["date"] })} className="field appearance-none pl-9"><option value="">All time</option><option value="today">Today</option><option value="week">Last 7 days</option></select></label>
      <select aria-label="Sort alerts" value={query.sort ?? "newest"} onChange={(event) => update({ sort: event.target.value as AlertQuery["sort"] })} className="field"><option value="newest">Newest first</option><option value="oldest">Oldest first</option><option value="severity">Highest severity</option></select>
      <button type="button" onClick={clear} className="secondary-button h-11"><X size={15} />Clear</button>
    </div>
    <div className="mt-3 flex min-h-8 flex-wrap items-center gap-2 text-[11px]"><span className="mr-1 flex items-center gap-1.5 text-muted"><Filter size={13} />Active filters:</span>{chips.length ? chips.map((chip) => <button type="button" key={chip.key} onClick={() => update({ [chip.key]: "" })} className="inline-flex h-8 items-center gap-2 rounded-lg border border-primary/10 bg-primary-soft px-3 font-semibold capitalize text-primary">{chip.text}<X size={12} /></button>) : <span className="text-muted">None</span>}</div>
  </div>;
}
