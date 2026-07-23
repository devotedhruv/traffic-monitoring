import { useEffect, useState } from "react";
import { Activity, Menu, Radio, X } from "lucide-react";
import { NavLink } from "react-router-dom";
import { useLive } from "../../app/LiveContext";
import { config } from "../../lib/config";
import { cx, formatDateTime } from "../../lib/format";

const links = [["/", "Dashboard"], ["/history", "History"], ["/analytics", "Analytics"]] as const;

export function AppHeader() {
  const [now, setNow] = useState(new Date());
  const [menu, setMenu] = useState(false);
  const { connection } = useLive();
  useEffect(() => {
    const timer = window.setInterval(() => setNow(new Date()), 1000);
    return () => window.clearInterval(timer);
  }, []);
  const label = connection === "connected" ? "LIVE" : connection.toUpperCase();
  const tone = connection === "connected" ? "text-success" : connection === "reconnecting" ? "text-amber" : "text-danger";

  return (
    <header className="sticky top-0 z-40 border-b border-line bg-surface/95 backdrop-blur">
      <div className="mx-auto flex h-16 max-w-[1800px] items-center gap-4 px-4 lg:px-6">
        <NavLink to="/" className="flex min-w-0 items-center gap-3" aria-label="TrafficOps dashboard">
          <span className="grid h-9 w-9 shrink-0 place-items-center rounded-md border border-cyan/30 bg-cyan-dark text-cyan"><Activity size={20} /></span>
          <span className="min-w-0">
            <span className="block text-sm font-extrabold tracking-[0.16em]">TRAFFICOPS</span>
            <span className="hidden truncate text-[11px] text-muted sm:block">AI traffic intelligence and violation monitoring</span>
          </span>
        </NavLink>
        <nav className="ml-6 hidden items-center gap-1 lg:flex" aria-label="Main navigation">
          {links.map(([to, text]) => <NavLink key={to} to={to} end={to === "/"} className={({ isActive }) => cx("rounded px-3 py-2 text-sm font-medium text-muted hover:bg-elevated hover:text-ink", isActive && "bg-elevated text-cyan")}>{text}</NavLink>)}
        </nav>
        <div className="ml-auto flex items-center gap-3">
          {config.useMocks && <span className="hidden rounded border border-amber/30 bg-amber/10 px-2 py-1 text-[10px] font-bold tracking-wider text-amber sm:block">DEMO DATA</span>}
          <label className="hidden items-center gap-2 text-xs text-muted md:flex">
            Camera
            <select className="rounded border border-line bg-elevated px-2 py-1.5 text-ink" aria-label="Select camera">
              <option>Camera 01 · North Junction</option>
            </select>
          </label>
          <div className={cx("flex items-center gap-1.5 text-xs font-bold", tone)} aria-live="polite"><Radio size={14} /><span>{label}</span></div>
          <time className="hidden w-44 text-right text-xs tabular-nums text-muted xl:block">{formatDateTime(now)}</time>
          <button className="rounded p-2 text-muted hover:bg-elevated hover:text-ink lg:hidden" onClick={() => setMenu((value) => !value)} aria-label={menu ? "Close navigation" : "Open navigation"} aria-expanded={menu}>{menu ? <X /> : <Menu />}</button>
        </div>
      </div>
      {menu && <nav className="border-t border-line p-2 lg:hidden" aria-label="Mobile navigation">{links.map(([to, text]) => <NavLink key={to} to={to} onClick={() => setMenu(false)} className={({ isActive }) => cx("block rounded px-3 py-2 text-sm text-muted", isActive && "bg-elevated text-cyan")}>{text}</NavLink>)}</nav>}
    </header>
  );
}
