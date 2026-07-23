import { useRef, useState } from "react";
import { Expand, Radio, VideoOff } from "lucide-react";
import { config } from "../../lib/config";
import { api } from "../../services/api";
import type { ConnectionStatus } from "../../types";

export function LiveCamera({ cameraId, cameraName, connection, fps, trackingId }: { cameraId: string; cameraName: string; connection: ConnectionStatus; fps: number; trackingId?: number }) {
  const container = useRef<HTMLDivElement>(null);
  const [loaded, setLoaded] = useState(false);
  const canStream = !config.useMocks && connection !== "offline";
  const fullscreen = () => container.current?.requestFullscreen?.();
  return (
    <div ref={container} className="relative grid aspect-video min-h-64 place-items-center overflow-hidden bg-black">
      {canStream ? <img src={api.getStreamUrl(cameraId)} onLoad={() => setLoaded(true)} onError={() => setLoaded(false)} className="h-full w-full object-contain" alt={`Annotated live traffic feed from ${cameraName}`} /> : (
        <div className="max-w-sm p-6 text-center text-muted"><VideoOff className="mx-auto mb-3" size={34} /><p className="text-sm font-semibold text-ink">{config.useMocks ? "Live video unavailable in demo mode" : "Camera stream offline"}</p><p className="mt-1 text-xs">The annotated MJPEG feed will appear here when the Python web backend is connected.</p></div>
      )}
      {canStream && !loaded && <span className="absolute text-sm text-muted">Connecting to camera stream…</span>}
      <div className="pointer-events-none absolute inset-x-0 top-0 flex items-center justify-between bg-gradient-to-b from-black/70 to-transparent p-3 text-[11px] font-bold">
        <span className="flex items-center gap-1.5"><Radio size={12} className={connection === "connected" ? "text-success" : "text-amber"} />{cameraName}</span>
        <span className="tabular-nums">{fps.toFixed(1)} FPS</span>
      </div>
      <div className="absolute inset-x-0 bottom-0 flex items-end justify-between bg-gradient-to-t from-black/70 to-transparent p-3">
        <span className="text-[11px] text-muted">{trackingId ? `LATEST VEHICLE #${trackingId}` : "AWAITING DETECTION"}</span>
        <button onClick={fullscreen} className="rounded bg-black/50 p-2 text-ink hover:bg-black" aria-label="View camera fullscreen"><Expand size={16} /></button>
      </div>
    </div>
  );
}
