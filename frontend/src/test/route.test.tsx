import fs from "node:fs";
import path from "node:path";
import { fireEvent, screen, waitFor, within } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";
import type { Plan, PlanItem, PlanStep } from "../api";
import { PlanSection } from "../components/Plan";
import { DeadlineTimeline, daysUntil } from "../components/charts/DeadlineTimeline";
import { stops } from "../components/plan/RouteMap";
import { Spark } from "../components/ds/Spark";
import { Stepper } from "../components/ds/Stepper";
import { FindingsChart } from "../components/charts/FindingsChart";
import { resetGalleryCache } from "../components/charts/RealCases";
import { check, finding, resultSession } from "./fixtures";
import { mockFetch } from "./mockFetch";
import { renderApp, renderIn } from "./render";

const SRC = path.resolve(__dirname, "..");
const B = (en: string) => ({ en, hi: `${en} (hi)` });
const it_ = (p: Partial<PlanItem> = {}): PlanItem => ({
  key: null, rule_id: null, text: B("Do this"), quote: null, page_no: null, source_id: null,
  source_title: null, source_label: null, date: null, date_label: null, link: null, ...p,
});
const step = (id: string, title: string, items: PlanItem[] = [it_()]): PlanStep => ({ id, title: B(title), items });

const PLAN: Plan = {
  kind: "health",
  supported: true,
  product_line: "health",
  unverified: null,
  title: B("Your plan"),
  text: B(""),
  verified: true,
  steps: [
    step("case", "Your case"),
    step("ask", "What to ask your insurer for", [it_({ rule_id: "MORATORIUM_60M", quote: "a quoted rule", page_no: 8 }), it_()]),
    step("letter", "Send your grievance letter", [it_({ date: { iso: "2026-11-16", display: "16/11/2026" }, date_label: B("Reply due") })]),
    step("ombudsman", "If there is no reply, or it does not settle the matter: Insurance Ombudsman", [it_({ quote: "ombudsman rule", page_no: 3 })]),
    step("commission", "If your claim is larger than the Ombudsman's limit"),
  ],
};

describe("the plan as a route", () => {
  it("puts a decision in front of each step whose title is a condition, and nothing else is invented", () => {
    const s = stops(PLAN);
    expect(s.map((x) => (x.kind === "turn" ? x.id : x.step.id))).toEqual(["case", "ask", "letter", "turn-ombudsman", "ombudsman", "turn-commission", "commission"]);
  });

  it("counts steps, decisions and quoted rules from the plan itself, and keeps every step's detail in the page", () => {
    const { container } = renderIn(<PlanSection plan={PLAN} />);
    const map = screen.getByRole("list", { name: "Your route, step by step" });
    expect(within(map).getAllByRole("button")).toHaveLength(5);
    expect(map.textContent).toContain("Does the insurer's reply settle it?");
    expect(map.textContent).toContain("Insurance Ombudsman");
    expect(map.textContent).toContain("1 quoted");
    expect(map.textContent).toContain("16/11/2026");
    // the detailed steps are all still there, each with the anchor the map points at
    for (const s of PLAN.steps) expect(container.querySelector(`#plan-step-${s.id} h4`)?.textContent).toBe(s.title.en);
  });

  it("one tab stop: the current stop is focusable, the rest are reached with the arrow keys", () => {
    renderIn(<PlanSection plan={PLAN} />);
    const buttons = within(screen.getByRole("list", { name: "Your route, step by step" })).getAllByRole("button");
    expect(buttons.filter((b) => b.tabIndex === 0)).toHaveLength(1);
    expect(buttons[0].getAttribute("aria-current")).toBe("step");
    fireEvent.keyDown(buttons[0], { key: "ArrowRight" });
    expect(buttons[1].getAttribute("aria-current")).toBe("step");
  });

  it("pressing a stop takes you to that step's detail", () => {
    const spy = vi.spyOn(Element.prototype, "scrollIntoView");
    renderIn(<PlanSection plan={PLAN} />);
    fireEvent.click(screen.getByRole("button", { name: /Send your grievance letter/ }));
    expect(spy).toHaveBeenCalled();
    expect(spy.mock.contexts.at(-1)).toBe(document.getElementById("plan-step-letter"));
    spy.mockRestore();
  });

  it("a one-step plan is just the step (no map for a route with one stop)", () => {
    renderIn(<PlanSection plan={{ ...PLAN, steps: [PLAN.steps[0]] }} />);
    expect(screen.queryByRole("list", { name: "Your route, step by step" })).toBeNull();
  });
});

