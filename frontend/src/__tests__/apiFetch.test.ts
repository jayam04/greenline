import { describe, it, expect, vi, beforeEach, afterEach } from "vitest";
import { apiFetch } from "../lib/api";

describe("apiFetch resilience", () => {
  beforeEach(() => {
    vi.restoreAllMocks();
  });

  afterEach(() => {
    vi.restoreAllMocks();
  });

  it("retries once when encountering transient TypeError Failed to fetch", async () => {
    let callCount = 0;
    const mockFetch = vi.fn().mockImplementation(async () => {
      callCount++;
      if (callCount === 1) {
        throw new TypeError("Failed to fetch");
      }
      return new Response(JSON.stringify([{ account_id: 1, account_name: "Checking" }]), {
        status: 200,
        headers: { "Content-Type": "application/json" },
      });
    });

    vi.stubGlobal("fetch", mockFetch);

    const result = await apiFetch<any[]>("/accounts");
    expect(mockFetch).toHaveBeenCalledTimes(2);
    expect(result).toHaveLength(1);
    expect(result[0].account_name).toBe("Checking");
  });

  it("retries once when encountering transient 502/504 Bad Gateway from proxy", async () => {
    let callCount = 0;
    const mockFetch = vi.fn().mockImplementation(async () => {
      callCount++;
      if (callCount === 1) {
        return new Response("Bad Gateway", { status: 502 });
      }
      return new Response(JSON.stringify({ status: "ok" }), {
        status: 200,
        headers: { "Content-Type": "application/json" },
      });
    });

    vi.stubGlobal("fetch", mockFetch);

    const result = await apiFetch<any>("/settings");
    expect(mockFetch).toHaveBeenCalledTimes(2);
    expect(result.status).toBe("ok");
  });
});
