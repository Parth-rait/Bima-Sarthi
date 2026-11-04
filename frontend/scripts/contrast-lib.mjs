// WCAG 2.x contrast math + the list of text/background pairs the design ships.
// Used by `npm run contrast` and by src/test/contrast.test.ts, so DESIGN.md's table can never drift.
import fs from "node:fs";
import path from "node:path";
import { fileURLToPath } from "node:url";

const here = path.dirname(fileURLToPath(import.meta.url));
export const TOKENS_CSS = path.join(here, "..", "src", "styles", "tokens.css");

export function readTokens(file = TOKENS_CSS) {
  const css = fs.readFileSync(file, "utf8");
  const raw = {};
  for (const m of css.matchAll(/--([a-z0-9-]+):\s*([^;]+);/g)) raw[m[1]] = m[2].trim();
  const resolve = (name, depth = 0) => {
    const v = raw[name];
    if (v === undefined) throw new Error(`token --${name} not found`);
    const ref = v.match(/^var\(--([a-z0-9-]+)\)$/);
    if (ref && depth < 8) return resolve(ref[1], depth + 1);
    return v;
  };
  return { raw, resolve };
}

function lum(hex) {
  const c = [1, 3, 5]
    .map((i) => parseInt(hex.slice(i, i + 2), 16) / 255)
    .map((v) => (v <= 0.03928 ? v / 12.92 : ((v + 0.055) / 1.055) ** 2.4));
  return 0.2126 * c[0] + 0.7152 * c[1] + 0.0722 * c[2];
}
export function ratio(a, b) {
  const [hi, lo] = [lum(a), lum(b)].sort((x, y) => y - x);
  return (hi + 0.05) / (lo + 0.05);
}

// Atmosphere values (src/design/atmosphere.ts) are read from the source file so a tuned colour is re-checked automatically.
export const ATMOSPHERE_TS = path.join(here, "..", "src", "design", "atmosphere.ts");
export function readAtmosphere(file = ATMOSPHERE_TS) {
  const ts = fs.readFileSync(file, "utf8");
  const hex = (key) => {
    const m = ts.match(new RegExp(`${key}:\\s*"(#[0-9a-fA-F]{6})"`));
    if (!m) throw new Error(`atmosphere.ts: ${key} not found`);
    return m[1].toLowerCase();
  };
  const num = (key) => {
    const m = ts.match(new RegExp(`${key}:\\s*([0-9.]+)`));
    if (!m) throw new Error(`atmosphere.ts: ${key} not found`);
    return Number(m[1]);
  };
  return {
    cloud: hex("cloudColor"),
    skyTop: hex("skyTopColor"),
    skyBottom: hex("skyBottomColor"),
    scrimAlpha: num("alpha"),
    navAlpha: num("navAlpha"),
    lampBg: hex("background"),
    lampGlow: hex("glow"),
    lampGlowOpacity: num("glowOpacity"),
  };
}

const toRgb = (h) => [1, 3, 5].map((i) => parseInt(h.slice(i, i + 2), 16));
const toHex = (c) => "#" + c.map((v) => Math.max(0, Math.min(255, Math.round(v))).toString(16).padStart(2, "0")).join("");
function mix(top, bottom, a) {
  const t = toRgb(top);
  const b = toRgb(bottom);
  return toHex(t.map((v, i) => v * a + b[i] * (1 - a)));
}

/** The darkest colour the cloud shader can paint (cloud shadow, the same arithmetic as the fragment shader; rim light and sun glow only lighten). */
export function darkestSky(a = readAtmosphere()) {
  const cloud = toRgb(a.cloud);
  const lit = toHex(cloud.map((v) => Math.min(255, v * 1.04)));
  const candidates = [a.skyTop, a.skyBottom];
  for (const sky of [a.skyTop, a.skyBottom]) {
    const shadow = mix(sky, toHex(cloud.map((v) => v * 0.6)), 0.38); // mix(cloud*0.60, sky, 0.38)
    candidates.push(mix(shadow, lit, 0.85)); // mix(lit, shadow, occlusion 1.0 * 0.85)
  }
  return candidates.sort((x, y) => lum(x) - lum(y))[0];
}

