import { useState, type ReactNode } from "react";
import { cx } from "../../lib/format";
import { AppHeader } from "./AppHeader";
import { AppSidebar } from "./AppSidebar";

export function AppLayout({ children }: { children: ReactNode }) {
  const [collapsed, setCollapsed] = useState(() => window.localStorage.getItem("trafficops-sidebar") === "collapsed");
  const [mobileOpen, setMobileOpen] = useState(false);
  const toggleCollapse = () => {
    setCollapsed((current) => {
      window.localStorage.setItem("trafficops-sidebar", current ? "expanded" : "collapsed");
      return !current;
    });
  };
  return (
    <div className="min-h-screen text-ink">
      <AppSidebar collapsed={collapsed} mobileOpen={mobileOpen} onCollapse={toggleCollapse} onClose={() => setMobileOpen(false)} />
      <AppHeader collapsed={collapsed} onMenu={() => setMobileOpen(true)} />
      <main className={cx("relative transition-[margin] duration-200", collapsed ? "lg:ml-[82px]" : "lg:ml-[252px]")}>
        <div className="mx-auto max-w-[1700px] px-3 py-5 sm:px-5 sm:py-6 xl:px-6 xl:py-7">{children}</div>
      </main>
    </div>
  );
}
