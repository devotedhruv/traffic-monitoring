import { ChevronRight } from "lucide-react";
import { Area, AreaChart, CartesianGrid, ResponsiveContainer, Tooltip, XAxis, YAxis } from "recharts";
import { Link } from "../../components/ui/Link";
import { Panel } from "../../components/ui/Panel";
import { EmptyState, LoadingSkeleton } from "../../components/ui/States";
import type { AnalyticsData } from "../../types";

const tooltipStyle = { background: "rgb(var(--color-surface))", border: "1px solid rgb(var(--color-border))", borderRadius: 10, color: "rgb(var(--color-ink))", boxShadow: "var(--shadow-card)", fontSize: 11 };

export function TrafficSummaryChart({ data, loading }: { data?: AnalyticsData; loading: boolean }) {
  return (
    <Panel title="Traffic Summary" action={<Link to="/analytics" className="panel-action">View report <ChevronRight size={14} /></Link>}>
      {loading ? <div className="p-4"><LoadingSkeleton className="h-44" /></div> : !data?.timeline.length ? <EmptyState title="No traffic trend yet" /> : <div className="h-[210px] p-3" role="img" aria-label="Traffic detection trend over the selected period">
        <ResponsiveContainer width="100%" height="100%"><AreaChart data={data.timeline} margin={{ left: -24, right: 4, top: 8, bottom: 0 }}><defs><linearGradient id="dashboardArea" x1="0" y1="0" x2="0" y2="1"><stop offset="0%" stopColor="rgb(var(--color-primary))" stopOpacity={0.38} /><stop offset="100%" stopColor="rgb(var(--color-primary))" stopOpacity={0.02} /></linearGradient></defs><CartesianGrid stroke="rgb(var(--color-border))" strokeDasharray="3 4" vertical={false} /><XAxis dataKey="label" stroke="rgb(var(--color-muted))" tickLine={false} axisLine={false} fontSize={10} /><YAxis stroke="rgb(var(--color-muted))" tickLine={false} axisLine={false} fontSize={10} /><Tooltip contentStyle={tooltipStyle} cursor={{ stroke: "rgb(var(--color-primary))", strokeDasharray: "3 3" }} /><Area type="monotone" dataKey="detections" name="Detections" stroke="rgb(var(--color-primary))" strokeWidth={2.5} fill="url(#dashboardArea)" activeDot={{ r: 4, strokeWidth: 2 }} /></AreaChart></ResponsiveContainer>
      </div>}
    </Panel>
  );
}