// [foreground, background, minimum ratio, where it is used]. A colour is a token name, {hex}, or {mix:[top, bottom, alpha]}
// (a translucent top over a bottom; top/bottom may themselves be token names or {hex}).
// 4.5 = normal text, 3 = large text or non-text UI (borders, focus rings, icons).
const TEXT = [
  // ink on every surface it sits on
  ["color-ink", "color-ivory", 4.5, "Body text and headings on the page"],
  ["color-ink", "color-peach", 4.5, "Text on a peach band"],
  ["color-ink", "color-paper", 4.5, "Text on a card, typed input text"],
  ["color-ink", "color-peach-deep", 4.5, "Hover on peach (accordion header, secondary button)"],
  ["color-ink", "color-sky-pale", 4.5, "Text on the sky band (pale blue end)"],
  ["color-ink", "color-sky-blue", 4.5, "Text on the sky band (deepest blue)"],
  ["color-ink", "color-lavender", 4.5, "Text on the sky band's lavender breath"],
  ["color-ink", "color-apricot", 4.5, "Primary button on hover"],
  ["color-ink", "color-apricot-soft", 4.5, "Primary button pressed; selected text"],
  ["color-ink", "color-on-ink", 4.5, "Button on the ink band (ivory fill)"],
  // secondary text
  ["color-ink-soft", "color-ivory", 4.5, "Secondary text on the page"],
  ["color-ink-soft", "color-peach", 4.5, "Secondary text on a peach band"],
  ["color-ink-soft", "color-paper", 4.5, "Hints, placeholders, captions on a card or field"],
  ["color-ink-soft", "color-sky-pale", 4.5, "Secondary text on the sky band"],
  // on ink
  ["color-on-ink", "color-ink", 4.5, "Text on the ink band; primary button label"],
  ["color-on-ink-soft", "color-ink", 4.5, "Secondary text on the ink band"],
  ["color-on-ink", "color-ink-raised", 4.5, "Text on a raised ink surface"],
  ["color-on-ink-soft", "color-ink-raised", 4.5, "Secondary text on a raised ink surface"],
  // states and verdicts (word + shape + sentence always accompany them)
  ["color-terracotta-ink", "color-ivory", 4.5, "Field error text on the page"],
  ["color-terracotta-ink", "color-paper", 4.5, "Field error text on a card"],
  ["color-terracotta-ink", "color-peach", 4.5, "Error text on a peach band"],
  ["color-terracotta-ink", "color-terracotta-wash", 4.5, "CHALLENGEABLE stamp; error box"],
  ["color-amber-ink", "color-amber-wash", 4.5, "NEED_INFO stamp; Please-confirm tag"],
  ["color-amber-ink", "color-ivory", 4.5, "Warm tag text on the page"],
  ["color-sage-ink", "color-sage-wash", 4.5, "CONSISTENT stamp"],
  ["color-ink", "color-terracotta-wash", 4.5, "Body text inside an error box"],
  // the two glass plates (the sticky stepper, the result summary): text is supposed to sit on the solid plate
  // in front, but the blur is checked to carry ink on its own anyway, over both bands it is ever placed on.
  ["color-ink", { mix: ["color-ivory", "color-peach", 0.74] }, 4.5, "Ink on the glass plate over a peach band"],
  ["color-ink", { mix: ["color-ivory", "color-paper", 0.74] }, 4.5, "Ink on the glass plate over the paper sheet"],
  ["color-ink-soft", { mix: ["color-ivory", "color-paper", 0.74] }, 4.5, "Secondary ink on the glass plate over the paper sheet"],
  // non-text (3:1)
  ["color-line-strong", "color-ivory", 3, "Control borders on the page"],
  ["color-line-strong", "color-paper", 3, "Input borders on a card"],
  ["color-line-strong", "color-peach", 3, "Control borders on a peach band"],
  ["color-focus-ring", "color-ivory", 3, "Focus ring on the page"],
  ["color-focus-ring", "color-paper", 3, "Focus ring on a card"],
  ["color-focus-ring", "color-peach", 3, "Focus ring on a peach band"],
  ["color-focus-ring", "color-sky-pale", 3, "Focus ring on the sky band"],
  ["color-focus-ring", "color-sky-blue", 3, "Focus ring over the deepest sky blue"],
  ["color-focus-ring-on-ink", "color-ink", 3, "Focus ring on the ink band"],
  ["color-terracotta", "color-ivory", 3, "Error border and CHALLENGEABLE mark on the page"],
  ["color-terracotta", "color-paper", 3, "Error border on an input"],
  ["color-terracotta", "color-peach", 3, "Error border on a peach band"],
  ["color-sage", "color-ivory", 3, "Success mark on the page"],
  ["color-gold", "color-ink", 3, "Champagne hairline on the ink band"],
  ["color-ink", "color-sky-pale", 3, "Primary button edge on the sky band"],
  ["color-ink", "color-sky-blue", 3, "Primary button edge over the deepest sky blue"],
];

