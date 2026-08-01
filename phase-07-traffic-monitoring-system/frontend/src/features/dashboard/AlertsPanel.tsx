import { AlertTriangle, Bike, ChevronRight, ShieldAlert } from "lucide-react";
import { Link } from "../../components/ui/Link";
import { Panel } from "../../components/ui/Panel";
import { formatSpeed, formatTime } from "../../lib/format";
import type { VehicleDetection } from "../../types";

export function AlertsPanel({ latest }: { latest: VehicleDetection | null }) {
  const overspeed = latest?.status === "OVERSPEED";
  return (
    <Panel title="Alerts & Violations" action={<Link to="/history?status=OVERSPEED" className="panel-action">View all <ChevronRight size={14} /></Link>}>
      <div className="grid gap-3 p-3 sm:grid-cols-3 xl:grid-cols-1 2xl:grid-cols-3">
        <article className={`alert-card ${overspeed ? "border-danger/25 bg-danger/5" : ""}`}>
          <span className="alert-icon bg-danger/10 text-danger"><ShieldAlert size={16} /></span>
          <div><h3 className="text-xs font-bold">{overspeed ? "Overspeed detected" : "Overspeed monitoring"}</h3><p className="mt-2 text-[11px] text-muted">{latest ? `Vehicle ID: #${latest.trackingId}` : "No active vehicle"}</p><p className={`mt-1 text-[11px] ${overspeed ? "font-semibold text-danger" : "text-muted"}`}>{latest ? `${formatSpeed(latest.speed)} km/h in ${latest.speedLimit} km/h zone` : "Waiting for detections"}</p><p className="mt-4 text-[10px] tabular-nums text-muted">{latest ? formatTime(latest.detectedAt) : "—"}</p></div>
        </article>
        <article className="alert-card"><span className="alert-icon bg-warning/10 text-warning"><Bike size={16} /></span><div><h3 className="text-xs font-bold">No helmet</h3><p className="mt-2 text-[11px] text-muted">No active event</p><p className="mt-1 text-[11px] text-muted">Motorcycle rider safety</p><p className="mt-4 text-[10px] text-success">Monitoring</p></div></article>
        <article className="alert-card"><span className="alert-icon bg-purple/10 text-purple"><AlertTriangle size={16} /></span><div><h3 className="text-xs font-bold">Wrong lane</h3><p className="mt-2 text-[11px] text-muted">No active event</p><p className="mt-1 text-[11px] text-muted">Lane discipline monitoring</p><p className="mt-4 text-[10px] text-success">Monitoring</p></div></article>
      </div>
    </Panel>
  );
}
