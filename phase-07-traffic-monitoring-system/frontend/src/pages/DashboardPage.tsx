import { Activity, CarFront, Gauge, MapPin, ShieldAlert } from "lucide-react";
import { useQuery } from "@tanstack/react-query";
import { useLive } from "../app/LiveContext";
import { PageHeader } from "../components/ui/PageHeader";
import { Panel } from "../components/ui/Panel";
import { LoadingSkeleton } from "../components/ui/States";
import { ActiveVehicleCard } from "../features/dashboard/ActiveVehicleCard";
import { AlertsPanel } from "../features/dashboard/AlertsPanel";
import { LiveCamera } from "../features/dashboard/LiveCamera";
import { MetricCard } from "../features/dashboard/MetricCard";
import { SpeedGauge } from "../features/dashboard/SpeedGauge";
import { TrafficSummaryChart } from "../features/dashboard/TrafficSummaryChart";
import { formatSpeed } from "../lib/format";
import { api } from "../services/api";

export function DashboardPage() {
  const { latest, connection, fps } = useLive();
  const summary = useQuery({ queryKey: ["summary"], queryFn: api.getSummary });
  const analytics = useQuery({ queryKey: ["analytics", "today"], queryFn: () => api.getAnalytics("today") });
  const currentSpeed = latest?.speed ?? 0;
  return (
    <div className="space-y-4">
      <PageHeader title="Traffic Command Centre" subtitle="Real-time vehicle movement, speed, and violation awareness." action={<span className="inline-flex h-10 items-center gap-2 rounded-xl border border-primary/20 bg-primary-soft px-3 text-xs font-semibold text-primary"><MapPin size={15} />Camera 01 · North Junction</span>} />
      <div className="grid gap-4 2xl:grid-cols-[minmax(0,1fr)_344px]">
        <div className="min-w-0 space-y-4">
          <section className="overflow-hidden rounded-2xl border border-border bg-card shadow-panel" aria-label="Live traffic camera"><LiveCamera cameraId="camera-01" cameraName="North Junction" connection={connection} fps={fps} trackingId={latest?.trackingId} /></section>
          <div className="grid gap-4 xl:grid-cols-[minmax(0,.95fr)_minmax(0,1.05fr)]"><AlertsPanel latest={latest} /><TrafficSummaryChart data={analytics.data} loading={analytics.isLoading} /></div>
        </div>
        <aside className="grid content-start gap-3 md:grid-cols-2 2xl:grid-cols-1">
          <Panel title="Overview" className="md:col-span-2 2xl:col-span-1">
            <div className="grid grid-cols-2 gap-2.5 p-3">
              {summary.isLoading ? <><LoadingSkeleton /><LoadingSkeleton /><LoadingSkeleton /><LoadingSkeleton /></> : <>
                <MetricCard compact label="Unique detections" value={(summary.data?.totalVehicles ?? 0).toLocaleString()} note="Recorded vehicles" icon={CarFront} />
                <MetricCard compact label="Overspeed" value={(summary.data?.overspeedVehicles ?? 0).toLocaleString()} note="Above configured limit" icon={ShieldAlert} tone="danger" />
                <MetricCard compact label="Average speed" value={formatSpeed(summary.data?.averageSpeed ?? 0)} unit="km/h" note="Current average" icon={Gauge} tone="amber" />
                <MetricCard compact label="Current FPS" value={fps.toFixed(1)} unit="FPS" note={connection === "connected" ? "Pipeline healthy" : "Stream unavailable"} icon={Activity} />
              </>}
            </div>
          </Panel>
          <Panel title="Speed Monitor"><SpeedGauge speed={currentSpeed} limit={latest?.speedLimit ?? summary.data?.speedLimit ?? 50} /><p className="-mt-3 pb-4 text-center text-[10px] text-muted">Current speed</p></Panel>
          <Panel title="Active Vehicle"><ActiveVehicleCard vehicle={latest} /></Panel>
        </aside>
      </div>
    </div>
  );
}
