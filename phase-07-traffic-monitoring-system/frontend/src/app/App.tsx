import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { lazy, Suspense } from "react";
import { AppLayout } from "../components/layout/AppLayout";
import { NotFoundPage } from "../pages/NotFoundPage";
import { LoadingSkeleton } from "../components/ui/States";
import { LiveProvider } from "./LiveContext";
import { ThemeProvider } from "./ThemeContext";
import { usePathname } from "./router";

const queryClient = new QueryClient({ defaultOptions: { queries: { staleTime: 10_000, retry: 1, refetchOnWindowFocus: false } } });
const DashboardPage = lazy(() => import("../pages/DashboardPage").then((module) => ({ default: module.DashboardPage })));
const HistoryPage = lazy(() => import("../pages/HistoryPage").then((module) => ({ default: module.HistoryPage })));
const AnalyticsPage = lazy(() => import("../pages/AnalyticsPage").then((module) => ({ default: module.AnalyticsPage })));
const UploadAnalysisPage = lazy(() => import("../pages/UploadAnalysisPage").then((module) => ({ default: module.UploadAnalysisPage })));

function CurrentPage() {
  const pathname = usePathname().replace(/\/+$/, "") || "/";
  const page = pathname === "/"
    ? <DashboardPage />
    : pathname === "/history"
      ? <HistoryPage />
      : pathname === "/analytics"
        ? <AnalyticsPage />
        : pathname === "/analyze"
          ? <UploadAnalysisPage />
        : <NotFoundPage />;

  return <AppLayout><Suspense fallback={<LoadingSkeleton className="h-[70vh]" />}>{page}</Suspense></AppLayout>;
}

export function App() {
  return <ThemeProvider><QueryClientProvider client={queryClient}><LiveProvider><CurrentPage /></LiveProvider></QueryClientProvider></ThemeProvider>;
}
