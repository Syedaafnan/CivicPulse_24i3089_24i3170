/**
 * The client-side validation mirrors the server; this test fails if they drift.
 * openapi.json is exported from the backend (backend/scripts/export_openapi.py).
 */
import { describe, expect, it } from "vitest";
import openapi from "../src/api/openapi.json";
import { getConfig } from "../src/config";
import { LIMITS } from "../src/validation";

describe("contract with the backend", () => {
  const props = openapi.components.schemas.ComplaintCreate.properties;

  it("mirrors the server's length limits exactly", () => {
    expect([props.text.minLength, props.text.maxLength]).toEqual([LIMITS.text.min, LIMITS.text.max]);
    expect([props.location.minLength, props.location.maxLength]).toEqual([LIMITS.location.min, LIMITS.location.max]);
  });

  it("uses a relative API base by default so no backend URL is baked into the bundle", () => {
    delete window.__CIVICPULSE_CONFIG__;
    expect(getConfig().apiBase).toBe("/api");
    window.__CIVICPULSE_CONFIG__ = { environment: "prod", apiBase: "/api/" };
    expect(getConfig()).toEqual({ environment: "prod", apiBase: "/api" });
  });
});
