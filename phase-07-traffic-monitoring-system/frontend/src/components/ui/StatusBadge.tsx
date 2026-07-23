import { AlertTriangle, CheckCircle2 } from "lucide-react";
import { cx } from "../../lib/format";
import type { VehicleStatus } from "../../types";

export function StatusBadge({ status, verbose = false }: { status: VehicleStatus; verbose?: boolean }) {
  const over = status === "OVERSPEED";
  const Icon = over ? AlertTriangle : CheckCircle2;
  return (
    <span className={cx(
      "inline-flex items-center gap-1.5 rounded border px-2 py-1 text-[11px] font-bold tracking-wide",
      over ? "border-danger/30 bg-danger-dark text-danger" : "border-success/25 bg-cyan-dark text-success"
    )}>
      <Icon size={13} aria-hidden="true" />
      {verbose ? (over ? "OVERSPEED VIOLATION" : "WITHIN SPEED LIMIT") : status}
    </span>
  );
}
