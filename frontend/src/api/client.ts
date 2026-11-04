import type {
  CheckResponse,
  ExplainResponse,
  ExtractResponse,
  FactsBody,
  FactsResponse,
  GalleryCase,
  GalleryList,
  EvidenceSummary,
  Health,
  PolicyBody,
  PolicyExtractResponse,
  PolicyResponse,
  SchemeAnswers,
  SchemeCatalogue,
  SchemeMatch,
  SessionCreated,
} from "./types";

/**
 * What kind of failure this is, decided once here so screens never look at raw status codes.
 *  expired            404  the session is gone (1 hour TTL, or server restart)
 *  needs_confirmation 409  {detail:{message, needs_confirmation[]}}
 *  needs_product_line 409  {detail:{message, needs_product_line:true, needs_confirmation[]}}
 *  conflict           409  detail is a plain string ("Run the check first.", letter messages)
 *  validation         422  {detail:{message, errors:{key: msg}}}
 *  too_large          413  upload over 25 MB
 *  unsupported_file   415  not jpg/png/pdf, or too many pages
 *  reader_unavailable 502/503  the reader or the rules are unavailable -> offer manual entry
 *  network            fetch itself failed
 *  unknown            anything else
 */
export type ApiErrorKind =
  | "expired"
  | "needs_confirmation"
  | "needs_product_line"
  | "conflict"
  | "validation"
  | "too_large"
  | "unsupported_file"
  | "reader_unavailable"
  | "network"
  | "unknown";

export class ApiError extends Error {
  readonly kind: ApiErrorKind;
  readonly status: number;
  readonly detail: unknown;
  readonly fieldErrors: Record<string, string>;
  readonly needsConfirmation: string[];
  readonly needsProductLine: boolean;

  constructor(status: number, detail: unknown, fallbackMessage: string) {
    const parsed = parseDetail(detail);
    super(parsed.message || fallbackMessage);
    this.name = "ApiError";
    this.status = status;
    this.detail = detail;
    this.fieldErrors = parsed.errors;
    this.needsConfirmation = parsed.needsConfirmation;
    this.needsProductLine = parsed.needsProductLine;
    this.kind = classify(status, parsed);
  }

  /** True when the reader/rules are down and the user can still enter facts by hand. */
  get canEnterManually(): boolean {
    return this.kind === "reader_unavailable";
  }
}

interface ParsedDetail {
  message: string;
  isObject: boolean;
  errors: Record<string, string>;
  needsConfirmation: string[];
  needsProductLine: boolean;
}

function parseDetail(detail: unknown): ParsedDetail {
  const empty: ParsedDetail = {
    message: "",
    isObject: false,
    errors: {},
    needsConfirmation: [],
    needsProductLine: false,
  };
  if (typeof detail === "string") return { ...empty, message: detail };
  if (Array.isArray(detail)) {
    // FastAPI's own validation errors: [{loc, msg, type}]
    const msg = detail
      .map((d) => (d && typeof d === "object" && "msg" in d ? String((d as { msg: unknown }).msg) : ""))
      .filter(Boolean)
      .join("; ");
    return { ...empty, message: msg };
  }
  if (detail && typeof detail === "object") {
    const d = detail as Record<string, unknown>;
    const errors: Record<string, string> = {};
    if (d.errors && typeof d.errors === "object") {
      for (const [k, v] of Object.entries(d.errors as Record<string, unknown>)) errors[k] = String(v);
    }
    return {
      message: typeof d.message === "string" ? d.message : "",
      isObject: true,
      errors,
      needsConfirmation: Array.isArray(d.needs_confirmation) ? d.needs_confirmation.map(String) : [],
      needsProductLine: d.needs_product_line === true,
    };
  }
  return empty;
}

function classify(status: number, p: ParsedDetail): ApiErrorKind {
  if (status === 0) return "network";
  if (status === 404) return "expired";
  if (status === 409) {
    if (p.needsProductLine) return "needs_product_line";
    if (p.isObject) return "needs_confirmation";
    return "conflict";
  }
  if (status === 413) return "too_large";
  if (status === 415) return "unsupported_file";
  if (status === 422) return "validation";
  if (status === 502 || status === 503) return "reader_unavailable";
  return "unknown";
}

export const DEFAULT_ERROR = "Something went wrong";

async function request<T>(method: string, path: string, opts: { json?: unknown; form?: FormData } = {}): Promise<T> {
  const init: RequestInit = { method, headers: {} };
  if (opts.form) {
    init.body = opts.form;
  } else if (opts.json !== undefined) {
    (init.headers as Record<string, string>)["content-type"] = "application/json";
    init.body = JSON.stringify(opts.json);
  }
  let res: Response;
  try {
    res = await fetch(path, init);
  } catch {
    throw new ApiError(0, null, "We could not reach the server. Check your connection and try again.");
  }
  let data: unknown = null;
  try {
    data = await res.json();
  } catch {
    /* non-JSON body */
  }
  if (!res.ok) {
    const detail = data && typeof data === "object" && "detail" in data ? (data as { detail: unknown }).detail : null;
    throw new ApiError(res.status, detail, DEFAULT_ERROR);
  }
  return data as T;
}

