import { AlertTriangle, X, type LucideIcon } from "lucide-react";
import type { InputHTMLAttributes, ReactNode, SelectHTMLAttributes } from "react";
import { cx } from "../../lib/format";

export function SettingsGroup({ icon: Icon, title, description, children, tone = "default" }: {
  icon: LucideIcon;
  title: string;
  description: string;
  children: ReactNode;
  tone?: "default" | "danger";
}) {
  return <section className={cx("overflow-hidden rounded-2xl border bg-card shadow-panel", tone === "danger" ? "border-danger/35" : "border-border")}>
    <header className={cx("flex gap-3 border-b px-4 py-4 sm:px-5", tone === "danger" ? "border-danger/20 bg-danger-dark/35" : "border-border")}>
      <span className={cx("grid h-10 w-10 shrink-0 place-items-center rounded-xl", tone === "danger" ? "bg-danger/10 text-danger" : "bg-primary-soft text-primary")}><Icon size={18} /></span>
      <div><h2 className="text-sm font-extrabold">{title}</h2><p className="mt-1 text-xs leading-5 text-muted">{description}</p></div>
    </header>
    <div className="divide-y divide-border">{children}</div>
  </section>;
}

export function SettingRow({ title, description, children, stack = false }: { title: string; description?: string; children: ReactNode; stack?: boolean }) {
  return <div className={cx("gap-4 px-4 py-4 sm:px-5", stack ? "block" : "flex flex-col sm:grid sm:grid-cols-[minmax(0,1fr)_minmax(220px,0.9fr)] sm:items-center")}>
    <div><h3 className="text-xs font-bold text-ink">{title}</h3>{description && <p className="mt-1 max-w-2xl text-[11px] leading-5 text-muted">{description}</p>}</div>
    <div className={cx(stack && "mt-4")}>{children}</div>
  </div>;
}

export function FieldLabel({ label, hint, children }: { label: string; hint?: string; children: ReactNode }) {
  return <label className="block"><span className="mb-1.5 flex items-center justify-between gap-3 text-[10px] font-bold text-secondary"><span>{label}</span>{hint && <span className="font-normal text-muted">{hint}</span>}</span>{children}</label>;
}

export function TextField({ label, hint, className, ...props }: InputHTMLAttributes<HTMLInputElement> & { label: string; hint?: string }) {
  return <FieldLabel label={label} hint={hint}><input {...props} className={cx("field", className)} /></FieldLabel>;
}

export function SelectField({ label, hint, className, children, ...props }: SelectHTMLAttributes<HTMLSelectElement> & { label: string; hint?: string; children: ReactNode }) {
  return <FieldLabel label={label} hint={hint}><select {...props} className={cx("field", className)}>{children}</select></FieldLabel>;
}

export function Toggle({ checked, onChange, label, disabled = false }: { checked: boolean; onChange: (checked: boolean) => void; label: string; disabled?: boolean }) {
  return <button type="button" role="switch" aria-checked={checked} aria-label={label} disabled={disabled} onClick={() => onChange(!checked)} className={cx("relative h-7 w-12 shrink-0 rounded-full border", checked ? "border-primary bg-primary" : "border-border-strong bg-elevated")}>
    <span className={cx("absolute top-[3px] h-5 w-5 rounded-full bg-white shadow-sm transition-transform", checked ? "translate-x-[22px]" : "translate-x-[3px]")} />
  </button>;
}

export function ToggleGrid({ items }: { items: Array<{ label: string; description?: string; checked: boolean; onChange: (checked: boolean) => void }> }) {
  return <div className="grid gap-2 sm:grid-cols-2">{items.map((item) => <div key={item.label} className="flex min-h-16 items-center justify-between gap-3 rounded-xl border border-border bg-surface-secondary/35 px-3 py-2.5"><div><p className="text-[11px] font-bold">{item.label}</p>{item.description && <p className="mt-0.5 text-[9px] leading-4 text-muted">{item.description}</p>}</div><Toggle checked={item.checked} onChange={item.onChange} label={`Toggle ${item.label}`} /></div>)}</div>;
}

export function StatusPill({ children, tone = "neutral" }: { children: ReactNode; tone?: "success" | "warning" | "danger" | "neutral" | "info" }) {
  const styles = { success: "bg-success/10 text-success", warning: "bg-warning/10 text-warning", danger: "bg-danger/10 text-danger", neutral: "bg-elevated text-muted", info: "bg-info/10 text-info" };
  return <span className={cx("inline-flex items-center rounded-full px-2.5 py-1 text-[9px] font-extrabold uppercase tracking-wider", styles[tone])}>{children}</span>;
}

export function Notice({ children, tone = "info" }: { children: ReactNode; tone?: "info" | "warning" | "danger" }) {
  const styles = { info: "border-info/20 bg-info/5 text-info", warning: "border-warning/25 bg-warning/5 text-warning", danger: "border-danger/25 bg-danger/5 text-danger" };
  return <div className={cx("rounded-xl border px-3 py-2.5 text-[10px] leading-5", styles[tone])}>{children}</div>;
}

export function ConfirmDialog({ open, title, description, confirmLabel, danger = false, onCancel, onConfirm }: {
  open: boolean;
  title: string;
  description: string;
  confirmLabel: string;
  danger?: boolean;
  onCancel: () => void;
  onConfirm: () => void;
}) {
  if (!open) return null;
  return <div className="fixed inset-0 z-[100] grid place-items-center bg-black/55 p-4 backdrop-blur-sm" onMouseDown={(event) => { if (event.target === event.currentTarget) onCancel(); }}>
    <section role="dialog" aria-modal="true" aria-labelledby="confirm-title" className="w-full max-w-md rounded-2xl border border-border bg-surface p-5 shadow-2xl">
      <div className="flex items-start gap-3"><span className={cx("grid h-10 w-10 shrink-0 place-items-center rounded-xl", danger ? "bg-danger/10 text-danger" : "bg-warning/10 text-warning")}><AlertTriangle size={18} /></span><div className="min-w-0 flex-1"><h2 id="confirm-title" className="text-sm font-extrabold">{title}</h2><p className="mt-2 text-xs leading-5 text-muted">{description}</p></div><button type="button" className="icon-button h-8 w-8" onClick={onCancel} aria-label="Close confirmation"><X size={14} /></button></div>
      <div className="mt-5 flex justify-end gap-2"><button type="button" className="secondary-button" onClick={onCancel}>Cancel</button><button type="button" className={cx("inline-flex h-10 items-center justify-center rounded-xl px-4 text-xs font-bold text-white", danger ? "bg-danger hover:bg-danger/85" : "bg-warning hover:bg-warning/85")} onClick={onConfirm}>{confirmLabel}</button></div>
    </section>
  </div>;
}
