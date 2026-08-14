import { useSyncExternalStore } from "react";

function subscribe(onStoreChange: () => void) {
  window.addEventListener("popstate", onStoreChange);
  return () => window.removeEventListener("popstate", onStoreChange);
}

function getPathname() {
  return window.location.pathname;
}

function getSearch() {
  return window.location.search;
}

export function usePathname() {
  return useSyncExternalStore(subscribe, getPathname, () => "/");
}

export function useSearch() {
  return useSyncExternalStore(subscribe, getSearch, () => "");
}

export function navigate(to: string) {
  const current = `${window.location.pathname}${window.location.search}${window.location.hash}`;
  if (current === to) return;
  const beforeNavigate = new CustomEvent("trafficops:before-navigate", { cancelable: true, detail: { to } });
  if (!window.dispatchEvent(beforeNavigate)) return;
  window.history.pushState(null, "", to);
  window.dispatchEvent(new PopStateEvent("popstate"));
  window.scrollTo({ top: 0 });
}