const sid = (id: string) => `/session/${encodeURIComponent(id)}`;

/** Real upload progress: bytes the browser has handed to the network so far, out of the body size. */
export interface UploadProgress {
  loaded: number;
  total: number;
}
export type OnProgress = (p: UploadProgress) => void;

/**
 * A multipart upload through XMLHttpRequest, used only when the caller wants byte progress (fetch cannot report upload progress).
 * Failures map to the same ApiError kinds as `request`: the status code and the `detail` body decide the kind, a dead network is status 0.
 * `lengthComputable` is checked: if the browser cannot say how many bytes there are, no progress is reported at all (never a guess).
 */
function uploadWithProgress<T>(path: string, form: FormData, onProgress: OnProgress): Promise<T> {
  return new Promise<T>((resolve, reject) => {
    const xhr = new XMLHttpRequest();
    xhr.open("POST", path);
    xhr.responseType = "text";
    xhr.upload.onprogress = (e: ProgressEvent) => {
      if (e.lengthComputable && e.total > 0) onProgress({ loaded: e.loaded, total: e.total });
    };
    xhr.onerror = () => reject(new ApiError(0, null, "We could not reach the server. Check your connection and try again."));
    xhr.onabort = xhr.onerror;
    xhr.ontimeout = xhr.onerror;
    xhr.onload = () => {
      let data: unknown = null;
      try {
        data = JSON.parse(xhr.responseText);
      } catch {
        /* non-JSON body */
      }
      if (xhr.status >= 200 && xhr.status < 300) return resolve(data as T);
      const detail = data && typeof data === "object" && "detail" in data ? (data as { detail: unknown }).detail : null;
      reject(new ApiError(xhr.status, detail, DEFAULT_ERROR));
    };
    xhr.send(form);
  });
}

function upload<T>(path: string, files: File[], onProgress?: OnProgress): Promise<T> {
  const form = filesForm(files);
  if (onProgress && typeof XMLHttpRequest !== "undefined") return uploadWithProgress<T>(path, form, onProgress);
  return request<T>("POST", path, { form });
}

function filesForm(files: File[]): FormData {
  const fd = new FormData();
  for (const f of files) fd.append("files", f);
  return fd;
}

export const api = {
  health: () => request<Health>("GET", "/health"),
  createSession: () => request<SessionCreated>("POST", "/session"),
  deleteSession: (id: string) => request<{ deleted: boolean }>("DELETE", sid(id)),
  extract: (id: string, files: File[], onProgress?: OnProgress) => upload<ExtractResponse>(`${sid(id)}/extract`, files, onProgress),
  putFacts: (id: string, body: FactsBody) => request<FactsResponse>("PUT", `${sid(id)}/facts`, { json: body }),
  check: (id: string) => request<CheckResponse>("POST", `${sid(id)}/check`),
  explain: (id: string, lang: "en" | "hi", helper: boolean) =>
    request<ExplainResponse>("POST", `${sid(id)}/explain?lang=${lang}&helper=${helper ? 1 : 0}`),
  policyExtract: (id: string, files: File[], onProgress?: OnProgress) => upload<PolicyExtractResponse>(`${sid(id)}/policy/extract`, files, onProgress),
  policyGet: (id: string) => request<PolicyResponse>("GET", `${sid(id)}/policy`),
  policyPut: (id: string, body: PolicyBody) => request<PolicyResponse>("PUT", `${sid(id)}/policy`, { json: body }),
  policyDelete: (id: string) => request<{ deleted: boolean }>("DELETE", `${sid(id)}/policy`),
  schemes: () => request<SchemeCatalogue>("GET", "/api/schemes"),
  matchSchemes: (answers: SchemeAnswers) => request<SchemeMatch>("POST", "/api/schemes/match", { json: answers }),
  evidence: () => request<EvidenceSummary>("GET", "/api/evidence"),
  gallery: () => request<GalleryList>("GET", "/gallery"),
  galleryCase: (caseId: string) => request<GalleryCase>("GET", `/gallery/${encodeURIComponent(caseId)}`),
  letterUrl: (id: string, lang: "en" | "hi") => `${sid(id)}/letter.pdf?lang=${lang}`,
  /** Fetch the letter as a Blob so a 409 can be shown instead of navigating to JSON. */
  async letter(id: string, lang: "en" | "hi"): Promise<Blob> {
    let res: Response;
    try {
      res = await fetch(`${sid(id)}/letter.pdf?lang=${lang}`);
    } catch {
      throw new ApiError(0, null, "We could not reach the server. Check your connection and try again.");
    }
    if (!res.ok) {
      let detail: unknown = null;
      try {
        const data = await res.json();
        detail = data && typeof data === "object" && "detail" in data ? data.detail : null;
      } catch {
        /* ignore */
      }
      throw new ApiError(res.status, detail, DEFAULT_ERROR);
    }
    return res.blob();
  },
};
