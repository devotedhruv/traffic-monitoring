import { useEffect, useRef } from "react";
import { Camera, ExternalLink, X } from "lucide-react";
import { Link } from "../../components/ui/Link";
import { formatDateTime, formatSpeed, titleCase } from "../../lib/format";
import { api } from "../../services/api";
import type { ViolationEvent } from "../../types";
import { violationLabel } from "./violationFormat";

export function ViolationDetailsDrawer({ violation, onClose }: { violation: ViolationEvent | null; onClose: () => void }) {
  const close = useRef<HTMLButtonElement>(null);
  useEffect(() => {
    if (!violation) return;
    close.current?.focus();
    const escape = (event: KeyboardEvent) => { if (event.key === "Escape") onClose(); };
    document.addEventListener("keydown", escape);
    return () => document.removeEventListener("keydown", escape);
  }, [violation, onClose]);
  if (!violation) return null;
  const evidence = violation.snapshotUrl ? api.resolveApiUrl(violation.snapshotUrl) : null;
  const details = [
    ["Violation event", `#${violation.id}`],
    ["Violation", violationLabel(violation.type)],
    ["Vehicle record", violation.vehicleId != null ? `#${violation.vehicleId}` : "Not available"],
    ["Tracking ID", `#${violation.trackingId}`],
    ["Vehicle type", titleCase(violation.vehicleType)],
    ["Plate", violation.plate || "Not available"],
    ["Speed", violation.speedAvailable && violation.speed != null ? `${formatSpeed(violation.speed)} km/h` : "Not available"],
    ["Speed limit", violation.speedLimit != null ? `${violation.speedLimit} km/h` : "Not available"],
    ["Confidence", `${Math.round(violation.confidence * 100)}%`],
    ["Lane", violation.laneId != null ? `Lane ${violation.laneId}` : "Not available"],
    ["Direction", violation.direction?.replaceAll("_", " ") || "Not available"],
    ["Camera", violation.cameraName || violation.cameraId],
    ["Detected", formatDateTime(violation.detectedAt)]
  ];
  const vehicleSearch = violation.plate || String(violation.trackingId);
  return <div className="fixed inset-0 z-50 bg-black/65" onMouseDown={(event) => { if (event.target === event.currentTarget) onClose(); }}>
    <aside role="dialog" aria-modal="true" aria-labelledby="violation-drawer-title" className="ml-auto flex h-full w-full max-w-lg flex-col border-l border-border bg-surface shadow-2xl">
      <header className="flex items-center justify-between border-b border-border p-4"><div><p className="text-xs font-bold uppercase tracking-wider text-danger">Confirmed violation</p><h2 id="violation-drawer-title" className="mt-1 text-lg font-bold">{violationLabel(violation.type)} · Event #{violation.id}</h2></div><button ref={close} onClick={onClose} className="rounded p-2 text-muted hover:bg-elevated hover:text-ink" aria-label="Close violation details"><X /></button></header>
      <div className="scrollbar-thin flex-1 overflow-y-auto p-4">
        {evidence ? <a href={evidence} target="_blank" rel="noreferrer" aria-label="Open full violation evidence"><img src={evidence} alt={`Evidence for violation ${violation.id}`} className="mb-4 aspect-video w-full rounded-xl border border-border object-cover" /></a> : <div className="mb-4 grid aspect-video place-items-center rounded-xl border border-border bg-page text-muted"><div className="text-center"><Camera className="mx-auto mb-2" /><span className="text-xs">No violation evidence available</span></div></div>}
        <dl className="divide-y divide-border rounded-xl border border-border">{details.map(([label, value]) => <div key={label} className="flex justify-between gap-4 p-3 text-sm"><dt className="text-muted">{label}</dt><dd className="text-right font-medium capitalize tabular-nums">{value}</dd></div>)}</dl>
        <div className="mt-4 grid gap-2 sm:grid-cols-2"><Link to={`/app/history?search=${encodeURIComponent(vehicleSearch)}`} className="secondary-button h-11">Open matching vehicle <ExternalLink size={14} /></Link>{evidence && <a href={evidence} target="_blank" rel="noreferrer" className="primary-button h-11">Open evidence <ExternalLink size={14} /></a>}</div>
      </div>
    </aside>
  </div>;
}
