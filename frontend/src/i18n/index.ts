import { legacyEn } from "./legacy-en";
import { legacyHi } from "./legacy-hi";
import { extraEn, helperEn } from "./extra-en";
import { extraHi, helperHi } from "./extra-hi";
import { uiEn, uiHelperEn } from "./ui-en";
import { uiHi, uiHelperHi } from "./ui-hi";

export type Lang = "en" | "hi";

export const en = { ...legacyEn, ...extraEn, ...uiEn } as const;
// DRAFT: Hindi dictionary pending human review (Q-007).
export const hi = { ...legacyHi, ...extraHi, ...uiHi } as const;
export type Key = keyof typeof en;

export const dictionaries: Record<Lang, Record<Key, string>> = { en, hi };
export const helperOverrides: Record<Lang, Partial<Record<Key, string>>> = { en: { ...helperEn, ...uiHelperEn }, hi: { ...helperHi, ...uiHelperHi } };

/** Look a string up. Helper mode swaps in third-person wording where one exists. */
export function translate(lang: Lang, helper: boolean, key: Key): string {
  if (helper) {
    const h = helperOverrides[lang][key];
    if (h !== undefined) return h;
  }
  return dictionaries[lang][key] ?? dictionaries.en[key] ?? key;
}

/** Pick the active language out of a {en, hi} object the API returns. */
export function pick(obj: { en: string; hi?: string } | null | undefined, lang: Lang): string {
  if (!obj) return "";
  return (lang === "hi" ? obj.hi : obj.en) || obj.en || "";
}

export const INDEPENDENT_NOTICE =
  "Bima Sarthi is an independent project, not affiliated with IRDAI, LIC or any insurer.";
export const RESULT_NOTICE = "This is a rules check, not legal or medical advice.";
export const ATTRIBUTION = "powered by IKanoon";
// Verbatim from the legacy page (DRAFT_HI). Shown whenever Hindi is selected.
export const HINDI_DRAFT_NOTE = "हिन्दी पाठ अभी मसौदा है और समीक्षा बाकी है (Q-007)। Hindi text is a draft pending review.";
export { REJECTION_GROUNDS, GROUND_LABEL, PRODUCT_KEYS, PRODUCT_LABEL } from "./labels";
export type { RejectionGround, ProductLine } from "./labels";
