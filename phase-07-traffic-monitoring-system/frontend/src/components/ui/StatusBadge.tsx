import { AlertTriangle, CheckCircle2 } from "lucide-react";
import { cx } from "../../lib/format";
import type { VehicleStatus } from "../../types";

export function StatusBadge({ status, verbose = false }: { status: VehicleStatus; verbose?: boolean }) {
  const over = status === "OVERSPEED";
  const Icon = over ? AlertTriangle : CheckCircle2;
  return (
    <span className={cx(
      "inline-flex items-center gap-1.5 rounded border px-2 py-1 text-[11px] font-bold tracking-wide",
      over ? "border-danger/25 bg-danger/10 text-danger" : "border-success/20 bg-success/10 text-success"
    )}>
      <Icon size={13} aria-hidden="true" />
      {verbose ? (over ? "OVERSPEED VIOLATION" : "WITHIN SPEED LIMIT") : status}
    </span>
  );
}
