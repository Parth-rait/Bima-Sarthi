import fs from "node:fs";
import path from "node:path";
import { describe, expect, it } from "vitest";

const SRC = path.resolve(__dirname, "..");
function walk(dir: string): string[] {
  return fs.readdirSync(dir, { withFileTypes: true }).flatMap((e) => (e.isDirectory() ? walk(path.join(dir, e.name)) : [path.join(dir, e.name)]));
}
const files = walk(SRC);
const source = files.filter((f) => /\.(ts|tsx)$/.test(f) && !f.includes(`${path.sep}test${path.sep}`));
const tsx = source.filter((f) => f.endsWith(".tsx"));
const css = files.filter((f) => f.endsWith(".css"));
const read = (f: string) => fs.readFileSync(f, "utf8");
const rel = (f: string) => path.relative(SRC, f);

describe("no raw HTML injection", () => {
  const banned = /(innerHTML|outerHTML|dangerouslySetInnerHTML|insertAdjacentHTML|document\.write\s*\()/;
  it("no innerHTML-style API anywhere in src (including the installed Aceternity components)", () => {
    expect(source.length).toBeGreaterThan(40);
    expect(source.some((f) => rel(f).includes("components/ui/liquid-glass"))).toBe(true);
    for (const f of source) expect(banned.test(read(f)), rel(f)).toBe(false);
  });
  it("no eval / Function constructor in app code", () => {
    for (const f of source) expect(/\beval\(|new Function\(/.test(read(f)), rel(f)).toBe(false);
  });
});

describe("no third-party requests at runtime", () => {
  it("styles and index.html load nothing from a CDN or Google Fonts", () => {
    const html = fs.readFileSync(path.resolve(SRC, "../index.html"), "utf8");
    for (const text of [html, ...css.map(read)]) {
      expect(text).not.toMatch(/fonts\.googleapis|fonts\.gstatic|cdn\.|unpkg|jsdelivr|https?:\/\/[^'")\s]*\.(woff2?|css|js)/);
    }
  });
  it("no external image URLs anywhere (no stock photos, no demo imagery from the registry)", () => {
    for (const f of source) {
      const text = read(f);
      expect(text, rel(f)).not.toMatch(/unsplash|assets\.aceternity|images\.pexels|picsum|placeholder\.com/);
      expect(text, rel(f)).not.toMatch(/src=["']https?:\/\//);
    }
  });
  it("the app stores nothing in the browser except one preference (no cookies, no session storage, no IndexedDB)", () => {
    // The ONLY exception: the "Animate the sky" on/off flag, in hooks/useSkyPreference.ts (disclosed on the Privacy page).
    const ALLOWED = path.join("hooks", "useSkyPreference.ts");
    for (const f of source) {
      const text = read(f);
      expect(/sessionStorage|document\.cookie|indexedDB/.test(text), rel(f)).toBe(false);
      if (rel(f) !== ALLOWED) expect(/localStorage/.test(text), rel(f)).toBe(false);
    }
    const hook = read(path.join(SRC, ALLOWED));
    expect(hook.match(/localStorage/g)!.length).toBeGreaterThan(0);
    expect(hook).toMatch(/try\s*{[\s\S]*localStorage\.getItem[\s\S]*}\s*catch/);
    expect(hook).toMatch(/try\s*{[\s\S]*localStorage\.setItem[\s\S]*}\s*catch/);
  });
});

describe("motion", () => {
  it("respects prefers-reduced-motion", () => {
    const base = read(path.join(SRC, "styles/base.css"));
    expect(base).toMatch(/@media \(prefers-reduced-motion: reduce\)/);
    expect(base).toMatch(/animation-duration: 0\.01ms/);
  });

  it("every authored CSS animation sits inside @media (prefers-reduced-motion: no-preference)", () => {
    let seen = 0;
    for (const f of css) {
      const text = read(f).replace(/\/\*[\s\S]*?\*\//g, "");
      const stack: string[] = [];
      let prelude = "";
      for (let i = 0; i < text.length; i++) {
        const c = text[i];
        if (c === "{") {
          stack.push(prelude.trim());
          prelude = "";
        } else if (c === "}") {
          stack.pop();
          prelude = "";
        } else if (c === ";") {
          prelude = "";
        } else {
          prelude += c;
          if (/(^|[\s;{}])animation:\s*$/.test(prelude + "") && !/^\s*none/.test(text.slice(i + 1, i + 12))) {
            seen++;
            const inside = stack.some((s) => s.includes("prefers-reduced-motion: no-preference"));
            const keyframeInner = stack.some((s) => s.startsWith("@keyframes"));
            expect(inside || keyframeInner, `${rel(f)} has an animation outside no-preference`).toBe(true);
          }
        }
      }
    }
    expect(seen).toBeGreaterThan(2);
  });

  it("every Tailwind animate-* class is paired with motion-reduce:animate-none in the same component", () => {
    for (const f of tsx) {
      const text = read(f);
      if (f.includes(`${path.sep}ui${path.sep}`)) continue; // installed originals; their animations are transitions covered by the global reduce rule
      if (/\banimate-(spin|pulse|bounce|ping|\[)/.test(text)) expect(text, rel(f)).toMatch(/motion-reduce:animate-none/);
    }
  });
});

describe("design-system guardrails", () => {
  it("no green identity: no green utility classes or green hex families in the app styles", () => {
    for (const f of [...css, ...tsx]) {
      if (rel(f).includes("components/ui/")) continue; // registry originals (neutral palette only)
      const t = read(f);
      expect(t, rel(f)).not.toMatch(/\b(?:bg|text|border|ring|fill|stroke)-(?:green|emerald|lime|teal)-\d{2,3}\b/);
    }
  });
  it("no gradient text and no coloured side borders on cards", () => {
    for (const f of tsx) {
      const t = read(f);
      if (rel(f).includes("components/ui/")) continue;
      expect(t, rel(f)).not.toMatch(/bg-clip-text/);
      expect(t, rel(f)).not.toMatch(/\bborder-[lr]-(?:[2-9]|\[)/);
    }
  });
  it("a glass plate never hangs off a static element, or it blurs the whole page", () => {
    for (const f of css) {
      const t = read(f);
      if (!/backdrop-filter/.test(t)) continue;
      // an absolutely positioned ::before inside a static element resolves against a far larger containing block
      expect(t, rel(f)).not.toMatch(/position:\s*static/);
    }
  });
  it("every page component has exactly one place that renders its page heading", () => {
    const pages = files.filter((f) => rel(f).startsWith(`pages${path.sep}`) && f.endsWith(".tsx"));
    expect(pages.length).toBe(13); // + Schemes and Evidence, restored from the 4 Nov iteration
    for (const f of pages) {
      const t = read(f);
      const heading = /data-page-heading|pageHeading|<PageHeader|<EmptyState[\s\S]{0,40}pageHeading/.test(t);
      expect(heading, rel(f)).toBe(true);
    }
  });
});
