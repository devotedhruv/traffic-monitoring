import { useEffect, useState } from "react";
import { useQuery } from "@tanstack/react-query";
import { Activity, AlertTriangle, BarChart3, ChevronDown, Clock3, LayoutDashboard, LogOut, Menu, Radio, Sparkles } from "lucide-react";
import { useAuth } from "../../app/AuthContext";
import { useLive } from "../../app/LiveContext";
import { navigate, usePathname } from "../../app/router";
import { config } from "../../lib/config";
import { cx } from "../../lib/format";
import { api } from "../../services/api";
import { Link } from "../ui/Link";
import { ThemeToggle } from "../ui/ThemeToggle";

const links = [
  { to: "/app", text: "Dashboard", icon: LayoutDashboard },
  { to: "/app/history", text: "History", icon: Clock3 },
  { to: "/app/violations", text: "Violations", icon: AlertTriangle },
  { to: "/app/analytics", text: "Analytics", icon: BarChart3 },
  { to: "/app/analyze", text: "Analyze video", icon: Sparkles }
] as const;

export function AppHeader({ collapsed, onMenu }: { collapsed: boolean; onMenu: () => void }) {
  const [now, setNow] = useState(new Date());
  const pathname = usePathname().replace(/\/+$/, "") || "/";
  const { connection } = useLive();
  const { user, signOut } = useAuth();
  const cameras = useQuery({ queryKey: ["cameras"], queryFn: api.getCameras });
  useEffect(() => {
    const timer = window.setInterval(() => setNow(new Date()), 1000);
    return () => window.clearInterval(timer);
  }, []);
  const label = connection === "connected" ? "LIVE" : connection.toUpperCase();

  return (
    <header className={cx("sticky top-0 z-40 h-[72px] border-b border-border bg-header/90 backdrop-blur-xl transition-[margin] duration-200", collapsed ? "lg:ml-[82px]" : "lg:ml-[252px]") }>
      <div className="flex h-full items-center gap-3 px-3 sm:px-5 xl:px-6">
        <button type="button" className="icon-button lg:hidden" onClick={onMenu} aria-label="Open navigation"><Menu size={20} /></button>
        <Link to="/app" className="flex items-center gap-2 md:hidden" aria-label="TrafficOps AI dashboard"><span className="grid h-8 w-8 place-items-center rounded-lg bg-primary text-white"><Activity size={17} /></span><strong className="hidden text-xs min-[360px]:block">TrafficOps <span className="text-primary">AI</span></strong></Link>
        <nav className="hidden items-center gap-1 rounded-xl border border-border bg-surface-secondary/70 p-1 md:flex" aria-label="Page navigation">
          {links.map(({ to, text, icon: Icon }) => <Link key={to} to={to} aria-current={pathname === to ? "page" : undefined} className={cx("top-nav-link", pathname === to && "top-nav-link-active")}><Icon size={16} />{text}</Link>)}
        </nav>
        <div className="ml-auto flex min-w-0 items-center gap-2 sm:gap-3">
          {config.useMocks && <span className="hidden rounded-full border border-warning/30 bg-warning/10 px-2.5 py-1 text-[9px] font-bold tracking-wider text-warning 2xl:block">DEMO DATA</span>}
          <label className="hidden items-center gap-2 text-xs text-muted lg:flex"><span className="hidden xl:inline">Camera</span><span className="relative"><select className="h-10 appearance-none rounded-xl border border-border bg-surface px-3 pr-9 text-xs font-semibold text-ink hover:border-border-strong" aria-label="Select camera">{(cameras.data ?? [{ id: "camera-01", name: "North Junction" }]).map((camera) => <option key={camera.id} value={camera.id}>{camera.name}</option>)}</select><ChevronDown className="pointer-events-none absolute right-3 top-3 text-muted" size={14} /></span></label>
          <div className={cx("live-badge", connection === "connected" ? "text-success" : connection === "reconnecting" ? "text-warning" : "text-danger")} aria-live="polite"><Radio size={14} /><span>{label}</span></div>
          <time className="hidden min-w-[148px] text-right text-[11px] tabular-nums text-muted 2xl:block"><span className="block">{new Intl.DateTimeFormat(undefined, { dateStyle: "medium" }).format(now)}</span><strong className="block text-xs text-ink">{new Intl.DateTimeFormat(undefined, { timeStyle: "medium" }).format(now)}</strong></time>
          <ThemeToggle />
          <details className="group relative">
            <summary className="flex h-10 cursor-pointer list-none items-center gap-2 rounded-xl border border-border bg-surface px-1.5 pr-2 text-secondary hover:border-border-strong hover:bg-elevated [&::-webkit-details-marker]:hidden" aria-label="Open account menu">
              <span className="grid h-7 w-7 place-items-center rounded-lg bg-primary-soft text-[9px] font-extrabold text-primary">{user?.name.split(" ").map((part) => part[0]).join("").slice(0, 2).toUpperCase() || "OP"}</span>
              <span className="hidden max-w-[95px] truncate text-[10px] font-bold xl:block">{user?.name || "Operator"}</span>
              <ChevronDown size={12} className="hidden group-open:rotate-180 xl:block" />
            </summary>
            <div className="absolute right-0 top-12 w-56 rounded-2xl border border-border bg-surface p-2 shadow-panel">
              <div className="border-b border-border px-3 py-2.5"><strong className="block truncate text-xs">{user?.name}</strong><span className="mt-0.5 block truncate text-[9px] text-muted">{user?.email}</span></div>
              <button type="button" className="mt-1 flex h-10 w-full items-center gap-2 rounded-xl px-3 text-left text-[11px] font-semibold text-secondary hover:bg-danger-dark hover:text-danger" onClick={async () => { await signOut(); navigate("/"); }}><LogOut size={15} />Sign out</button>
            </div>
          </details>
        </div>
      </div>
    </header>
  );
}
