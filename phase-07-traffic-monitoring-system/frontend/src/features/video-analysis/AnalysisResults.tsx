import { useMemo, useRef, useState } from "react";
import {
  Activity,
  AlertTriangle,
  CarFront,
  CheckCircle2,
  Clock3,
  Eye,
  Gauge,
  Info,
  MapPin,
  Palette,
  Play,
  Radar,
  Radio,
  Search,
  ShieldAlert,
  Video,
  XCircle
} from "lucide-react";
import { Bar, BarChart, CartesianGrid, Legend, ResponsiveContainer, Tooltip, XAxis, YAxis } from "recharts";
import { MetricCard } from "../dashboard/MetricCard";
import { Panel } from "../../components/ui/Panel";
import { EmptyState } from "../../components/ui/States";
import { cx, formatBytes, formatDuration, formatSpeed, titleCase } from "../../lib/format";
import { api } from "../../services/api";
import type { AnalyzedVehicle, VideoAnalysisResult, VideoAnalysisViolation } from "../../types";

type ResultTab = "overview" | "detections" | "violations";
type AnalysisFilter = "all" | "violation" | "overspeed" | string;

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

function buildViolationEvents(vehicles: AnalyzedVehicle[]): VideoAnalysisViolation[] {
  return vehicles.flatMap((vehicle) => vehicle.violations.map((type) => ({
    id: `${vehicle.trackingId}:${type}`,
    trackingId: vehicle.trackingId,
    type,
    vehicleType: vehicle.vehicleType,
    plate: vehicle.plate,
    lane: vehicle.lane,
    direction: vehicle.direction,
    speed: vehicle.estimatedSpeed,
    speedLimit: vehicle.speedLimit,
    confidence: vehicle.confidence,
    detectedAtSeconds: vehicle.countedAtSeconds ?? vehicle.firstSeenSeconds
  })));
}

function matchesFilter(vehicle: AnalyzedVehicle, filter: AnalysisFilter) {
  if (filter === "all") return true;
  if (filter === "violation") return vehicle.violations.length > 0;
  if (filter === "overspeed") return vehicle.violations.includes("OVERSPEED");
  return vehicle.vehicleType.toLowerCase() === filter;
}

