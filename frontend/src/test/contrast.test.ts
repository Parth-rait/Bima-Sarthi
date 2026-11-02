import { describe, expect, it } from "vitest";
// @ts-expect-error plain ESM helper shared with `npm run contrast`
import { computeTable, ratio } from "../../scripts/contrast-lib.mjs";

describe("WCAG AA contrast of every shipped colour pair", () => {
  const rows = computeTable() as Array<{ use: string; fg: string; bg: string; ratio: number; min: number; pass: boolean }>;
  it("covers the pairs the design uses", () => {
    expect(rows.length).toBeGreaterThanOrEqual(30);
  });
  for (const r of rows) {
    it(`${r.use}: ${r.fg} on ${r.bg} is ${r.ratio.toFixed(2)}:1 (needs ${r.min}:1)`, () => {
      expect(r.pass).toBe(true);
    });
  }
  it("the math matches known values (black on white = 21:1)", () => {
    expect(ratio("#000000", "#ffffff")).toBeCloseTo(21, 5);
  });
});
