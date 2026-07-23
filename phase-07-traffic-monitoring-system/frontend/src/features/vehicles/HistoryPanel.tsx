import { useState } from "react";
import { useQuery } from "@tanstack/react-query";
import { Panel } from "../../components/ui/Panel";
import { api } from "../../services/api";
import type { VehicleDetection, VehicleQuery } from "../../types";
import { DetectionFilters } from "./DetectionFilters";
import { DetectionTable } from "./DetectionTable";
import { VehicleDetailsDrawer } from "./VehicleDetailsDrawer";

export function HistoryPanel({ compact = false }: { compact?: boolean }) {
  const [query, setQuery] = useState<VehicleQuery>({ page: 1, pageSize: compact ? 10 : 20, status: "", type: "", search: "", sort: "time_desc" });
  const [selected, setSelected] = useState<VehicleDetection | null>(null);
  const result = useQuery({ queryKey: ["vehicles", query], queryFn: () => api.getVehicles(query) });
  return (
    <>
      <Panel title="Detection history">
        {!compact && <DetectionFilters query={query} onChange={setQuery} />}
        <DetectionTable data={result.data} query={query} loading={result.isLoading} error={result.isError} onQueryChange={setQuery} onSelect={setSelected} />
      </Panel>
      <VehicleDetailsDrawer vehicle={selected} onClose={() => setSelected(null)} />
    </>
  );
}
