import { fireEvent, screen, waitFor, within } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";
import { VerdictCard } from "../components/Verdict";
import { DeadlinesBox } from "../components/Plan";
import { INDEPENDENT_NOTICE, RESULT_NOTICE } from "../i18n";
import type { Plan } from "../api";
import { FACTS, GRIEVANCE_QUOTE, POLICY, check, explain, fact, finding } from "./fixtures";
import { mockFetch } from "./mockFetch";
import { renderApp, renderIn } from "./render";

afterEach(() => vi.unstubAllGlobals());

const resultState = (over = {}) => {
  const c = check();
  return {
    view: "result" as const,
    sid: "s1",
    facts: FACTS,
    result: {
      supported: true,
      productLine: "health",
      findings: c.findings,
      deadlines: c.deadlines,
      plan: null,
      checklist: null,
      text: "Explanation text.",
      explainFailed: false,
    },
    ...over,
  };
};

describe("verdict rendering: word + shape + sentence, never colour alone", () => {
  for (const v of ["CHALLENGEABLE", "NEED_INFO", "CONSISTENT"] as const) {
    it(`${v} shows a word, a drawn shape and the plain sentence`, async () => {
      const { container } = renderIn(<VerdictCard f={finding(v)} />);
      const stamp = container.querySelector(`.stamp[data-verdict="${v}"]`)!;
      expect(stamp).toBeTruthy();
      expect(stamp.querySelector("svg.verdict-shape")).toBeTruthy();
      expect(stamp.querySelector(".stamp-word")!.textContent!.trim().length).toBeGreaterThan(3);
      expect(container.querySelector("h3")!.textContent).toMatch(/\S{3,}/);
    });
  }
  it("the three shapes are three different silhouettes", async () => {
    const sig = (v: "CHALLENGEABLE" | "NEED_INFO" | "CONSISTENT") => {
      const { container, unmount } = renderIn(<VerdictCard f={finding(v)} />);
      const svg = container.querySelector("svg.verdict-shape")!;
      const s = [...svg.children].map((c) => c.tagName).join(",");
      unmount();
      return s;
    };
    const shapes = [sig("CHALLENGEABLE"), sig("NEED_INFO"), sig("CONSISTENT")];
    expect(new Set(shapes).size).toBe(3);
  });
  it("shows the rule quote with its page and the rule id only as a muted reference chip", async () => {
    const { container } = renderIn(<VerdictCard f={finding("CHALLENGEABLE")} />);
    expect(screen.getByText(/After sixty continuous months/)).toBeTruthy();
    expect(container.textContent).toMatch(/page 7/);
    const chip = container.querySelector(".rule-chip")!;
    expect(chip.textContent).toMatch(/Rule reference/);
    expect(chip.querySelector("code")!.textContent).toBe("MORATORIUM_60M");
    expect(container.querySelector("h3")!.textContent).not.toMatch(/MORATORIUM/);
  });
  it("shows the facts used with their quotes and uses API labels, not snake_case", async () => {
    const { container } = renderIn(<VerdictCard f={finding("CHALLENGEABLE")} />, { labels: { inception_date: { en: "policy start date", hi: "पॉलिसी शुरू होने की तारीख़" } } });
    expect(container.textContent).toMatch(/policy start date:/);
    expect(container.textContent).not.toMatch(/inception_date/);
    expect(container.textContent).toMatch(/Policy start 01\/04\/2019/);
  });
  it("shows ISO dates from the rule engine in the Indian DD/MM/YYYY format", async () => {
    const f = { ...finding("CHALLENGEABLE"), facts_used: { admission_date: { value: "2024-09-10", quote: "10/09/2024", page_no: 1 }, cashless_request_at: { value: "2024-09-10T14:30:00", quote: "2:30 pm", page_no: 1 } } };
    const { container } = renderIn(<VerdictCard f={f} />);
    expect(container.textContent).toMatch(/admission date: 10\/09\/2024/);
    expect(container.textContent).toMatch(/10\/09\/2024 14:30/);
    expect(container.textContent).not.toMatch(/2024-09-10/);
  });
  it("NEED_INFO asks, CONSISTENT does not suggest an action", async () => {
    const need = renderIn(<VerdictCard f={finding("NEED_INFO")} />);
    expect(need.container.textContent).toMatch(/What we need: Was your cover continuous\?/);
    need.unmount();
    const ok = renderIn(<VerdictCard f={finding("CONSISTENT")} />);
    expect(ok.container.textContent).not.toMatch(/What you can do/);
  });
});

