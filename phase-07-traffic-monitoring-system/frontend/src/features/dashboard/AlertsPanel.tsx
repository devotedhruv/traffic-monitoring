import { AlertTriangle, Bike, ChevronRight, ShieldAlert } from "lucide-react";
import type { ReactNode } from "react";
import { Link } from "../../components/ui/Link";
import { Panel } from "../../components/ui/Panel";
import { formatSpeed, formatTime } from "../../lib/format";
import type { Capability, VehicleDetection, ViolationEvent } from "../../types";

function SpecialistAlert({ title, icon, event, capability, tone, link }: {
  title: string;
  icon: ReactNode;
  event?: ViolationEvent;
  capability?: Capability;
  tone: "warning" | "purple";
  link: string;
}) {
  const configured = capability?.available === true;
  const active = Boolean(event);
  const toneClass = tone === "warning" ? "bg-warning/10 text-warning" : "bg-purple/10 text-purple";
  return <article className={`alert-card ${active ? "border-danger/25 bg-danger/5" : ""}`}>
    <span className={`alert-icon ${toneClass}`}>{icon}</span>
    <div className="min-w-0">
      <h3 className="text-xs font-bold">{active ? `${title} detected` : title}</h3>
      {!configured ? <>
        <p className="mt-2 text-[11px] font-semibold text-warning">Not configured</p>
        <p className="mt-1 line-clamp-2 text-[10px] text-muted">{capability?.reason ?? "Capability status unavailable"}</p>
      </> : event ? <>
        <p className="mt-2 text-[11px] text-muted">Vehicle ID: #{event.trackingId}{event.laneId ? ` · Lane ${event.laneId}` : ""}</p>
        <p className="mt-1 text-[10px] text-muted">{event.cameraName ?? event.cameraId} · {Math.round(event.confidence * 100)}% confidence</p>
        {event.snapshotUrl && <a href={event.snapshotUrl} target="_blank" rel="noreferrer" className="mt-2 block" aria-label={`Open ${title.toLowerCase()} evidence`}><img src={event.snapshotUrl} alt={`${title} evidence for vehicle ${event.trackingId}`} className="h-14 w-full rounded-lg border border-border object-cover" /></a>}
        <p className="mt-2 text-[10px] tabular-nums text-muted">{formatTime(event.detectedAt)}{event.snapshotUrl && <> · <a href={event.snapshotUrl} target="_blank" rel="noreferrer" className="font-semibold text-primary">Evidence</a></>}</p>
      </> : <>
        <p className="mt-2 text-[11px] text-muted">No confirmed event</p>
        <p className="mt-1 text-[10px] text-success">Monitoring</p>
      </>}
      <Link to={link} className="mt-2 inline-flex text-[10px] font-semibold text-primary">View history</Link>
    </div>
  </article>;
}

export function AlertsPanel({ latest, violations, capabilities }: {
  latest: VehicleDetection | null;
  violations: ViolationEvent[];
  capabilities?: { helmetDetection: Capability; wrongLaneDetection: Capability };
}) {
  const overspeed = latest?.status === "OVERSPEED";
  const noHelmet = violations.find((event) => event.type === "NO_HELMET");
  const wrongLane = violations.find((event) => event.type === "WRONG_LANE");
  return (
    <Panel title="Alerts & Violations" action={<Link to="/app/history" className="panel-action">View all <ChevronRight size={14} /></Link>}>
      <div className="grid gap-3 p-3 sm:grid-cols-3 xl:grid-cols-1 2xl:grid-cols-3">
        <article className={`alert-card ${overspeed ? "border-danger/25 bg-danger/5" : ""}`}>
          <span className="alert-icon bg-danger/10 text-danger"><ShieldAlert size={16} /></span>
          <div><h3 className="text-xs font-bold">{overspeed ? "Overspeed detected" : "Overspeed monitoring"}</h3><p className="mt-2 text-[11px] text-muted">{latest ? `Vehicle ID: #${latest.trackingId}` : "No active vehicle"}</p><p className={`mt-1 text-[11px] ${overspeed ? "font-semibold text-danger" : "text-muted"}`}>{latest ? `${formatSpeed(latest.speed)} km/h in ${latest.speedLimit} km/h zone` : "Waiting for detections"}</p><p className="mt-4 text-[10px] tabular-nums text-muted">{latest ? formatTime(latest.detectedAt) : "—"}</p></div>
        </article>
        <SpecialistAlert title="No helmet" icon={<Bike size={16} />} event={noHelmet} capability={capabilities?.helmetDetection} tone="warning" link="/app/history?violation=NO_HELMET" />
        <SpecialistAlert title="Wrong lane" icon={<AlertTriangle size={16} />} event={wrongLane} capability={capabilities?.wrongLaneDetection} tone="purple" link="/app/history?violation=WRONG_LANE" />
      </div>
    </Panel>
  );
}
