import { HistoryPanel } from "../features/vehicles/HistoryPanel";

export function HistoryPage() {
  return <div><div className="mb-4"><p className="text-xs font-bold uppercase tracking-[0.15em] text-cyan">Traffic archive</p><h1 className="mt-1 text-2xl font-bold">Detection history</h1><p className="mt-1 text-sm text-muted">Search, filter, and inspect recorded vehicle events.</p></div><HistoryPanel /></div>;
}