describe("deadlines never show an assumed date", () => {
  const d = check().deadlines;
  it("hides computed dates when the user has not entered the complaint date", async () => {
    const { container } = renderIn(<DeadlinesBox d={d} complaintEntered={false} />);
    expect(container.textContent).not.toMatch(/16\/11\/2026|02\/12\/2026|02\/11\/2027/);
    expect(container.textContent).not.toMatch(/today's date/);
    expect(container.textContent).toMatch(/Add the date you sent your complaint/);
    expect(container.textContent).toContain(GRIEVANCE_QUOTE); // the rule is still shown
    expect(container.textContent).toMatch(/GRIEVANCE_ROUTE/);
  });
  it("shows them once the user has entered it", async () => {
    const { container } = renderIn(<DeadlinesBox d={d} complaintEntered />);
    expect(container.textContent).toMatch(/16\/11\/2026/);
    expect(container.textContent).toMatch(/02\/12\/2026/);
    expect(container.textContent).toMatch(/02\/11\/2027/);
  });
  it("hides them when the API says the letter cannot be dated (reply date without complaint date)", async () => {
    const { container } = renderIn(<DeadlinesBox d={{ ...d, letter_available: false, insurer_reply_by: null, ombudsman_earliest: null, ombudsman_latest: null }} complaintEntered />);
    expect(container.textContent).not.toMatch(/\d{2}\/\d{2}\/\d{4}/);
  });
});

describe("result screen", () => {
  it("shows both required notices, the verdicts ordered CHALLENGEABLE, NEED_INFO, CONSISTENT", async () => {
    const { container } = await renderApp(resultState());
    expect(container.textContent).toContain(RESULT_NOTICE);
    expect(container.textContent).toContain(INDEPENDENT_NOTICE);
    const order = [...container.querySelectorAll("article.finding")].map((a) => a.getAttribute("data-verdict"));
    expect(order).toEqual(["CHALLENGEABLE", "NEED_INFO", "CONSISTENT"]);
    expect(container.textContent).toContain("Explanation text.");
  });

  it("the independent-project notice is on every screen", async () => {
    for (const view of ["upload", "confirm", "deleted"] as const) {
      mockFetch({ "GET /gallery": () => ({ json: { attribution: "powered by IKanoon", cases: [] } }) });
      const { container, unmount } = await renderApp({ view, facts: FACTS, sid: "s1" });
      expect(container.textContent, view).toContain(INDEPENDENT_NOTICE);
      unmount();
    }
  });

  it("an unsupported product gets the general plan and the 'not a rules check' label, no verdicts", async () => {
    const plan: Plan = {
      kind: "general",
      supported: false,
      product_line: "motor",
      unverified: null,
      title: { en: "We don't have a checked rules engine for this type of insurance yet.", hi: "x" },
      steps: [
        {
          id: "papers",
          title: { en: "Keep your papers in order", hi: "x" },
          items: [
            { key: null, rule_id: null, text: { en: "Keep copies of your policy.", hi: "x" }, quote: null, page_no: null, source_id: null, source_title: null, source_label: null, date: null, date_label: null, link: null },
          ],
        },
      ],
      text: { en: "", hi: "" },
      verified: true,
    };
    const base = resultState();
    const { container } = await renderApp({
      ...base,
      result: { ...base.result, supported: false, productLine: "motor", findings: [], plan, deadlines: { available: false, note: "Dates, where the sources apply, are shown in your plan." }, text: "" },
    });
    expect(container.textContent).toMatch(/not a rules check/);
    expect(container.querySelectorAll("article.finding")).toHaveLength(0);
    expect(container.textContent).toMatch(/A general plan/);
    expect(container.textContent).toMatch(/Keep copies of your policy\./);
    expect(container.textContent).not.toMatch(/We don't have a checked rule for this reason yet/);
  });

  it("the plan shows a date only when the API gave one, else the 'Add the date' message", async () => {
    const plan: Plan = {
      kind: "health",
      supported: true,
      product_line: "health",
      unverified: null,
      title: { en: "Your plan", hi: "x" },
      steps: [
        {
          id: "letter",
          title: { en: "Send your grievance letter", hi: "x" },
          items: [
            { key: "missing_dates", rule_id: null, text: { en: "Add the date you sent your complaint to see your Ombudsman dates", hi: "x" }, quote: null, page_no: null, source_id: null, source_title: null, source_label: null, date: null, date_label: null, link: null },
            { key: "letter", rule_id: null, text: { en: "Download the grievance letter.", hi: "x" }, quote: null, page_no: null, source_id: null, source_title: null, source_label: null, date: null, date_label: null, link: "letter" },
          ],
        },
      ],
      text: { en: "", hi: "" },
      verified: true,
    };
    const base = resultState();
    const { container } = await renderApp({ ...base, result: { ...base.result, plan } });
    const planEl = container.querySelector("#plan")!;
    expect(planEl.textContent).toMatch(/Add the date you sent your complaint/);
    expect(planEl.textContent).not.toMatch(/\d{2}\/\d{2}\/\d{4}/);
    expect(within(planEl as HTMLElement).getByRole("button", { name: /Download grievance letter/ })).toBeTruthy();
  });

  it("shows 'What your policy says' read only when a policy was read", async () => {
    const { container } = await renderApp({ ...resultState(), policy: POLICY });
    const sec = container.querySelector("#policy-section")!;
    expect(sec.textContent).toMatch(/What your policy says/);
    expect(sec.textContent).toMatch(/Sum Insured: Rs\. 5,00,000/);
    expect(sec.querySelector("input, button")).toBeNull();
  });

  it("helper mode adds a print button and asks for third-person wording", async () => {
    const m = mockFetch({ "POST /session/s1/explain": () => ({ json: explain() }) });
    await renderApp(resultState());
    expect(screen.queryByRole("button", { name: /Print this summary/ })).toBeNull();
    fireEvent.click(screen.getByRole("button", { name: "Helping someone" }));
    expect(screen.getByRole("button", { name: /Print this summary/ })).toBeTruthy();
    expect(screen.getByRole("button", { name: /Delete their data now/ })).toBeTruthy();
    await waitFor(() => expect(m.calls.some((c) => c.url.includes("helper=1"))).toBe(true));
  });

  it("switching to Hindi re-fetches the explanation in Hindi and marks the text as a draft", async () => {
    const m = mockFetch({ "POST /session/s1/explain": () => ({ json: explain({ text: "हिंदी व्याख्या" }) }) });
    const { container } = await renderApp(resultState());
    fireEvent.click(screen.getByRole("button", { name: "हिन्दी" }));
    await waitFor(() => expect(container.textContent).toContain("हिंदी व्याख्या"));
    expect(m.calls.at(-1)!.url).toContain("lang=hi");
    expect(container.textContent).toMatch(/Q-007/);
    expect(document.documentElement.lang).toBe("hi");
  });

  it("entering the complaint date saves it, re-runs the check and shows the dates", async () => {
    const m = mockFetch({
      "PUT /session/s1/facts": () => ({ json: { facts: { ...FACTS, complaint_sent_date: fact("complaint_sent_date", { value: "02/11/2026", status: "user_confirmed" }) }, needs_confirmation: [] } }),
      "POST /session/s1/check": () => ({ json: check() }),
      "POST /session/s1/explain": () => ({ json: explain() }),
    });
    const { container } = await renderApp(resultState());
    expect(container.querySelector("#deadlines")!.textContent).not.toMatch(/16\/11\/2026/);
    fireEvent.change(screen.getByLabelText(/Date you sent your complaint/), { target: { value: "02/11/2026" } });
    fireEvent.click(screen.getByRole("button", { name: "Update my dates" }));
    await waitFor(() => expect(container.querySelector("#deadlines")!.textContent).toMatch(/16\/11\/2026/));
    // the session calls, in order (the result also reads the public real-case list, GET /gallery, for its chart)
    expect(m.calls.map((c) => c.key).filter((k) => k !== "GET /gallery")).toEqual(["PUT /session/s1/facts", "POST /session/s1/check", "POST /session/s1/explain"]);
    expect(m.calls.find((c) => c.key === "PUT /session/s1/facts")!.body).toEqual({ facts: { complaint_sent_date: { value: "02/11/2026" } } });
  });

  it("a 409 from the letter route is shown, not navigated to", async () => {
    mockFetch({ "GET /session/s1/letter.pdf": () => ({ status: 409, json: { detail: "There is no challengeable finding, so there is no letter to write." } }) });
    await renderApp(resultState());
    fireEvent.click(screen.getAllByRole("button", { name: /Download grievance letter/ })[0]);
    expect(await screen.findByRole("alert")).toHaveProperty("textContent", expect.stringMatching(/no letter to write/));
  });

  it("downloads the letter as a file when it works", async () => {
    mockFetch({ "GET /session/s1/letter.pdf": () => ({}) });
    const create = vi.fn(() => "blob:x");
    vi.stubGlobal("URL", Object.assign(URL, { createObjectURL: create, revokeObjectURL: vi.fn() }));
    await renderApp(resultState());
    fireEvent.click(screen.getAllByRole("button", { name: /Download grievance letter/ })[0]);
    await waitFor(() => expect(create).toHaveBeenCalled());
  });

  it("delete my data calls DELETE and shows the confirmation", async () => {
    const m = mockFetch({ "DELETE /session/s1": () => ({ json: { deleted: true } }) });
    await renderApp(resultState());
    fireEvent.click(screen.getByRole("button", { name: /Delete my data now/ }));
    // a destructive action asks first: a dialog, with "Keep my data" as the safe default focus
    const dialog = await screen.findByRole("dialog", { name: "Delete your data now?" });
    expect(document.activeElement).toBe(within(dialog).getByRole("button", { name: "Keep my data" }));
    expect(m.count("DELETE /session/s1")).toBe(0);
    fireEvent.click(within(dialog).getByRole("button", { name: "Yes, delete my data" }));
    expect(await screen.findByText("Your data was deleted.")).toBeTruthy();
    expect(m.count("DELETE /session/s1")).toBe(1);
    fireEvent.click(screen.getByRole("button", { name: "Start again" }));
    expect(await screen.findByText("Upload your documents")).toBeTruthy();
  });

  it("an expired session (404) shows the recovery banner and starts again", async () => {
    mockFetch({ "POST /session/s1/explain": () => ({ status: 404, json: { detail: "expired" } }) });
    await renderApp(resultState());
    fireEvent.click(screen.getByRole("button", { name: "हिन्दी" }));
    const banner = await screen.findByText("आपका सत्र समाप्त हो गया है। कृपया फिर से शुरू करें।");
    expect(banner).toBeTruthy();
    fireEvent.click(screen.getByRole("button", { name: "फिर से शुरू करें" }));
    expect(await screen.findByText("अपने दस्तावेज़ अपलोड करें")).toBeTruthy();
  });
});

describe("gallery", () => {
  it("lists real cases with citations and 'powered by IKanoon', and opens one", async () => {
    mockFetch({
      "GET /gallery": () => ({
        json: { attribution: "powered by IKanoon", cases: [{ case_id: "c1", citation: { forum: "NCDRC", case_number: "CC/12/2023", decided_on: "2024-05-01", source_url: null }, outcome: "allowed", verdicts: ["CHALLENGEABLE", "CONSISTENT"] }] },
      }),
      "GET /gallery/c1": () => ({
        json: { case_id: "c1", citation: { forum: "NCDRC", case_number: "CC/12/2023", decided_on: "2024-05-01", source_url: "https://indiankanoon.org/doc/1/" }, insurer: "Some Insurer", outcome: "allowed", relief_amount: null, licence_note: null, findings: [finding("CHALLENGEABLE")], attribution: "powered by IKanoon" },
      }),
    });
    const { container } = await renderApp({}, "/cases");
    expect(await screen.findByRole("heading", { name: "CC/12/2023" })).toBeTruthy();
    expect(container.textContent).toContain("powered by IKanoon");
    expect(container.querySelectorAll("li [data-verdict]")).toHaveLength(2);
    fireEvent.click((await screen.findAllByRole("button", { name: /View this case/ }))[0]);
    expect(await screen.findByText(/Outcome:/)).toBeTruthy();
    expect(container.textContent).toContain("powered by IKanoon");
    const link = container.querySelector("a[href^='https://indiankanoon.org']")!;
    expect(link.getAttribute("rel")).toContain("noopener");
  });

  it("does not link a non-https source", async () => {
    mockFetch({
      "GET /gallery": () => ({ json: { attribution: "powered by IKanoon", cases: [{ case_id: "c1", citation: { forum: null, case_number: null, decided_on: null, source_url: null }, outcome: null, verdicts: [] }] } }),
      "GET /gallery/c1": () => ({ json: { case_id: "c1", citation: { forum: null, case_number: null, decided_on: null, source_url: "javascript:alert(1)" }, insurer: null, outcome: null, relief_amount: null, licence_note: null, findings: [], attribution: "powered by IKanoon" } }),
    });
    const { container } = await renderApp({}, "/cases");
    fireEvent.click((await screen.findAllByRole("button", { name: /View this case/ }))[0]);
    await screen.findByText(/Outcome:/);
    expect(container.querySelector("a[href^='javascript']")).toBeNull();
  });
});
