import { render, screen, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, expect, it } from "vitest";
import { DashboardPage } from "../src/pages/DashboardPage";
import { ENUMS, complaint, mockFetch } from "./helpers";

const CONFLICT = "Invalid status transition: open → resolved. 'open' can move to: in_progress, rejected.";

function server(opts: { total?: number } = {}) {
  const calls: string[] = [];
  const spy = mockFetch((url, init) => {
    calls.push(`${init?.method ?? "GET"} ${url}`);
    if (url.includes("/meta/enums")) return { body: ENUMS };
    if (init?.method === "PATCH") {
      const target = JSON.parse(String(init.body)).status;
      if (target === "resolved") return { status: 409, body: { detail: CONFLICT, current: "open", attempted: "resolved" } };
      return { body: complaint({ status: target, allowed_transitions: ["resolved", "rejected"] }) };
    }
    return { body: { items: [complaint()], total: opts.total ?? 1, page: 1, page_size: 10 } };
  });
  return { spy, calls };
}

describe("DashboardPage", () => {
  it("renders complaints and offers the server's allowed transitions", async () => {
    server();
    render(<DashboardPage />);
    const row = await screen.findByTestId("complaint-row");
    expect(row).toHaveTextContent("Burst main flooding Street 12");
    const group = within(row).getByRole("group", { name: /allowed next/i });
    expect(within(group).getAllByRole("option").map((o) => o.textContent)).toEqual(["in progress", "rejected"]);
  });

  it("shows the server's 409 message verbatim, not a generic error", async () => {
    server();
    render(<DashboardPage />);
    const row = await screen.findByTestId("complaint-row");
    await screen.findAllByRole("option", { name: "resolved" });
    await userEvent.selectOptions(within(row).getByRole("combobox"), "resolved");
    expect(await screen.findByRole("alert")).toHaveTextContent(CONFLICT);
  });

  it("applies a valid transition from the server response", async () => {
    server();
    render(<DashboardPage />);
    const row = await screen.findByTestId("complaint-row");
    await userEvent.selectOptions(within(row).getByRole("combobox"), "in_progress");
    expect(await within(row).findByText("in progress")).toHaveClass("badge-status");
  });

  it("sends filters and pagination to the API", async () => {
    const { calls } = server({ total: 25 });
    render(<DashboardPage />);
    await screen.findByTestId("complaint-row");
    await screen.findAllByRole("option", { name: "roads" });
    await userEvent.selectOptions(screen.getByLabelText("Category filter"), "roads");
    await screen.findByText(/page 1 of 3/i);
    await userEvent.click(screen.getByRole("button", { name: /next/i }));
    await screen.findByText(/page 2 of 3/i);
    const lists = calls.filter((c) => c.startsWith("GET /api/complaints"));
    expect(lists.at(-2)).toContain("category=roads");
    expect(lists.at(-1)).toContain("page=2");
  });
});
