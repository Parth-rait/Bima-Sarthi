import {
  createContext,
  useCallback,
  useContext,
  useEffect,
  useMemo,
  useReducer,
  useRef,
  type ReactNode,
} from "react";
import { ApiError, api } from "../api";
import type { ExtractResponse, FactsBody, FactsResponse, OnProgress, PolicyBody, PolicyExtractResponse } from "../api";
import type { ConfirmForm } from "../lib/confirm";
import { translate, type Key, type Lang } from "../i18n";
import { SLOW_AFTER_MS, deriveActivity, type AppActivity, type BusyKind, type ViewName } from "./activity";
import { effectiveProduct, initialState, pendingKeys, reducer, type SessionState, type SlotId, type Step } from "./session";
import { saveBlob } from "../lib/download";

export type Outcome<T = void> = { ok: true; value: T } | { ok: false; error: ApiError };

export interface Actions {
  setLang(lang: Lang): void;
  setHelper(helper: boolean): void;
  goto(view: ViewName): void;
  toggleChecked(id: string): void;
  openGallery(): void;
  closeGallery(): void;
  setProductChoice(v: SessionState["productChoice"]): void;
  startManual(): Promise<Outcome>;
  /** `advance: false` keeps the current step (the workspace moves on itself after the policy has been read too). */
  extract(files: File[], opts?: { onProgress?: OnProgress; advance?: boolean }): Promise<Outcome<ExtractResponse>>;
  policyExtract(files: File[], opts?: { onProgress?: OnProgress }): Promise<Outcome<PolicyExtractResponse>>;
  /** step 1: read every slot that has files waiting (the letter first, then the optional policy), with real upload progress */
  readDocuments(): Promise<Outcome<{ letterRead: boolean }>>;
  setStep(step: Step): void;
  setForm(update: ConfirmForm | ((f: ConfirmForm) => ConfirmForm)): void;
  setSlotFiles(slot: SlotId, files: File[]): void;
  policySave(body: PolicyBody): Promise<Outcome>;
  policyRemove(): Promise<Outcome>;
  saveFacts(body: FactsBody): Promise<Outcome<FactsResponse>>;
  /** PUT the facts, then run the check, then fetch the written explanation. */
  saveAndCheck(body: FactsBody): Promise<Outcome>;
  downloadLetter(): Promise<Outcome>;
  deleteData(): Promise<void>;
  restart(): void;
}

interface Ctx {
  state: SessionState;
  actions: Actions;
  activity: AppActivity;
  t: (key: Key) => string;
}

const SessionContext = createContext<Ctx | null>(null);

/** A random id for the in-memory report URL. Deliberately unrelated to the server session id. */
function newReportId(): string {
  const c = typeof crypto !== "undefined" ? crypto : undefined;
  if (c?.randomUUID) return c.randomUUID();
  return Array.from({ length: 4 }, () => Math.floor(Math.random() * 0xffffffff).toString(16).padStart(8, "0")).join("");
}

function toApiError(e: unknown): ApiError {
  return e instanceof ApiError ? e : new ApiError(0, null, e instanceof Error ? e.message : "Something went wrong");
}

