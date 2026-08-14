import { cleanup, fireEvent, render, screen, waitFor } from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { App } from "../app/App";

describe("public and authentication experience", () => {
  beforeEach(() => {
    vi.stubGlobal("fetch", vi.fn().mockResolvedValue({
      ok: false,
      status: 401,
      json: () => Promise.resolve({ detail: "Authentication required" })
    }));
    vi.spyOn(window, "scrollTo").mockImplementation(() => undefined);
  });

  afterEach(() => {
    cleanup();
    vi.restoreAllMocks();
    vi.unstubAllGlobals();
  });

  it("presents the traffic intelligence landing page", async () => {
    window.history.replaceState(null, "", "/");
    render(<App />);
    expect(screen.getByRole("heading", { name: /see every road/i })).toBeInTheDocument();
    expect(screen.getByRole("link", { name: /start monitoring/i })).toHaveAttribute("href", "/sign-up");
    await waitFor(() => expect(fetch).toHaveBeenCalled());
  });

  it("validates password confirmation before creating an account", async () => {
    window.history.replaceState(null, "", "/sign-up");
    render(<App />);
    await screen.findByRole("heading", { name: /start with sadakdrishti/i });
    fireEvent.change(screen.getByPlaceholderText("Traffic operator"), { target: { value: "Road Admin" } });
    fireEvent.change(screen.getByPlaceholderText("you@organization.com"), { target: { value: "admin@example.com" } });
    fireEvent.change(screen.getByPlaceholderText("At least 8 characters"), { target: { value: "correct-pass" } });
    fireEvent.change(screen.getByPlaceholderText("Repeat your password"), { target: { value: "different-pass" } });
    fireEvent.click(screen.getByRole("button", { name: "Create account" }));
    expect(screen.getByRole("alert")).toHaveTextContent("Passwords do not match");
    expect(fetch).toHaveBeenCalledTimes(1);
  });

  it("catches a common Gmail domain typo before creating an account", async () => {
    window.history.replaceState(null, "", "/sign-up");
    render(<App />);
    await screen.findByRole("heading", { name: /start with sadakdrishti/i });
    fireEvent.change(screen.getByPlaceholderText("Traffic operator"), { target: { value: "Road Admin" } });
    fireEvent.change(screen.getByPlaceholderText("you@organization.com"), { target: { value: "admin@gmaiil.com" } });
    fireEvent.change(screen.getByPlaceholderText("At least 8 characters"), { target: { value: "correct-pass" } });
    fireEvent.change(screen.getByPlaceholderText("Repeat your password"), { target: { value: "correct-pass" } });
    fireEvent.click(screen.getByRole("button", { name: "Create account" }));
    expect(screen.getByRole("alert")).toHaveTextContent("Did you mean admin@gmail.com?");
    expect(fetch).toHaveBeenCalledTimes(1);
  });
});
