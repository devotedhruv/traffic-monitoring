import { ChevronDown, Clapperboard, Radio } from "lucide-react";
import { useJunctions } from "../../app/JunctionContext";
import { cx } from "../../lib/format";
import type { SourceMode } from "../../types";

function SelectShell({ label, children }: { label: string; children: React.ReactNode }) {
  return (
    <label className="flex min-w-0 items-center gap-2 text-xs text-muted">
      <span className="hidden xl:inline">{label}</span>
      <span className="relative min-w-0">{children}<ChevronDown className="pointer-events-none absolute right-3 top-3 text-muted" size={14} /></span>
    </label>
  );
}

export function JunctionSelector() {
  const { junctions, selectedJunction, selectedCamera, junctionCameras, selectedJunctionId, selectedCameraId, sourceMode, setSourceMode, selectJunction, selectCamera } = useJunctions();
  if (!junctions.length) return null;
  return (
    <div className="hidden items-center gap-2 lg:flex" aria-label="Junction and source selection">
      <SelectShell label="Junction">
        <select className="h-10 appearance-none rounded-xl border border-border bg-surface pl-3 pr-9 text-xs font-semibold text-ink hover:border-border-strong" value={selectedJunctionId} onChange={(event) => selectJunction(event.target.value)} aria-label="Select junction">
          {junctions.map((junction) => <option key={junction.id} value={junction.id}>{junction.name}</option>)}
        </select>
      </SelectShell>
      <SelectShell label="Camera">
        <select className="h-10 appearance-none rounded-xl border border-border bg-surface pl-3 pr-9 text-xs font-semibold text-ink hover:border-border-strong" value={selectedCameraId} onChange={(event) => selectCamera(event.target.value)} aria-label="Select camera">
          {junctionCameras.map((camera) => <option key={camera.id} value={camera.id}>{camera.name}</option>)}
        </select>
      </SelectShell>
      <div className="flex h-10 items-center rounded-xl border border-border bg-surface p-1" role="group" aria-label="Source mode">
        <button type="button" onClick={() => setSourceMode("live")} aria-pressed={sourceMode === "live"} className={cx("flex h-full items-center gap-1.5 rounded-lg px-3 text-[10px] font-bold tracking-wide transition-colors", sourceMode === "live" ? "bg-primary-soft text-primary" : "text-muted hover:text-ink")}><Radio size={12} className={sourceMode === "live" ? "text-success" : undefined} />LIVE</button>
        <button type="button" onClick={() => setSourceMode("demo")} aria-pressed={sourceMode === "demo"} className={cx("flex h-full items-center gap-1.5 rounded-lg px-3 text-[10px] font-bold tracking-wide transition-colors", sourceMode === "demo" ? "bg-danger/10 text-danger" : "text-muted hover:text-ink")}><Clapperboard size={12} />DEMO</button>
      </div>
      {selectedJunction && <span className="hidden max-w-[130px] truncate text-[9px] text-muted 2xl:block">{selectedJunction.location}</span>}
      {selectedCamera && <span className="sr-only">Selected camera {selectedCamera.name}</span>}
    </div>
  );
}

export type { SourceMode };
