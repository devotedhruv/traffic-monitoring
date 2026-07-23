import { createContext, useContext, type ReactNode } from "react";
import { useLiveEvents } from "../hooks/useLiveEvents";

/* eslint-disable react-refresh/only-export-components */
type LiveContextValue = ReturnType<typeof useLiveEvents>;
const LiveContext = createContext<LiveContextValue | null>(null);

export function LiveProvider({ children }: { children: ReactNode }) {
  const value = useLiveEvents();
  return <LiveContext.Provider value={value}>{children}</LiveContext.Provider>;
}

export function useLive() {
  const value = useContext(LiveContext);
  if (!value) throw new Error("useLive must be used within LiveProvider");
  return value;
}
