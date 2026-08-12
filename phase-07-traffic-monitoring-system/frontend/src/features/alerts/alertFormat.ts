import type { AlertSeverity, AlertStatus, ViolationType } from "../../types";

export const alertTypeLabel = (type: ViolationType) => ({
  OVERSPEED: "Overspeed",
  NO_HELMET: "No helmet",
  WRONG_LANE: "Wrong lane",
  WRONG_DIRECTION: "Wrong direction"
})[type];

export const alertStatusLabel = (status: AlertStatus) => status === "FALSE_POSITIVE"
  ? "False positive"
  : status.charAt(0) + status.slice(1).toLowerCase();

export const severityTone = (severity: AlertSeverity) => ({
  LOW: "border-border bg-elevated text-muted",
  MEDIUM: "border-warning/20 bg-warning/10 text-warning",
  HIGH: "border-danger/20 bg-danger/10 text-danger",
  CRITICAL: "border-danger/40 bg-danger text-white"
})[severity];

export const statusTone = (status: AlertStatus) => ({
  NEW: "bg-danger/10 text-danger",
  ACKNOWLEDGED: "bg-primary-soft text-primary",
  INVESTIGATING: "bg-warning/10 text-warning",
  RESOLVED: "bg-success/10 text-success",
  FALSE_POSITIVE: "bg-elevated text-muted"
})[status];
