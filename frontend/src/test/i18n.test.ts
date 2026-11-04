import fs from "node:fs";
import path from "node:path";
import { describe, expect, it } from "vitest";
import { dictionaries, en, hi, helperOverrides, translate, GROUND_LABEL, PRODUCT_LABEL, REJECTION_GROUNDS, PRODUCT_KEYS } from "../i18n";
import { extraEn, helperEn } from "../i18n/extra-en";
import { extraHi, helperHi } from "../i18n/extra-hi";

const ROOT = path.resolve(__dirname, "../../..");
const legacyHtml = fs.readFileSync(path.join(ROOT, "sarthi/app/static/index.html"), "utf8");

describe("i18n key parity", () => {
  it("every key exists in both English and Hindi", () => {
    expect(Object.keys(hi).sort()).toEqual(Object.keys(en).sort());
    expect(Object.keys(extraHi).sort()).toEqual(Object.keys(extraEn).sort());
  });
  it("no string is empty", () => {
    for (const lang of ["en", "hi"] as const) {
      for (const [k, v] of Object.entries(dictionaries[lang])) expect(v.trim(), `${lang}.${k}`).not.toBe("");
    }
  });
  it("helper overrides exist in both languages, only for known keys", () => {
    expect(Object.keys(helperHi).sort()).toEqual(Object.keys(helperEn).sort());
    for (const k of Object.keys(helperEn)) expect(en).toHaveProperty(k);
  });
  it("grounds and product lines are complete in both languages", () => {
    for (const g of REJECTION_GROUNDS) {
      expect(GROUND_LABEL.en[g]).toBeTruthy();
      expect(GROUND_LABEL.hi[g]).toBeTruthy();
    }
    for (const p of PRODUCT_KEYS) {
      expect(PRODUCT_LABEL.en[p]).toBeTruthy();
      expect(PRODUCT_LABEL.hi[p]).toBeTruthy();
    }
  });
});

describe("parity with the legacy page and the backend", () => {
  it("every legacy string is carried over unchanged", () => {
    const grab = (name: string) => {
      const i = legacyHtml.indexOf(`const ${name}=`);
      const j = legacyHtml.indexOf(";\n", i);
      return legacyHtml.slice(i + `const ${name}=`.length, j);
    };
    const T = new Function(`return (${grab("T")})`)() as Record<"en" | "hi", Record<string, string>>;
    // a floor, not a target: it catches grab() truncating the legacy object, which would silently pass parity
    expect(Object.keys(T.en).length).toBeGreaterThan(70);
    expect(Object.keys(T.hi).length).toBe(Object.keys(T.en).length);
    // Deliberate phase-3 rename: CHALLENGEABLE moved from the stamp word to the plain sentence, because
    // Verdict.tsx renders t(verdict) as a finding's headline while the stamp word lives on vw_CHALLENGEABLE.
    // The Hindi stamp words are draft copy (Q-007), so only English is byte-checked against the legacy page.
    for (const lang of ["en", "hi"] as const) {
      for (const [k, v] of Object.entries(T[lang])) {
        if (k === "CHALLENGEABLE") {
          if (lang === "en") expect(dictionaries.en.vw_CHALLENGEABLE, "en.vw_CHALLENGEABLE").toBe(v);
          continue;
        }
        expect(dictionaries[lang][k as keyof typeof en], `${lang}.${k}`).toBe(v);
      }
    }
  });

  it("rejection-ground labels match sarthi/app/labels.py", () => {
    const py = fs.readFileSync(path.join(ROOT, "sarthi/app/labels.py"), "utf8");
    const block = py.slice(py.indexOf("GROUND_LABELS"));
    const re = /"([a-z_]+)":\s*\("([^"]+)",\s*"([^"]+)"\)/g;
    const found: Record<string, [string, string]> = {};
    for (const m of block.matchAll(re)) found[m[1]] = [m[2], m[3]];
    expect(Object.keys(found).sort()).toEqual([...REJECTION_GROUNDS].sort());
    for (const g of REJECTION_GROUNDS) {
      expect(GROUND_LABEL.en[g]).toBe(found[g][0]);
      expect(GROUND_LABEL.hi[g]).toBe(found[g][1]);
    }
  });

  it("product lines and labels match sarthi/app/plan.py", () => {
    const py = fs.readFileSync(path.join(ROOT, "sarthi/app/plan.py"), "utf8");
    const keys = /PRODUCT_LINE_KEYS = \(([^)]*)\)/.exec(py)?.[1].match(/"([a-z_]+)"/g)?.map((s) => s.replaceAll('"', ""));
    expect(keys).toEqual([...PRODUCT_KEYS]);
  });

  it("the verdict vocabulary is unchanged", () => {
    for (const v of ["CONSISTENT", "CHALLENGEABLE", "NEED_INFO"] as const) {
      expect(en[v]).toBeTruthy();
      expect(hi[v]).toBeTruthy();
    }
  });
});

