import {
  useEffect,
  useRef,
  useState,
  type ChangeEvent,
  type DragEvent,
  type FormEvent
} from "react";
import { useMutation, useQuery } from "@tanstack/react-query";
import {
  BarChart3,
  CheckCircle2,
  ChevronDown,
  FileVideo2,
  LoaderCircle,
  LockKeyhole,
  MapPin,
  Minus,
  Plus,
  RotateCcw,
  ShieldCheck,
  Sparkles,
  UploadCloud
} from "lucide-react";
import { Panel } from "../components/ui/Panel";
import { AnalysisResults } from "../features/video-analysis/AnalysisResults";
import { CalibrationEditor } from "../features/video-analysis/CalibrationEditor";
import { StepProgress } from "../features/video-analysis/StepProgress";
import { cx, formatBytes } from "../lib/format";
import { api } from "../services/api";
import type { RoadCalibration, VideoAnalysisOptions } from "../types";

const ACCEPTED_EXTENSIONS = [".mp4", ".mov", ".avi", ".mkv", ".webm", ".mpeg", ".mpg", ".m4v"];
const MAX_UPLOAD_BYTES = 500 * 1024 * 1024;
const BUNDLED_VIDEO_BYTES = 10_352_631;
const BUNDLED_ROAD_POINTS = [
  { x: 0.27, y: 0.5 },
  { x: 0.69, y: 0.5 },
  { x: 0.88, y: 0.98 },
  { x: 0.06, y: 0.98 }
];

const DEFAULT_CALIBRATION: RoadCalibration = {
  enabled: true,
  sourcePoints: [],
  roadWidthMeters: 0,
  roadLengthMeters: 0,
  laneCount: 0,
  countingLinePosition: 0.62,
  stabilize: true,
  analysisFps: 15,
  tracker: "botsort.yaml",
  allowedDirection: "both"
};

function validateVideo(file: File) {
  const extension = file.name.slice(file.name.lastIndexOf(".")).toLowerCase();
  if (!ACCEPTED_EXTENSIONS.includes(extension)) return "Choose an MP4, MOV, AVI, MKV, WebM, MPEG, MPG, or M4V video.";
  if (!file.size) return "This video file is empty.";
  if (file.size > MAX_UPLOAD_BYTES) return "The maximum upload size is 500 MB.";
  return "";
}

