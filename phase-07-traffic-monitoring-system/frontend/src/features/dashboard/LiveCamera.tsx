import { useRef, useState } from "react";
import { Camera, Expand, Grid2X2, Monitor, Radio, SlidersHorizontal, VideoOff } from "lucide-react";
import { config } from "../../lib/config";
import { cx } from "../../lib/format";
import { api } from "../../services/api";
import type { ConnectionStatus } from "../../types";

const categories = [
  { name: "All", color: "bg-success" }, { name: "Vehicle", color: "bg-info" },
  { name: "Person", color: "bg-purple" }, { name: "Bicycle", color: "bg-warning" }, { name: "Violation", color: "bg-danger" }
] as const;

export function LiveCamera({ cameraId, cameraName, connection, fps, trackingId }: { cameraId: string; cameraName: string; connection: ConnectionStatus; fps: number; trackingId?: number }) {
  const container = useRef<HTMLDivElement>(null);
  const imageRef = useRef<HTMLImageElement>(null);
  const [loaded, setLoaded] = useState(false);
  const [grid, setGrid] = useState(false);
  const [contain, setContain] = useState(false);
  const [category, setCategory] = useState<(typeof categories)[number]["name"]>("All");
  const [confidence, setConfidence] = useState(30);
  const [message, setMessage] = useState("");
  const canStream = !config.useMocks && connection !== "offline";
  const fullscreen = () => container.current?.requestFullscreen?.();
  const screenshot = () => {
    const image = imageRef.current;
    if (!image?.naturalWidth) { setMessage("No camera frame is available yet."); return; }
    try {
      const canvas = document.createElement("canvas");
      canvas.width = image.naturalWidth; canvas.height = image.naturalHeight;
      canvas.getContext("2d")?.drawImage(image, 0, 0);
      const link = document.createElement("a");
      link.download = `trafficops-${Date.now()}.png`; link.href = canvas.toDataURL("image/png"); link.click();
      setMessage("Camera snapshot downloaded.");
    } catch { setMessage("Snapshot permission was denied by the camera server."); }
  };
  return (
    <div>
      <div ref={container} className="relative grid aspect-video min-h-64 place-items-center overflow-hidden rounded-t-2xl bg-black text-white">
        {canStream ? <img ref={imageRef} crossOrigin="anonymous" src={api.getStreamUrl(cameraId)} onLoad={() => setLoaded(true)} onError={() => setLoaded(false)} className={cx("h-full w-full", contain ? "object-contain" : "object-cover")} alt={`Annotated live traffic feed from ${cameraName}`} /> : <div className="max-w-sm p-6 text-center text-white/65"><VideoOff className="mx-auto mb-3" size={34} /><p className="text-sm font-semibold text-white">{config.useMocks ? "Live video unavailable in demo mode" : "Camera stream offline"}</p><p className="mt-1 text-xs">Connect the Python camera pipeline to display the real annotated feed.</p></div>}
        {canStream && !loaded && <span className="absolute text-sm text-white/60">Connecting to camera stream…</span>}
        {grid && <div className="pointer-events-none absolute inset-0 bg-[linear-gradient(rgb(255_255_255/.12)_1px,transparent_1px),linear-gradient(90deg,rgb(255_255_255/.12)_1px,transparent_1px)] bg-[size:12.5%_12.5%]" />}
        <div className="pointer-events-none absolute inset-x-0 top-0 flex items-center justify-between bg-gradient-to-b from-black/75 to-transparent p-3 text-[10px] font-bold">
          <span className="flex items-center gap-2 rounded-lg bg-black/45 px-2.5 py-1.5"><Radio size={12} className={connection === "connected" ? "text-success" : "text-warning"} /><strong>LIVE FEED</strong><span className="font-medium text-white/75">{cameraName}</span></span>
          <span className="flex items-center gap-2"><button type="button" onClick={screenshot} className="pointer-events-auto grid h-8 w-8 place-items-center rounded-lg bg-black/50 hover:bg-black/80" aria-label="Download camera screenshot" title="Screenshot"><Camera size={15} /></button><button type="button" onClick={fullscreen} className="pointer-events-auto grid h-8 w-8 place-items-center rounded-lg bg-black/50 hover:bg-black/80" aria-label="View camera fullscreen" title="Fullscreen"><Expand size={15} /></button><span className="rounded-lg bg-black/50 px-2.5 py-2 tabular-nums text-success">● {fps.toFixed(1)} FPS</span></span>
        </div>
        <div className="pointer-events-none absolute inset-x-0 bottom-0 flex items-end justify-between bg-gradient-to-t from-black/75 to-transparent p-3"><span className="rounded-lg bg-black/50 px-2.5 py-1.5 text-[10px] font-semibold">{trackingId ? `LATEST VEHICLE #${trackingId}` : "AWAITING DETECTION"}</span>{message && <span role="status" className="max-w-[52%] rounded-lg bg-black/70 px-2 py-1 text-right text-[9px]">{message}</span>}</div>
      </div>
      <div className="flex flex-wrap items-center gap-2 border-t border-border bg-card p-3">
        <button type="button" className={cx("detection-control", grid && "detection-control-active")} onClick={() => setGrid((value) => !value)} aria-pressed={grid} title="Grid overlay"><Grid2X2 size={16} /></button>
        <button type="button" className={cx("detection-control", contain && "detection-control-active")} onClick={() => setContain((value) => !value)} aria-pressed={contain} title="Camera fit"><Monitor size={16} /></button>
        <span className="mx-1 hidden h-6 w-px bg-border sm:block" />
        {categories.map((item) => <button type="button" key={item.name} onClick={() => setCategory(item.name)} aria-pressed={category === item.name} className={cx("detection-pill", category === item.name && "detection-pill-active")}><span className={cx("h-2 w-2 rounded-full", item.color)} />{item.name}</button>)}
        <label className="ml-auto flex min-w-[185px] items-center gap-2 text-[10px] text-muted"><span>Confidence</span><output className="rounded-lg border border-border px-2 py-1 tabular-nums text-ink">{(confidence / 100).toFixed(2)}</output><input type="range" min="10" max="90" step="5" value={confidence} onChange={(event) => setConfidence(Number(event.target.value))} className="min-w-0 flex-1 accent-primary" aria-label="Detection confidence threshold" /></label>
        <button type="button" className="detection-control" onClick={() => setMessage(`Showing ${category.toLowerCase()} detections at ${(confidence / 100).toFixed(2)} confidence.`)} aria-label="Apply detection settings" title="Detection settings"><SlidersHorizontal size={16} /></button>
      </div>
    </div>
  );
}
