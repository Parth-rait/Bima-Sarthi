import { vi } from "vitest";

export type Handler = (req: { url: string; method: string; body: unknown }) => { status?: number; json?: unknown; blob?: Blob } | Promise<{ status?: number; json?: unknown; blob?: Blob }>;

/** Route table keyed "METHOD /path" (query string ignored). Records every call. */
export function mockFetch(routes: Record<string, Handler>) {
  const calls: Array<{ key: string; url: string; body: unknown }> = [];
  const fn = vi.fn(async (input: RequestInfo | URL, init?: RequestInit) => {
    const url = String(input);
    const method = (init?.method ?? "GET").toUpperCase();
    const path = url.split("?")[0];
    const key = `${method} ${path}`;
    let body: unknown = undefined;
    if (typeof init?.body === "string") body = JSON.parse(init.body);
    else if (init?.body) body = init.body;
    calls.push({ key, url, body });
    const h = routes[key] ?? routes[`${method} *`];
    if (!h) throw new Error(`unmocked ${key}`);
    const r = await h({ url, method, body });
    const status = r.status ?? 200;
    return {
      ok: status >= 200 && status < 300,
      status,
      json: async () => r.json ?? null,
      blob: async () => r.blob ?? new Blob(["%PDF"]),
    } as Response;
  });
  vi.stubGlobal("fetch", fn);
  return { fn, calls, count: (key: string) => calls.filter((c) => c.key === key).length };
}
