import { cleanup, render, screen } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";

vi.mock("../app/AuthContext", () => ({ useAuth: () => ({ user: { name: "Operator", email: "operator@example.com" } }) }));
vi.mock("../app/router", () => ({ usePathname: () => "/app/reports" }));
vi.mock("../services/api", () => ({ api: { getAlertSummary: () => Promise.resolve({ new: 0 }) } }));

import { AppSidebar } from "../components/layout/AppSidebar";

afterEach(cleanup);

describe("reports navigation", () => {
  it("uses a dedicated reports route and marks it active", () => {
    render(<AppSidebar collapsed={false} mobileOpen={false} onCollapse={() => undefined} onClose={() => undefined} />);
    expect(screen.getByRole("link", { name: "Reports" })).toHaveAttribute("href", "/app/reports");
    expect(screen.getByRole("link", { name: "Reports" })).toHaveAttribute("aria-current", "page");
    expect(screen.getByRole("link", { name: "Analytics" })).not.toHaveAttribute("aria-current");
  });
});
