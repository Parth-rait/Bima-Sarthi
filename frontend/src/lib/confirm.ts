/**
 * Pure logic of the Confirm screen: what to show, what to send, and what still blocks the check.
 * Kept free of React so the gating rules can be unit-tested.
 */
import type { Fact, FactEdit, FactMap, FactsBody } from "../api";
import type { ProductLine } from "../i18n";
import type { Key } from "../i18n";
import { FALLBACK_LABELS } from "../i18n/factLabels";
import { REJECTION_GROUNDS } from "../i18n/labels";
import { isDeductionList, parseEdit, valText } from "./facts";

/** Absence/yes-no facts: the user must answer explicitly, never by default. */
export const BOOL_KEYS = [
  "fraud_alleged",
  "crc_approval_mentioned",
  "reasons_cite_terms",
  "continuity_confirmed",
  "cited_clause_found",
] as const;

/** Letter details: [fact key, i18n label key]. */
export const LETTER_FIELDS: ReadonlyArray<readonly [string, Key]> = [
  ["policyholder_name", "name"],
  ["policy_number", "policy"],
  ["claim_number", "claimno"],
  ["claim_amount_inr", "amount"],
  ["insurer_name", "insurer"],
  ["complaint_sent_date", "sentdate"],
];
const LETTER_KEYS = new Set(LETTER_FIELDS.map(([k]) => k));

/** Rejection grounds for which a continuity answer matters. */
export const CONT_GROUNDS = [
  "pre_existing_disease",
  "portability",
  "specific_waiting_period",
  "initial_waiting_period",
  "non_disclosure",
];
/** Dates the check may need that were not read from the documents. */
export const ADD_KEYS = ["claim_date", "admission_date", "inception_date", "policy_renewal_date"] as const;

export type YesNo = "yes" | "no" | "";
export type YesNoUnsure = "yes" | "no" | "unsure" | "";

export interface ConfirmForm {
  text: Record<string, string>;
  confirmed: Record<string, boolean>;
  bools: Record<string, YesNo>;
  ground: string;
  deductions: Record<string, YesNoUnsure[]>;
  letter: Record<string, string>;
  added: Record<string, string>;
  reply: string;
  cont: YesNoUnsure;
  /** facts the user removed (sent as {clear: true}); the rejection reason can never be cleared */
  cleared: Record<string, boolean>;
}

const PLACEHOLDER_GROUND: Fact = {
  key: "rejection_ground",
  label: FALLBACK_LABELS.rejection_ground,
  value: null,
  quote: null,
  page_no: null,
  confidence: "low",
  status: "needs_confirmation",
};

/** The extracted reason is free text from the document; only a listed ground can be sent. */
export const knownGround = (v: unknown): string =>
  typeof v === "string" && (REJECTION_GROUNDS as readonly string[]).includes(v) ? v : "";

export const isPending = (f: Fact | undefined): boolean => f?.status === "needs_confirmation";
export const isBoolFact = (k: string, f: Fact): boolean =>
  (BOOL_KEYS as readonly string[]).includes(k) || typeof f.value === "boolean";

/** The facts to list, pending first. The rejection reason is always listed. */
export function visibleFacts(facts: FactMap): Array<[string, Fact]> {
  const all: FactMap = { ...facts };
  if (!all.rejection_ground) all.rejection_ground = PLACEHOLDER_GROUND;
  const entries = Object.entries(all).filter(
    ([k]) => k !== "product_line" && k !== "continuity_confirmed" && !LETTER_KEYS.has(k),
  );
  return [...entries.filter(([, f]) => isPending(f)), ...entries.filter(([, f]) => !isPending(f))];
}

export function groundOf(facts: FactMap): string | null {
  const v = facts.rejection_ground?.value;
  return typeof v === "string" ? v : null;
}

/** Whether to show the continuity question (Yes / No / Not sure). */
export function needsContinuity(facts: FactMap): boolean {
  const g = groundOf(facts);
  return (g !== null && CONT_GROUNDS.includes(g)) || !!facts.ported_from_date || !!facts.renewal_gap_days || !!facts.continuity_confirmed;
}

export function initialForm(facts: FactMap): ConfirmForm {
  const form: ConfirmForm = {
    text: {},
    confirmed: {},
    bools: {},
    ground: "",
    deductions: {},
    letter: {},
    added: {},
    reply: "",
    cont: "",
    cleared: {},
  };
  for (const [k, f] of visibleFacts(facts)) {
    const pend = isPending(f);
    if (k === "rejection_ground") {
      form.ground = knownGround(f.value);
      form.confirmed[k] = !pend;
    } else if (isBoolFact(k, f)) {
      form.bools[k] = pend || typeof f.value !== "boolean" ? "" : f.value ? "yes" : "no";
    } else if (k === "deductions" && isDeductionList(f.value)) {
      form.deductions[k] = f.value.map((it) =>
        it.nonpayable_listed === true ? "yes" : it.nonpayable_listed === false ? "no" : "unsure",
      );
      form.confirmed[k] = !pend;
    } else {
      form.text[k] = valText(f.value);
      form.confirmed[k] = !pend;
    }
  }
  for (const [k] of LETTER_FIELDS) form.letter[k] = valText(facts[k]?.value);
  for (const k of ADD_KEYS) form.added[k] = "";
  const c = facts.continuity_confirmed;
  form.cont = c && typeof c.value === "boolean" && !isPending(c) ? (c.value ? "yes" : "no") : "";
  return form;
}

