import type { Bilingual, CheckResponse, ExplainResponse, Fact, FactMap, LabelMap, PolicyView, Verdict } from "../api";
import type { Lang, ProductLine } from "../i18n";
import type { BusyKind, ViewName } from "./activity";
import type { ApiErrorKind } from "../api";
import { rebaseForm, type ConfirmForm } from "../lib/confirm";

/** The five steps of the claim workspace (src/workspace). `view` stays the coarse state the activity signal reads. */
export type Step = 1 | 2 | 3 | 4 | 5;
export const STEPS: readonly Step[] = [1, 2, 3, 4, 5];
export const viewForStep = (step: Step): ViewName => (step === 1 ? "upload" : step === 5 ? "result" : "confirm");
export const stepForView = (view: ViewName): Step => (view === "result" ? 5 : view === "confirm" ? 2 : 1);

export type SlotId = "letter" | "policy";
/** empty: nothing chosen; ready: chosen, not sent; uploading: bytes on the wire; reading: sent, the reader is working; done; failed */
export type SlotStatus = "empty" | "ready" | "uploading" | "reading" | "done" | "failed";
export interface SlotState {
  files: File[];
  status: SlotStatus;
  /** 0..1 share of the request body the browser has sent. null = not known (never invented). */
  progress: number | null;
  error: { kind: ApiErrorKind; message: string } | null;
  /** names, page count and bytes of what the server has already read for this slot */
  readNames: string[];
  readPages: number;
  readBytes: number;
}
export const emptySlot = (): SlotState => ({ files: [], status: "empty", progress: null, error: null, readNames: [], readPages: 0, readBytes: 0 });

export interface ResultState {
  supported: boolean;
  productLine: string;
  findings: CheckResponse["findings"];
  deadlines: CheckResponse["deadlines"];
  plan: CheckResponse["plan"];
  checklist: CheckResponse["request_checklist"];
  /** The written explanation; empty until /explain returns. */
  text: string;
  explainFailed: boolean;
}

export interface SessionState {
  lang: Lang;
  helper: boolean;
  view: ViewName;
  /** the workspace step on screen, and the furthest step that has been legitimately reached (the stepper lets you revisit up to it) */
  step: Step;
  reached: Step;
  galleryReturn: ViewName;
  /** the two upload slots of step 1 */
  slots: Record<SlotId, SlotState>;
  /** everything typed in steps 2 and 3, kept in memory while moving between steps; null before the first reading */
  form: ConfirmForm | null;
  sid: string | null;
  facts: FactMap;
  pages: number;
  readerBackend: string | null;
  productHint: string | null;
  /** null = untouched (the server hint may be pre-selected); "" = the user explicitly cleared it */
  productChoice: ProductLine | "" | null;
  policy: PolicyView | null;
  result: ResultState | null;
  labels: LabelMap;
  busy: BusyKind | null;
  slow: boolean;
  lastError: ApiErrorKind | null;
  expired: boolean;
  /** Random id of the current in-memory report (/results/:id). Not the server session id. */
  reportId: string | null;
  /** Action-plan checklist ticks, kept for this session only. */
  checkedItems: Record<string, boolean>;
}

export function initialState(partial: Partial<SessionState> = {}): SessionState {
  const view = partial.view ?? "upload";
  const step = partial.step ?? stepForView(view);
  const defaults: SessionState = {
    lang: "en",
    helper: false,
    view,
    step,
    reached: step,
    slots: { letter: emptySlot(), policy: emptySlot() },
    form: null,
    galleryReturn: "upload",
    sid: null,
    facts: {},
    pages: 0,
    readerBackend: null,
    productHint: null,
    productChoice: null,
    policy: null,
    result: null,
    labels: {},
    busy: null,
    slow: false,
    lastError: null,
    expired: false,
    reportId: null,
    checkedItems: {},
  };
  return { ...defaults, ...partial, view, step };
}

export type Action =
  | { type: "lang"; lang: Lang }
  | { type: "helper"; helper: boolean }
  | { type: "view"; view: ViewName }
  | { type: "step"; step: Step }
  | { type: "form"; form: ConfirmForm }
  | { type: "form_update"; fn: (f: ConfirmForm) => ConfirmForm }
  | { type: "slot_files"; slot: SlotId; files: File[] }
  | { type: "slot"; slot: SlotId; patch: Partial<SlotState> }
  | { type: "gallery_open" }
  | { type: "gallery_close" }
  | { type: "sid"; sid: string }
  | { type: "busy"; busy: BusyKind | null }
  | { type: "slow" }
  | { type: "error"; kind: ApiErrorKind }
  | { type: "ok" }
  | { type: "expired" }
  | { type: "facts"; facts: FactMap }
  | { type: "extracted"; facts: FactMap; pages: number; backend: string | null; hint: string | null; advance?: boolean }
  | { type: "manual" }
  | { type: "product_choice"; value: ProductLine | "" | null }
  | { type: "policy"; policy: PolicyView | null }
  | { type: "checked"; check: CheckResponse; reportId: string }
  | { type: "toggle_item"; id: string }
  | { type: "explained"; ex: ExplainResponse }
  | { type: "explain_failed" }
  | { type: "reset"; view: ViewName };

