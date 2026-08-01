import { Activity, CarFront, Clock3, Gauge, Info, MapPin, Palette, Radar, ShieldAlert } from "lucide-react";
import { Bar, BarChart, CartesianGrid, Legend, ResponsiveContainer, Tooltip, XAxis, YAxis } from "recharts";
import { MetricCard } from "../dashboard/MetricCard";
import { Panel } from "../../components/ui/Panel";
import { EmptyState } from "../../components/ui/States";
import { cx, formatBytes, formatDuration, formatSpeed, titleCase } from "../../lib/format";
import type { AnalyzedVehicle, VideoAnalysisResult } from "../../types";

const tooltipStyle = {
  background: "rgb(var(--color-surface))",
  border: "1px solid rgb(var(--color-border))",
  borderRadius: 12,
  color: "rgb(var(--color-ink))",
  boxShadow: "var(--shadow-card)"
};

function ResultBadge({ status }: { status: AnalyzedVehicle["status"] }) {
  return (
    <span className={cx(
      "inline-flex rounded-full border px-2.5 py-1 text-[10px] font-extrabold tracking-wide",
      status === "OVERSPEED"
        ? "border-danger/30 bg-danger/10 text-danger"
        : status === "NORMAL"
          ? "border-success/30 bg-success/10 text-success"
          : "border-line bg-elevated text-muted"
    )}>
      {status === "INSUFFICIENT_DATA" ? "NEEDS MORE FRAMES" : status}
    </span>
  );
}

function Distribution({
  title,
  icon: Icon,
  items
}: {
  title: string;
  icon: typeof CarFront;
  items: { name: string; value: number }[];
}) {
  const maximum = Math.max(...items.map((item) => item.value), 1);
  return (
    <Panel title={title}>
      <div className="space-y-4 p-4">
        {items.length ? items.map((item) => (
          <div key={item.name}>
            <div className="mb-1.5 flex items-center justify-between gap-3 text-sm">
              <span className="flex items-center gap-2 font-semibold"><Icon size={15} className="text-cyan" />{titleCase(item.name)}</span>
              <span className="tabular-nums text-muted">{item.value}</span>
            </div>
            <div className="h-2 overflow-hidden rounded-full bg-elevated">
              <div className="h-full rounded-full bg-primary" style={{ width: `${item.value / maximum * 100}%` }} />
            </div>
          </div>
        )) : <p className="py-6 text-center text-sm text-muted">No reliable data available.</p>}
      </div>
    </Panel>
  );
}

