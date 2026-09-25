import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, expect, it } from "vitest";
import { SubmitPage } from "../src/pages/SubmitPage";
import { complaint, mockFetch } from "./helpers";

async function fill(text: string, location: string) {
  const user = userEvent.setup();
  await user.type(screen.getByLabelText(/what is the problem/i), text);
  await user.type(screen.getByLabelText(/^location/i), location);
  await user.click(screen.getByRole("button", { name: /submit complaint/i }));
}

describe("SubmitPage", () => {
  it("blocks invalid input on the client and never calls the server", async () => {
    const fetchSpy = mockFetch(() => ({ body: {} }));
    render(<SubmitPage />);
    await fill("short", "x");
    expect(screen.getByText(/at least 10 characters/i)).toBeInTheDocument();
    expect(screen.getByText(/at least 3 characters/i)).toBeInTheDocument();
    expect(fetchSpy).not.toHaveBeenCalled();
  });

  it("shows an honest loading state, then category, priority, summary and provider", async () => {
    let release!: () => void;
    const gate = new Promise<void>((r) => (release = r));
    const fetchSpy = mockFetch(() => ({ status: 201, body: complaint() }));
    fetchSpy.mockImplementationOnce(async () => {
      await gate;
      return new Response(JSON.stringify(complaint()), { status: 201 });
    });
    render(<SubmitPage />);
    await fill("Burst water main flooding Street 12", "G-11/3");

    expect(await screen.findByRole("status")).toHaveTextContent(/triaging with ai/i);
    expect(screen.getByRole("button", { name: /submitting/i })).toBeDisabled();

    release();
    const result = await screen.findByTestId("triage-result");
    expect(result).toHaveTextContent("Burst main flooding Street 12");
    expect(result).toHaveTextContent("water");
    expect(result).toHaveTextContent("high");
    expect(result).toHaveTextContent("llm:groq");
  });

  it("explains a rules fallback to the citizen", async () => {
    mockFetch(() => ({ status: 201, body: complaint({ triaged_by: "rules:fallback" }) }));
    render(<SubmitPage />);
    await fill("Burst water main flooding Street 12", "G-11/3");
    expect(await screen.findByText(/AI unavailable/i)).toBeInTheDocument();
  });

  it("maps server field-level 400 errors onto the form", async () => {
    mockFetch(() => ({
      status: 400,
      body: { detail: "Validation failed", errors: [{ field: "location", message: "Location is not recognised" }] },
    }));
    render(<SubmitPage />);
    await fill("Burst water main flooding Street 12", "G-11/3");
    expect(await screen.findByText("Location is not recognised")).toBeInTheDocument();
  });

  it("surfaces the rate-limit message from a 429", async () => {
    mockFetch(() => ({
      status: 429,
      body: { detail: "Too many complaints from this address. Try again in 42 s." },
      headers: { "Retry-After": "42" },
    }));
    render(<SubmitPage />);
    await fill("Burst water main flooding Street 12", "G-11/3");
    await waitFor(() => expect(screen.getByRole("alert")).toHaveTextContent("Try again in 42 s."));
  });
});
