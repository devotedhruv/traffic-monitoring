import { cleanup, fireEvent, render, screen } from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { usePathname } from "../app/router";
import { Link } from "../components/ui/Link";

function RouterProbe() {
  const pathname = usePathname();
  return <><Link to="/history">History</Link><output>{pathname}</output></>;
}

describe("client router", () => {
  beforeEach(() => {
    window.history.replaceState(null, "", "/");
    vi.spyOn(window, "scrollTo").mockImplementation(() => undefined);
  });

  afterEach(() => {
    cleanup();
    vi.restoreAllMocks();
  });

  it("navigates internal links without reloading the page", () => {
    render(<RouterProbe />);
    fireEvent.click(screen.getByRole("link", { name: "History" }));
    expect(screen.getByRole("status")).toHaveTextContent("/history");
  });

  it("reacts to browser history navigation", () => {
    render(<RouterProbe />);
    window.history.pushState(null, "", "/analytics");
    fireEvent.popState(window);
    expect(screen.getByRole("status")).toHaveTextContent("/analytics");
  });
});
