import type { FactMap, FactValueData, LabelMap, PolicyView } from "../api";
import { GROUND_LABEL, type Lang } from "../i18n";
import { FALLBACK_LABELS } from "../i18n/factLabels";

export interface LabelSources {
  facts?: FactMap;
  labels?: LabelMap;
  policy?: PolicyView | null;
}

/** Plain-language name for a fact/term key. Falls back to the key with spaces, never invents text. */
export function labelOf(key: string, lang: Lang, src: LabelSources = {}): string {
  const l =
    src.facts?.[key]?.label ??
    (src.labels && Object.hasOwn(src.labels, key) ? src.labels[key] : undefined) ??
    src.policy?.terms.find((x) => x.key === key)?.label ??
    FALLBACK_LABELS[key];
  if (l) return (lang === "hi" ? l.hi : l.en) || l.en;
  return key.replaceAll("_", " ");
}

/** Text for an input box: scalars as-is, lists comma-joined (the server splits on commas), objects as JSON. */
export function valText(v: unknown): string {
  if (v == null) return "";
  if (typeof v === "boolean") return v ? "yes" : "no";
  if (typeof v === "object") {
    if (Array.isArray(v) && v.every((x) => typeof x !== "object")) return v.join(",");
    return JSON.stringify(v);
  }
  return String(v);
}

type Yn = (b: boolean) => string;

/** Human-readable display of a fact value (legacy showVal). */
export function showVal(
  v: unknown,
  key: string,
  lang: Lang,
  yn: Yn,
  label: (k: string) => string,
): string {
  if (v == null) return "";
  if (typeof v === "boolean") return yn(v);
  if (typeof v === "string") {
    // The rule engine sends dates as ISO; Indian users read DD/MM/YYYY (PRODUCT.md).
    const iso = /^(\d{4})-(\d{2})-(\d{2})(?:T(\d{2}):(\d{2}))?/.exec(v);
    if (iso && /^\d{4}-\d{2}-\d{2}(?:T[\d:.]+)?$/.test(v)) return `${iso[3]}/${iso[2]}/${iso[1]}${iso[4] ? ` ${iso[4]}:${iso[5]}` : ""}`;
    return key === "rejection_ground" && Object.hasOwn(GROUND_LABEL[lang], v)
      ? GROUND_LABEL[lang][v as keyof (typeof GROUND_LABEL)["en"]]
      : v;
  }
  if (Array.isArray(v)) return v.map((x) => showVal(x, key, lang, yn, label)).join("; ");
  if (typeof v === "object") {
    return Object.entries(v as Record<string, unknown>)
      .filter(([, x]) => x != null)
      .map(([k, x]) => `${label(k)}: ${showVal(x, k, lang, yn, label)}`)
      .join(", ");
  }
  return String(v);
}

export function parseEdit(text: string, orig: FactValueData): unknown {
  const txt = text.trim();
  if (Array.isArray(orig) && orig.length && typeof orig[0] === "object") {
    try {
      return JSON.parse(txt);
    } catch {
      return txt;
    }
  }
  return txt;
}

export function isDeductionList(v: unknown): v is Array<Record<string, unknown>> {
  return Array.isArray(v) && v.length > 0 && v.every((x) => x && typeof x === "object");
}

function parseLooseDate(v: unknown): Date | null {
  if (typeof v !== "string") return null;
  let m = /^(\d{4})-(\d{2})-(\d{2})/.exec(v);
  if (m) return new Date(+m[1], +m[2] - 1, +m[3]);
  m = /^(\d{1,2})\/(\d{1,2})\/(\d{4})/.exec(v);
  if (m) return new Date(+m[3], +m[2] - 1, +m[1]);
  return null;
}

/** Whole years between two dates the app holds as ISO or DD/MM/YYYY strings; null when either is missing. */
export function yearsBetween(a: unknown, b: unknown): number | null {
  const da = parseLooseDate(a);
  const db = parseLooseDate(b);
  if (!da || !db) return null;
  const years = (db.getTime() - da.getTime()) / (365.25 * 864e5);
  return years >= 0 ? Math.round(years * 10) / 10 : null;
}

/** How old the policy was when the claim happened, for placing the user's case on the case-terrain chart. */
export function policyYearsAtClaim(facts: FactMap): number | null {
  return yearsBetween(facts.inception_date?.value, facts.admission_date?.value ?? facts.claim_date?.value);
}