/** Pairs measured over atmosphere: they depend on src/design/atmosphere.ts. Computed, not listed. */
export function atmospherePairs(a = readAtmosphere()) {
  const dark = darkestSky(a);
  const ivory = (alpha) => ({ mix: ["color-ivory", { hex: dark }, alpha] });
  const glow = { mix: [{ hex: a.lampGlow }, { hex: a.lampBg }, a.lampGlowOpacity] };
  return [
    ["color-ink", { hex: dark }, 3, `Ink directly on the darkest cloud shadow (${dark}): reference only, the hero never relies on it`],
    ["color-ink", ivory(a.scrimAlpha), 4.5, "Hero headline, lead and links: ink on the ivory scrim over the darkest cloud"],
    ["color-ink", ivory(a.navAlpha), 4.5, "Transparent navbar over the sky: ink on the top ivory wash over the darkest cloud"],
    ["color-ink", ivory(0.8), 4.5, "Dev page captions: ink on an ivory/80 plate over the darkest cloud"],
    ["color-on-ink", glow, 4.5, "Lamp heading: ivory over the lamp's widest glow at its set opacity"],
    ["color-on-ink-soft", glow, 4.5, "Lamp lead text: secondary ivory over the lamp's glow"],
    ["color-on-ink", { mix: ["color-ink", "color-ivory", 0.9] }, 4.5, "Glass chip text: ink plate at 90% over the lightest artwork"],
  ];
}

export const PAIRS = TEXT;

export function computeTable(tokens = readTokens(), atmosphere = readAtmosphere()) {
  const res = (c) => {
    if (typeof c === "string") return tokens.resolve(c);
    if (c.hex) return c.hex;
    return mix(res(c.mix[0]), res(c.mix[1]), c.mix[2]);
  };
  const name = (c) => (typeof c === "string" ? c : c.hex ? c.hex : `${typeof c.mix[0] === "string" ? c.mix[0] : c.mix[0].hex}@${c.mix[2]}`);
  return [...PAIRS, ...atmospherePairs(atmosphere)].map(([fg, bg, min, use]) => {
    const f = res(fg);
    const b = res(bg);
    const r = ratio(f, b);
    return { fg: name(fg), bg: name(bg), fgHex: f, bgHex: b, min, use, ratio: r, pass: r >= min };
  });
}

export function toMarkdown(rows = computeTable()) {
  const head = "| Text / element | on | Colours | Ratio | Needs | Result |\n|---|---|---|---|---|---|\n";
  return (
    head +
    rows
      .map(
        (r) =>
          `| ${r.use} (\`${r.fg}\`) | \`${r.bg}\` | ${r.fgHex} on ${r.bgHex} | ${r.ratio.toFixed(2)}:1 | ${r.min}:1 | ${r.pass ? "pass" : "FAIL"} |`,
      )
      .join("\n")
  );
}
