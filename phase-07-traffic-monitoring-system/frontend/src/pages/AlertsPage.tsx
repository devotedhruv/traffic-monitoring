import { AlarmClock, BellRing, RefreshCw, ShieldAlert, Siren, TimerReset } from "lucide-react";
import { useEffect, useState } from "react";
import { useQuery } from "@tanstack/react-query";
import { PageHeader } from "../components/ui/PageHeader";
import { Panel } from "../components/ui/Panel";
import { LoadingSkeleton } from "../components/ui/States";
import { AlertDetailsDrawer } from "../features/alerts/AlertDetailsDrawer";
import { AlertFilters } from "../features/alerts/AlertFilters";
import { AlertPreferencesControl } from "../features/alerts/AlertPreferencesControl";
import { AlertTable } from "../features/alerts/AlertTable";
import { api } from "../services/api";
import type { AlertQuery, AlertRecord, AlertSeverity, AlertStatus, ViolationType } from "../types";

const statuses: AlertStatus[] = ["NEW", "ACKNOWLEDGED", "INVESTIGATING", "RESOLVED", "FALSE_POSITIVE"];
const severities: AlertSeverity[] = ["LOW", "MEDIUM", "HIGH", "CRITICAL"];
const violationTypes: ViolationType[] = ["OVERSPEED", "NO_HELMET", "WRONG_LANE", "WRONG_DIRECTION"];

function initialQuery(): AlertQuery {
  const params = new URLSearchParams(window.location.search);
  const status = statuses.includes(params.get("status") as AlertStatus) ? params.get("status") as AlertStatus : "";
  const severity = severities.includes(params.get("severity") as AlertSeverity) ? params.get("severity") as AlertSeverity : "";
  const type = violationTypes.includes(params.get("type") as ViolationType) ? params.get("type") as ViolationType : "";
  const vehicleType = ["bicycle", "car", "motorcycle", "bus", "truck", "unknown"].includes(params.get("vehicleType") ?? "") ? params.get("vehicleType") as AlertQuery["vehicleType"] : "";
  const date = ["today", "week"].includes(params.get("date") ?? "") ? params.get("date") as AlertQuery["date"] : "";
  const sort = ["newest", "oldest", "severity"].includes(params.get("sort") ?? "") ? params.get("sort") as AlertQuery["sort"] : "newest";
  const assigned = params.get("assignedTo") ?? "";
  const assignedTo = assigned === "me" || assigned === "unassigned" || /^\d+$/.test(assigned) ? assigned as AlertQuery["assignedTo"] : "";
  return { page: Math.max(1, Number(params.get("page")) || 1), pageSize: 20, status, severity, type, vehicleType, camera: (params.get("camera") ?? "").slice(0, 100), assignedTo, search: (params.get("search") ?? "").slice(0, 100), date, sort };
}

function formatResponseTime(seconds: number | null | undefined) {
  if (seconds == null) return "—";
  if (seconds < 60) return `${Math.round(seconds)}s`;
  if (seconds < 3600) return `${Math.round(seconds / 60)}m`;
  return `${(seconds / 3600).toFixed(1)}h`;
}

