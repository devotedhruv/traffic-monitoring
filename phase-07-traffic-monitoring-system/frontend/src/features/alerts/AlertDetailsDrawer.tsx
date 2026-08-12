import { useEffect, useRef, useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { Camera, CheckCircle2, ExternalLink, SearchCheck, ShieldCheck, UserRoundCheck, X, XCircle } from "lucide-react";
import { Link } from "../../components/ui/Link";
import { ErrorState, LoadingSkeleton } from "../../components/ui/States";
import { cx, formatDateTime, formatSpeed, titleCase } from "../../lib/format";
import { api } from "../../services/api";
import type { AlertDetail, AlertRecord, AuthUser } from "../../types";
import { alertStatusLabel, alertTypeLabel, severityTone, statusTone } from "./alertFormat";

type NoteAction = "resolve" | "false-positive";

export function AlertDetailsDrawer({ alert, operators, onClose }: {
  alert: AlertRecord | null;
  operators: AuthUser[];
  onClose: () => void;
}) {
  const client = useQueryClient();
  const close = useRef<HTMLButtonElement>(null);
  const [noteAction, setNoteAction] = useState<NoteAction | null>(null);
  const [note, setNote] = useState("");
  const detail = useQuery({
    queryKey: ["alerts", "detail", alert?.id],
    queryFn: () => api.getAlert(alert!.id),
    enabled: Boolean(alert),
    placeholderData: alert ? { ...alert, activity: [], occurrences: [] } satisfies AlertDetail : undefined
  });
  const commit = (updated: AlertDetail) => {
    client.setQueryData(["alerts", "detail", updated.id], updated);
    void client.invalidateQueries({ queryKey: ["alerts"] });
    void client.invalidateQueries({ queryKey: ["alert-summary"] });
    setNoteAction(null);
    setNote("");
  };
  const workflow = useMutation({
    mutationFn: ({ action, text, version }: { action: "acknowledge" | "investigate" | NoteAction; text?: string; version: number }) => api.updateAlertStatus(alert!.id, action, version, text),
    onSuccess: commit
  });
  const assignment = useMutation({
    mutationFn: ({ userId, version }: { userId: number | null; version: number }) => api.assignAlert(alert!.id, userId, version),
    onSuccess: commit
  });
  useEffect(() => {
    if (!alert) return;
    close.current?.focus();
    const escape = (event: KeyboardEvent) => { if (event.key === "Escape") onClose(); };
    document.addEventListener("keydown", escape);
    return () => document.removeEventListener("keydown", escape);
  }, [alert, onClose]);
  if (!alert) return null;
  const current = detail.data;
  const busy = workflow.isPending || assignment.isPending;
  const error = workflow.error || assignment.error;
  const evidence = current?.snapshotUrl ? api.resolveApiUrl(current.snapshotUrl) : null;
  const run = (action: "acknowledge" | "investigate") => {
    if (current) workflow.mutate({ action, version: current.version });
  };
  const confirmNote = () => {
    if (current && noteAction && note.trim()) workflow.mutate({ action: noteAction, text: note.trim(), version: current.version });
  };
  const details = current ? [
    ["Alert", `#${current.id}`],
    ["Violation", `${alertTypeLabel(current.type)} · #${current.violationId}`],
    ["Vehicle", `${titleCase(current.vehicleType)}${current.vehicleId != null ? ` · DB #${current.vehicleId}` : ""}`],
    ["Plate / tracking", current.plate || `Track #${current.trackingId}`],
    ["Speed", current.speedAvailable && current.speed != null ? `${formatSpeed(current.speed)} / ${current.speedLimit} km/h` : "Not available"],
    ["Lane / direction", `${current.laneId != null ? `Lane ${current.laneId}` : "Not available"}${current.direction ? ` · ${current.direction.replaceAll("_", " ")}` : ""}`],
    ["Camera", current.cameraName],
    ["Confidence", `${Math.round(current.confidence * 100)}%`],
    ["Occurrences", String(current.occurrenceCount)],
    ["First detected", formatDateTime(current.firstOccurrenceAt)],
    ["Last detected", formatDateTime(current.lastOccurrenceAt)]
  ] : [];
  return <div className="fixed inset-0 z-50 bg-black/65" onMouseDown={(event) => { if (event.target === event.currentTarget) onClose(); }}>
    <aside role="dialog" aria-modal="true" aria-labelledby="alert-drawer-title" className="ml-auto flex h-full w-full max-w-2xl flex-col border-l border-border bg-surface shadow-2xl">
      <header className="flex items-start justify-between gap-4 border-b border-border p-4"><div><p className="text-xs font-bold uppercase tracking-wider text-danger">Operational alert</p><h2 id="alert-drawer-title" className="mt-1 text-lg font-bold">{current ? `${alertTypeLabel(current.type)} · Alert #${current.id}` : `Alert #${alert.id}`}</h2>{current && <div className="mt-2 flex gap-2"><span className={cx("rounded-lg border px-2 py-1 text-[9px] font-extrabold", severityTone(current.severity))}>{current.severity}</span><span className={cx("rounded-lg px-2 py-1 text-[9px] font-bold uppercase", statusTone(current.status))}>{alertStatusLabel(current.status)}</span></div>}</div><button ref={close} onClick={onClose} className="rounded p-2 text-muted hover:bg-elevated hover:text-ink" aria-label="Close alert details"><X /></button></header>
      <div className="scrollbar-thin flex-1 overflow-y-auto p-4">
        {detail.isLoading && <LoadingSkeleton className="h-80" />}
        {detail.isError && <ErrorState message="Alert details could not be loaded." />}
        {current && <>
          {evidence ? <a href={evidence} target="_blank" rel="noreferrer"><img src={evidence} alt={`Evidence for alert ${current.id}`} className="mb-4 aspect-video w-full rounded-xl border border-border object-cover" /></a> : <div className="mb-4 grid aspect-video place-items-center rounded-xl border border-border bg-page text-muted"><div className="text-center"><Camera className="mx-auto mb-2" /><span className="text-xs">No evidence image is available</span></div></div>}
          <section className="mb-4 rounded-xl border border-border bg-card p-3" aria-label="Alert workflow">
            <div className="flex flex-wrap gap-2">
              {current.status === "NEW" && <button disabled={busy} type="button" onClick={() => run("acknowledge")} className="secondary-button"><ShieldCheck size={14} />Acknowledge</button>}
              {["NEW", "ACKNOWLEDGED"].includes(current.status) && <button disabled={busy} type="button" onClick={() => run("investigate")} className="secondary-button"><SearchCheck size={14} />Investigate</button>}
              {!(["RESOLVED", "FALSE_POSITIVE"] as string[]).includes(current.status) && <><button disabled={busy} type="button" onClick={() => setNoteAction("resolve")} className="secondary-button text-success"><CheckCircle2 size={14} />Resolve</button><button disabled={busy} type="button" onClick={() => setNoteAction("false-positive")} className="secondary-button text-muted"><XCircle size={14} />False positive</button></>}
            </div>
            <label className="mt-3 block text-[10px] font-bold uppercase tracking-wider text-muted">Assigned operator<select disabled={busy || ["RESOLVED", "FALSE_POSITIVE"].includes(current.status)} value={current.assignedTo?.id ?? ""} onChange={(event) => assignment.mutate({ userId: event.target.value ? Number(event.target.value) : null, version: current.version })} className="field mt-1"><option value="">Unassigned</option>{operators.map((operator) => <option key={operator.id} value={operator.id}>{operator.name} · {operator.email}</option>)}</select></label>
            {noteAction && <div className="mt-3 rounded-xl border border-border bg-surface-secondary p-3"><label className="text-xs font-semibold">{noteAction === "resolve" ? "Resolution note" : "False-positive reason"}<textarea autoFocus maxLength={500} value={note} onChange={(event) => setNote(event.target.value)} className="field mt-2 h-24 resize-none py-3" placeholder={noteAction === "resolve" ? "Describe the action taken…" : "Explain why this detection is not valid…"} /></label><div className="mt-2 flex justify-end gap-2"><button type="button" onClick={() => { setNoteAction(null); setNote(""); }} className="secondary-button">Cancel</button><button type="button" disabled={!note.trim() || busy} onClick={confirmNote} className="primary-button h-10">Confirm</button></div></div>}
            {error && <p role="alert" className="mt-3 rounded-lg bg-danger/10 p-2 text-xs text-danger">{error instanceof Error ? error.message : "The alert could not be updated."}</p>}
          </section>
          <dl className="divide-y divide-border rounded-xl border border-border">{details.map(([label, value]) => <div key={label} className="flex justify-between gap-4 p-3 text-sm"><dt className="text-muted">{label}</dt><dd className="text-right font-medium capitalize tabular-nums">{value}</dd></div>)}</dl>
          <div className="mt-4 grid gap-2 sm:grid-cols-2"><Link to={`/app/violations?type=${current.type}&search=${encodeURIComponent(String(current.trackingId))}`} className="secondary-button h-11">Open violation record <ExternalLink size={14} /></Link><Link to={`/app/history?search=${encodeURIComponent(current.plate || String(current.trackingId))}`} className="secondary-button h-11">Open matching vehicle <ExternalLink size={14} /></Link>{evidence && <a href={evidence} target="_blank" rel="noreferrer" className="primary-button h-11 sm:col-span-2">Open evidence <ExternalLink size={14} /></a>}</div>
          <section className="mt-5"><h3 className="mb-2 flex items-center gap-2 text-xs font-bold uppercase tracking-wider"><UserRoundCheck size={15} className="text-primary" />Activity trail</h3>{current.activity.length ? <ol className="space-y-2">{current.activity.map((item) => <li key={item.id} className="rounded-xl border border-border bg-card p-3 text-xs"><div className="flex justify-between gap-3"><strong className="capitalize">{item.action.replaceAll("_", " ").toLowerCase()}</strong><time className="tabular-nums text-muted">{formatDateTime(item.createdAt)}</time></div><p className="mt-1 text-muted">{item.actorName}{item.fromStatus && item.toStatus ? ` · ${alertStatusLabel(item.fromStatus)} → ${alertStatusLabel(item.toStatus)}` : ""}</p>{item.note && <p className="mt-2 rounded-lg bg-elevated p-2">{item.note}</p>}</li>)}</ol> : <p className="rounded-xl border border-border p-4 text-xs text-muted">Loading activity trail…</p>}</section>
        </>}
      </div>
    </aside>
  </div>;
}