describe("the deadline chart", () => {
  const d = check().deadlines;
  it("draws both windows from the API's dates only, with today marked and the status in words", () => {
    renderIn(<DeadlineTimeline d={d} today="2026-11-10" />);
    const fig = screen.getByRole("img");
    expect(fig.getAttribute("aria-label")).toMatch(/02\/11\/2026 – 16\/11\/2026\. 6 days left/);
    expect(fig.getAttribute("aria-label")).toMatch(/Opens in 22 days/);
    expect(fig.textContent).toContain("02/11/2027");
  });
  it("draws nothing when a window has no dates", () => {
    const { container } = renderIn(<DeadlineTimeline d={{ ...d, letter_date: null, ombudsman_earliest: null }} today="2026-11-10" />);
    expect(container.textContent).toBe("");
  });
  it("counts whole days", () => {
    expect(daysUntil("2026-11-16", "2026-11-10")).toBe(6);
    expect(daysUntil("2026-11-01", "2026-11-10")).toBe(-9);
  });
});

describe("motion that explains", () => {
  it("Spark wraps the action without changing it: same button, same name, decoration hidden from assistive tech", () => {
    renderIn(
      <Spark>
        <button type="button">Run the check</button>
      </Spark>,
    );
    expect(screen.getByRole("button", { name: "Run the check" })).toBeTruthy();
    expect(screen.getAllByRole("button")).toHaveLength(1);
  });
  it("the falling copy of a sheet is never a second screen (no ids, no names, inert, aria-hidden)", () => {
    const tumble = fs.readFileSync(path.join(SRC, "components/flow/Tumble.tsx"), "utf8");
    expect(tumble).toMatch(/removeAttribute\("id"\)/);
    expect(tumble).toMatch(/removeAttribute\("name"\)/);
    expect(tumble).toMatch(/setAttribute\("inert"/);
    expect(tumble).toMatch(/setAttribute\("aria-hidden", "true"\)/);
    expect(tumble).toMatch(/typeof el\.animate !== "function"/);
  });
  it("the ring shader is raw WebGL (it never pulls three.js into the result screen) and keeps its colours in atmosphere.ts", () => {
    const rings = fs.readFileSync(path.join(SRC, "components/ui/shader-rings.tsx"), "utf8");
    expect(rings).not.toMatch(/from "three"/);
    expect(rings).not.toMatch(/#[0-9a-f]{6}/i);
    expect(rings).toMatch(/prefers-reduced-motion/);
  });
});

const STEPS = [
  { id: "upload", text: "1. Upload" },
  { id: "confirm", text: "2. Confirm" },
  { id: "result", text: "3. Result" },
];
const CASE = (id: string, won: boolean | null, ground = "pre_existing_disease") => ({
  case_id: id,
  rejection_ground: ground,
  policyholder_prevailed: won,
  citation: { forum: "District Commission", case_number: null, decided_on: "2024-01-02", source_url: null },
  outcome: null,
  verdicts: [],
});

describe("tracing back through the claim steps", () => {
  it("a reached step is a button, the current step and unreached steps are not", () => {
    const go = vi.fn();
    renderIn(<Stepper steps={STEPS} current="confirm" label="Steps" reachable={["upload", "confirm"]} onGo={go} />);
    const nav = screen.getByRole("navigation", { name: "Steps" });
    expect(within(nav).getAllByRole("button")).toHaveLength(1);
    fireEvent.click(within(nav).getByRole("button", { name: "1. Upload" }));
    expect(go).toHaveBeenCalledWith("upload");
  });

  it("no step can be opened while the app is busy", () => {
    renderIn(<Stepper steps={STEPS} current="result" label="Steps" reachable={["upload", "confirm", "result"]} onGo={() => {}} disabled />);
    for (const b of within(screen.getByRole("navigation", { name: "Steps" })).getAllByRole("button")) expect((b as HTMLButtonElement).disabled).toBe(true);
  });

  it("from the result you can go back to Confirm and return to the result without running the check again", async () => {
    resetGalleryCache();
    const m = mockFetch({ "GET /gallery": () => ({ json: { attribution: "x", cases: [] } }) });
    await renderApp({ ...resultSession(), step: 5, reached: 5 });
    const nav = screen.getByRole("navigation", { name: "Steps" });
    fireEvent.click(within(nav).getByRole("button", { name: "Go back to step: 2. Confirm" }));
    expect(await screen.findByRole("button", { name: "Run the check" })).toBeTruthy();
    fireEvent.click(within(screen.getByRole("navigation", { name: "Steps" })).getByRole("button", { name: "Go back to step: 3. Result" }));
    expect(await screen.findByRole("heading", { name: "Result" })).toBeTruthy();
    expect(m.calls.filter((c) => c.key !== "GET /gallery")).toHaveLength(0);
  });

  it("the result has a Change my answers button that opens Confirm", async () => {
    resetGalleryCache();
    mockFetch({ "GET /gallery": () => ({ json: { attribution: "x", cases: [] } }) });
    await renderApp({ ...resultSession(), step: 5, reached: 5 });
    fireEvent.click(screen.getByRole("button", { name: "Change my answers" }));
    expect(await screen.findByRole("button", { name: "Run the check" })).toBeTruthy();
  });
});

describe("the result in one picture", () => {
  const F = [finding("CHALLENGEABLE", "A"), finding("CHALLENGEABLE", "B"), finding("NEED_INFO", "C"), finding("CONSISTENT", "D")];

  it("counts the rules by verdict, writes the count on each part, and says it is not a chance of winning", () => {
    resetGalleryCache();
    mockFetch({ "GET /gallery": () => ({ json: { attribution: "x", cases: [] } }) });
    renderIn(<FindingsChart findings={F} ground={null} />);
    expect(document.body.textContent).toContain("checked against 4 IRDAI rules: 2 say the decision can be challenged, 1 need more information, 1 agree with the insurer");
    const bar = screen.getByRole("img", { name: "Challengeable: 2, Need info: 1, Consistent: 1" });
    expect(bar.querySelectorAll("[data-part]")).toHaveLength(3);
    expect(document.body.textContent).toMatch(/not a chance of winning/);
  });

  it("adds real cases with the same reason, counted by who won, when there are any", async () => {
    resetGalleryCache();
    mockFetch({ "GET /gallery": () => ({ json: { attribution: "x", cases: [CASE("c1", true), CASE("c2", false), CASE("c3", true, "exclusion")] } }) });
    renderIn(<FindingsChart findings={F} ground="pre_existing_disease" />);
    await waitFor(() => expect(document.body.textContent).toContain("The policyholder won 1 of 2 similar real cases."));
  });

  it("draws nothing without findings", () => {
    const { container } = renderIn(<FindingsChart findings={[]} ground={null} />);
    expect(container.textContent).toBe("");
  });
});

describe("dev server", () => {
  it("forwards /api to the backend (the schemes finder and the evidence page read /api/...)", () => {
    const cfg = fs.readFileSync(path.resolve(SRC, "../vite.config.ts"), "utf8");
    expect(cfg).toMatch(/"\/api": API/);
  });
});
