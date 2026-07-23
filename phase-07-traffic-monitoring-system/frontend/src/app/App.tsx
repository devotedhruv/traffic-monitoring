import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { createBrowserRouter, RouterProvider } from "react-router-dom";
import { AppLayout } from "../components/layout/AppLayout";
import { AnalyticsPage } from "../pages/AnalyticsPage";
import { DashboardPage } from "../pages/DashboardPage";
import { HistoryPage } from "../pages/HistoryPage";
import { NotFoundPage } from "../pages/NotFoundPage";
import { LiveProvider } from "./LiveContext";

const queryClient = new QueryClient({ defaultOptions: { queries: { staleTime: 10_000, retry: 1, refetchOnWindowFocus: false } } });
const router = createBrowserRouter([{ path: "/", element: <AppLayout />, children: [{ index: true, element: <DashboardPage /> }, { path: "history", element: <HistoryPage /> }, { path: "analytics", element: <AnalyticsPage /> }, { path: "*", element: <NotFoundPage /> }] }]);

export function App() {
  return <QueryClientProvider client={queryClient}><LiveProvider><RouterProvider router={router} /></LiveProvider></QueryClientProvider>;
}