export function SessionProvider({ children, initial }: { children: ReactNode; initial?: Partial<SessionState> }) {
  const [state, dispatch] = useReducer(reducer, undefined, () => initialState({ ...initial }));
  const ref = useRef(state);
  ref.current = state;

  // Slow-request detector: a request in flight past SLOW_AFTER_MS marks the app as "waiting".
  useEffect(() => {
    if (!state.busy) return;
    const id = setTimeout(() => dispatch({ type: "slow" }), SLOW_AFTER_MS);
    return () => clearTimeout(id);
  }, [state.busy]);

  const guard = useCallback(async <T,>(kind: BusyKind, fn: () => Promise<T>): Promise<Outcome<T>> => {
    dispatch({ type: "busy", busy: kind });
    try {
      const value = await fn();
      dispatch({ type: "ok" });
      return { ok: true, value };
    } catch (e) {
      const error = toApiError(e);
      if (error.kind === "expired") dispatch({ type: "expired" });
      else dispatch({ type: "error", kind: error.kind });
      return { ok: false, error };
    } finally {
      dispatch({ type: "busy", busy: null });
    }
  }, []);

  const ensureSid = useCallback(async (): Promise<string> => {
    if (ref.current.sid) return ref.current.sid;
    const { session_id } = await api.createSession();
    dispatch({ type: "sid", sid: session_id });
    ref.current = { ...ref.current, sid: session_id };
    return session_id;
  }, []);

  const requireSid = (): string => {
    const id = ref.current.sid;
    if (!id) throw new ApiError(404, null, "This session has expired or does not exist. Please start again.");
    return id;
  };

  /** Fetch the written explanation; failure is non-fatal (the findings stand on their own). */
  const explainInto = useCallback(async (afterCheck = false) => {
    const { sid, lang, helper, result } = ref.current;
    // right after a check the new result is dispatched but not yet rendered into ref.current
    if (!sid || (!result && !afterCheck)) return;
    const out = await guard("explain", () => api.explain(sid, lang, helper));
    if (out.ok) dispatch({ type: "explained", ex: out.value });
    else if (out.error.kind !== "expired") dispatch({ type: "explain_failed" });
  }, [guard]);

  // Language or helper change: re-fetch the explanation in the new language/wording.
  const first = useRef(true);
  useEffect(() => {
    if (first.current) {
      first.current = false;
      return;
    }
    if (ref.current.result && ref.current.sid) void explainInto();
  }, [state.lang, state.helper, explainInto]);

  useEffect(() => {
    document.documentElement.lang = state.lang;
  }, [state.lang]);

  const reading = useRef(false);

  const actions = useMemo<Actions>(() => {
    const extract: Actions["extract"] = (files, opts) =>
      guard("extract", async () => {
        const id = await ensureSid();
        const r = await api.extract(id, files, opts?.onProgress);
        dispatch({
          type: "extracted",
          facts: r.facts,
          pages: r.pages,
          backend: r.reader_backend ?? null,
          hint: r.product_line_hint ?? null,
          advance: opts?.advance,
        });
        return r;
      });
    const policyExtract: Actions["policyExtract"] = (files, opts) =>
      guard("policy", async () => {
        const r = await api.policyExtract(requireSid(), files, opts?.onProgress);
        dispatch({ type: "policy", policy: r.policy ?? null });
        return r;
      });

    /** Progress reporter for one slot: "uploading" with a real share of bytes, then "reading" the moment the last byte is sent. */
    const progressFor = (slot: SlotId): OnProgress => {
      let last = -1;
      return ({ loaded, total }) => {
        const pct = Math.min(100, Math.floor((loaded / total) * 100));
        if (pct === last) return;
        last = pct;
        dispatch({ type: "slot", slot, patch: loaded >= total ? { status: "reading", progress: 1 } : { status: "uploading", progress: pct / 100 } });
      };
    };
    const names = (files: File[]) => files.map((f) => f.name);
    const bytes = (files: File[]) => files.reduce((n, f) => n + f.size, 0);
    const waiting = (slot: SlotId) => {
      const sl = ref.current.slots[slot];
      return sl.files.length > 0 && (sl.status === "ready" || sl.status === "failed");
    };

    const readDocuments: Actions["readDocuments"] = async () => {
      // idempotent: a second press while the first is in flight does nothing (the buttons are disabled too)
      if (reading.current) return { ok: true, value: { letterRead: false } };
      reading.current = true;
      try {
        let letterRead = false;
        if (waiting("letter")) {
          const files = ref.current.slots.letter.files;
          dispatch({ type: "slot", slot: "letter", patch: { status: "uploading", progress: 0, error: null } });
          const out = await extract(files, { advance: false, onProgress: progressFor("letter") });
          if (!out.ok) {
            dispatch({ type: "slot", slot: "letter", patch: { status: "failed", progress: null, error: { kind: out.error.kind, message: out.error.message } } });
            return out;
          }
          const prev = ref.current.slots.letter;
          dispatch({
            type: "slot",
            slot: "letter",
            patch: { status: "done", progress: null, error: null, files: [], readNames: [...prev.readNames, ...names(files)], readPages: out.value.pages, readBytes: prev.readBytes + bytes(files) },
          });
          letterRead = true;
        }
        if (waiting("policy")) {
          const files = ref.current.slots.policy.files;
          dispatch({ type: "slot", slot: "policy", patch: { status: "uploading", progress: 0, error: null } });
          const out = await policyExtract(files, { onProgress: progressFor("policy") });
          if (out.ok) {
            dispatch({ type: "slot", slot: "policy", patch: { status: "done", progress: null, error: null, files: [], readNames: names(files), readPages: out.value.pages, readBytes: bytes(files) } });
          } else {
            // the policy is optional: its failure is shown on its own slot and does not stop the letter's result
            dispatch({ type: "slot", slot: "policy", patch: { status: "failed", progress: null, error: { kind: out.error.kind, message: out.error.message } } });
            if (!letterRead) return out;
          }
        }
        if (letterRead) dispatch({ type: "step", step: 2 });
        return { ok: true, value: { letterRead } };
      } finally {
        reading.current = false;
      }
    };

    const saveFacts = (body: FactsBody) =>
      guard("facts", async () => {
        const r = await api.putFacts(requireSid(), body);
        dispatch({ type: "facts", facts: r.facts });
        return r;
      });
    const runCheck = async (): Promise<Outcome> => {
      const out = await guard("check", async () => {
        const c = await api.check(requireSid());
        dispatch({ type: "checked", check: c, reportId: newReportId() });
      });
      if (out.ok) await explainInto(true);
      return out;
    };
    return {
      setLang: (lang) => dispatch({ type: "lang", lang }),
      setHelper: (helper) => dispatch({ type: "helper", helper }),
      goto: (view) => dispatch({ type: "view", view }),
      toggleChecked: (id) => dispatch({ type: "toggle_item", id }),
      openGallery: () => dispatch({ type: "gallery_open" }),
      closeGallery: () => dispatch({ type: "gallery_close" }),
      setProductChoice: (value) => dispatch({ type: "product_choice", value }),
      startManual: () =>
        guard("session", async () => {
          await ensureSid();
          dispatch({ type: "manual" });
        }),
      extract,
      policyExtract,
      readDocuments,
      setStep: (step) => dispatch({ type: "step", step }),
      setForm: (update) => dispatch(typeof update === "function" ? { type: "form_update", fn: update } : { type: "form", form: update }),
      setSlotFiles: (slot, files) => dispatch({ type: "slot_files", slot, files }),
      policySave: (body) =>
        guard("facts", async () => {
          const r = await api.policyPut(requireSid(), body);
          dispatch({ type: "policy", policy: r.policy ?? null });
        }),
      policyRemove: () =>
        guard("facts", async () => {
          await api.policyDelete(requireSid());
          dispatch({ type: "policy", policy: null });
        }),
      saveFacts,
      saveAndCheck: async (body) => {
        const saved = await saveFacts(body);
        if (!saved.ok) return saved;
        return runCheck();
      },
      downloadLetter: () =>
        guard("letter", async () => {
          const blob = await api.letter(requireSid(), ref.current.lang);
          saveBlob(blob, "grievance-letter.pdf");
        }),
      deleteData: async () => {
        const id = ref.current.sid;
        dispatch({ type: "busy", busy: "delete" });
        try {
          if (id) await api.deleteSession(id);
        } catch {
          /* the session may already be gone; either way the client forgets it */
        }
        dispatch({ type: "busy", busy: null });
        dispatch({ type: "reset", view: "deleted" });
      },
      restart: () => dispatch({ type: "reset", view: "upload" }),
    };
  }, [guard, ensureSid, explainInto]);

  const activity = deriveActivity({
    view: state.view,
    busy: state.busy,
    slow: state.slow,
    lastError: state.lastError,
    pendingCount: pendingKeys(state.facts).length,
    productChosen: effectiveProduct(state) !== "",
  });

  const t = useCallback((key: Key) => translate(state.lang, state.helper, key), [state.lang, state.helper]);
  const value = useMemo(() => ({ state, actions, activity, t }), [state, actions, activity, t]);
  return <SessionContext.Provider value={value}>{children}</SessionContext.Provider>;
}

export function useSession(): Ctx {
  const c = useContext(SessionContext);
  if (!c) throw new Error("useSession must be used inside <SessionProvider>");
  return c;
}
