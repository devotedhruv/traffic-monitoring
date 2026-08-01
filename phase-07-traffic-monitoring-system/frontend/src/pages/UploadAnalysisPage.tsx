import { useEffect, useRef, useState, type ChangeEvent, type DragEvent, type FormEvent } from "react";
import { useMutation, useQuery } from "@tanstack/react-query";
import { BarChart3, CheckCircle2, ChevronDown, Cloud, FileVideo2, Link2, LoaderCircle, LockKeyhole, MapPin, Minus, Plus, RotateCcw, ShieldCheck, Sparkles, UploadCloud, X, Youtube } from "lucide-react";
import { Panel } from "../components/ui/Panel";
import { AnalysisResults } from "../features/video-analysis/AnalysisResults";
import { StepProgress } from "../features/video-analysis/StepProgress";
import { cx, formatBytes } from "../lib/format";
import { api } from "../services/api";
import type { VideoAnalysisOptions } from "../types";

const ACCEPTED_EXTENSIONS = [".mp4", ".mov", ".avi", ".mkv", ".webm", ".mpeg", ".mpg", ".m4v"];
const MAX_UPLOAD_BYTES = 500 * 1024 * 1024;
type SourceMode = "upload" | "link";

function validateVideo(file: File) {
  const extension = file.name.slice(file.name.lastIndexOf(".")).toLowerCase();
  if (!ACCEPTED_EXTENSIONS.includes(extension)) return "Choose an MP4, MOV, AVI, MKV, WebM, MPEG, MPG, or M4V video.";
  if (!file.size) return "This video file is empty.";
  if (file.size > MAX_UPLOAD_BYTES) return "The maximum upload size is 500 MB.";
  return "";
}

function validateLink(value: string) {
  try {
    const url = new URL(value.trim());
    return url.protocol === "https:" || url.protocol === "http:" ? "" : "The video link must start with https:// or http://.";
  } catch { return "Enter a valid public video link."; }
}

