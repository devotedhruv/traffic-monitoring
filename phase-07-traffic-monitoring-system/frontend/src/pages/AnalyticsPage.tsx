import { useMemo, useState } from "react";
import { useQuery } from "@tanstack/react-query";
import { BarChart3, CalendarDays, Clock3, Download, Gauge, Radar, ShieldAlert, TrendingUp } from "lucide-react";
import { Area, AreaChart, ResponsiveContainer } from "recharts";
import { PageHeader } from "../components/ui/PageHeader";
import { ErrorState, LoadingSkeleton } from "../components/ui/States";
import { AnalyticsCharts } from "../features/analytics/AnalyticsCharts";
import { config } from "../lib/config";
import { cx, formatSpeed } from "../lib/format";
import { api } from "../services/api";
import type { AnalyticsData, AnalyticsRange } from "../types";

function AnalyticsMetric({ label, value, unit, icon: Icon, data, tone = "primary" }: { label: string; value: string; unit?: string; icon: typeof Gauge; data: AnalyticsData["timeline"]; tone?: "primary" | "danger" }) {
  const color = tone === "danger" ? "danger" : "primary";
  return <article className="grid min-h-[142px] grid-cols-[1fr_130px] items-center gap-3 rounded-2xl border border-border bg-card p-4 shadow-panel"><div><span className={cx("grid h-10 w-10 place-items-center rounded-xl", tone === "danger" ? "bg-danger/10 text-danger" : "bg-primary/10 text-primary")}><Icon size={19} /></span><p className="mt-3 text-[10px] font-bold uppercase tracking-[.08em] text-muted">{label}</p><p className="mt-1 text-[27px] font-extrabold tracking-tight tabular-nums">{value} {unit && <span className="text-xs font-semibold text-secondary">{unit}</span>}</p><p className="mt-1 flex items-center gap-1 text-[10px] text-muted"><TrendingUp size={12} className="text-success" />Current selected period</p></div><div className="h-20"><ResponsiveContainer width="100%" height="100%"><AreaChart data={data}><defs><linearGradient id={`metric-${color}`} x1="0" y1="0" x2="0" y2="1"><stop offset="0%" stopColor={`rgb(var(--color-${color}))`} stopOpacity={.28} /><stop offset="100%" stopColor={`rgb(var(--color-${color}))`} stopOpacity={0} /></linearGradient></defs><Area type="monotone" dataKey="detections" stroke={`rgb(var(--color-${color}))`} strokeWidth={2} fill={`url(#metric-${color})`} /></AreaChart></ResponsiveContainer></div></article>;
}

function downloadReport(data: AnalyticsData, range: string) {
  const rows = ["Period,Detections,Overspeed", ...data.timeline.map((item) => `${item.label},${item.detections},${item.overspeed}`)].join("\n");
  const url = URL.createObjectURL(new Blob([rows], { type: "text/csv" })); const link = document.createElement("a"); link.href = url; link.download = `trafficops-analytics-${range}.csv`; link.click(); URL.revokeObjectURL(url);
}

export function AnalyticsPage() {
  const [range, setRange] = useState<AnalyticsRange>("today");
  const result = useQuery({ queryKey: ["analytics", range], queryFn: () => api.getAnalytics(range) });
  const total = result.data?.byStatus.reduce((sum, item) => sum + item.value, 0) ?? 0;
  const overspeed = result.data?.byStatus.find((item) => item.name === "OVERSPEED")?.value ?? 0;
  const share = total ? overspeed / total * 100 : 0;
  const busiest = useMemo(() => result.data?.timeline.length ? [...result.data.timeline].sort((a, b) => b.detections - a.detections)[0] : null, [result.data]);
  return (
    <div className="space-y-4">
      <PageHeader title="Analytics" subtitle="Operational trends from recorded vehicle detections." eyebrow={config.useMocks ? "Traffic intelligence · Demo data" : undefined} action={<div className="flex flex-wrap items-center gap-2"><label className="flex h-10 items-center gap-2 text-xs text-muted"><CalendarDays size={16} />Time range <select value={range} onChange={(event) => setRange(event.target.value as AnalyticsRange)} className="h-10 rounded-xl border border-border bg-surface px-3 text-xs font-semibold text-ink"><option value="hour">Last hour</option><option value="today">Today</option><option value="week">Last 7 days</option></select></label><button type="button" disabled={!result.data} onClick={() => result.data && downloadReport(result.data, range)} className="secondary-button"><Download size={15} />Export report</button></div>} />
      {result.isLoading ? <><div className="grid gap-3 md:grid-cols-3"><LoadingSkeleton className="h-36" /><LoadingSkeleton className="h-36" /><LoadingSkeleton className="h-36" /></div><LoadingSkeleton className="h-96" /></> : result.isError || !result.data ? <ErrorState message="Analytics could not be loaded. Check the API connection and try again." /> : <>
        <div className="grid gap-3 md:grid-cols-3"><AnalyticsMetric label="Average speed" value={formatSpeed(result.data.averageSpeed)} unit="km/h" icon={Gauge} data={result.data.timeline} /><AnalyticsMetric label="Maximum speed" value={formatSpeed(result.data.maxSpeed)} unit="km/h" icon={Radar} data={result.data.timeline} /><AnalyticsMetric label="Overspeed share" value={`${share.toFixed(1)}%`} icon={ShieldAlert} data={result.data.timeline.map((item) => ({ ...item, detections: item.overspeed }))} tone="danger" /></div>
        <AnalyticsCharts data={result.data} />
        <section className="grid divide-y divide-border overflow-hidden rounded-2xl border border-border bg-card shadow-panel sm:grid-cols-2 sm:divide-x sm:divide-y-0 xl:grid-cols-5"><div className="flex items-center gap-3 p-4"><span className="summary-icon"><BarChart3 size={17} /></span><div><strong className="block text-sm">Today at a glance</strong><span className="text-[10px] text-muted">Key traffic insights</span></div></div><div className="summary-stat"><Clock3 /><div><span>Busiest period</span><strong>{busiest?.label ?? "—"}</strong><small>{busiest?.detections.toLocaleString() ?? 0} detections</small></div></div><div className="summary-stat"><BarChart3 /><div><span>Total detections</span><strong>{total.toLocaleString()}</strong><small>Selected period</small></div></div><div className="summary-stat"><Radar /><div><span>Highest speed</span><strong>{formatSpeed(result.data.maxSpeed)} <small>km/h</small></strong><small>Recorded maximum</small></div></div><div className="summary-stat text-danger"><ShieldAlert /><div><span>Overspeed events</span><strong>{overspeed.toLocaleString()}</strong><small>{share.toFixed(2)}% of total</small></div></div></section>
      </>}
    </div>
  );
}
