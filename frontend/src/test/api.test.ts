import { afterEach, describe, expect, it, vi } from "vitest";
import { ApiError, api } from "../api";
import { mockFetch } from "./mockFetch";

afterEach(() => vi.unstubAllGlobals());

async function fail(status: number, detail: unknown): Promise<ApiError> {
  mockFetch({ "POST /session/s1/check": () => ({ status, json: { detail } }) });
  try {
    await api.check("s1");
  } catch (e) {
    return e as ApiError;
  }
  throw new Error("expected a failure");
}

describe("api client error mapping", () => {
  it("409 with an object detail and needs_confirmation[]", async () => {
    const e = await fail(409, { message: "Please confirm these facts before the check runs.", needs_confirmation: ["rejection_ground", "fraud_alleged"] });
    expect(e).toBeInstanceOf(ApiError);
    expect(e.kind).toBe("needs_confirmation");
    expect(e.status).toBe(409);
    expect(e.needsConfirmation).toEqual(["rejection_ground", "fraud_alleged"]);
    expect(e.needsProductLine).toBe(false);
    expect(e.message).toMatch(/confirm these facts/);
  });

  it("409 with needs_product_line", async () => {
    const e = await fail(409, { message: "Please choose the type of insurance before the check runs.", needs_product_line: true, needs_confirmation: [] });
    expect(e.kind).toBe("needs_product_line");
    expect(e.needsProductLine).toBe(true);
  });

  it("409 with a plain string detail is a conflict (e.g. 'Run the check first.')", async () => {
    const e = await fail(409, "Run the check first.");
    expect(e.kind).toBe("conflict");
    expect(e.message).toBe("Run the check first.");
  });

  it("404 means the session expired", async () => {
    const e = await fail(404, "This session has expired or does not exist. Please start again.");
    expect(e.kind).toBe("expired");
  });

  it("422 carries per-field errors", async () => {
    const e = await fail(422, { message: "Some entries could not be read.", errors: { claim_date: "Enter a real date as DD/MM/YYYY, for example 05/03/2024.", insurer_reply_date: "x" } });
    expect(e.kind).toBe("validation");
    expect(e.fieldErrors.claim_date).toMatch(/DD\/MM\/YYYY/);
    expect(Object.keys(e.fieldErrors)).toEqual(["claim_date", "insurer_reply_date"]);
  });

  it("422 from FastAPI's own validation (a list) still yields a message", async () => {
    const e = await fail(422, [{ loc: ["body"], msg: "Field required", type: "missing" }]);
    expect(e.kind).toBe("validation");
    expect(e.message).toBe("Field required");
  });

  it("413 and 415 uploads", async () => {
    expect((await fail(413, "Uploads are limited to 25 MB in total.")).kind).toBe("too_large");
    expect((await fail(415, "Unsupported file type.")).kind).toBe("unsupported_file");
  });

  it("502 and 503 mean the reader/rules are unavailable and manual entry is offered", async () => {
    const a = await fail(502, "We could not read these documents right now. Please try again.");
    const b = await fail(503, "The rules are not available right now. Please try again later.");
    expect(a.kind).toBe("reader_unavailable");
    expect(b.kind).toBe("reader_unavailable");
    expect(a.canEnterManually).toBe(true);
    expect(b.canEnterManually).toBe(true);
  });

  it("a failed fetch becomes a network error", async () => {
    vi.stubGlobal("fetch", vi.fn(async () => { throw new TypeError("offline"); }));
    await expect(api.health()).rejects.toMatchObject({ kind: "network", status: 0 });
  });

  it("an unexpected status is 'unknown' with a default message", async () => {
    const e = await fail(500, null);
    expect(e.kind).toBe("unknown");
    expect(e.message.length).toBeGreaterThan(0);
  });

  it("sends the documented request shapes", async () => {
    const m = mockFetch({
      "PUT /session/s1/facts": () => ({ json: { facts: {}, needs_confirmation: [] } }),
      "POST /session/s1/explain": () => ({ json: {} }),
    });
    await api.putFacts("s1", { facts: { claim_date: { value: "05/03/2024" } }, insurer_reply_date: "01/04/2026" });
    await api.explain("s1", "hi", true);
    expect(m.calls[0].body).toEqual({ facts: { claim_date: { value: "05/03/2024" } }, insurer_reply_date: "01/04/2026" });
    expect(m.calls[1].url).toBe("/session/s1/explain?lang=hi&helper=1");
  });

  it("extract posts multipart files under the name 'files'", async () => {
    const m = mockFetch({ "POST /session/s1/extract": () => ({ json: { facts: {}, needs_confirmation: [], pages: 1, reader_backend: null, product_line_hint: null } }) });
    await api.extract("s1", [new File(["a"], "a.png"), new File(["b"], "b.pdf")]);
    const body = m.calls[0].body as FormData;
    expect(body.getAll("files")).toHaveLength(2);
  });
});
