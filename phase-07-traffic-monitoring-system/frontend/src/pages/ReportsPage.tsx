import { BellRing, Camera, CarFront, FileCheck2, FilePlus2, FileWarning, Files, RefreshCw, ShieldAlert, TimerReset } from "lucide-react";
import { useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { PageHeader } from "../components/ui/PageHeader";
import { Panel } from "../components/ui/Panel";
import { LoadingSkeleton } from "../components/ui/States";
import { ReportCreationDialog } from "../features/reports/ReportCreationDialog";
import { ReportPreviewDrawer } from "../features/reports/ReportPreviewDrawer";
import { ReportSchedulePanel } from "../features/reports/ReportSchedulePanel";
import { ReportFiltersBar, ReportTable } from "../features/reports/ReportTable";
import { api } from "../services/api";
import type { ReportQuery, ReportRecord, ReportTemplate, ReportType } from "../types";

const templateIcons = { TRAFFIC_SUMMARY: Files, VIOLATION_ENFORCEMENT: ShieldAlert, ALERT_RESPONSE: BellRing, VEHICLE_FLOW: CarFront, CAMERA_PERFORMANCE: Camera, CUSTOM: FilePlus2 } as const;
const fallbackTemplates: ReportTemplate[] = [
  { type: "TRAFFIC_SUMMARY", name: "Traffic Summary", description: "Vehicle totals, measured speed statistics, trends, and comparison.", sections: ["kpis", "trafficTrend", "vehicleDistribution", "comparison"] },
  { type: "VIOLATION_ENFORCEMENT", name: "Violation Enforcement", description: "Confirmed rule violations with vehicle and evidence metadata.", sections: ["kpis", "violationDistribution", "violationRecords"] },
  { type: "ALERT_RESPONSE", name: "Alert Response", description: "Workflow status, severity, response time, and resolution outcomes.", sections: ["kpis", "alertDistribution", "alertRecords", "auditSummary"] },
  { type: "VEHICLE_FLOW", name: "Vehicle Flow", description: "Traffic volume, vehicle distribution, lanes, and directions.", sections: ["kpis", "trafficTrend", "vehicleDistribution", "laneDirection"] },
  { type: "CAMERA_PERFORMANCE", name: "Camera Performance", description: "Detection volume and truthful current configuration status.", sections: ["kpis", "cameraSummary", "capabilities"] },
  { type: "CUSTOM", name: "Custom Report", description: "Choose which operational sections are included.", sections: ["kpis"] }
];

export function ReportsPage() {
  const client = useQueryClient();
  const [query, setQuery] = useState<ReportQuery>({ page: 1, pageSize: 20, search: "", type: "", status: "", creator: null, date: "", sort: "newest" });
  const [createType, setCreateType] = useState<ReportType | null>(null);
  const [selected, setSelected] = useState<ReportRecord | null>(null);
  const templates = useQuery({ queryKey: ["report-templates"], queryFn: api.getReportTemplates });
  const records = useQuery({ queryKey: ["reports", "records", query], queryFn: () => api.getReports(query), refetchInterval: 30_000 });
  const summary = useQuery({ queryKey: ["reports-summary"], queryFn: api.getReportSummary, refetchInterval: 30_000 });
  const schedules = useQuery({ queryKey: ["report-schedules"], queryFn: api.getReportSchedules });
  const cameras = useQuery({ queryKey: ["cameras"], queryFn: api.getCameras });
  const operators = useQuery({ queryKey: ["alert-operators"], queryFn: api.getAlertOperators });
  const regenerate = useMutation({ mutationFn: (report: ReportRecord) => api.regenerateReport(report.id), onSuccess: (report) => { void client.invalidateQueries({ queryKey: ["reports"] }); void client.invalidateQueries({ queryKey: ["reports-summary"] }); setSelected(report); } });
  const availableTemplates = templates.data?.items.length ? templates.data.items : fallbackTemplates;
  const generated = (report: ReportRecord) => { setCreateType(null); setSelected(report); void client.invalidateQueries({ queryKey: ["reports"] }); void client.invalidateQueries({ queryKey: ["reports-summary"] }); };
  const metrics = [
    { label: "Reports generated", value: summary.data?.total ?? 0, note: "Persistent report runs", icon: Files, tone: "text-primary" },
    { label: "Ready reports", value: summary.data?.ready ?? 0, note: "PDF and CSV available", icon: FileCheck2, tone: "text-success" },
    { label: "Scheduled reports", value: summary.data?.scheduled ?? 0, note: "Enabled schedules", icon: TimerReset, tone: "text-primary" },
    { label: "Failed reports", value: summary.data?.failed ?? 0, note: "Review and regenerate", icon: FileWarning, tone: "text-danger" },
    { label: "Generated this month", value: summary.data?.thisMonth ?? 0, note: "Current UTC month", icon: FilePlus2, tone: "text-warning" }
  ];
  return <div className="space-y-5"><PageHeader eyebrow="Traffic Archive  ›  Reports" title="Reports Centre" subtitle="Generate, review, and export operational traffic records." action={<button type="button" onClick={() => setCreateType("TRAFFIC_SUMMARY")} className="primary-button h-11"><FilePlus2 size={16} />Create report</button>} />
    <section className="grid gap-3 sm:grid-cols-2 xl:grid-cols-5" aria-label="Reports summary">{summary.isLoading ? <LoadingSkeleton className="h-24 sm:col-span-2 xl:col-span-5" /> : metrics.map(({ label, value, note, icon: Icon, tone }) => <article key={label} className="flex min-h-24 items-center gap-3 rounded-2xl border border-border bg-card p-4 shadow-panel"><span className={`grid h-10 w-10 place-items-center rounded-xl bg-elevated ${tone}`}><Icon size={18} /></span><div><p className="metric-label">{label}</p><strong className="metric-small">{value.toLocaleString()}</strong><p className="metric-note">{note}</p></div></article>)}</section>
    <section><div className="mb-3"><h2 className="text-sm font-bold">Quick report templates</h2><p className="mt-1 text-xs text-muted">Generate an immutable report from recorded data.</p></div><div className="grid gap-3 sm:grid-cols-2 xl:grid-cols-3">{availableTemplates.map((template) => { const Icon = templateIcons[template.type]; return <article key={template.type} className="flex min-h-44 flex-col rounded-2xl border border-border bg-card p-4 shadow-panel"><span className="grid h-10 w-10 place-items-center rounded-xl bg-primary-soft text-primary"><Icon size={18} /></span><h3 className="mt-3 text-sm font-bold">{template.name}</h3><p className="mt-1 flex-1 text-xs leading-5 text-muted">{template.description}</p><button type="button" onClick={() => setCreateType(template.type)} className="secondary-button mt-3 self-start">Generate report</button></article>; })}</div></section>
    <Panel title="Generated reports" action={<button type="button" onClick={() => { void records.refetch(); void summary.refetch(); }} className="icon-button h-9 w-9" aria-label="Refresh reports"><RefreshCw size={14} /></button>}><ReportFiltersBar query={query} operators={operators.data?.items ?? []} onChange={setQuery} /><ReportTable items={records.data?.items ?? []} total={records.data?.total ?? 0} query={query} loading={records.isLoading} error={records.isError} onQueryChange={setQuery} onOpen={setSelected} onRegenerate={(report) => regenerate.mutate(report)} /></Panel>
    {regenerate.error && <p role="alert" className="rounded-xl bg-danger/10 p-3 text-xs text-danger">{regenerate.error.message}</p>}
    <ReportSchedulePanel schedules={schedules.data?.items ?? []} templates={availableTemplates} cameras={cameras.data ?? []} operators={operators.data?.items ?? []} />
    {createType && <ReportCreationDialog key={createType} open initialType={createType} templates={availableTemplates} cameras={cameras.data ?? []} operators={operators.data?.items ?? []} onClose={() => setCreateType(null)} onGenerated={generated} />}
    <ReportPreviewDrawer key={selected?.id ?? "closed"} report={selected} onClose={() => setSelected(null)} onRegenerated={(report) => { setSelected(report); void client.invalidateQueries({ queryKey: ["reports"] }); }} />
  </div>;
}
