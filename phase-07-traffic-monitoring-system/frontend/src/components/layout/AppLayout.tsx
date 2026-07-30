import type { ReactNode } from "react";
import { AppHeader } from "./AppHeader";

export function AppLayout({ children }: { children: ReactNode }) {
  return <div className="min-h-screen bg-page text-ink"><AppHeader /><main className="mx-auto max-w-[1800px] p-3 sm:p-4 lg:p-6">{children}</main></div>;
}
