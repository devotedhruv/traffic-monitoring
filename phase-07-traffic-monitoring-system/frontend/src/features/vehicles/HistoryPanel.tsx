import { useState } from "react";
import { useQuery } from "@tanstack/react-query";
import { Columns3, Download, RefreshCw } from "lucide-react";
import { Panel } from "../../components/ui/Panel";
import { api } from "../../services/api";
import type { VehicleDetection, VehicleQuery } from "../../types";
import { DetectionFilters } from "./DetectionFilters";
import { DetectionTable } from "./DetectionTable";
import { VehicleDetailsDrawer } from "./VehicleDetailsDrawer";

function initialQuery(compact: boolean): VehicleQuery {
  const params = new URLSearchParams(window.location.search);
  return { page: 1, pageSize: compact ? 10 : 20, status: params.get("status") === "OVERSPEED" ? "OVERSPEED" : "", type: "", speed: "", date: compact ? "" : "today", search: "", sort: "time_desc" };
}

function exportRows(rows: VehicleDetection[]) {
  const csv = ["Tracking ID,Vehicle Type,Plate,Speed,Speed Limit,Status,Detection Time", ...rows.map((item) => [item.trackingId, item.vehicleType, item.plate || "UNKNOWN", item.speed, item.speedLimit, item.status, item.detectedAt].map((value) => `"${String(value).replaceAll('"', '""')}"`).join(","))].join("\n");
  const url = URL.createObjectURL(new Blob([csv], { type: "text/csv" }));
  const link = document.createElement("a"); link.href = url; link.download = `trafficops-detections-${new Date().toISOString().slice(0, 10)}.csv`; link.click(); URL.revokeObjectURL(url);
}

export function HistoryPanel({ compact = false }: { compact?: boolean }) {
  const [query, setQuery] = useState<VehicleQuery>(() => initialQuery(compact));
  const [selected, setSelected] = useState<VehicleDetection | null>(null);
  const result = useQuery({ queryKey: ["vehicles", query], queryFn: () => api.getVehicles(query) });
  return (
    <>
      <Panel title={compact ? "Recent detections" : "Detection records"} action={<div className="flex items-center gap-2"><span className="hidden text-[11px] font-semibold text-muted sm:inline">{result.data?.total.toLocaleString() ?? "—"} results</span><button type="button" className="secondary-button h-9" onClick={() => exportRows(result.data?.items ?? [])} disabled={!result.data?.items.length}><Download size={14} />Export</button><button type="button" className="icon-button h-9 w-9" onClick={() => result.refetch()} aria-label="Refresh detections" title="Refresh"><RefreshCw size={14} /></button><button type="button" className="secondary-button h-9" title="Core columns are optimized for this screen"><Columns3 size={14} />Columns</button></div>}>
        {!compact && <DetectionFilters query={query} onChange={setQuery} />}
        <DetectionTable data={result.data} query={query} loading={result.isLoading} error={result.isError} onQueryChange={setQuery} onSelect={setSelected} selectedId={selected?.id} />
      </Panel>
      <VehicleDetailsDrawer vehicle={selected} onClose={() => setSelected(null)} />
    </>
  );
}
