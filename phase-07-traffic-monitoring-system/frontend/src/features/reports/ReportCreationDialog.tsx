import { useEffect, useRef, useState } from "react";
import { ArrowLeft, ArrowRight, Check, FilePlus2, LoaderCircle, X } from "lucide-react";
import type { AuthUser, Camera, ReportFilters, ReportRecord, ReportTemplate, ReportType } from "../../types";
import { api } from "../../services/api";
import { allReportSections, reportTypeLabel, sectionLabel } from "./reportFormat";

const steps = ["Template", "Name", "Period", "Filters", "Sections", "Review", "Generate"];

function localInput(date: Date) {
  const adjusted = new Date(date.getTime() - date.getTimezoneOffset() * 60_000);
  return adjusted.toISOString().slice(0, 16);
}

function todayStart() {
  const date = new Date();
  date.setHours(0, 0, 0, 0);
  return date;
}

export function ReportCreationDialog({ open, initialType, templates, cameras, operators, onClose, onGenerated }: {
  open: boolean;
  initialType: ReportType;
  templates: ReportTemplate[];
  cameras: Camera[];
  operators: AuthUser[];
  onClose: () => void;
  onGenerated: (report: ReportRecord) => void;
}) {
  const closeButton = useRef<HTMLButtonElement>(null);
  const [step, setStep] = useState(0);
  const [type, setType] = useState<ReportType>(initialType);
  const initialTemplate = templates.find((item) => item.type === initialType);
  const [name, setName] = useState(`${initialTemplate?.name ?? reportTypeLabel(initialType)} · ${new Intl.DateTimeFormat(undefined, { dateStyle: "medium" }).format(new Date())}`);
  const [preset, setPreset] = useState("today");
  const [start, setStart] = useState(() => localInput(todayStart()));
  const [end, setEnd] = useState(() => localInput(new Date()));
  const [filters, setFilters] = useState<Omit<ReportFilters, "startAt" | "endAt">>({ timezone: "Asia/Kathmandu", camera: "", vehicleType: "", violationType: "", alertSeverity: "", alertStatus: "", assignedTo: null });
  const [sections, setSections] = useState<string[]>(initialTemplate?.sections ?? ["kpis"]);
  const [error, setError] = useState("");
  const [submitting, setSubmitting] = useState(false);
  useEffect(() => {
    if (!open) return;
    closeButton.current?.focus();
    const escape = (event: KeyboardEvent) => { if (event.key === "Escape") onClose(); };
    document.addEventListener("keydown", escape);
    return () => document.removeEventListener("keydown", escape);
  }, [open, onClose]);
  if (!open) return null;
  const selectType = (next: ReportType) => {
    setType(next);
    const template = templates.find((item) => item.type === next);
    setSections(template?.sections ?? ["kpis"]);
    if (!name.trim() || templates.some((item) => name.startsWith(item.name))) setName(`${template?.name ?? reportTypeLabel(next)} · ${new Intl.DateTimeFormat(undefined, { dateStyle: "medium" }).format(new Date())}`);
  };
  const applyPreset = (next: string) => {
    setPreset(next);
    const now = new Date();
    const from = new Date(now);
    if (next === "today") from.setHours(0, 0, 0, 0);
    if (next === "yesterday") { from.setDate(from.getDate() - 1); from.setHours(0, 0, 0, 0); now.setDate(now.getDate() - 1); now.setHours(23, 59, 59, 999); }
    if (next === "week") from.setDate(from.getDate() - 7);
    if (next === "month") from.setDate(from.getDate() - 30);
    if (next !== "custom") { setStart(localInput(from)); setEnd(localInput(now)); }
  };
  const validateStep = () => {
    if (step === 1 && name.trim().length < 2) return "Enter a report name with at least 2 characters.";
    if (step === 2) {
      const from = new Date(start); const to = new Date(end);
      if (!start || !end || Number.isNaN(from.getTime()) || Number.isNaN(to.getTime())) return "Choose a valid start and end time.";
      if (from >= to) return "The start time must be before the end time.";
      if (to > new Date(Date.now() + 5 * 60_000)) return "The end time cannot be in the future.";
      if (to.getTime() - from.getTime() > 366 * 86_400_000) return "The reporting period cannot exceed 366 days.";
    }
    if (step === 4 && !sections.length) return "Select at least one report section.";
    return "";
  };
  const next = () => {
    const issue = validateStep();
    if (issue) { setError(issue); return; }
    setError("");
    setStep((current) => Math.min(6, current + 1));
  };
  const generate = async () => {
    setSubmitting(true); setError("");
    try {
      const report = await api.generateReport({
        name: name.trim(), type, sections,
        filters: { ...filters, startAt: new Date(start).toISOString(), endAt: new Date(end).toISOString() }
      });
      onGenerated(report);
    } catch (reason) {
      setError(reason instanceof Error ? reason.message : "Report generation failed.");
    } finally {
      setSubmitting(false);
    }
  };
  const renderStep = () => {
    if (step === 0) return <div className="grid gap-3 sm:grid-cols-2">{templates.map((template) => <button type="button" key={template.type} onClick={() => selectType(template.type)} aria-pressed={type === template.type} className={`rounded-xl border p-4 text-left ${type === template.type ? "border-primary bg-primary-soft" : "border-border bg-card hover:border-border-strong"}`}><strong className="block text-sm">{template.name}</strong><span className="mt-1 block text-xs leading-5 text-muted">{template.description}</span></button>)}</div>;
    if (step === 1) return <label className="block text-xs font-semibold">Report name<input autoFocus value={name} maxLength={120} onChange={(event) => setName(event.target.value)} className="field mt-2" placeholder="Daily traffic summary" /><span className="mt-2 block font-normal text-muted">This name appears in report history and exported documents.</span></label>;
    if (step === 2) return <div className="space-y-4"><fieldset><legend className="mb-2 text-xs font-semibold">Reporting period</legend><div className="flex flex-wrap gap-2">{[["today", "Today"], ["yesterday", "Yesterday"], ["week", "Last 7 days"], ["month", "Last 30 days"], ["custom", "Custom"]].map(([value, label]) => <button key={value} type="button" onClick={() => applyPreset(value)} aria-pressed={preset === value} className={`secondary-button ${preset === value ? "border-primary bg-primary-soft text-primary" : ""}`}>{label}</button>)}</div></fieldset><div className="grid gap-3 sm:grid-cols-2"><label className="text-xs font-semibold">Start date and time<input type="datetime-local" value={start} onChange={(event) => { setPreset("custom"); setStart(event.target.value); }} className="field mt-2" /></label><label className="text-xs font-semibold">End date and time<input type="datetime-local" value={end} onChange={(event) => { setPreset("custom"); setEnd(event.target.value); }} className="field mt-2" /></label></div><p className="text-xs text-muted">Stored in UTC and displayed in Asia/Kathmandu.</p></div>;
    if (step === 3) return <div className="grid gap-3 sm:grid-cols-2"><label className="text-xs font-semibold">Camera<select value={filters.camera} onChange={(event) => setFilters({ ...filters, camera: event.target.value })} className="field mt-2"><option value="">All cameras</option>{cameras.map((camera) => <option key={camera.id} value={camera.id}>{camera.name}</option>)}</select></label><label className="text-xs font-semibold">Vehicle type<select value={filters.vehicleType} onChange={(event) => setFilters({ ...filters, vehicleType: event.target.value as ReportFilters["vehicleType"] })} className="field mt-2"><option value="">All vehicles</option><option value="bicycle">Bicycle</option><option value="car">Car</option><option value="motorcycle">Motorcycle</option><option value="bus">Bus</option><option value="truck">Truck</option><option value="unknown">Unknown</option></select></label><label className="text-xs font-semibold">Violation type<select value={filters.violationType} onChange={(event) => setFilters({ ...filters, violationType: event.target.value as ReportFilters["violationType"] })} className="field mt-2"><option value="">All violations</option><option value="OVERSPEED">Overspeed</option><option value="NO_HELMET">No helmet</option><option value="WRONG_LANE">Wrong lane</option><option value="WRONG_DIRECTION">Wrong direction</option></select></label><label className="text-xs font-semibold">Alert severity<select value={filters.alertSeverity} onChange={(event) => setFilters({ ...filters, alertSeverity: event.target.value as ReportFilters["alertSeverity"] })} className="field mt-2"><option value="">All severities</option><option value="CRITICAL">Critical</option><option value="HIGH">High</option><option value="MEDIUM">Medium</option><option value="LOW">Low</option></select></label><label className="text-xs font-semibold">Alert status<select value={filters.alertStatus} onChange={(event) => setFilters({ ...filters, alertStatus: event.target.value as ReportFilters["alertStatus"] })} className="field mt-2"><option value="">All statuses</option><option value="NEW">New</option><option value="ACKNOWLEDGED">Acknowledged</option><option value="INVESTIGATING">Investigating</option><option value="RESOLVED">Resolved</option><option value="FALSE_POSITIVE">False positive</option></select></label><label className="text-xs font-semibold">Assigned operator<select value={filters.assignedTo ?? ""} onChange={(event) => setFilters({ ...filters, assignedTo: event.target.value ? Number(event.target.value) : null })} className="field mt-2"><option value="">All operators</option>{operators.map((operator) => <option key={operator.id} value={operator.id}>{operator.name}</option>)}</select></label></div>;
    if (step === 4) return <fieldset><legend className="mb-3 text-xs font-semibold">Sections included in this report</legend><div className="grid gap-2 sm:grid-cols-2">{allReportSections.map((section) => <label key={section} className="flex items-center gap-3 rounded-xl border border-border bg-card p-3 text-xs"><input type="checkbox" checked={sections.includes(section)} onChange={(event) => setSections(event.target.checked ? [...sections, section] : sections.filter((item) => item !== section))} className="accent-primary" />{sectionLabel(section)}</label>)}</div></fieldset>;
    const summary = <dl className="divide-y divide-border rounded-xl border border-border bg-card text-sm"><div className="flex justify-between gap-3 p-3"><dt className="text-muted">Template</dt><dd className="font-semibold">{reportTypeLabel(type)}</dd></div><div className="flex justify-between gap-3 p-3"><dt className="text-muted">Name</dt><dd className="text-right font-semibold">{name}</dd></div><div className="flex justify-between gap-3 p-3"><dt className="text-muted">Period</dt><dd className="text-right tabular-nums">{new Date(start).toLocaleString()} – {new Date(end).toLocaleString()}</dd></div><div className="flex justify-between gap-3 p-3"><dt className="text-muted">Camera</dt><dd>{cameras.find((item) => item.id === filters.camera)?.name ?? "All cameras"}</dd></div><div className="flex justify-between gap-3 p-3"><dt className="text-muted">Sections</dt><dd className="text-right">{sections.map(sectionLabel).join(", ")}</dd></div></dl>;
    return <div>{summary}{step === 6 && <div className="mt-4 rounded-xl border border-primary/20 bg-primary-soft p-4 text-sm"><strong className="flex items-center gap-2 text-primary"><FilePlus2 size={17} />Ready to generate</strong><p className="mt-1 text-xs text-muted">The report will preserve an immutable result snapshot and create real PDF and CSV exports.</p></div>}</div>;
  };
  return <div className="fixed inset-0 z-[70] bg-black/65 p-3 sm:p-6" onMouseDown={(event) => { if (event.target === event.currentTarget && !submitting) onClose(); }}><section role="dialog" aria-modal="true" aria-labelledby="create-report-title" className="mx-auto flex max-h-full w-full max-w-4xl flex-col overflow-hidden rounded-2xl border border-border bg-surface shadow-2xl"><header className="flex items-center justify-between border-b border-border p-4"><div><p className="text-[10px] font-bold uppercase tracking-wider text-primary">Step {step + 1} of 7 · {steps[step]}</p><h2 id="create-report-title" className="mt-1 text-lg font-bold">Create operational report</h2></div><button ref={closeButton} type="button" disabled={submitting} onClick={onClose} className="icon-button" aria-label="Close report creation"><X size={18} /></button></header><div className="flex gap-1 border-b border-border px-4 py-3" aria-label="Report creation progress">{steps.map((label, index) => <span key={label} title={label} className={`h-1.5 flex-1 rounded-full ${index <= step ? "bg-primary" : "bg-elevated"}`} />)}</div><div className="scrollbar-thin min-h-72 flex-1 overflow-y-auto p-4 sm:p-6">{renderStep()}{error && <p role="alert" className="mt-4 rounded-xl bg-danger/10 p-3 text-xs text-danger">{error}</p>}</div><footer className="flex items-center justify-between border-t border-border p-4"><button type="button" disabled={step === 0 || submitting} onClick={() => { setError(""); setStep((current) => current - 1); }} className="secondary-button"><ArrowLeft size={14} />Back</button>{step < 6 ? <button type="button" onClick={next} className="primary-button h-10">Continue<ArrowRight size={14} /></button> : <button type="button" disabled={submitting} onClick={() => void generate()} className="primary-button h-10">{submitting ? <><LoaderCircle className="animate-spin" size={15} />Generating…</> : <><Check size={15} />Generate report</>}</button>}</footer></section></div>;
}
