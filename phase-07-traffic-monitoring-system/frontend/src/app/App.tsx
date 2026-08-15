import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { lazy, Suspense, useEffect } from "react";
import { AppLayout } from "../components/layout/AppLayout";
import { NotFoundPage } from "../pages/NotFoundPage";
import { LoadingSkeleton } from "../components/ui/States";
import { LiveProvider } from "./LiveContext";
import { ThemeProvider } from "./ThemeContext";
import { LanguageProvider } from "./LanguageContext";
import { navigate, usePathname, useSearch } from "./router";
import { AuthProvider, useAuth } from "./AuthContext";
import { JunctionProvider } from "./JunctionContext";
import { AlertNotificationManager } from "../features/alerts/AlertNotificationManager";

import { LandingPage } from "../pages/LandingPage";
import { AuthPage } from "../pages/AuthPage";

const queryClient = new QueryClient({ defaultOptions: { queries: { staleTime: 10_000, retry: 1, refetchOnWindowFocus: false } } });
const DashboardPage = lazy(() => import("../pages/DashboardPage").then((module) => ({ default: module.DashboardPage })));
const HistoryPage = lazy(() => import("../pages/HistoryPage").then((module) => ({ default: module.HistoryPage })));
const ViolationsPage = lazy(() => import("../pages/ViolationsPage").then((module) => ({ default: module.ViolationsPage })));
const AlertsPage = lazy(() => import("../pages/AlertsPage").then((module) => ({ default: module.AlertsPage })));
const ReportsPage = lazy(() => import("../pages/ReportsPage").then((module) => ({ default: module.ReportsPage })));
const AnalyticsPage = lazy(() => import("../pages/AnalyticsPage").then((module) => ({ default: module.AnalyticsPage })));
const UploadAnalysisPage = lazy(() => import("../pages/UploadAnalysisPage").then((module) => ({ default: module.UploadAnalysisPage })));
const SettingsPage = lazy(() => import("../pages/SettingsPage").then((module) => ({ default: module.SettingsPage })));

function RedirectToSignIn({ from }: { from: string }) {
  useEffect(() => navigate(`/sign-in?next=${encodeURIComponent(from)}`), [from]);
  return <div className="mx-auto mt-24 max-w-sm"><LoadingSkeleton className="h-48" /></div>;
}

function Application({ pathname, search }: { pathname: string; search: string }) {
  const { status } = useAuth();
  if (status === "loading") return <div className="mx-auto mt-24 max-w-md px-5"><LoadingSkeleton className="h-64" /></div>;
  if (status === "anonymous") return <RedirectToSignIn from={`${window.location.pathname}${window.location.search}`} />;

  const settingsPanel = pathname === "/app" && new URLSearchParams(search).get("panel") === "settings";
  const page = pathname === "/app"
    ? settingsPanel ? <SettingsPage /> : <DashboardPage />
    : pathname === "/app/history"
      ? <HistoryPage />
      : pathname === "/app/violations"
        ? <ViolationsPage />
      : pathname === "/app/alerts"
        ? <AlertsPage />
      : pathname === "/app/reports"
        ? <ReportsPage />
      : pathname === "/app/analytics"
        ? <AnalyticsPage />
        : pathname === "/app/analyze"
          ? <UploadAnalysisPage />
          : <NotFoundPage inApp />;

  return <LiveProvider><AlertNotificationManager /><AppLayout><Suspense fallback={<LoadingSkeleton className="h-[70vh]" />}>{page}</Suspense></AppLayout></LiveProvider>;
}

function CurrentPage() {
  const pathname = usePathname().replace(/\/+$/, "") || "/";
  const search = useSearch();
  if (pathname === "/") return <LandingPage />;
  if (pathname === "/sign-in") return <AuthPage mode="signin" />;
  if (pathname === "/sign-up") return <AuthPage mode="signup" />;
  if (pathname === "/app" || pathname.startsWith("/app/")) return <Application pathname={pathname} search={search} />;
  return <NotFoundPage />;
}

export function App() {
  return <ThemeProvider><LanguageProvider><QueryClientProvider client={queryClient}><AuthProvider><JunctionProvider><CurrentPage /></JunctionProvider></AuthProvider></QueryClientProvider></LanguageProvider></ThemeProvider>;
}