export function AnalysisResults({ result }: { result: VideoAnalysisResult }) {
  const { summary, video, analysis } = result;
  const videoRef = useRef<HTMLVideoElement>(null);
  const [currentTime, setCurrentTime] = useState(0);
  const [playbackDuration, setPlaybackDuration] = useState(video.durationSeconds);
  const [playing, setPlaying] = useState(false);
  const [tab, setTab] = useState<ResultTab>("overview");
  const [filter, setFilter] = useState<AnalysisFilter>("all");
  const [query, setQuery] = useState("");
  const violationEvents = useMemo(
    () => result.violations ?? buildViolationEvents(result.vehicles),
    [result.vehicles, result.violations]
  );
  const typeFilters = useMemo(
    () => [...new Set(result.vehicles.map((vehicle) => vehicle.vehicleType.toLowerCase()))],
    [result.vehicles]
  );
  const filteredVehicles = useMemo(() => {
    const needle = query.trim().toLowerCase();
    return result.vehicles.filter((vehicle) => {
      if (!matchesFilter(vehicle, filter)) return false;
      if (!needle) return true;
      return [
        vehicle.trackingId,
        vehicle.vehicleType,
        vehicle.plate,
        vehicle.color,
        vehicle.direction,
        vehicle.status,
        ...vehicle.violations
      ].some((value) => String(value ?? "").toLowerCase().includes(needle));
    });
  }, [filter, query, result.vehicles]);
  const activeVehicles = useMemo(
    () => result.vehicles.filter((vehicle) => (
      matchesFilter(vehicle, filter)
      && currentTime >= Math.max(0, vehicle.firstSeenSeconds - 0.2)
      && currentTime <= vehicle.lastSeenSeconds + 0.35
    )),
    [currentTime, filter, result.vehicles]
  );
  const filteredViolations = useMemo(() => violationEvents.filter((event) => {
    if (filter === "overspeed") return event.type === "OVERSPEED";
    if (filter !== "all" && filter !== "violation") return event.vehicleType.toLowerCase() === filter;
    return true;
  }), [filter, violationEvents]);

  const seekTo = (seconds: number) => {
    if (!videoRef.current) return;
    videoRef.current.currentTime = Math.max(0, Math.min(seconds, playbackDuration || video.durationSeconds));
    setCurrentTime(videoRef.current.currentTime);
    void videoRef.current.play().catch(() => undefined);
  };
  const selectFilter = (next: AnalysisFilter) => {
    setFilter(next);
    if (next === "violation" || next === "overspeed") setTab("violations");
  };
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
          <p className="eyebrow">In-app analysis command centre</p>
          <h2 id="analysis-results-title" className="mt-1 text-2xl font-extrabold tracking-tight sm:text-3xl">Analyzed traffic playback</h2>
          <p className="mt-1 text-sm text-muted">Review detections, tracks, speeds and violations without downloading the result.</p>
        </div>
        <span className="inline-flex items-center gap-2 rounded-full border border-success/25 bg-success/10 px-3 py-1.5 text-xs font-bold text-success">
          <Activity size={14} /> Processed in {analysis.processingSeconds.toFixed(1)}s
        </span>
      </div>

      <div className="grid gap-3 sm:grid-cols-2 xl:grid-cols-4">
        <MetricCard label="Validated vehicles" value={summary.totalVehicles} note={`${summary.lineCrossingVehicles} crossed the count line`} icon={CarFront} />
        <MetricCard label="Rule violations" value={summary.totalViolations ?? violationEvents.length} note={`${summary.overspeedVehicles} overspeed events`} icon={ShieldAlert} tone="danger" />
        <MetricCard label="Average speed" value={summary.averageSpeed === null ? "—" : formatSpeed(summary.averageSpeed)} note="km/h · calibrated estimate" icon={Gauge} tone="amber" />
        <MetricCard label="Maximum speed" value={summary.maxSpeed === null ? "—" : formatSpeed(summary.maxSpeed)} note="km/h · per-vehicle estimate" icon={Radar} tone="success" />
      </div>

      <div className="grid gap-4 xl:grid-cols-[minmax(0,1.55fr)_minmax(300px,.45fr)]">
        <Panel title="Annotated traffic playback">
          {result.artifacts.annotatedVideoUrl ? (
            <div className="p-3">
              <div className="relative overflow-hidden rounded-xl bg-black">
                <video
                  ref={videoRef}
                  controls
                  autoPlay
                  muted
                  playsInline
                  preload="metadata"
                  className="aspect-video w-full object-contain"
                  src={api.resolveApiUrl(result.artifacts.annotatedVideoUrl)}
                  aria-label="Annotated analysis playback with vehicle tracks, road lanes, speed and count line"
                  onLoadedMetadata={(event) => setPlaybackDuration(event.currentTarget.duration || video.durationSeconds)}
                  onTimeUpdate={(event) => setCurrentTime(event.currentTarget.currentTime)}
                  onPlay={() => setPlaying(true)}
                  onPause={() => setPlaying(false)}
                  onEnded={() => setPlaying(false)}
                />
                <div className="pointer-events-none absolute left-3 top-3 flex items-center gap-2 rounded-lg bg-black/75 px-2.5 py-1.5 text-[10px] font-bold text-white backdrop-blur">
                  <Radio size={12} className={playing ? "text-success" : "text-warning"} />
                  {playing ? "ANALYSIS PLAYING" : "ANALYSIS PAUSED"}
                </div>
                <div className="pointer-events-none absolute bottom-11 left-3 flex items-center gap-2 rounded-lg bg-black/75 px-2.5 py-1.5 text-[10px] font-bold text-white backdrop-blur">
                  DETECTED {result.vehicles.length} · ON SCREEN {activeVehicles.length} · {formatDuration(currentTime)}
                </div>
              </div>
              <div className="mt-3 flex flex-wrap gap-2" aria-label="Filter analyzed traffic data">
                {["all", ...typeFilters, "violation", "overspeed"].map((value) => (
                  <button
                    key={value}
                    type="button"
                    aria-pressed={filter === value}
                    onClick={() => selectFilter(value)}
                    className={cx(
                      "inline-flex min-h-9 items-center gap-2 rounded-lg border px-3 text-[10px] font-semibold transition",
                      filter === value ? "border-primary bg-primary-soft text-primary" : "border-border bg-surface text-muted hover:text-ink"
                    )}
                  >
                    <span className={cx("h-2 w-2 rounded-full", value === "violation" || value === "overspeed" ? "bg-danger" : "bg-primary")} />
                    {titleCase(value)}
                  </button>
                ))}
              </div>
              <p className="mt-2 flex items-start gap-2 text-[10px] leading-4 text-muted">
                <Video size={13} className="mt-0.5 shrink-0 text-primary" />
                The verification video keeps every audit box visible. Filters update the synchronized tracks and records shown in this workspace.
              </p>
            </div>
          ) : <EmptyState title="Annotated output unavailable" message="The video codec could not produce a browser-playable verification file." />}
        </Panel>

        <Panel title={`Tracks at ${formatDuration(currentTime)}`}>
          <div className="max-h-[510px] divide-y divide-line overflow-auto scrollbar-thin">
            {activeVehicles.length ? activeVehicles.map((vehicle) => (
              <button key={vehicle.trackingId} type="button" onClick={() => seekTo(vehicle.firstSeenSeconds)} className="block w-full p-4 text-left transition hover:bg-elevated/50">
                <div className="flex items-start justify-between gap-2">
                  <div><p className="font-bold text-cyan">Track #{vehicle.trackingId}</p><p className="mt-1 text-xs text-muted">{titleCase(vehicle.vehicleType)} · {titleCase(vehicle.color)}</p></div>
                  <ResultBadge status={vehicle.status} />
                </div>
                <div className="mt-3 grid grid-cols-2 gap-2 text-[10px]">
                  <span className="text-muted">Speed <strong className="ml-1 text-ink">{vehicle.estimatedSpeed === null ? "—" : `${formatSpeed(vehicle.estimatedSpeed)} km/h`}</strong></span>
                  <span className="text-muted">Lane <strong className="ml-1 text-ink">{vehicle.lane ?? "—"}</strong></span>
                  <span className="col-span-2 truncate text-muted">{vehicle.direction}</span>
                </div>
              </button>
            )) : (
              <div className="px-4 py-12 text-center"><Eye className="mx-auto text-muted" size={25} /><p className="mt-3 text-sm font-bold">No matching track on screen</p><p className="mt-1 text-[10px] leading-4 text-muted">Play or seek the video, or choose another filter.</p></div>
            )}
          </div>
        </Panel>
      </div>

      <nav className="flex flex-wrap gap-1 rounded-xl border border-border bg-card p-1" aria-label="Analysis result sections">
        {([
          ["overview", "Overview", result.vehicles.length],
          ["detections", "Detections", filteredVehicles.length],
          ["violations", "Violations", filteredViolations.length]
        ] as const).map(([value, label, count]) => (
          <button key={value} type="button" onClick={() => setTab(value)} className={cx("rounded-lg px-4 py-2 text-xs font-bold transition", tab === value ? "bg-primary-soft text-primary" : "text-muted hover:text-ink")}>{label} <span className="ml-1 tabular-nums opacity-70">{count}</span></button>
        ))}
      </nav>

      {tab === "overview" && (
        <div className="space-y-4">
          <div className={cx("flex gap-3 rounded-2xl border p-4 text-sm text-secondary", analysis.perspectiveCalibrated ? "border-primary/20 bg-primary-soft" : "border-warning/30 bg-warning/10")}>
            <Info className="mt-0.5 shrink-0 text-primary" size={18} />
            <div><p className="font-bold">{analysis.perspectiveCalibrated ? "Perspective-calibrated speed" : "Low-confidence fallback speed"}</p><p className="mt-1 text-xs leading-5 text-muted">{analysis.note}{!analysis.perspectiveCalibrated && ` Current fallback: ${analysis.calibrationMetersPerPixel} metres per pixel.`}</p></div>
          </div>
          <div className="grid gap-4 xl:grid-cols-[minmax(0,1.5fr)_minmax(320px,0.7fr)]">
            <Panel title="Traffic arrival timeline">
              {result.timeline.length ? (
                <div className="h-80 p-4" role="img" aria-label="Chart of vehicle appearances and overspeed vehicles over video time">
                  <ResponsiveContainer width="100%" height="100%">
                    <BarChart data={result.timeline} onClick={(state) => { if (state?.activePayload?.[0]?.payload?.startSeconds !== undefined) seekTo(state.activePayload[0].payload.startSeconds); }}>
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
                    <dt className="text-muted">{label}</dt><dd className="max-w-[65%] break-words text-right font-semibold tabular-nums">{value}</dd>
                  </div>
                ))}
              </dl>
              <div className="grid grid-cols-2 border-t border-line">
                <div className="border-r border-line p-4"><Clock3 size={16} className="mb-2 text-cyan" /><p className="text-[10px] font-bold uppercase tracking-wider text-muted">Peak traffic</p><p className="mt-1 font-bold tabular-nums">{summary.peakTrafficAtSeconds === null ? "—" : formatDuration(summary.peakTrafficAtSeconds)}</p></div>
                <div className="p-4"><MapPin size={16} className="mb-2 text-cyan" /><p className="text-[10px] font-bold uppercase tracking-wider text-muted">Road / place</p><p className="mt-1 truncate font-bold" title={video.location}>{video.location}</p></div>
              </div>
            </Panel>
          </div>
          <div className="grid gap-4 md:grid-cols-2"><Distribution title="Vehicle mix" icon={CarFront} items={result.vehicleTypes} /><Distribution title="Detected colours" icon={Palette} items={result.vehicleColors} /></div>
          <Panel title="Analysis capabilities">
            <div className="grid md:grid-cols-2 xl:grid-cols-3">
              {Object.entries(result.capabilities).map(([name, capability]) => (
                <div key={name} className="flex items-start gap-3 border-b border-line p-4 md:border-r">
                  {capability.available ? <CheckCircle2 size={16} className="mt-0.5 shrink-0 text-success" /> : <XCircle size={16} className="mt-0.5 shrink-0 text-muted" />}
                  <div className="min-w-0"><p className="text-xs font-bold">{titleCase(name.replace(/([A-Z])/g, " $1"))}</p><p className="mt-1 text-[10px] leading-4 text-muted">{capability.available ? capability.model || capability.method || "Enabled" : capability.reason || "Not configured"}</p></div>
                </div>
              ))}
            </div>
          </Panel>
        </div>
      )}

      {tab === "detections" && (
        <Panel title={`Detection records · ${filteredVehicles.length}`}>
          <div className="border-b border-line p-3">
            <label className="flex max-w-md items-center gap-2 rounded-xl border border-border bg-surface px-3 text-muted"><Search size={15} /><input value={query} onChange={(event) => setQuery(event.target.value)} placeholder="Search track, type, plate, direction…" className="h-10 min-w-0 flex-1 bg-transparent text-xs text-ink outline-none" /></label>
          </div>
          {filteredVehicles.length ? (
            <div className="max-h-[620px] overflow-auto scrollbar-thin">
              <table className="w-full min-w-[1120px] border-collapse text-left text-sm">
                <thead className="sticky top-0 z-10 bg-elevated text-[10px] uppercase tracking-wider text-muted"><tr>{["Track", "Type / plate", "Colour", "First seen", "Visible for", "Lane / direction", "Confidence", "Est. speed", "Peak", "Status", "Evidence"].map((heading) => <th key={heading} className="border-b border-line px-4 py-3 font-bold">{heading}</th>)}</tr></thead>
                <tbody className="divide-y divide-line">
                  {filteredVehicles.map((vehicle) => (
                    <tr key={vehicle.trackingId} className="hover:bg-elevated/50">
                      <td className="px-4 py-3 font-bold tabular-nums text-cyan">#{vehicle.trackingId}</td>
                      <td className="px-4 py-3 font-semibold">{titleCase(vehicle.vehicleType)}{vehicle.plate && <small className="mt-1 block font-mono text-cyan">{vehicle.plate}</small>}</td>
                      <td className="px-4 py-3 text-muted">{titleCase(vehicle.color)}</td>
                      <td className="px-4 py-3 tabular-nums">{formatDuration(vehicle.firstSeenSeconds)}</td>
                      <td className="px-4 py-3 tabular-nums text-muted">{vehicle.trackedForSeconds.toFixed(1)}s</td>
                      <td className="px-4 py-3 text-muted">{vehicle.lane ? `Lane ${vehicle.lane} · ` : ""}{vehicle.direction}</td>
                      <td className="px-4 py-3 tabular-nums">{Math.round(vehicle.confidence * 100)}%</td>
                      <td className="px-4 py-3 font-semibold tabular-nums">{vehicle.estimatedSpeed === null ? "—" : `${formatSpeed(vehicle.estimatedSpeed)} km/h`}<small className="mt-1 block text-[9px] text-muted">{vehicle.speedConfidence} · {vehicle.speedSamples} samples</small></td>
                      <td className="px-4 py-3 tabular-nums text-muted">{vehicle.peakSpeed === null ? "—" : `${formatSpeed(vehicle.peakSpeed)} km/h`}</td>
                      <td className="px-4 py-3"><ResultBadge status={vehicle.status} /></td>
                      <td className="px-4 py-3"><button type="button" onClick={() => seekTo(vehicle.firstSeenSeconds)} className="secondary-button whitespace-nowrap"><Play size={13} />View track</button></td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          ) : <EmptyState title="No matching detections" message="Clear the search or choose another vehicle filter." />}
        </Panel>
      )}

      {tab === "violations" && (
        <Panel title={`Violation evidence · ${filteredViolations.length}`}>
          {filteredViolations.length ? (
            <div className="max-h-[620px] overflow-auto scrollbar-thin">
              <table className="w-full min-w-[980px] border-collapse text-left text-sm">
                <thead className="sticky top-0 z-10 bg-elevated text-[10px] uppercase tracking-wider text-muted"><tr>{["Event", "Vehicle", "Violation", "Speed / limit", "Lane / direction", "Detected", "Confidence", "Evidence"].map((heading) => <th key={heading} className="border-b border-line px-4 py-3 font-bold">{heading}</th>)}</tr></thead>
                <tbody className="divide-y divide-line">
                  {filteredViolations.map((event, index) => (
                    <tr key={event.id} className="hover:bg-elevated/50">
                      <td className="px-4 py-3 font-bold text-cyan">#{index + 1}</td>
                      <td className="px-4 py-3"><strong>{titleCase(event.vehicleType)} · Track #{event.trackingId}</strong><small className="mt-1 block font-mono text-muted">{event.plate || "Plate unavailable"}</small></td>
                      <td className="px-4 py-3"><span className="inline-flex items-center gap-1.5 rounded-full border border-danger/30 bg-danger/10 px-2.5 py-1 text-[10px] font-extrabold text-danger"><AlertTriangle size={11} />{titleCase(event.type)}</span></td>
                      <td className="px-4 py-3 font-semibold tabular-nums">{event.speed === null ? "Not measured" : `${formatSpeed(event.speed)} / ${formatSpeed(event.speedLimit)} km/h`}</td>
                      <td className="px-4 py-3 text-muted">{event.lane ? `Lane ${event.lane} · ` : ""}{event.direction}</td>
                      <td className="px-4 py-3 tabular-nums">{formatDuration(event.detectedAtSeconds)}</td>
                      <td className="px-4 py-3 tabular-nums">{Math.round(event.confidence * 100)}%</td>
                      <td className="px-4 py-3"><button type="button" onClick={() => seekTo(event.detectedAtSeconds)} className="secondary-button whitespace-nowrap"><Eye size={13} />Review moment</button></td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          ) : <EmptyState title="No confirmed violations" message="No configured traffic rule was violated in the selected video or filter." />}
        </Panel>
      )}
    </section>
  );
}