export function AlertsPage() {
  const [query, setQuery] = useState<AlertQuery>(initialQuery);
  const [selected, setSelected] = useState<AlertRecord | null>(null);
  const records = useQuery({ queryKey: ["alerts", "records", query], queryFn: () => api.getAlerts(query), refetchInterval: 30_000 });
  const summary = useQuery({ queryKey: ["alert-summary", "all"], queryFn: () => api.getAlertSummary("all"), refetchInterval: 30_000 });
  const cameras = useQuery({ queryKey: ["cameras"], queryFn: api.getCameras });
  const operators = useQuery({ queryKey: ["alert-operators"], queryFn: api.getAlertOperators });
  useEffect(() => {
    const params = new URLSearchParams();
    if (query.page > 1) params.set("page", String(query.page));
    if (query.status) params.set("status", query.status);
    if (query.severity) params.set("severity", query.severity);
    if (query.type) params.set("type", query.type);
    if (query.vehicleType) params.set("vehicleType", query.vehicleType);
    if (query.camera) params.set("camera", query.camera);
    if (query.assignedTo) params.set("assignedTo", query.assignedTo);
    if (query.search) params.set("search", query.search);
    if (query.date) params.set("date", query.date);
    if (query.sort && query.sort !== "newest") params.set("sort", query.sort);
    window.history.replaceState(null, "", `/app/alerts${params.size ? `?${params}` : ""}`);
  }, [query]);
  useEffect(() => {
    if (summary.data) window.dispatchEvent(new CustomEvent("trafficops:alert-count", { detail: summary.data.new }));
  }, [summary.data]);
  const metrics = [
    { label: "New alerts", value: summary.data?.new ?? 0, note: "Needs acknowledgement", icon: BellRing, tone: "text-danger" },
    { label: "Critical active", value: summary.data?.critical ?? 0, note: "Immediate attention", icon: Siren, tone: "text-danger" },
    { label: "Unresolved", value: summary.data?.unresolved ?? 0, note: "Open workflow", icon: ShieldAlert, tone: "text-warning" },
    { label: "Resolved today", value: summary.data?.resolvedToday ?? 0, note: "Completed actions", icon: TimerReset, tone: "text-success" },
    { label: "Average response", value: formatResponseTime(summary.data?.averageResponseSeconds), note: "Created to acknowledged", icon: AlarmClock, tone: "text-primary" }
  ];
  return <div className="space-y-5">
    <PageHeader eyebrow="Live Operations  ›  Alerts" title="Operational Alerts" subtitle="Triage confirmed traffic-rule events, assign operators, and preserve every response in an audit trail." />
    <section className="grid gap-3 sm:grid-cols-2 xl:grid-cols-5" aria-label="Alert queue summary">{summary.isLoading ? <LoadingSkeleton className="h-24 sm:col-span-2 xl:col-span-5" /> : metrics.map(({ label, value, note, icon: Icon, tone }) => <article key={label} className="flex min-h-24 items-center gap-3 rounded-2xl border border-border bg-card p-4 shadow-panel"><span className={`grid h-10 w-10 place-items-center rounded-xl bg-elevated ${tone}`}><Icon size={18} /></span><div><p className="metric-label">{label}</p><strong className="metric-small">{typeof value === "number" ? value.toLocaleString() : value}</strong><p className="metric-note">{note}</p></div></article>)}</section>
    <Panel title="Notification preferences"><div className="flex flex-wrap items-center justify-between gap-3 p-3 sm:p-4"><p className="max-w-2xl text-xs text-muted">Alerts always remain in the queue. Sound and browser notifications are optional, stored only in this browser, and enabled only after your explicit choice.</p><AlertPreferencesControl /></div></Panel>
    <Panel title="Alert queue" action={<div className="flex items-center gap-2"><span className="hidden text-[11px] font-semibold text-muted sm:inline">{records.data?.total.toLocaleString() ?? "—"} alerts</span><button type="button" className="icon-button h-9 w-9" onClick={() => { void records.refetch(); void summary.refetch(); }} aria-label="Refresh alert queue" title="Refresh"><RefreshCw size={14} /></button></div>}>
      <AlertFilters query={query} cameras={cameras.data ?? []} operators={operators.data?.items ?? []} onChange={setQuery} />
      <AlertTable data={records.data} query={query} loading={records.isLoading} error={records.isError} selectedId={selected?.id} onQueryChange={setQuery} onSelect={setSelected} />
    </Panel>
    <AlertDetailsDrawer key={selected?.id ?? "closed"} alert={selected} operators={operators.data?.items ?? []} onClose={() => setSelected(null)} />
  </div>;
}
