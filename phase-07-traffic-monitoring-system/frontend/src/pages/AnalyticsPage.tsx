import { useState } from "react";
import { useQuery } from "@tanstack/react-query";
import { Gauge, Radar, ShieldAlert } from "lucide-react";
import { ErrorState, LoadingSkeleton } from "../components/ui/States";
import { AnalyticsCharts } from "../features/analytics/AnalyticsCharts";
import { MetricCard } from "../features/dashboard/MetricCard";
import { config } from "../lib/config";
import { formatSpeed } from "../lib/format";
import { api } from "../services/api";
import type { AnalyticsRange } from "../types";

export function AnalyticsPage() {
  const [range, setRange] = useState<AnalyticsRange>("today");
  const result = useQuery({ queryKey: ["analytics", range], queryFn: () => api.getAnalytics(range) });
  return (
    <div className="space-y-4">
      <div className="flex flex-wrap items-end justify-between gap-3"><div><div className="flex items-center gap-2"><p className="text-xs font-bold uppercase tracking-[0.15em] text-cyan">Traffic intelligence</p>{config.useMocks && <span className="rounded border border-amber/30 px-2 py-0.5 text-[10px] font-bold text-amber">DEMO DATA</span>}</div><h1 className="mt-1 text-2xl font-bold">Analytics</h1><p className="mt-1 text-sm text-muted">Operational trends from recorded vehicle detections.</p></div><label className="text-xs text-muted">Time range <select value={range} onChange={(e) => setRange(e.target.value as AnalyticsRange)} className="ml-2 rounded border border-line bg-elevated px-3 py-2 text-sm text-ink"><option value="hour">Last hour</option><option value="today">Today</option><option value="week">Last 7 days</option></select></label></div>
      {result.isLoading ? <LoadingSkeleton className="h-80" /> : result.isError || !result.data ? <ErrorState /> : <><div className="grid gap-3 sm:grid-cols-3"><MetricCard label="Average speed" value={formatSpeed(result.data.averageSpeed)} note="km/h" icon={Gauge} tone="amber" /><MetricCard label="Maximum speed" value={formatSpeed(result.data.maxSpeed)} note="km/h" icon={Radar} tone="danger" /><MetricCard label="Overspeed share" value={`${Math.round((result.data.byStatus.find((s) => s.name === "OVERSPEED")?.value ?? 0) / result.data.byStatus.reduce((sum, item) => sum + item.value, 0) * 100)}%`} note="of detected vehicles" icon={ShieldAlert} tone="danger" /></div><AnalyticsCharts data={result.data} /></>}
    </div>
  );
}
