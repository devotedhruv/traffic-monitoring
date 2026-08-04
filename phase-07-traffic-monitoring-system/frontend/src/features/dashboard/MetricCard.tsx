import type { LucideIcon } from "lucide-react";
import { cx } from "../../lib/format";

export function MetricCard({ label, value, unit, note, icon: Icon, tone = "success", compact = false }: { label: string; value: string | number; unit?: string; note?: string; icon: LucideIcon; tone?: "cyan" | "danger" | "amber" | "success" | "info" | "purple"; compact?: boolean }) {
  const tones = { cyan: "text-cyan bg-cyan/10", danger: "text-danger bg-danger/10", amber: "text-warning bg-warning/10", success: "text-success bg-success/10", info: "text-info bg-info/10", purple: "text-purple bg-purple/10" };
  return (
    <article className={cx("group rounded-2xl border border-border bg-card shadow-panel transition hover:-translate-y-0.5 hover:border-border-strong hover:shadow-card", compact ? "p-3.5" : "p-4")}>
      <span className={cx("inline-grid rounded-xl p-2.5 transition group-hover:scale-105", tones[tone])}><Icon size={18} aria-hidden="true" /></span>
      <p className="mt-3 text-[10px] font-bold uppercase tracking-[0.08em] text-muted">{label}</p>
      <p className="mt-1 flex items-baseline gap-1 text-[25px] font-extrabold tracking-[-0.035em] tabular-nums">{value}{unit && <span className="text-[11px] font-semibold tracking-normal text-secondary">{unit}</span>}</p>
      {note && <p className="mt-1 text-[10px] leading-4 text-muted">{note}</p>}
    </article>
  );
}
