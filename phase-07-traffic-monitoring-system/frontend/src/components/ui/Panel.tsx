import type { ReactNode } from "react";
import { cx } from "../../lib/format";

export function Panel({ title, action, children, className }: { title: string; action?: ReactNode; children: ReactNode; className?: string }) {
  return (
    <section className={cx("overflow-hidden rounded-lg border border-line bg-card shadow-panel", className)}>
      <header className="flex min-h-11 items-center justify-between border-b border-line px-4">
        <div className="flex items-center gap-3">
          <span className="h-5 w-0.5 rounded-full bg-cyan" aria-hidden="true" />
          <h2 className="text-xs font-bold uppercase tracking-[0.14em] text-ink">{title}</h2>
        </div>
        {action}
      </header>
      {children}
    </section>
  );
}
