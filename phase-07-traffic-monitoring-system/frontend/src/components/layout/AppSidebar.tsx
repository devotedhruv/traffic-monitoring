import {
  AlertTriangle, BarChart3, Bell, CarFront, ChevronLeft, ChevronRight,
  FileText, RadioTower, Settings, ShieldCheck, Video
} from "lucide-react";
import { useEffect, useState } from "react";
import { useAuth } from "../../app/AuthContext";
import { usePathname } from "../../app/router";
import { cx } from "../../lib/format";
import { api } from "../../services/api";
import { PRODUCT_NAME, PRODUCT_TAGLINE } from "../../lib/brand";
import { BrandLogo } from "../ui/BrandLogo";
import { Link } from "../ui/Link";

const navigation = [
  { to: "/app", label: "Live Operations", icon: RadioTower },
  { to: "/app/history", label: "Vehicles", icon: CarFront },
  { to: "/app/violations", label: "Violations", icon: AlertTriangle },
  { to: "/app/alerts", label: "Alerts", icon: Bell },
  { to: "/app/analytics", label: "Analytics", icon: BarChart3 },
  { to: "/app/reports", label: "Reports", icon: FileText },
  { to: "/app/analyze", label: "Analyze Video", icon: Video },
  { to: "/app?panel=settings", label: "Settings", icon: Settings }
] as const;

function Brand({ collapsed = false }: { collapsed?: boolean }) {
  return (
    <Link to="/app" className={cx("flex items-center gap-3", collapsed && "justify-center")} aria-label={`${PRODUCT_NAME} dashboard`}>
      <BrandLogo variant="mark" className="brand-mark p-1" />
      {!collapsed && <span className="min-w-0"><strong className="block whitespace-nowrap text-[17px] tracking-[-0.02em]">Sadak<span className="text-[#FF8395]">Drishti</span></strong><span className="block whitespace-nowrap text-[10px] text-muted">{PRODUCT_TAGLINE}</span></span>}
    </Link>
  );
}

function SystemStatus({ collapsed = false }: { collapsed?: boolean }) {
  return (
    <section className={cx("system-card", collapsed && "px-2")} aria-label="System status: 98 percent healthy">
      {!collapsed && <><p className="text-xs font-semibold">System Status</p><p className="mt-2 flex items-center gap-2 text-[11px] font-semibold text-success"><span className="status-dot" />All systems operational</p></>}
      <div className={cx("health-ring", collapsed ? "mx-auto mt-0 h-11 w-11" : "mx-auto mt-5 h-24 w-24")}><ShieldCheck size={collapsed ? 18 : 29} /></div>
      {!collapsed && <div className="mt-3 text-center"><strong className="block text-2xl tabular-nums text-success">98%</strong><span className="text-xs text-muted">System Health</span></div>}
    </section>
  );
}

function Operator({ collapsed = false }: { collapsed?: boolean }) {
  const { user } = useAuth();
  const initials = user?.name.split(" ").map((part) => part[0]).join("").slice(0, 2).toUpperCase() || "OP";
  return (
    <div className={cx("operator-card", collapsed && "justify-center px-2")} title={`Signed in as ${user?.name || "Operator"}`}>
      <span className="grid h-9 w-9 shrink-0 place-items-center rounded-full bg-primary-soft text-primary"><span className="text-xs font-bold">{initials}</span></span>
      {!collapsed && <span className="min-w-0 flex-1 text-left"><span className="block text-[10px] text-muted">Operator</span><strong className="block truncate text-xs">{user?.name || "Operator"}</strong><span className="block truncate text-[8px] text-muted">{user?.email}</span></span>}
    </div>
  );
}

