import type { ReactNode } from "react";

export function PageHeader({ eyebrow, title, subtitle, action }: { eyebrow?: ReactNode; title: string; subtitle: string; action?: ReactNode }) {
  return (
    <header className="flex flex-wrap items-end justify-between gap-4">
      <div>{eyebrow && <div className="eyebrow">{eyebrow}</div>}<h1 className="page-title mt-1">{title}</h1><p className="page-subtitle">{subtitle}</p></div>
      {action && <div className="shrink-0">{action}</div>}
    </header>
  );
}