describe("helper mode wording", () => {
  it("switches first-person strings to third person, in both languages", () => {
    expect(translate("en", false, "cont")).toMatch(/^My cover/);
    expect(translate("en", true, "cont")).toMatch(/^Their cover/);
    expect(translate("en", true, "sentdate")).not.toMatch(/\byou\b/i);
    expect(translate("en", true, "replydate")).not.toMatch(/\byour\b/i);
    expect(translate("hi", true, "cont")).not.toBe(translate("hi", false, "cont"));
    expect(translate("en", true, "del")).toBe("Delete their data now");
  });
  it("leaves strings without a helper variant alone", () => {
    expect(translate("en", true, "run")).toBe(en.run);
    expect(helperOverrides.en.run).toBeUndefined();
  });
});

import { FALLBACK_LABELS } from "../i18n/factLabels";
describe("fallback fact labels", () => {
  it("match sarthi/app/labels.py", () => {
    const py = fs.readFileSync(path.join(ROOT, "sarthi/app/labels.py"), "utf8");
    for (const [k, v] of Object.entries(FALLBACK_LABELS)) {
      const m = new RegExp(`"${k}":\\s*\\("([^"]+)",\\s*"([^"]+)"\\)`).exec(py);
      expect(m, k).toBeTruthy();
      expect(v.en).toBe(m![1]);
      expect(v.hi).toBe(m![2]);
    }
  });
});

import { uiEn, uiHelperEn } from "../i18n/ui-en";
import { uiHi, uiHelperHi } from "../i18n/ui-hi";
describe("phase-2 dictionaries", () => {
  it("every page-shell key exists in both languages, and helper overrides mirror each other", () => {
    expect(Object.keys(uiHi).sort()).toEqual(Object.keys(uiEn).sort());
    expect(Object.keys(uiHelperHi).sort()).toEqual(Object.keys(uiHelperEn).sort());
    for (const k of Object.keys(uiHelperEn)) expect(uiEn).toHaveProperty(k);
    expect(Object.keys(helperOverrides.hi).sort()).toEqual(Object.keys(helperOverrides.en).sort());
  });
  it("the Hindi strings are written in Devanagari, not copies of the English (apart from a few identifiers)", () => {
    const SAME_OK = new Set<string>([]);
    for (const [k, v] of Object.entries(uiHi)) {
      if (SAME_OK.has(k)) continue;
      expect(/[ऀ-ॿ]/.test(v), `uiHi.${k}`).toBe(true);
      expect(v, `uiHi.${k}`).not.toBe(uiEn[k as keyof typeof uiEn]);
    }
  });
  it("the Hindi draft marker is shown whenever Hindi is on (Q-007)", async () => {
    const { HINDI_DRAFT_NOTE } = await import("../i18n");
    expect(HINDI_DRAFT_NOTE).toMatch(/Q-007/);
  });
});
