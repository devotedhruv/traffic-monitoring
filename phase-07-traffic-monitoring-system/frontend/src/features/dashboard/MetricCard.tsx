import type { LucideIcon } from "lucide-react";
import { cx } from "../../lib/format";

export function MetricCard({ label, value, note, icon: Icon, tone = "cyan" }: { label: string; value: string | number; note?: string; icon: LucideIcon; tone?: "cyan" | "danger" | "amber" | "success" }) {
  const tones = { cyan: "text-cyan bg-cyan/10", danger: "text-danger bg-danger/10", amber: "text-amber bg-amber/10", success: "text-success bg-success/10" };
  return (
    <article className="rounded-lg border border-line bg-card p-4">
      <div className="flex items-start justify-between">
        <div><p className="text-[11px] font-bold uppercase tracking-[0.12em] text-muted">{label}</p><p className="mt-2 text-2xl font-bold tabular-nums">{value}</p></div>
        <span className={cx("rounded-md p-2", tones[tone])}><Icon size={18} aria-hidden="true" /></span>
      </div>
      {note && <p className="mt-2 text-xs text-muted">{note}</p>}
    </article>
  );
}
