import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { AppLayout } from "../components/layout/AppLayout";
import { AnalyticsPage } from "../pages/AnalyticsPage";
import { DashboardPage } from "../pages/DashboardPage";
import { HistoryPage } from "../pages/HistoryPage";
import { NotFoundPage } from "../pages/NotFoundPage";
import { LiveProvider } from "./LiveContext";
import { usePathname } from "./router";

const queryClient = new QueryClient({ defaultOptions: { queries: { staleTime: 10_000, retry: 1, refetchOnWindowFocus: false } } });

function CurrentPage() {
  const pathname = usePathname().replace(/\/+$/, "") || "/";
  const page = pathname === "/"
    ? <DashboardPage />
    : pathname === "/history"
      ? <HistoryPage />
      : pathname === "/analytics"
        ? <AnalyticsPage />
        : <NotFoundPage />;

  return <AppLayout>{page}</AppLayout>;
}

export function App() {
  return <QueryClientProvider client={queryClient}><LiveProvider><CurrentPage /></LiveProvider></QueryClientProvider>;
}
