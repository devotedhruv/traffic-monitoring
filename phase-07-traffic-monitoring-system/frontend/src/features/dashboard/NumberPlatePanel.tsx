import { CarFront, ScanLine, ShieldCheck } from "lucide-react";
import { Link } from "../../components/ui/Link";
import { Panel } from "../../components/ui/Panel";
import { formatSpeed, formatTime } from "../../lib/format";
import { api } from "../../services/api";
import type { Capability, VehicleDetection } from "../../types";

export function NumberPlatePanel({ vehicles, total = 0, capability, loading = false }: {
  vehicles: VehicleDetection[];
  total?: number;
  capability?: Capability;
  loading?: boolean;
}) {
  return <Panel title="Number plate recognition" action={<span className="text-[10px] font-semibold text-muted">{total.toLocaleString()} confirmed</span>}>
    {!capability?.available ? <div className="m-3 flex min-h-28 items-start gap-3 rounded-xl border border-warning/25 bg-warning/5 p-4">
      <span className="grid h-9 w-9 shrink-0 place-items-center rounded-lg bg-warning/10 text-warning"><ScanLine size={18} /></span>
      <div><p className="text-xs font-bold">Plate recognition not configured</p><p className="mt-1 text-[11px] leading-5 text-muted">{capability?.reason ?? "Checking detector and OCR availability…"}</p><p className="mt-2 text-[10px] text-muted">Install dedicated plate-detector weights and the configured OCR engine. Unknown plates are never guessed.</p></div>
    </div> : loading ? <div className="p-4 text-xs text-muted">Loading confirmed plate reads…</div> : vehicles.length === 0 ? <div className="m-3 grid min-h-28 place-items-center rounded-xl border border-dashed border-border p-4 text-center"><div><ShieldCheck className="mx-auto text-success" size={22} /><p className="mt-2 text-xs font-semibold">Monitoring confirmed plates</p><p className="mt-1 text-[10px] text-muted">A plate appears here only after consistent OCR reads across multiple frames.</p></div></div> : <div className="grid gap-2 p-3 md:grid-cols-2 xl:grid-cols-3">
      {vehicles.map((vehicle) => <article key={vehicle.id} className="grid grid-cols-[88px_minmax(0,1fr)] gap-3 rounded-xl border border-border bg-surface-secondary/35 p-2.5">
        <div className="grid h-[68px] place-items-center overflow-hidden rounded-lg border border-border bg-black/80">
          {vehicle.plateSnapshotUrl ? <img src={api.resolveApiUrl(vehicle.plateSnapshotUrl)} alt={`Plate ${vehicle.plate}`} className="h-full w-full object-cover" /> : <ScanLine size={21} className="text-white/55" />}
        </div>
        <div className="min-w-0">
          <div className="flex items-start justify-between gap-2"><strong className="truncate rounded-md bg-primary-soft px-2 py-1 font-mono text-sm tracking-wide text-primary">{vehicle.plate}</strong><span className="text-[9px] font-semibold tabular-nums text-success">{vehicle.plateConfidence == null ? "—" : `${Math.round(vehicle.plateConfidence * 100)}%`}</span></div>
          <p className="mt-2 flex items-center gap-1 text-[10px] font-semibold capitalize text-secondary"><CarFront size={12} />{vehicle.vehicleType} · ID #{vehicle.trackingId}</p>
          <p className="mt-1 text-[9px] tabular-nums text-muted">{vehicle.speedAvailable === false ? "Speed pending" : `${formatSpeed(vehicle.speed)} km/h`} · {formatTime(vehicle.detectedAt)}</p>
          <Link to={`/app/history?search=${encodeURIComponent(vehicle.plate ?? String(vehicle.trackingId))}`} className="mt-1 inline-flex text-[9px] font-bold text-primary">Matching vehicle data</Link>
        </div>
      </article>)}
    </div>}
  </Panel>;
}
