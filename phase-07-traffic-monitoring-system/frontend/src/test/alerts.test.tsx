import { cleanup, render, screen } from "@testing-library/react";
import { afterEach, describe, expect, it } from "vitest";
import { AlertTable } from "../features/alerts/AlertTable";

afterEach(cleanup);

describe("operational alerts", () => {
  it("distinguishes a healthy empty queue from filtered no-results", () => {
    const query = { page: 1, pageSize: 20, status: "" as const };
    const { rerender } = render(<AlertTable data={{ items: [], total: 0, page: 1, pageSize: 20 }} query={query} onQueryChange={() => undefined} onSelect={() => undefined} />);

    expect(screen.getByText("No operational alerts")).toBeInTheDocument();

    rerender(<AlertTable data={{ items: [], total: 0, page: 1, pageSize: 20 }} query={{ ...query, status: "NEW" }} onQueryChange={() => undefined} onSelect={() => undefined} />);
    expect(screen.getByText("No alerts match these filters")).toBeInTheDocument();
  });
});
