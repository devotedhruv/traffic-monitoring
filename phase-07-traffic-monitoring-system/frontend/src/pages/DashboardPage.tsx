import { Activity, CarFront, Gauge, ShieldAlert } from "lucide-react";
import { useQuery } from "@tanstack/react-query";
import { useLive } from "../app/LiveContext";
import { Panel } from "../components/ui/Panel";
import { LoadingSkeleton } from "../components/ui/States";
import { ActiveVehicleCard } from "../features/dashboard/ActiveVehicleCard";
import { LiveCamera } from "../features/dashboard/LiveCamera";
import { MetricCard } from "../features/dashboard/MetricCard";
import { SpeedGauge } from "../features/dashboard/SpeedGauge";
import { HistoryPanel } from "../features/vehicles/HistoryPanel";
import { formatSpeed } from "../lib/format";
import { api } from "../services/api";

export function DashboardPage() {
  const { latest, connection, fps } = useLive();
  const summary = useQuery({ queryKey: ["summary"], queryFn: api.getSummary });
  const currentSpeed = latest?.speed ?? 0;
  return (
    <div className="space-y-4">
      <div className="grid gap-4 xl:grid-cols-[minmax(0,1fr)_380px]">
        <Panel title="Camera 01 / Live feed" className="min-w-0"><LiveCamera cameraId="camera-01" cameraName="North Junction" connection={connection} fps={fps} trackingId={latest?.trackingId} /></Panel>
        <aside className="grid content-start gap-4">
          <div className="grid grid-cols-2 gap-3">
            {summary.isLoading ? <><LoadingSkeleton /><LoadingSkeleton /><LoadingSkeleton /><LoadingSkeleton /></> : <>
              <MetricCard label="Vehicles" value={summary.data?.totalVehicles ?? 0} note="Unique detections" icon={CarFront} />
              <MetricCard label="Overspeed" value={summary.data?.overspeedVehicles ?? 0} note="Above 50 km/h" icon={ShieldAlert} tone="danger" />
              <MetricCard label="Average speed" value={`${formatSpeed(summary.data?.averageSpeed ?? 0)}`} note="km/h" icon={Gauge} tone="amber" />
              <MetricCard label="Current FPS" value={fps.toFixed(1)} note={connection === "connected" ? "Pipeline healthy" : "Stream unavailable"} icon={Activity} tone="success" />
            </>}
          </div>
          <Panel title="Current speed"><SpeedGauge speed={currentSpeed} limit={latest?.speedLimit ?? 50} /></Panel>
          <Panel title="Active vehicle"><ActiveVehicleCard vehicle={latest} /></Panel>
        </aside>
      </div>
      <HistoryPanel compact />
    </div>
  );
}
