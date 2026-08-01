import {
  Activity, AlertTriangle, BarChart3, Bell, CarFront, ChevronLeft, ChevronRight,
  FileText, RadioTower, Settings, ShieldCheck, Video
} from "lucide-react";
import { usePathname } from "../../app/router";
import { cx } from "../../lib/format";
import { Link } from "../ui/Link";

const navigation = [
  { to: "/", label: "Live Operations", icon: RadioTower },
  { to: "/history", label: "Vehicles", icon: CarFront },
  { to: "/history?status=OVERSPEED", label: "Violations", icon: AlertTriangle },
  { to: "/history?status=OVERSPEED&view=alerts", label: "Alerts", icon: Bell },
  { to: "/analytics", label: "Analytics", icon: BarChart3 },
  { to: "/analytics?view=reports", label: "Reports", icon: FileText },
  { to: "/analyze", label: "Analyze Video", icon: Video },
  { to: "/?panel=settings", label: "Settings", icon: Settings }
] as const;

function Brand({ collapsed = false }: { collapsed?: boolean }) {
  return (
    <Link to="/" className={cx("flex items-center gap-3", collapsed && "justify-center")} aria-label="TrafficOps AI dashboard">
      <span className="brand-mark"><Activity size={25} strokeWidth={2.2} /></span>
      {!collapsed && <span className="min-w-0"><strong className="block whitespace-nowrap text-[17px] tracking-[-0.02em]">TrafficOps <span className="text-primary">AI</span></strong><span className="block whitespace-nowrap text-[10px] text-muted">Road intelligence, made visible</span></span>}
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
  return (
    <button type="button" className={cx("operator-card", collapsed && "justify-center px-2")} title="Signed in as Traffic Admin">
      <span className="grid h-9 w-9 shrink-0 place-items-center rounded-full bg-primary-soft text-primary"><span className="text-xs font-bold">TA</span></span>
      {!collapsed && <><span className="min-w-0 flex-1 text-left"><span className="block text-[10px] text-muted">Operator</span><strong className="block truncate text-xs">Traffic Admin</strong></span><ChevronRight size={15} className="text-muted" /></>}
    </button>
  );
}

export function AppSidebar({ collapsed, mobileOpen, onCollapse, onClose }: { collapsed: boolean; mobileOpen: boolean; onCollapse: () => void; onClose: () => void }) {
  const pathname = usePathname().replace(/\/+$/, "") || "/";
  const sidebar = (
    <div className="flex h-full flex-col">
      <div className={cx("flex h-[82px] items-center border-b border-border px-5", collapsed && "justify-center px-2")}><Brand collapsed={collapsed} /></div>
      <nav className="scrollbar-thin flex-1 space-y-1 overflow-y-auto px-3 py-2" aria-label="Product navigation">
        {navigation.map(({ to, label, icon: Icon }) => {
          const path = to.split("?")[0];
          const active = path === "/" ? pathname === "/" && label === "Live Operations" : pathname === path && (path === "/history" ? label === "Vehicles" : path === "/analytics" ? label === "Analytics" : true);
          return <Link key={label} to={to} onClick={onClose} aria-current={active ? "page" : undefined} title={collapsed ? label : undefined} className={cx("sidebar-link", active && "sidebar-link-active", collapsed && "justify-center px-0")}><Icon size={18} strokeWidth={1.9} /><span className={cx(collapsed && "sr-only")}>{label}</span></Link>;
        })}
      </nav>
      <div className="space-y-3 p-3"><SystemStatus collapsed={collapsed} /><Operator collapsed={collapsed} /></div>
      <button type="button" onClick={onCollapse} className="absolute -right-3 top-[96px] hidden h-7 w-7 place-items-center rounded-full border border-border bg-surface text-muted shadow-card hover:text-primary lg:grid" aria-label={collapsed ? "Expand sidebar" : "Collapse sidebar"}>{collapsed ? <ChevronRight size={15} /> : <ChevronLeft size={15} />}</button>
    </div>
  );
  return <>
    <aside className={cx("fixed inset-y-0 left-0 z-50 hidden border-r border-border bg-sidebar transition-[width] duration-200 lg:block", collapsed ? "w-[82px]" : "w-[252px]")}>{sidebar}</aside>
    <div className={cx("fixed inset-0 z-[60] bg-black/45 backdrop-blur-sm transition lg:hidden", mobileOpen ? "visible opacity-100" : "invisible opacity-0")} onMouseDown={(event) => { if (event.target === event.currentTarget) onClose(); }}>
      <aside className={cx("h-full w-[286px] max-w-[86vw] border-r border-border bg-sidebar shadow-2xl transition-transform duration-200", mobileOpen ? "translate-x-0" : "-translate-x-full")} aria-hidden={!mobileOpen}>{mobileOpen && <div className="h-full">{sidebar}</div>}</aside>
    </div>
  </>;
}