export function reducer(s: SessionState, a: Action): SessionState {
  switch (a.type) {
    case "lang":
      return { ...s, lang: a.lang };
    case "helper":
      return { ...s, helper: a.helper };
    case "view":
      return { ...s, view: a.view };
    case "gallery_open":
      return { ...s, galleryReturn: s.view === "gallery" ? s.galleryReturn : s.view, view: "gallery" };
    case "gallery_close":
      return { ...s, view: s.galleryReturn };
    case "sid":
      return { ...s, sid: a.sid };
    case "busy":
      return { ...s, busy: a.busy, slow: false };
    case "slow":
      return s.busy ? { ...s, slow: true } : s;
    case "error":
      return { ...s, lastError: a.kind };
    case "ok":
      return s.lastError === null ? s : { ...s, lastError: null };
    case "expired":
      return { ...s, sid: null, expired: true, lastError: "expired" };
    case "step": {
      const reached = a.step > s.reached ? a.step : s.reached;
      return { ...s, step: a.step, reached, view: viewForStep(a.step) };
    }
    case "form":
      return { ...s, form: a.form };
    case "form_update":
      return { ...s, form: a.fn(s.form ?? rebaseForm(null, s.facts)) };
    case "slot_files": {
      const slot = s.slots[a.slot];
      const status: SlotStatus = a.files.length ? "ready" : slot.readNames.length ? "done" : "empty";
      return { ...s, slots: { ...s.slots, [a.slot]: { ...slot, files: a.files, status, progress: null, error: null } } };
    }
    case "slot":
      return { ...s, slots: { ...s.slots, [a.slot]: { ...s.slots[a.slot], ...a.patch } } };
    case "facts":
      return { ...s, facts: a.facts, form: rebaseForm(s.form, a.facts) };
    case "extracted": {
      const advance = a.advance !== false;
      return {
        ...s,
        facts: a.facts,
        form: rebaseForm(s.form, a.facts),
        pages: a.pages,
        readerBackend: a.backend,
        productHint: a.hint,
        result: null,
        reportId: null,
        checkedItems: {},
        step: advance ? 2 : s.step,
        reached: 2,
        view: advance ? "confirm" : s.view,
        lastError: null,
      };
    }
    case "manual":
      return { ...s, facts: {}, form: rebaseForm(null, {}), pages: 0, productHint: null, result: null, reportId: null, checkedItems: {}, step: 2, reached: 2, view: "confirm", lastError: null };
    case "product_choice":
      return { ...s, productChoice: a.value };
    case "policy":
      return { ...s, policy: a.policy };
    case "checked":
      return {
        ...s,
        view: "result",
        step: 5,
        reached: 5,
        // a re-check of the same claim (e.g. after adding a date) keeps the report id and the ticks
        reportId: s.reportId ?? a.reportId,
        labels: { ...s.labels, ...a.check.labels },
        readerBackend: a.check.reader_backend || s.readerBackend,
        result: {
          supported: a.check.supported !== false,
          productLine: a.check.product_line,
          findings: a.check.findings,
          deadlines: a.check.deadlines,
          plan: a.check.plan ?? null,
          checklist: a.check.request_checklist ?? null,
          text: "",
          explainFailed: false,
        },
        lastError: null,
      };
    case "toggle_item":
      return { ...s, checkedItems: { ...s.checkedItems, [a.id]: !s.checkedItems[a.id] } };
    case "explained":
      return s.result
        ? {
            ...s,
            labels: { ...s.labels, ...a.ex.labels },
            readerBackend: a.ex.reader_backend || s.readerBackend,
            result: {
              ...s.result,
              text: a.ex.text || "",
              findings: a.ex.findings || s.result.findings,
              deadlines: a.ex.deadlines || s.result.deadlines,
              plan: a.ex.plan || s.result.plan,
              checklist: a.ex.request_checklist ?? s.result.checklist,
              explainFailed: false,
            },
          }
        : s;
    case "explain_failed":
      return s.result ? { ...s, result: { ...s.result, text: "", explainFailed: true } } : s;
    case "reset":
      return initialState({ lang: s.lang, helper: s.helper, view: a.view, step: 1, reached: 1 });
  }
}

export function pendingKeys(facts: FactMap): string[] {
  const keys = Object.entries(facts)
    .filter(([k, f]) => k !== "product_line" && f.status === "needs_confirmation")
    .map(([k]) => k);
  const g = facts.rejection_ground;
  if ((!g || g.value == null || g.value === "") && !keys.includes("rejection_ground")) keys.unshift("rejection_ground");
  return keys;
}

export type { Bilingual, Fact, Verdict };

import { PRODUCT_KEYS } from "../i18n/labels";

/** The type of insurance currently selected: the user's pick, else a stored value, else the server hint. */
export function effectiveProduct(s: Pick<SessionState, "productChoice" | "facts" | "productHint">): ProductLine | "" {
  const valid = (v: unknown): v is ProductLine => typeof v === "string" && (PRODUCT_KEYS as readonly string[]).includes(v);
  if (s.productChoice !== null) return s.productChoice;
  const stored = s.facts.product_line?.value;
  if (valid(stored)) return stored;
  return valid(s.productHint) ? s.productHint : "";
}
