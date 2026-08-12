import type { ReportStatus, ReportType } from "../../types";

export const reportTypeLabel = (type: ReportType) => ({
  TRAFFIC_SUMMARY: "Traffic Summary",
  VIOLATION_ENFORCEMENT: "Violation Enforcement",
  ALERT_RESPONSE: "Alert Response",
  VEHICLE_FLOW: "Vehicle Flow",
  CAMERA_PERFORMANCE: "Camera Performance",
  CUSTOM: "Custom Report"
})[type];

export const reportStatusTone = (status: ReportStatus) => ({
  GENERATING: "bg-warning/10 text-warning",
  READY: "bg-success/10 text-success",
  FAILED: "bg-danger/10 text-danger"
})[status];

const sectionLabels: Record<string, string> = {
  kpis: "KPI summary",
  trafficTrend: "Traffic trend",
  vehicleDistribution: "Vehicle distribution",
  comparison: "Previous-period comparison",
  violationDistribution: "Violation distribution",
  violationRecords: "Violation records",
  alertDistribution: "Alert distribution",
  alertRecords: "Alert records",
  auditSummary: "Audit summary",
  laneDirection: "Lane and direction",
  cameraSummary: "Camera summary",
  capabilities: "Capability status"
};

export const sectionLabel = (section: string) => sectionLabels[section] ?? section.replaceAll(/([A-Z])/g, " $1").trim();

export const allReportSections = [
  "kpis", "trafficTrend", "vehicleDistribution", "comparison",
  "violationDistribution", "violationRecords", "alertDistribution",
  "alertRecords", "auditSummary", "laneDirection", "cameraSummary", "capabilities"
];
