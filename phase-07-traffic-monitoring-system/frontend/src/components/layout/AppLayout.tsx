import { Outlet } from "react-router-dom";
import { AppHeader } from "./AppHeader";

export function AppLayout() {
  return <div className="min-h-screen bg-page text-ink"><AppHeader /><main className="mx-auto max-w-[1800px] p-3 sm:p-4 lg:p-6"><Outlet /></main></div>;
}
