import { Bar, BarChart, CartesianGrid, Cell, Legend, Pie, PieChart, ResponsiveContainer, Tooltip, XAxis, YAxis } from "recharts";
import type { AnalyticsData } from "../../types";

const tooltipStyle = { background: "#151d2b", border: "1px solid #273449", borderRadius: 6, color: "#edf3fb" };

export function AnalyticsCharts({ data }: { data: AnalyticsData }) {
  return (
    <div className="grid gap-4 xl:grid-cols-2">
      <section className="rounded-lg border border-line bg-card p-4"><h2 className="mb-4 text-sm font-bold">Detections over time</h2><div className="h-72" role="img" aria-label="Bar chart of detections and overspeed violations over time"><ResponsiveContainer width="100%" height="100%"><BarChart data={data.timeline}><CartesianGrid stroke="#273449" vertical={false} /><XAxis dataKey="label" stroke="#8997aa" fontSize={11} /><YAxis stroke="#8997aa" fontSize={11} /><Tooltip contentStyle={tooltipStyle} /><Legend /><Bar dataKey="detections" name="Detections" fill="#21d4c2" radius={[3, 3, 0, 0]} /><Bar dataKey="overspeed" name="Overspeed" fill="#ff5d6c" radius={[3, 3, 0, 0]} /></BarChart></ResponsiveContainer></div></section>
      <section className="rounded-lg border border-line bg-card p-4"><h2 className="mb-4 text-sm font-bold">Vehicle distribution</h2><div className="h-72" role="img" aria-label="Pie chart of detections by vehicle type"><ResponsiveContainer width="100%" height="100%"><PieChart><Pie data={data.byType} dataKey="value" nameKey="name" innerRadius={55} outerRadius={88} paddingAngle={3}>{["#21d4c2", "#ffbd59", "#45dc8c", "#8997aa"].map((color) => <Cell key={color} fill={color} />)}</Pie><Tooltip contentStyle={tooltipStyle} /><Legend /></PieChart></ResponsiveContainer></div></section>
    </div>
  );
}
