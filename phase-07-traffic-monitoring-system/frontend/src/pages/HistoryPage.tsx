import { CalendarDays, Database, ShieldCheck } from "lucide-react";
import { useQuery } from "@tanstack/react-query";
import { PageHeader } from "../components/ui/PageHeader";
import { LoadingSkeleton } from "../components/ui/States";
import { HistoryPanel } from "../features/vehicles/HistoryPanel";
import { api } from "../services/api";

export function HistoryPage() {
  const summary = useQuery({ queryKey: ["summary"], queryFn: api.getSummary });
  const today = useQuery({ queryKey: ["vehicles", "today-count"], queryFn: () => api.getVehicles({ page: 1, pageSize: 1, date: "today", status: "", type: "", speed: "", search: "", sort: "time_desc" }) });
  const total = summary.data?.totalVehicles ?? 0;
  const normal = total ? Math.max(0, (total - (summary.data?.overspeedVehicles ?? 0)) / total * 100) : 0;
  return <div className="space-y-5">
    <div className="grid gap-4 xl:grid-cols-[minmax(0,1fr)_minmax(480px,.8fr)]"><PageHeader eyebrow="Traffic Archive  ›  Detections" title="Detection History" subtitle="Search, filter, and inspect recorded vehicle events." />
      <section className="grid grid-cols-3 divide-x divide-border rounded-2xl border border-border bg-card p-3 shadow-panel" aria-label="Detection summary">{summary.isLoading ? <LoadingSkeleton className="col-span-3 h-16" /> : <><div className="flex items-center gap-3 px-3"><span className="summary-icon"><Database size={17} /></span><div><p className="metric-label">Total detections</p><strong className="metric-small">{total.toLocaleString()}</strong><p className="metric-note">All time</p></div></div><div className="flex items-center gap-3 px-3"><span className="summary-icon"><CalendarDays size={17} /></span><div><p className="metric-label">Today’s detections</p><strong className="metric-small">{today.data?.total.toLocaleString() ?? "—"}</strong><p className="metric-note">Last 24 hours</p></div></div><div className="flex items-center gap-3 px-3"><span className="summary-icon"><ShieldCheck size={17} /></span><div><p className="metric-label">Normal events</p><strong className="metric-small">{normal.toFixed(1)}%</strong><p className="metric-note">Of total detections</p></div></div></> }</section>
    </div><HistoryPanel /></div>;
}
