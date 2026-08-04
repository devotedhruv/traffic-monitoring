import type { ReactNode } from "react";
import { cx } from "../../lib/format";

export function Panel({ title, action, children, className, flush = false }: { title: string; action?: ReactNode; children: ReactNode; className?: string; flush?: boolean }) {
  return (
    <section className={cx("overflow-hidden rounded-2xl border border-border bg-card shadow-panel", className)}>
      <header className={cx("flex min-h-[50px] items-center justify-between gap-3 px-4", !flush && "border-b border-border")}>
        <h2 className="text-[11px] font-extrabold uppercase tracking-[0.08em] text-ink">{title}</h2>
        {action}
      </header>
      {children}
    </section>
  );
}