export function AnalysisResults({ result }: { result: VideoAnalysisResult }) {
  const { summary, video, analysis } = result;
  const videoDetails = [
    ["Source", video.sourceType === "link" ? video.sourcePlatform || "Public video link" : "Device upload"],
    ...(video.sourceTitle ? [["Original title", video.sourceTitle]] : []),
    ...(video.sourceUploader ? [["Publisher", video.sourceUploader]] : []),
    ["File", video.filename],
    ["Location", video.location],
    ["File size", formatBytes(video.sizeBytes)],
    ["Duration", formatDuration(video.durationSeconds)],
    ["Resolution", video.width && video.height ? `${video.width} × ${video.height}` : "Unknown"],
    ["Frame rate", `${video.fps.toFixed(1)} FPS`],
    ["Source frames", video.totalFrames.toLocaleString()],
    ["Analyzed frames", video.analyzedFrames.toLocaleString()]
  ];

  return (
    <section className="space-y-4" aria-labelledby="analysis-results-title">
      <div className="flex flex-wrap items-end justify-between gap-3">
        <div>
          <p className="eyebrow">Completed intelligence report</p>
          <h2 id="analysis-results-title" className="mt-1 text-2xl font-extrabold tracking-tight sm:text-3xl">What the video revealed</h2>
          <p className="mt-1 text-sm text-muted">AI-tracked traffic insights from {video.filename}.</p>
        </div>
        <span className="inline-flex items-center gap-2 rounded-full border border-success/25 bg-success/10 px-3 py-1.5 text-xs font-bold text-success">
          <Activity size={14} /> Processed in {analysis.processingSeconds.toFixed(1)}s
        </span>
      </div>

      <div className="grid gap-3 sm:grid-cols-2 xl:grid-cols-4">
        <MetricCard label="Unique vehicles" value={summary.totalVehicles} note="Tracked across the video" icon={CarFront} />
        <MetricCard label="Overspeed" value={summary.overspeedVehicles} note={`Estimated above ${formatSpeed(summary.speedLimit)} km/h`} icon={ShieldAlert} tone="danger" />
        <MetricCard label="Average speed" value={summary.averageSpeed === null ? "—" : formatSpeed(summary.averageSpeed)} note="km/h · calibrated estimate" icon={Gauge} tone="amber" />
        <MetricCard label="Maximum speed" value={summary.maxSpeed === null ? "—" : formatSpeed(summary.maxSpeed)} note="km/h · per-vehicle estimate" icon={Radar} tone="success" />
      </div>

      <div className="flex gap-3 rounded-2xl border border-primary/20 bg-primary-soft p-4 text-sm text-secondary">
        <Info className="mt-0.5 shrink-0 text-primary" size={18} />
        <div><p className="font-bold">Speed calibration matters</p><p className="mt-1 text-xs leading-5 text-muted">{analysis.note} Current scale: {analysis.calibrationMetersPerPixel} metres per pixel.</p></div>
      </div>

      <div className="grid gap-4 xl:grid-cols-[minmax(0,1.5fr)_minmax(320px,0.7fr)]">
        <Panel title="Traffic arrival timeline">
          {result.timeline.length ? (
            <div className="h-80 p-4" role="img" aria-label="Chart of vehicle appearances and overspeed vehicles over video time">
              <ResponsiveContainer width="100%" height="100%">
                <BarChart data={result.timeline}>
                  <CartesianGrid stroke="rgb(var(--color-border))" strokeDasharray="4 5" vertical={false} />
                  <XAxis dataKey="label" stroke="rgb(var(--color-muted))" fontSize={11} />
                  <YAxis allowDecimals={false} stroke="rgb(var(--color-muted))" fontSize={11} />
                  <Tooltip contentStyle={tooltipStyle} />
                  <Legend />
                  <Bar dataKey="detections" name="Vehicles" fill="rgb(var(--color-primary))" radius={[5, 5, 0, 0]} />
                  <Bar dataKey="overspeed" name="Overspeed" fill="rgb(var(--color-danger))" radius={[5, 5, 0, 0]} />
                </BarChart>
              </ResponsiveContainer>
            </div>
          ) : <EmptyState title="No timeline available" message="The uploaded video did not expose readable timing information." />}
        </Panel>

        <Panel title="Video details">
          <dl className="divide-y divide-line">
            {videoDetails.map(([label, value]) => (
              <div key={label} className="flex items-start justify-between gap-4 px-4 py-3 text-sm">
                <dt className="text-muted">{label}</dt>
                <dd className="max-w-[65%] break-words text-right font-semibold tabular-nums">{value}</dd>
              </div>
            ))}
          </dl>
          <div className="grid grid-cols-2 border-t border-line">
            <div className="border-r border-line p-4"><Clock3 size={16} className="mb-2 text-cyan" /><p className="text-[10px] font-bold uppercase tracking-wider text-muted">Peak traffic</p><p className="mt-1 font-bold tabular-nums">{summary.peakTrafficAtSeconds === null ? "—" : formatDuration(summary.peakTrafficAtSeconds)}</p></div>
            <div className="p-4"><MapPin size={16} className="mb-2 text-cyan" /><p className="text-[10px] font-bold uppercase tracking-wider text-muted">Road / place</p><p className="mt-1 truncate font-bold" title={video.location}>{video.location}</p></div>
          </div>
        </Panel>
      </div>

      <div className="grid gap-4 md:grid-cols-2">
        <Distribution title="Vehicle mix" icon={CarFront} items={result.vehicleTypes} />
        <Distribution title="Detected colours" icon={Palette} items={result.vehicleColors} />
      </div>

      <Panel title={`Vehicle details · ${result.vehicles.length}`}>
        {result.vehicles.length ? (
          <>
            <div className="hidden max-h-[560px] overflow-auto lg:block scrollbar-thin">
              <table className="w-full min-w-[1050px] border-collapse text-left text-sm">
                <thead className="sticky top-0 z-10 bg-elevated text-[10px] uppercase tracking-wider text-muted">
                  <tr>{["Track", "Type", "Colour", "First seen", "Visible for", "Direction", "Confidence", "Est. speed", "Peak", "Status"].map((heading) => <th key={heading} className="border-b border-line px-4 py-3 font-bold">{heading}</th>)}</tr>
                </thead>
                <tbody className="divide-y divide-line">
                  {result.vehicles.map((vehicle) => (
                    <tr key={vehicle.trackingId} className="hover:bg-elevated/50">
                      <td className="px-4 py-3 font-bold tabular-nums text-cyan">#{vehicle.trackingId}</td>
                      <td className="px-4 py-3 font-semibold">{titleCase(vehicle.vehicleType)}</td>
                      <td className="px-4 py-3 text-muted">{titleCase(vehicle.color)}</td>
                      <td className="px-4 py-3 tabular-nums">{formatDuration(vehicle.firstSeenSeconds)}</td>
                      <td className="px-4 py-3 tabular-nums text-muted">{vehicle.trackedForSeconds.toFixed(1)}s</td>
                      <td className="px-4 py-3 text-muted">{vehicle.direction}</td>
                      <td className="px-4 py-3 tabular-nums">{Math.round(vehicle.confidence * 100)}%</td>
                      <td className="px-4 py-3 font-semibold tabular-nums">{vehicle.estimatedSpeed === null ? "—" : `${formatSpeed(vehicle.estimatedSpeed)} km/h`}</td>
                      <td className="px-4 py-3 tabular-nums text-muted">{vehicle.peakSpeed === null ? "—" : `${formatSpeed(vehicle.peakSpeed)} km/h`}</td>
                      <td className="px-4 py-3"><ResultBadge status={vehicle.status} /></td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
            <div className="divide-y divide-line lg:hidden">
              {result.vehicles.map((vehicle) => (
                <article key={vehicle.trackingId} className="space-y-3 p-4">
                  <div className="flex items-start justify-between gap-3"><div><p className="font-extrabold text-cyan">Track #{vehicle.trackingId}</p><p className="text-sm text-muted">{titleCase(vehicle.vehicleType)} · {titleCase(vehicle.color)}</p></div><ResultBadge status={vehicle.status} /></div>
                  <dl className="grid grid-cols-2 gap-3 text-xs">
                    <div><dt className="text-muted">Est. speed</dt><dd className="mt-1 font-bold">{vehicle.estimatedSpeed === null ? "—" : `${formatSpeed(vehicle.estimatedSpeed)} km/h`}</dd></div>
                    <div><dt className="text-muted">First seen</dt><dd className="mt-1 font-bold">{formatDuration(vehicle.firstSeenSeconds)}</dd></div>
                    <div><dt className="text-muted">Direction</dt><dd className="mt-1 font-bold">{vehicle.direction}</dd></div>
                    <div><dt className="text-muted">Confidence</dt><dd className="mt-1 font-bold">{Math.round(vehicle.confidence * 100)}%</dd></div>
                  </dl>
                </article>
              ))}
            </div>
          </>
        ) : <EmptyState title="No road vehicles detected" message="Try a clearer road video with visible cars, motorcycles, buses, trucks, or bicycles." />}
      </Panel>
    </section>
  );
}
