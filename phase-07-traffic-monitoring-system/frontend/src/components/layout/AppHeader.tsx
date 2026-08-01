import { useEffect, useState } from "react";
import { Activity, BarChart3, ChevronDown, Clock3, LayoutDashboard, Menu, Radio, Sparkles } from "lucide-react";
import { useLive } from "../../app/LiveContext";
import { usePathname } from "../../app/router";
import { config } from "../../lib/config";
import { cx } from "../../lib/format";
import { Link } from "../ui/Link";
import { ThemeToggle } from "../ui/ThemeToggle";

const links = [
  { to: "/", text: "Dashboard", icon: LayoutDashboard },
  { to: "/history", text: "History", icon: Clock3 },
  { to: "/analytics", text: "Analytics", icon: BarChart3 },
  { to: "/analyze", text: "Analyze video", icon: Sparkles }
] as const;

export function AppHeader({ collapsed, onMenu }: { collapsed: boolean; onMenu: () => void }) {
  const [now, setNow] = useState(new Date());
  const pathname = usePathname().replace(/\/+$/, "") || "/";
  const { connection } = useLive();
  useEffect(() => {
    const timer = window.setInterval(() => setNow(new Date()), 1000);
    return () => window.clearInterval(timer);
  }, []);
  const label = connection === "connected" ? "LIVE" : connection.toUpperCase();

  return (
    <header className={cx("sticky top-0 z-40 h-[72px] border-b border-border bg-header/90 backdrop-blur-xl transition-[margin] duration-200", collapsed ? "lg:ml-[82px]" : "lg:ml-[252px]") }>
      <div className="flex h-full items-center gap-3 px-3 sm:px-5 xl:px-6">
        <button type="button" className="icon-button lg:hidden" onClick={onMenu} aria-label="Open navigation"><Menu size={20} /></button>
        <Link to="/" className="flex items-center gap-2 md:hidden" aria-label="TrafficOps AI dashboard"><span className="grid h-8 w-8 place-items-center rounded-lg bg-primary text-white"><Activity size={17} /></span><strong className="hidden text-xs min-[360px]:block">TrafficOps <span className="text-primary">AI</span></strong></Link>
        <nav className="hidden items-center gap-1 rounded-xl border border-border bg-surface-secondary/70 p-1 md:flex" aria-label="Page navigation">
          {links.map(({ to, text, icon: Icon }) => <Link key={to} to={to} aria-current={pathname === to ? "page" : undefined} className={cx("top-nav-link", pathname === to && "top-nav-link-active")}><Icon size={16} />{text}</Link>)}
        </nav>
        <div className="ml-auto flex min-w-0 items-center gap-2 sm:gap-3">
          {config.useMocks && <span className="hidden rounded-full border border-warning/30 bg-warning/10 px-2.5 py-1 text-[9px] font-bold tracking-wider text-warning 2xl:block">DEMO DATA</span>}
          <label className="hidden items-center gap-2 text-xs text-muted lg:flex"><span className="hidden xl:inline">Camera</span><span className="relative"><select className="h-10 appearance-none rounded-xl border border-border bg-surface px-3 pr-9 text-xs font-semibold text-ink hover:border-border-strong" aria-label="Select camera"><option>Camera 01 · North Junction</option></select><ChevronDown className="pointer-events-none absolute right-3 top-3 text-muted" size={14} /></span></label>
          <div className={cx("live-badge", connection === "connected" ? "text-success" : connection === "reconnecting" ? "text-warning" : "text-danger")} aria-live="polite"><Radio size={14} /><span>{label}</span></div>
          <time className="hidden min-w-[148px] text-right text-[11px] tabular-nums text-muted 2xl:block"><span className="block">{new Intl.DateTimeFormat(undefined, { dateStyle: "medium" }).format(now)}</span><strong className="block text-xs text-ink">{new Intl.DateTimeFormat(undefined, { timeStyle: "medium" }).format(now)}</strong></time>
          <ThemeToggle />
        </div>
      </div>
    </header>
  );
}
