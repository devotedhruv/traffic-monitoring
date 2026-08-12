import { AlertTriangle, Bike, Gauge, RefreshCw, Route, ShieldAlert } from "lucide-react";
import { useEffect, useState } from "react";
import { useQuery } from "@tanstack/react-query";
import { PageHeader } from "../components/ui/PageHeader";
import { Panel } from "../components/ui/Panel";
import { LoadingSkeleton } from "../components/ui/States";
import { ViolationDetailsDrawer } from "../features/violations/ViolationDetailsDrawer";
import { ViolationFilters } from "../features/violations/ViolationFilters";
import { ViolationTable } from "../features/violations/ViolationTable";
import { api } from "../services/api";
import type { ViolationEvent, ViolationQuery, ViolationType } from "../types";

const validTypes: ViolationType[] = ["OVERSPEED", "NO_HELMET", "WRONG_LANE", "WRONG_DIRECTION"];

function initialQuery(): ViolationQuery {
  const params = new URLSearchParams(window.location.search);
  const type = validTypes.includes(params.get("type") as ViolationType) ? params.get("type") as ViolationType : "";
  const vehicleType = ["bicycle", "car", "motorcycle", "bus", "truck", "unknown"].includes(params.get("vehicleType") ?? "") ? params.get("vehicleType") as ViolationQuery["vehicleType"] : "";
  const date = ["today", "week"].includes(params.get("date") ?? "") ? params.get("date") as ViolationQuery["date"] : "";
  const sort = ["time_desc", "time_asc", "speed_desc", "confidence_desc"].includes(params.get("sort") ?? "") ? params.get("sort") as ViolationQuery["sort"] : "time_desc";
  return { page: Math.max(1, Number(params.get("page")) || 1), pageSize: 20, type, vehicleType, search: (params.get("search") ?? "").slice(0, 100), date, camera: (params.get("camera") ?? "").slice(0, 100), sort };
}

export function ViolationsPage() {
  const [query, setQuery] = useState<ViolationQuery>(initialQuery);
  const [selected, setSelected] = useState<ViolationEvent | null>(null);
  const records = useQuery({ queryKey: ["violations", "records", query], queryFn: () => api.getViolationRecords(query) });
  const summary = useQuery({ queryKey: ["violation-summary", "all"], queryFn: () => api.getViolationSummary("all") });
  const capabilities = useQuery({ queryKey: ["capabilities"], queryFn: api.getCapabilities });
  const cameras = useQuery({ queryKey: ["cameras"], queryFn: api.getCameras });
  useEffect(() => {
    const params = new URLSearchParams();
    if (query.page > 1) params.set("page", String(query.page));
    if (query.type) params.set("type", query.type);
    if (query.vehicleType) params.set("vehicleType", query.vehicleType);
    if (query.search) params.set("search", query.search);
    if (query.date) params.set("date", query.date);
    if (query.camera) params.set("camera", query.camera);
    if (query.sort && query.sort !== "time_desc") params.set("sort", query.sort);
    window.history.replaceState(null, "", `/app/violations${params.size ? `?${params}` : ""}`);
  }, [query]);
  const counts = summary.data?.counts ?? {};
  const unavailable = [
    capabilities.data?.helmetDetection.available === false && capabilities.data.helmetDetection.reason,
    capabilities.data?.wrongLaneDetection.available === false && capabilities.data.wrongLaneDetection.reason,
    capabilities.data?.wrongDirectionDetection.available === false && capabilities.data.wrongDirectionDetection.reason
  ].filter(Boolean) as string[];
  const summaryCards = [
    { label: "Total violations", value: summary.data?.total ?? 0, icon: ShieldAlert, tone: "text-danger" },
    { label: "Overspeed", value: counts.OVERSPEED ?? 0, icon: Gauge, tone: "text-danger" },
    { label: "Wrong lane", value: counts.WRONG_LANE ?? 0, icon: Route, tone: "text-purple" },
    { label: "No helmet", value: counts.NO_HELMET ?? 0, icon: Bike, tone: "text-warning" },
    { label: "Wrong direction", value: counts.WRONG_DIRECTION ?? 0, icon: AlertTriangle, tone: "text-warning" }
  ];
  return <div className="space-y-5">
    <PageHeader eyebrow="Traffic Archive  ›  Violations" title="Violation History" subtitle="Review confirmed traffic-rule violations and their matching vehicle evidence." />
    <section className="grid gap-3 sm:grid-cols-2 xl:grid-cols-5" aria-label="Violation summary">{summary.isLoading ? <LoadingSkeleton className="h-24 sm:col-span-2 xl:col-span-5" /> : summaryCards.map(({ label, value, icon: Icon, tone }) => <article key={label} className="flex min-h-24 items-center gap-3 rounded-2xl border border-border bg-card p-4 shadow-panel"><span className={`grid h-10 w-10 place-items-center rounded-xl bg-elevated ${tone}`}><Icon size={18} /></span><div><p className="metric-label">{label}</p><strong className="metric-small">{value.toLocaleString()}</strong><p className="metric-note">Confirmed events</p></div></article>)}</section>
    {unavailable.length > 0 && <aside className="rounded-2xl border border-warning/25 bg-warning/5 p-4 text-xs text-muted" aria-label="Unavailable violation capabilities"><strong className="flex items-center gap-2 text-warning"><AlertTriangle size={15} />Some specialist detection is not configured</strong><p className="mt-1">No events are fabricated. {Array.from(new Set(unavailable)).join(" ")}</p></aside>}
    <Panel title="Violation records" action={<div className="flex items-center gap-2"><span className="hidden text-[11px] font-semibold text-muted sm:inline">{records.data?.total.toLocaleString() ?? "—"} results</span><button type="button" className="icon-button h-9 w-9" onClick={() => { void records.refetch(); void summary.refetch(); }} aria-label="Refresh violations" title="Refresh"><RefreshCw size={14} /></button></div>}>
      <ViolationFilters query={query} cameras={cameras.data ?? []} onChange={setQuery} />
      <ViolationTable data={records.data} query={query} loading={records.isLoading} error={records.isError} capabilitiesUnavailable={unavailable.length > 0} onQueryChange={setQuery} onSelect={setSelected} selectedId={selected?.id} />
    </Panel>
    <ViolationDetailsDrawer violation={selected} onClose={() => setSelected(null)} />
  </div>;
}