const keepOf = (f: Fact): boolean | null => (isPending(f) || typeof f.value !== "boolean" ? null : f.value);

function deductionsChanged(f: Fact, form: ConfirmForm, k: string): boolean {
  const items = f.value as Array<Record<string, unknown>>;
  const now = form.deductions[k] ?? [];
  return items.some((it, i) => {
    const before = it.nonpayable_listed === true ? "yes" : it.nonpayable_listed === false ? "no" : "unsure";
    return now[i] !== before;
  });
}

/** Whether the user has dealt with one pending fact (answered, confirmed, changed or removed it) in the current form. */
export function isResolved(k: string, f: Fact, form: ConfirmForm): boolean {
  if (!isPending(f)) return true;
  if (form.cleared[k] && k !== "rejection_ground") return true;
  if (k === "rejection_ground") {
    // a pre-filled reason still needs the user's tick (or a different choice)
    const original = knownGround(f.value);
    return !!form.ground && !(form.ground === original && !form.confirmed[k]);
  }
  if (isBoolFact(k, f)) return !!form.bools[k];
  if (k === "deductions" && isDeductionList(f.value)) return !!form.confirmed[k] || deductionsChanged(f, form, k);
  const changed = (form.text[k] ?? "") !== valText(f.value);
  const hasValue = (form.text[k] ?? "").trim() !== "";
  return hasValue && (changed || !!form.confirmed[k]);
}

/** The facts the user still has to answer or confirm before the check can run. */
export function unresolvedKeys(facts: FactMap, form: ConfirmForm): string[] {
  const out: string[] = [];
  for (const [k, f] of visibleFacts(facts)) {
    if (isPending(f) && !isResolved(k, f, form)) out.push(k);
  }
  const c = facts.continuity_confirmed;
  if (c && isPending(c) && !form.cont) out.push("continuity_confirmed");
  return out;
}

/** The PUT /facts body for this form. Unanswered tri-state continuity sends nothing. */
export function buildPayload(facts: FactMap, form: ConfirmForm, product: ProductLine): FactsBody {
  const payload: Record<string, FactEdit> = { product_line: { value: product } };
  for (const k of LETTER_KEYS) {
    const v = (form.letter[k] ?? "").trim();
    if (v) payload[k] = { value: v };
  }
  for (const [k, f] of visibleFacts(facts)) {
    const pend = isPending(f);
    if (form.cleared[k] && k !== "rejection_ground") {
      if (facts[k]) payload[k] = { clear: true };
      continue;
    }
    if (k === "rejection_ground") {
      if (form.ground && (form.ground !== knownGround(f.value) || pend)) payload[k] = { value: form.ground };
    } else if (isBoolFact(k, f)) {
      const ans = form.bools[k];
      if (ans && (pend || (ans === "yes") !== keepOf(f))) payload[k] = { value: ans };
    } else if (k === "deductions" && isDeductionList(f.value)) {
      const changed = deductionsChanged(f, form, k);
      if (changed || (pend && form.confirmed[k])) {
        payload[k] = {
          value: f.value.map((it, i) => ({
            ...it,
            nonpayable_listed: form.deductions[k]?.[i] === "yes" ? true : form.deductions[k]?.[i] === "no" ? false : null,
          })),
        };
      }
    } else {
      const txt = form.text[k] ?? "";
      if (txt !== valText(f.value)) payload[k] = { value: parseEdit(txt, f.value) };
      else if (form.confirmed[k] && pend) payload[k] = { confirm: true };
    }
  }
  for (const k of ADD_KEYS) {
    const v = (form.added[k] ?? "").trim();
    if (v && !facts[k]) payload[k] = { value: v };
  }
  if (form.cont === "yes" || form.cont === "no") payload.continuity_confirmed = { value: form.cont === "yes" };
  else if (form.cont === "unsure" && facts.continuity_confirmed) payload.continuity_confirmed = { clear: true };
  const body: FactsBody = { facts: payload };
  if (form.reply.trim()) body.insurer_reply_date = form.reply.trim();
  return body;
}

/**
 * Keep what the person has typed when the facts change under them (a save, a second reading): a fresh form from the new facts,
 * with the letter details, the missing dates, the reply date and an unsaved continuity answer carried over.
 */
export function rebaseForm(prev: ConfirmForm | null, facts: FactMap): ConfirmForm {
  const next = initialForm(facts);
  if (!prev) return next;
  for (const [k] of LETTER_FIELDS) if (!facts[k] && prev.letter[k]) next.letter[k] = prev.letter[k];
  for (const k of ADD_KEYS) next.added[k] = facts[k] ? "" : prev.added[k] ?? "";
  next.reply = prev.reply;
  if (!next.cont) next.cont = prev.cont;
  return next;
}
