import { useSyncExternalStore } from "react";

function subscribe(onStoreChange: () => void) {
  window.addEventListener("popstate", onStoreChange);
  return () => window.removeEventListener("popstate", onStoreChange);
}

function getPathname() {
  return window.location.pathname;
}

export function usePathname() {
  return useSyncExternalStore(subscribe, getPathname, () => "/");
}

export function navigate(to: string) {
  if (window.location.pathname === to) return;
  window.history.pushState(null, "", to);
  window.dispatchEvent(new PopStateEvent("popstate"));
  window.scrollTo({ top: 0 });
}
