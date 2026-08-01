import { Check } from "lucide-react";
import { cx } from "../../lib/format";

const steps = [{ title: "Upload", note: "Add your video" }, { title: "Analyze", note: "AI processes data" }, { title: "Results", note: "View insights" }];

export function StepProgress({ current }: { current: 1 | 2 | 3 }) {
  return <ol className="grid grid-cols-3 gap-2" aria-label={`Video analysis step ${current} of 3`}>{steps.map((step, index) => { const number = index + 1; const complete = number < current; const active = number === current; return <li key={step.title} className="relative text-center"><div className="mb-3 flex items-center"><span className={cx("h-px flex-1", index === 0 ? "bg-transparent" : complete || active ? "bg-primary" : "bg-border")} /><span className={cx("grid h-9 w-9 shrink-0 place-items-center rounded-full border text-xs font-bold", complete || active ? "border-primary bg-primary text-white shadow-card" : "border-border bg-elevated text-muted")}>{complete ? <Check size={16} /> : number}</span><span className={cx("h-px flex-1", index === steps.length - 1 ? "bg-transparent" : complete ? "bg-primary" : "bg-border")} /></div><strong className={cx("block text-xs", active ? "text-primary" : "text-ink")}>{step.title}</strong><span className="mt-1 block text-[9px] text-muted">{step.note}</span></li>})}</ol>;
}