export function UploadAnalysisPage() {
  const input = useRef<HTMLInputElement>(null);
  const [sourceMode, setSourceMode] = useState<SourceMode>("upload");
  const [file, setFile] = useState<File | null>(null);
  const [videoUrl, setVideoUrl] = useState("");
  const [confirmedRights, setConfirmedRights] = useState(false);
  const [previewUrl, setPreviewUrl] = useState("");
  const [dragging, setDragging] = useState(false);
  const [validationError, setValidationError] = useState("");
  const [jobId, setJobId] = useState<string | null>(null);
  const [options, setOptions] = useState<VideoAnalysisOptions>({ location: "", speedLimit: 50, metersPerPixel: 0.05 });

  useEffect(() => () => { if (previewUrl) URL.revokeObjectURL(previewUrl); }, [previewUrl]);

  const startAnalysis = useMutation({
    mutationFn: (request: { source: "upload"; selected: File; settings: VideoAnalysisOptions } | { source: "link"; url: string; settings: VideoAnalysisOptions; confirmedRights: boolean }) => request.source === "upload" ? api.startVideoAnalysis(request.selected, request.settings) : api.startLinkVideoAnalysis({ videoUrl: request.url, confirmedRights: request.confirmedRights, ...request.settings }),
    onSuccess: (job) => setJobId(job.id)
  });
  const jobQuery = useQuery({ queryKey: ["video-analysis", jobId], queryFn: () => api.getVideoAnalysis(jobId!), enabled: Boolean(jobId), refetchInterval: (query) => { const status = query.state.data?.status; return status === "completed" || status === "failed" ? false : 800; } });
  const job = jobQuery.data ?? startAnalysis.data;
  const active = startAnalysis.isPending || job?.status === "queued" || job?.status === "processing";

  const chooseFile = (next: File | null) => {
    if (!next) return;
    const error = validateVideo(next); setValidationError(error); if (error) return;
    if (previewUrl) URL.revokeObjectURL(previewUrl);
    setFile(next); setPreviewUrl(URL.createObjectURL(next)); setJobId(null); startAnalysis.reset();
  };
  const handleInput = (event: ChangeEvent<HTMLInputElement>) => { chooseFile(event.target.files?.[0] ?? null); event.target.value = ""; };
  const handleDrop = (event: DragEvent<HTMLDivElement>) => { event.preventDefault(); setDragging(false); chooseFile(event.dataTransfer.files?.[0] ?? null); };
  const reset = () => { if (previewUrl) URL.revokeObjectURL(previewUrl); setFile(null); setPreviewUrl(""); setJobId(null); setValidationError(""); startAnalysis.reset(); };
  const changeSource = (mode: SourceMode) => { if (active || mode === sourceMode) return; setSourceMode(mode); setJobId(null); setValidationError(""); startAnalysis.reset(); };

  const submit = (event: FormEvent) => {
    event.preventDefault(); if (active || options.speedLimit < 5 || options.metersPerPixel <= 0) return; setJobId(null);
    if (sourceMode === "upload") { if (file) startAnalysis.mutate({ source: "upload", selected: file, settings: options }); return; }
    const error = validateLink(videoUrl); setValidationError(error); if (!error && confirmedRights) startAnalysis.mutate({ source: "link", url: videoUrl.trim(), settings: options, confirmedRights });
  };

  const failure = startAnalysis.error?.message || jobQuery.error?.message || job?.error;
  const sourceReady = sourceMode === "upload" ? Boolean(file) : Boolean(videoUrl.trim() && confirmedRights);
  const currentStep: 1 | 2 | 3 = job?.status === "completed" ? 3 : active || job?.status === "failed" ? 2 : 1;
  const disabledReason = sourceReady ? options.speedLimit < 5 ? "Enter a speed limit of at least 5 km/h." : options.metersPerPixel <= 0 ? "Enter a valid road scale." : "" : sourceMode === "upload" ? "Choose a road video to enable analysis." : "Enter a public link and confirm permission to continue.";

  return (
    <div className="space-y-5">
      <form onSubmit={submit} data-source-mode={sourceMode} className="grid gap-4 xl:grid-cols-[minmax(0,1fr)_390px]">
        <div className="min-w-0 space-y-4">
          <section className="relative min-h-[300px] overflow-hidden rounded-2xl border border-primary/20 bg-card px-5 py-6 shadow-panel sm:px-7">
            <div className="absolute inset-0 bg-[radial-gradient(circle_at_82%_30%,rgb(var(--color-primary)/.13),transparent_18rem)]" />
            <div className="relative z-10 max-w-[670px]"><span className="inline-flex items-center gap-2 rounded-full border border-primary/25 bg-primary-soft px-3 py-1.5 text-[10px] font-bold uppercase tracking-[.08em] text-primary"><Sparkles size={13} />Step {currentStep} of 3</span><h1 className="mt-4 max-w-[620px] text-[28px] font-extrabold leading-tight tracking-[-.04em] sm:text-[34px]">Turn any road video into traffic insights.</h1><p className="mt-3 max-w-[620px] text-sm leading-6 text-muted">Upload footage from your device or provide a public video link. TrafficOps AI will analyze visible vehicles and report timing, type, colour, direction, estimated speed, and possible overspeed events.</p><div className="mt-6 flex flex-wrap gap-2"><span className="trust-chip"><ShieldCheck />Temporary processing<small>Deleted after analysis</small></span><span className="trust-chip"><LockKeyhole />Secure & private<small>Encrypted transport</small></span><span className="trust-chip"><CheckCircle2 />No impact to live data<small>Separate history</small></span></div></div>
            <div className="pointer-events-none absolute bottom-5 right-7 hidden h-44 w-56 items-end justify-center lg:flex"><div className="absolute bottom-0 h-32 w-24 [clip-path:polygon(42%_0,58%_0,100%_100%,0_100%)] bg-primary/15" /><div className="absolute bottom-0 h-32 w-px bg-primary/70" /><div className="absolute bottom-12 grid h-20 w-20 place-items-center rounded-[28px] border border-primary/30 bg-primary text-white shadow-card"><UploadCloud size={36} /></div><BarChart3 className="absolute right-0 top-5 text-primary/50" size={48} /></div>
          </section>

          <Panel title="Upload Road Footage">
            <div className="p-3 sm:p-4">
              <div className="mb-3 grid grid-cols-2 rounded-xl border border-border bg-surface-secondary p-1" aria-label="Choose video source"><button type="button" onClick={() => changeSource("upload")} aria-pressed={sourceMode === "upload"} disabled={active} className={cx("source-tab", sourceMode === "upload" && "source-tab-active")}><UploadCloud size={15} />Upload file</button><button type="button" onClick={() => changeSource("link")} aria-pressed={sourceMode === "link"} disabled={active} className={cx("source-tab", sourceMode === "link" && "source-tab-active")}><Link2 size={15} />Video link</button></div>
              {sourceMode === "upload" && (!file ? <div onDragEnter={(event) => { event.preventDefault(); setDragging(true); }} onDragOver={(event) => event.preventDefault()} onDragLeave={(event) => { if (event.currentTarget === event.target) setDragging(false); }} onDrop={handleDrop} className={cx("grid min-h-[275px] cursor-pointer place-items-center rounded-2xl border border-dashed p-6 text-center", dragging ? "border-primary bg-primary/10" : "border-primary/55 bg-primary/[.025] hover:bg-primary/[.055]")} role="button" tabIndex={0} onClick={() => input.current?.click()} onKeyDown={(event) => { if (event.key === "Enter" || event.key === " ") input.current?.click(); }}><div><span className="mx-auto grid h-16 w-16 place-items-center rounded-full bg-primary-soft text-primary ring-8 ring-primary/5"><UploadCloud size={29} /></span><h2 className="mt-5 text-lg font-bold">Drag & drop your video here</h2><p className="mt-1 text-xs text-muted">or click to browse from your device</p><span className="secondary-button mt-5"><FileVideo2 size={15} />Browse files</span><p className="mt-4 text-[10px] text-muted">MP4, MOV, AVI, MKV, WebM · Up to 500 MB</p></div></div> : <div className="space-y-3"><div className="relative overflow-hidden rounded-2xl border border-border bg-black"><video src={previewUrl} controls className="aspect-video w-full object-contain" aria-label={`Preview of ${file.name}`} />{!active && <button type="button" onClick={reset} className="absolute right-3 top-3 grid h-9 w-9 place-items-center rounded-full bg-black/70 text-white hover:bg-black" aria-label="Remove selected video"><X size={16} /></button>}</div><div className="flex flex-wrap items-center justify-between gap-3 rounded-xl border border-border bg-surface-secondary/50 p-3"><div className="flex min-w-0 items-center gap-3"><span className="grid h-10 w-10 place-items-center rounded-xl bg-primary-soft text-primary"><FileVideo2 size={19} /></span><div className="min-w-0"><p className="truncate text-xs font-bold">{file.name}</p><p className="mt-1 text-[10px] text-muted">{formatBytes(file.size)} · {file.type || "video file"}</p></div></div>{!active && <button type="button" onClick={() => input.current?.click()} className="secondary-button">Replace file</button>}</div></div>)}
              {sourceMode === "link" && <div className="flex min-h-[275px] flex-col justify-center rounded-2xl border border-primary/30 bg-primary/[.025] p-5 sm:p-7"><span className="grid h-12 w-12 place-items-center rounded-xl bg-primary text-white"><Link2 size={21} /></span><h2 className="mt-4 text-base font-bold">Paste a public video link</h2><p className="mt-1 text-xs leading-5 text-muted">The video is temporarily downloaded, analyzed, then removed.</p><label className="relative mt-4"><Link2 className="absolute left-3 top-3.5 text-primary" size={16} /><input type="url" value={videoUrl} onChange={(event) => { setVideoUrl(event.target.value); setValidationError(""); }} disabled={active} placeholder="https://youtube.com/watch?v=…" className="field pl-10" aria-label="Public video URL" /></label><div className="mt-3 flex flex-wrap gap-2"><span className="source-chip"><Youtube size={13} />YouTube</span><span className="source-chip"><Cloud size={13} />Google Drive</span>{["Instagram", "TikTok", "Facebook", "Vimeo"].map((source) => <span key={source} className="source-chip">{source}</span>)}</div><label className="mt-4 flex cursor-pointer items-start gap-3 rounded-xl border border-border bg-surface p-3 text-[11px] leading-5 text-muted"><input type="checkbox" checked={confirmedRights} onChange={(event) => setConfirmedRights(event.target.checked)} disabled={active} className="mt-0.5 h-4 w-4 accent-primary" /><span>I own this video or have permission to download and analyze it.</span></label></div>}
              <input ref={input} type="file" accept="video/*,.mkv,.avi" onChange={handleInput} className="sr-only" aria-label="Choose a road video" />{validationError && <p role="alert" className="mt-3 text-xs font-semibold text-danger">{validationError}</p>}
              <div className="mt-3 flex items-center gap-2 rounded-xl border border-primary/15 bg-primary-soft px-3 py-2.5 text-[10px] text-secondary"><LockKeyhole size={14} className="shrink-0 text-primary" />Your video is processed in a secure environment and automatically deleted after analysis.</div>
            </div>
          </Panel>
        </div>

        <aside className="space-y-4">
          <Panel title="Analysis Settings"><div className="space-y-4 p-4"><p className="-mt-1 text-[10px] text-muted">Configure how TrafficOps AI analyzes your video.</p><label className="block text-[11px] font-semibold text-secondary"><span className="mb-2 flex items-center gap-2"><MapPin size={14} className="text-primary" />Road or location <span className="font-normal text-muted">(optional)</span></span><input value={options.location} onChange={(event) => setOptions((current) => ({ ...current, location: event.target.value }))} maxLength={160} placeholder="e.g. Kalanki Junction, Kathmandu" disabled={active} className="field" /></label><label className="block text-[11px] font-semibold text-secondary"><span className="mb-2 block">Speed limit <span className="font-normal text-muted">(km/h)</span></span><div className="flex h-12 items-center rounded-xl border border-border bg-surface px-3"><input type="number" min={5} max={200} step={1} value={options.speedLimit} onChange={(event) => setOptions((current) => ({ ...current, speedLimit: Number(event.target.value) }))} disabled={active} className="min-w-0 flex-1 bg-transparent text-sm tabular-nums text-ink" /><button type="button" onClick={() => setOptions((current) => ({ ...current, speedLimit: Math.max(5, current.speedLimit - 5) }))} disabled={active} className="stepper-button" aria-label="Decrease speed limit"><Minus size={14} /></button><button type="button" onClick={() => setOptions((current) => ({ ...current, speedLimit: Math.min(200, current.speedLimit + 5) }))} disabled={active} className="stepper-button ml-2" aria-label="Increase speed limit"><Plus size={14} /></button></div></label><div className="flex gap-2 rounded-xl border border-primary/20 bg-primary-soft p-3 text-[10px] leading-5 text-secondary"><CheckCircle2 size={15} className="mt-0.5 shrink-0 text-primary" />Overspeed events will be detected when a vehicle exceeds the configured speed limit.</div><details className="group rounded-xl border border-border"><summary className="flex min-h-12 cursor-pointer list-none items-center justify-between px-3 text-[11px] font-semibold text-secondary">Advanced speed calibration<ChevronDown size={15} className="transition group-open:rotate-180" /></summary><div className="border-t border-border p-3"><label className="text-[10px] text-muted">Road scale (metres per pixel)<input type="number" min={0.0001} max={10} step={0.001} value={options.metersPerPixel} onChange={(event) => setOptions((current) => ({ ...current, metersPerPixel: Number(event.target.value) }))} disabled={active} className="field mt-2 tabular-nums" /></label><p className="mt-2 text-[9px] leading-4 text-muted">Use a known road distance for accurate speed estimates.</p></div></details><button type="submit" disabled={!sourceReady || active || options.speedLimit < 5 || options.metersPerPixel <= 0} className="primary-button w-full">{active ? <><LoaderCircle size={17} className="animate-spin" />Processing video</> : <><Sparkles size={17} />Analyze Traffic Video</>}</button>{!active && disabledReason && <p className="text-center text-[10px] leading-4 text-muted">{disabledReason}</p>}</div></Panel>
          {sourceMode === "link" && <button type="submit" disabled={!sourceReady || active || options.speedLimit < 5 || options.metersPerPixel <= 0} className="link-submit-button primary-button w-full"><Sparkles size={17} />Analyze Video Link</button>}
          <section className="rounded-2xl border border-border bg-card p-4 shadow-panel"><StepProgress current={currentStep} /></section>
          {job && <Panel title="Analysis Progress"><div className="p-4"><div className="flex justify-between gap-3 text-xs"><strong>{job.stage}</strong><span className="tabular-nums text-primary">{job.progress}%</span></div><div className="mt-3 h-2 overflow-hidden rounded-full bg-elevated"><div className="h-full rounded-full bg-primary transition-[width] duration-500" style={{ width: `${job.progress}%` }} /></div><p className="mt-2 truncate text-[10px] text-muted">{job.filename}</p></div></Panel>}
          {failure && <div role="alert" className="rounded-2xl border border-danger/30 bg-danger/10 p-4 text-xs text-danger"><strong>Analysis could not finish</strong><p className="mt-1 leading-5">{failure}</p><button type="button" onClick={() => { setJobId(null); startAnalysis.reset(); }} className="secondary-button mt-3 border-danger/25 text-danger"><RotateCcw size={14} />Try again</button></div>}
        </aside>
      </form>
      {job?.status === "completed" && job.result && <AnalysisResults result={job.result} />}
    </div>
  );
}
