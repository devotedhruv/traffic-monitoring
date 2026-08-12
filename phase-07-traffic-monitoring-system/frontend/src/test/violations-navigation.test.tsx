import { cleanup, render, screen } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";

vi.mock("../app/AuthContext", () => ({
  useAuth: () => ({ user: { name: "Traffic Operator", email: "operator@example.com" } })
}));
vi.mock("../app/router", () => ({
  usePathname: () => "/app/violations",
  navigate: vi.fn()
}));
vi.mock("../services/api", () => ({
  api: { getAlertSummary: () => Promise.resolve({ new: 0 }) }
}));

import { AppSidebar } from "../components/layout/AppSidebar";

afterEach(cleanup);

describe("violations navigation", () => {
  it("opens a dedicated violations route and marks it active", () => {
    render(<AppSidebar collapsed={false} mobileOpen={false} onCollapse={() => undefined} onClose={() => undefined} />);

    expect(screen.getByRole("link", { name: "Violations" })).toHaveAttribute("href", "/app/violations");
    expect(screen.getByRole("link", { name: "Violations" })).toHaveAttribute("aria-current", "page");
    expect(screen.getByRole("link", { name: "Vehicles" })).not.toHaveAttribute("aria-current");
    expect(screen.getByRole("link", { name: "Alerts" })).toHaveAttribute("href", "/app/alerts");
  });
});