export function UploadAnalysisPage() {
  const input = useRef<HTMLInputElement>(null);
  const resultSection = useRef<HTMLDivElement>(null);
  const [file, setFile] = useState<File | null>(null);
  const [previewUrl, setPreviewUrl] = useState("");
  const [dragging, setDragging] = useState(false);
  const [validationError, setValidationError] = useState("");
  const [jobId, setJobId] = useState<string | null>(null);
  const [options, setOptions] = useState<VideoAnalysisOptions>({
    location: "",
    speedLimit: 50,
    metersPerPixel: 0.05,
    calibration: DEFAULT_CALIBRATION
  });

  useEffect(() => () => {
    if (previewUrl) URL.revokeObjectURL(previewUrl);
  }, [previewUrl]);

  const startAnalysis = useMutation({
    mutationFn: (request: { selected: File; settings: VideoAnalysisOptions }) =>
      api.startVideoAnalysis(request.selected, request.settings),
    onSuccess: (job) => setJobId(job.id)
  });
  const jobQuery = useQuery({
    queryKey: ["video-analysis", jobId],
    queryFn: () => api.getVideoAnalysis(jobId!),
    enabled: Boolean(jobId),
    refetchInterval: (query) => {
      const state = query.state.data?.status;
      return state === "completed" || state === "failed" ? false : 800;
    }
  });
  const job = jobQuery.data ?? startAnalysis.data;
  const active = startAnalysis.isPending || job?.status === "queued" || job?.status === "processing";
  const calibration = options.calibration ?? DEFAULT_CALIBRATION;

  useEffect(() => {
    if (job?.status !== "completed" || !job.result) return;
    const frame = window.requestAnimationFrame(() => {
      resultSection.current?.scrollIntoView({ behavior: "smooth", block: "start" });
    });
    return () => window.cancelAnimationFrame(frame);
  }, [job?.result, job?.status]);

  const chooseFile = (next: File | null) => {
    if (!next) return;
    const error = validateVideo(next);
    setValidationError(error);
    if (error) return;
    if (previewUrl) URL.revokeObjectURL(previewUrl);
    setFile(next);
    setPreviewUrl(URL.createObjectURL(next));
    const bundledProfile = next.name.toLowerCase() === "traffic.mp4" && next.size === BUNDLED_VIDEO_BYTES;
    setOptions((current) => ({
      ...current,
      calibration: {
        ...(current.calibration ?? DEFAULT_CALIBRATION),
        enabled: true,
        sourcePoints: bundledProfile ? BUNDLED_ROAD_POINTS : [],
        roadWidthMeters: bundledProfile ? 13 : 0,
        roadLengthMeters: bundledProfile ? 50 : 0,
        laneCount: bundledProfile ? 2 : 0
      }
    }));
    setJobId(null);
    startAnalysis.reset();
  };

  const handleInput = (event: ChangeEvent<HTMLInputElement>) => {
    chooseFile(event.target.files?.[0] ?? null);
    event.target.value = "";
  };
  const handleDrop = (event: DragEvent<HTMLDivElement>) => {
    event.preventDefault();
    setDragging(false);
    chooseFile(event.dataTransfer.files?.[0] ?? null);
  };
  const reset = () => {
    if (previewUrl) URL.revokeObjectURL(previewUrl);
    setFile(null);
    setPreviewUrl("");
    setJobId(null);
    setValidationError("");
    startAnalysis.reset();
  };
  const sourceReady = Boolean(file);
  const dimensionsReady = calibration.roadWidthMeters >= 2 && calibration.roadWidthMeters <= 80
    && calibration.roadLengthMeters >= 5 && calibration.roadLengthMeters <= 1000
    && Number.isInteger(calibration.laneCount) && calibration.laneCount >= 1 && calibration.laneCount <= 8;
  const calibrationReady = calibration.enabled && calibration.sourcePoints.length === 4 && dimensionsReady;
  const settingsReady = options.speedLimit >= 5 && options.speedLimit <= 200 && calibrationReady;
  const disabledReason = !sourceReady
    ? "Choose a road video to enable analysis."
    : options.speedLimit < 5
      ? "Enter a speed limit of at least 5 km/h."
      : options.speedLimit > 200
        ? "Speed limit cannot exceed 200 km/h."
        : calibration.sourcePoints.length !== 4
        ? "Mark all four road-plane points on the video preview."
        : !dimensionsReady
          ? "Enter measured road dimensions and a lane count within the supported ranges."
          : "";

  const submit = (event: FormEvent) => {
    event.preventDefault();
    if (active || !settingsReady) return;
    setJobId(null);
    if (file) startAnalysis.mutate({ selected: file, settings: options });
  };

  const failure = startAnalysis.error?.message || jobQuery.error?.message || job?.error;
  const currentStep: 1 | 2 | 3 = job?.status === "completed" ? 3 : active || job?.status === "failed" ? 2 : 1;

  const updateCalibration = (changes: Partial<RoadCalibration>) => {
    setOptions((current) => ({
      ...current,
      calibration: { ...(current.calibration ?? DEFAULT_CALIBRATION), ...changes }
    }));
  };

  return (
    <div className="space-y-5">
      <form onSubmit={submit} className="grid gap-4 xl:grid-cols-[minmax(0,1fr)_390px]">
        <div className="min-w-0 space-y-4">
          <section className="relative min-h-[300px] overflow-hidden rounded-2xl border border-primary/20 bg-card px-5 py-6 shadow-panel sm:px-7">
            <div className="absolute inset-0 bg-[radial-gradient(circle_at_82%_30%,rgb(var(--color-primary)/.13),transparent_18rem)]" />
            <div className="relative z-10 max-w-[670px]">
              <span className="inline-flex items-center gap-2 rounded-full border border-primary/25 bg-primary-soft px-3 py-1.5 text-[10px] font-bold uppercase tracking-[.08em] text-primary"><Sparkles size={13} />Step {currentStep} of 3</span>
              <h1 className="mt-4 max-w-[620px] text-[28px] font-extrabold leading-tight tracking-[-.04em] sm:text-[34px]">Turn any road video into traffic insights.</h1>
              <p className="mt-3 max-w-[620px] text-sm leading-6 text-muted">Upload a road-video clip and calibrate its visible road plane. Ground-plane tracking reports vehicle type, trajectory, measured speed, line crossings, and possible violations.</p>
              <div className="mt-6 flex flex-wrap gap-2">
                <span className="trust-chip"><ShieldCheck />Temporary processing<small>Deleted after analysis</small></span>
                <span className="trust-chip"><LockKeyhole />Secure & private<small>Encrypted transport</small></span>
                <span className="trust-chip"><CheckCircle2 />Auditable output<small>Annotated evidence video</small></span>
              </div>
            </div>
            <div className="pointer-events-none absolute bottom-5 right-7 hidden h-44 w-56 items-end justify-center lg:flex">
              <div className="absolute bottom-0 h-32 w-24 [clip-path:polygon(42%_0,58%_0,100%_100%,0_100%)] bg-primary/15" />
              <div className="absolute bottom-0 h-32 w-px bg-primary/70" />
              <div className="absolute bottom-12 grid h-20 w-20 place-items-center rounded-[28px] border border-primary/30 bg-primary text-white shadow-card"><UploadCloud size={36} /></div>
              <BarChart3 className="absolute right-0 top-5 text-primary/50" size={48} />
            </div>
          </section>

          <Panel title="Upload Road Footage">
            <div className="p-3 sm:p-4">
              {!file ? (
                <div
                  onDragEnter={(event) => { event.preventDefault(); setDragging(true); }}
                  onDragOver={(event) => event.preventDefault()}
                  onDragLeave={(event) => { if (event.currentTarget === event.target) setDragging(false); }}
                  onDrop={handleDrop}
                  className={cx("grid min-h-[275px] cursor-pointer place-items-center rounded-2xl border border-dashed p-6 text-center transition", dragging ? "border-primary bg-primary/10" : "border-primary/55 bg-primary/[.025] hover:bg-primary/[.055]")}
                  role="button"
                  tabIndex={0}
                  onClick={() => input.current?.click()}
                  onKeyDown={(event) => { if (event.key === "Enter" || event.key === " ") input.current?.click(); }}
                >
                  <div>
                    <span className="mx-auto grid h-16 w-16 place-items-center rounded-full bg-primary-soft text-primary ring-8 ring-primary/5"><UploadCloud size={29} /></span>
                    <h2 className="mt-5 text-lg font-bold">Drag & drop your video here</h2>
                    <p className="mt-1 text-xs text-muted">or click to browse from your device</p>
                    <span className="secondary-button mt-5"><FileVideo2 size={15} />Browse files</span>
                    <p className="mt-4 text-[10px] text-muted">MP4, MOV, AVI, MKV, WebM · Up to 500 MB</p>
                  </div>
                </div>
              ) : (
                <div className="space-y-3">
                  <CalibrationEditor
                    previewUrl={previewUrl}
                    filename={file.name}
                    points={calibration.sourcePoints}
                    countingLinePosition={calibration.countingLinePosition}
                    enabled={calibration.enabled}
                    disabled={active}
                    onChange={(sourcePoints) => updateCalibration({ sourcePoints })}
                    onRemove={reset}
                  />
                  <div className="flex flex-wrap items-center justify-between gap-3 rounded-xl border border-border bg-surface-secondary/50 p-3">
                    <div className="flex min-w-0 items-center gap-3">
                      <span className="grid h-10 w-10 place-items-center rounded-xl bg-primary-soft text-primary"><FileVideo2 size={19} /></span>
                      <div className="min-w-0"><p className="truncate text-xs font-bold">{file.name}</p><p className="mt-1 text-[10px] text-muted">{formatBytes(file.size)} · {file.type || "video file"}</p></div>
                    </div>
                    {!active && <button type="button" onClick={() => input.current?.click()} className="secondary-button">Replace file</button>}
                  </div>
                </div>
              )}

              <input ref={input} type="file" accept="video/*,.mkv,.avi" onChange={handleInput} className="sr-only" aria-label="Choose a road video" />
              {validationError && <p role="alert" className="mt-3 text-xs font-semibold text-danger">{validationError}</p>}
              <div className="mt-3 flex items-center gap-2 rounded-xl border border-primary/15 bg-primary-soft px-3 py-2.5 text-[10px] text-secondary"><LockKeyhole size={14} className="shrink-0 text-primary" />Your source video is removed after analysis; the annotated result expires with the temporary job.</div>
            </div>
          </Panel>
        </div>

        <aside className="space-y-4">
          <Panel title="Analysis Settings">
            <div className="space-y-4 p-4">
              <p className="-mt-1 text-[10px] text-muted">Configure detection, road geometry, and violation rules.</p>
              <label className="block text-[11px] font-semibold text-secondary">
                <span className="mb-2 flex items-center gap-2"><MapPin size={14} className="text-primary" />Road or location <span className="font-normal text-muted">(optional)</span></span>
                <input value={options.location} onChange={(event) => setOptions((current) => ({ ...current, location: event.target.value }))} maxLength={160} placeholder="e.g. Kalanki Junction, Kathmandu" disabled={active} className="field" />
              </label>
              <label className="block text-[11px] font-semibold text-secondary">
                <span className="mb-2 block">Speed limit <span className="font-normal text-muted">(km/h)</span></span>
                <div className="flex h-12 items-center rounded-xl border border-border bg-surface px-3">
                  <input type="number" min={5} max={200} step={1} value={options.speedLimit} onChange={(event) => setOptions((current) => ({ ...current, speedLimit: Number(event.target.value) }))} disabled={active} className="min-w-0 flex-1 bg-transparent text-sm tabular-nums text-ink" />
                  <button type="button" onClick={() => setOptions((current) => ({ ...current, speedLimit: Math.max(5, current.speedLimit - 5) }))} disabled={active} className="stepper-button" aria-label="Decrease speed limit"><Minus size={14} /></button>
                  <button type="button" onClick={() => setOptions((current) => ({ ...current, speedLimit: Math.min(200, current.speedLimit + 5) }))} disabled={active} className="stepper-button ml-2" aria-label="Increase speed limit"><Plus size={14} /></button>
                </div>
              </label>

              <details open className="group rounded-xl border border-border">
                <summary className="flex min-h-12 cursor-pointer list-none items-center justify-between px-3 text-[11px] font-semibold text-secondary">Perspective & road calibration<ChevronDown size={15} className="transition group-open:rotate-180" /></summary>
                <div className="space-y-3 border-t border-border p-3">
                  <label className="flex items-start justify-between gap-3 text-[11px] text-secondary">
                    <span><strong className="block">Four-point calibration required</strong><small className="text-muted">Prevents uncalibrated speed from being reported as reliable data</small></span>
                    <CheckCircle2 size={16} className="mt-1 shrink-0 text-primary" />
                  </label>

                  <>
                      <div className="grid grid-cols-2 gap-2">
                        <label className="text-[10px] text-muted">Actual measured width (m)<input type="number" min={2} max={80} step={0.5} value={calibration.roadWidthMeters} onChange={(event) => updateCalibration({ roadWidthMeters: Number(event.target.value) })} disabled={active} className="field mt-1.5 tabular-nums" /></label>
                        <label className="text-[10px] text-muted">Actual measured length (m)<input type="number" min={5} max={1000} step={1} value={calibration.roadLengthMeters} onChange={(event) => updateCalibration({ roadLengthMeters: Number(event.target.value) })} disabled={active} className="field mt-1.5 tabular-nums" /></label>
                      </div>
                      <label className="block text-[10px] text-muted">Calibrated lanes<input type="number" min={1} max={8} step={1} value={calibration.laneCount} onChange={(event) => updateCalibration({ laneCount: Number(event.target.value) })} disabled={active} className="field mt-1.5 tabular-nums" /></label>
                      <label className="block text-[10px] text-muted">Counting-line position · {Math.round(calibration.countingLinePosition * 100)}%<input type="range" min={0.05} max={0.95} step={0.01} value={calibration.countingLinePosition} onChange={(event) => updateCalibration({ countingLinePosition: Number(event.target.value) })} disabled={active} className="mt-2 w-full accent-primary" /></label>
                      <label className="block text-[10px] text-muted">Allowed travel direction<select value={calibration.allowedDirection} onChange={(event) => updateCalibration({ allowedDirection: event.target.value as RoadCalibration["allowedDirection"] })} disabled={active} className="field mt-1.5"><option value="both">Both directions</option><option value="approaching">Approaching camera</option><option value="moving_away">Moving away</option><option value="left_to_right">Left to right</option><option value="right_to_left">Right to left</option></select></label>
                      <label className="flex items-center gap-2 text-[10px] font-semibold text-secondary"><input type="checkbox" checked={calibration.stabilize} onChange={(event) => updateCalibration({ stabilize: event.target.checked })} disabled={active} className="h-4 w-4 accent-primary" />Stabilize camera motion before detection</label>
                      <p className="rounded-lg bg-success/10 p-2 text-[9px] leading-4 text-success">BoT-SORT lifecycle tracking · {calibration.analysisFps} analyzed FPS · calibrated count line</p>
                    </>
                </div>
              </details>

              <div className="flex gap-2 rounded-xl border border-primary/20 bg-primary-soft p-3 text-[10px] leading-5 text-secondary"><CheckCircle2 size={15} className="mt-0.5 shrink-0 text-primary" />Overspeed is reported when calibrated trajectory speed exceeds the configured limit.</div>
              <button type="submit" disabled={!sourceReady || active || !settingsReady} className="primary-button w-full">
                {active ? <><LoaderCircle size={17} className="animate-spin" />Processing video</> : <><Sparkles size={17} />Analyze Traffic Video</>}
              </button>
              {!active && disabledReason && <p className="text-center text-[10px] leading-4 text-muted">{disabledReason}</p>}
            </div>
          </Panel>

          <section className="rounded-2xl border border-border bg-card p-4 shadow-panel"><StepProgress current={currentStep} /></section>
          {job && <Panel title="Analysis Progress"><div className="p-4"><div className="flex justify-between gap-3 text-xs"><strong>{job.stage}</strong><span className="tabular-nums text-primary">{job.progress}%</span></div><div className="mt-3 h-2 overflow-hidden rounded-full bg-elevated"><div className="h-full rounded-full bg-primary transition-[width] duration-500" style={{ width: `${job.progress}%` }} /></div><p className="mt-2 truncate text-[10px] text-muted">{job.filename}</p></div></Panel>}
          {failure && <div role="alert" className="rounded-2xl border border-danger/30 bg-danger/10 p-4 text-xs text-danger"><strong>Analysis could not finish</strong><p className="mt-1 leading-5">{failure}</p><button type="button" onClick={() => { setJobId(null); startAnalysis.reset(); }} className="secondary-button mt-3 border-danger/25 text-danger"><RotateCcw size={14} />Try again</button></div>}
        </aside>
      </form>
      {job?.status === "completed" && job.result && <div ref={resultSection} className="scroll-mt-24"><AnalysisResults result={job.result} /></div>}
    </div>
  );
}