export function AppSidebar({ collapsed, mobileOpen, onCollapse, onClose }: { collapsed: boolean; mobileOpen: boolean; onCollapse: () => void; onClose: () => void }) {
  const pathname = usePathname().replace(/\/+$/, "") || "/";
  const settingsActive = pathname === "/app" && new URLSearchParams(window.location.search).get("panel") === "settings";
  const [newAlerts, setNewAlerts] = useState(0);
  useEffect(() => {
    const increment = () => setNewAlerts((count) => count + 1);
    const synchronize = (event: Event) => setNewAlerts(Math.max(0, Number((event as CustomEvent<number>).detail) || 0));
    window.addEventListener("trafficops:new-alert", increment);
    window.addEventListener("trafficops:alert-count", synchronize);
    return () => {
      window.removeEventListener("trafficops:new-alert", increment);
      window.removeEventListener("trafficops:alert-count", synchronize);
    };
  }, []);
  useEffect(() => {
    void api.getAlertSummary("all").then((summary) => setNewAlerts(summary.new)).catch(() => undefined);
  }, []);
  const sidebar = (
    <div className="flex h-full flex-col">
      <div className={cx("flex h-[82px] items-center border-b border-border px-5", collapsed && "justify-center px-2")}><Brand collapsed={collapsed} /></div>
      <nav className="scrollbar-thin flex-1 space-y-1 overflow-y-auto px-3 py-2" aria-label="Product navigation">
        {navigation.map(({ to, label, icon: Icon }) => {
          const path = to.split("?")[0];
          const active = path === "/app"
            ? pathname === "/app" && (label === "Settings" ? settingsActive : label === "Live Operations" && !settingsActive)
            : pathname === path && (
              path === "/app/history" ? label === "Vehicles"
              : path === "/app/violations" ? label === "Violations"
              : path === "/app/analytics" ? label === "Analytics"
              : true
            );
          return <Link key={label} to={to} onClick={onClose} aria-current={active ? "page" : undefined} title={collapsed ? label : undefined} className={cx("sidebar-link relative", active && "sidebar-link-active", collapsed && "justify-center px-0")}><Icon size={18} strokeWidth={1.9} /><span className={cx(collapsed && "sr-only")}>{label}</span>{label === "Alerts" && newAlerts > 0 && <span className={cx("ml-auto min-w-5 rounded-full bg-danger px-1.5 py-0.5 text-center text-[9px] font-bold text-white", collapsed && "absolute right-1 top-1")}>{newAlerts > 99 ? "99+" : newAlerts}</span>}</Link>;
        })}
      </nav>
      <div className="space-y-3 p-3"><SystemStatus collapsed={collapsed} /><Operator collapsed={collapsed} /></div>
      <button type="button" onClick={onCollapse} className="sidebar-collapse-button absolute -right-3 top-[96px] hidden h-7 w-7 place-items-center rounded-full border border-border bg-surface text-muted shadow-card hover:text-primary lg:grid" aria-label={collapsed ? "Expand sidebar" : "Collapse sidebar"}>{collapsed ? <ChevronRight size={15} /> : <ChevronLeft size={15} />}</button>
    </div>
  );
  return <>
    <aside className={cx("app-sidebar-shell fixed inset-y-0 left-0 z-50 hidden border-r border-border bg-sidebar transition-[width] duration-200 lg:block", collapsed ? "w-[82px]" : "w-[252px]")}>{sidebar}</aside>
    <div className={cx("fixed inset-0 z-[60] bg-black/45 backdrop-blur-sm transition lg:hidden", mobileOpen ? "visible opacity-100" : "invisible opacity-0")} onMouseDown={(event) => { if (event.target === event.currentTarget) onClose(); }}>
      <aside className={cx("app-sidebar-shell h-full w-[286px] max-w-[86vw] border-r border-border bg-sidebar shadow-2xl transition-transform duration-200", mobileOpen ? "translate-x-0" : "-translate-x-full")} aria-hidden={!mobileOpen}>{mobileOpen && <div className="h-full">{sidebar}</div>}</aside>
    </div>
  </>;
}
