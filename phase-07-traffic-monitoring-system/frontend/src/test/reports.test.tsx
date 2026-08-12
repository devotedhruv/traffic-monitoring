import { cleanup, fireEvent, render, screen } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";
import { ReportTable } from "../features/reports/ReportTable";
import { ReportCreationDialog } from "../features/reports/ReportCreationDialog";
import type { ReportQuery, ReportTemplate } from "../types";

const query: ReportQuery = { page: 1, pageSize: 20, search: "", type: "", status: "", creator: null, date: "", sort: "newest" };
const templates: ReportTemplate[] = [{ type: "TRAFFIC_SUMMARY", name: "Traffic Summary", description: "Recorded traffic totals.", sections: ["kpis"] }];

afterEach(() => { cleanup(); vi.restoreAllMocks(); });

describe("reports centre", () => {
  it("distinguishes no reports from filtered no-results", () => {
    const props = { items: [], total: 0, query, onQueryChange: vi.fn(), onOpen: vi.fn(), onRegenerate: vi.fn() };
    const { rerender } = render(<ReportTable {...props} />);
    expect(screen.getByText("No reports have been generated")).toBeInTheDocument();

    rerender(<ReportTable {...props} query={{ ...query, status: "FAILED" }} />);
    expect(screen.getByText("No reports match these filters")).toBeInTheDocument();
  });

  it("selects a template and validates an invalid reporting period", () => {
    render(<ReportCreationDialog open initialType="TRAFFIC_SUMMARY" templates={templates} cameras={[]} operators={[]} onClose={vi.fn()} onGenerated={vi.fn()} />);
    expect(screen.getByRole("button", { name: /traffic summary recorded traffic totals/i })).toHaveAttribute("aria-pressed", "true");
    fireEvent.click(screen.getByRole("button", { name: /continue/i }));
    fireEvent.click(screen.getByRole("button", { name: /continue/i }));

    const inputs = screen.getAllByDisplayValue(/2026|2025|2027/);
    fireEvent.change(inputs[0], { target: { value: "2026-08-13T12:00" } });
    fireEvent.change(inputs[1], { target: { value: "2026-08-13T11:00" } });
    fireEvent.click(screen.getByRole("button", { name: /continue/i }));

    expect(screen.getByRole("alert")).toHaveTextContent(/start time must be before/i);
  });
});
