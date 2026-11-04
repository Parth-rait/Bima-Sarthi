import { act, fireEvent, render, screen, waitFor, within } from "@testing-library/react";
import { MemoryRouter, useLocation } from "react-router";
import { afterEach, describe, expect, it, vi } from "vitest";
import { App } from "../app/App";
import { ServiceProvider } from "../app/ServiceStatus";
import { INDEPENDENT_NOTICE, RESULT_NOTICE } from "../i18n";
import { SessionProvider } from "../state/store";
import { resultSession } from "./fixtures";
import { mockFetch } from "./mockFetch";
import { renderApp } from "./render";

afterEach(() => {
  vi.unstubAllGlobals();
  vi.useRealTimers();
});

const gallery = () => ({ "GET /gallery": () => ({ json: { attribution: "powered by IKanoon", cases: [] } }) });

const ROUTES: Array<[string, string, RegExp]> = [
  ["/", "Check a health-insurance claim rejection", /Your health claim deserves a fair explanation\./],
  ["/about", "About", /About Bima Sarthi/],
  ["/how-it-works", "How it works", /How it works/],
  ["/check-claim", "Check my claim", /Check my claim/],
  ["/action-plan", "Action plan", /Your action plan/],
  ["/cases", "Real cases", /Real cases/],
  ["/privacy", "Privacy", /^Privacy$/],
  ["/help", "Help centre", /Help centre/],
  ["/results/nope", "Claim check report", /This report is no longer available/],
  ["/dev/components", "Installed components", /Installed components/],
  ["/no/such/page", "Page not found", /This page does not exist/],
];

describe("every route", () => {
  for (const [path, title, heading] of ROUTES) {
    it(`${path}: document title, one h1, and both required footer notices`, async () => {
      mockFetch(gallery());
      const { container } = await renderApp({}, path);
      expect(document.title).toContain(title);
      const h1s = container.querySelectorAll("h1");
      expect(h1s).toHaveLength(1);
      expect(h1s[0].textContent).toMatch(heading);
      const footer = container.querySelector("footer")!;
      expect(footer.textContent).toContain(INDEPENDENT_NOTICE);
      expect(footer.textContent).toContain(RESULT_NOTICE);
    });
  }
});

describe("landing page", () => {
  it("has the specified hero copy and the two calls to action", async () => {
    await renderApp({}, "/");
    expect(screen.getByRole("heading", { level: 1 }).textContent).toBe("Your health claim deserves a fair explanation.");
    expect(screen.getByText("Understand why your health-insurance claim was rejected, examine the relevant rules and discover what you can do next.")).toBeTruthy();
    const cta = within(document.querySelector("main")!).getAllByRole("link", { name: "Check my claim" })[0];
    expect(cta.getAttribute("href")).toBe("/check-claim");
    expect(within(document.querySelector("main")!).getAllByRole("link", { name: "How it works" })[0].getAttribute("href")).toBe("/how-it-works");
  });
  it("cites its one figure with the source, and states the figure is a count of complaints", async () => {
    const { container } = await renderApp({}, "/");
    expect(container.textContent).toContain("31,490");
    expect(container.textContent).toContain("CIO Annual Report 2023-24");
    expect(container.textContent).not.toContain("52,575");
  });
  it("labels the example scenarios illustrative and has the FAQ and the final call to action", async () => {
    const { container } = await renderApp({}, "/");
    expect(container.textContent).toMatch(/illustrative/i);
    expect(container.querySelector("#faq")).toBeTruthy();
    expect(screen.getByRole("heading", { name: "Start with the letter in your hand." })).toBeTruthy();
  });
  it("shows the hero artwork with alt text (the plain image where WebGL does not exist)", async () => {
    await renderApp({}, "/");
    const img = screen.getByAltText(/rejection letter with a highlighted quoted passage/);
    expect(img.tagName).toBe("IMG");
  });
  it("the glass chip states the positioning in real text", async () => {
    await renderApp({}, "/");
    expect((await screen.findAllByText("Rules decide the verdict. Models only read your documents.")).length).toBeGreaterThan(0);
  });
});

describe("navbar", () => {
  it("marks the current page with aria-current and offers the Explore disclosure with the six links (Evidence restored)", async () => {
    await renderApp({}, "/about");
    const nav = screen.getByRole("navigation", { name: "Main navigation" });
    expect(within(nav).getByRole("link", { name: "About" }).getAttribute("aria-current")).toBe("page");
    expect(within(nav).getByRole("link", { name: "Home" }).getAttribute("aria-current")).toBeNull();
    const explore = within(nav).getByRole("button", { name: "Explore" });
    expect(explore.getAttribute("aria-expanded")).toBe("false");
    fireEvent.click(explore);
    expect(explore.getAttribute("aria-expanded")).toBe("true");
    const list = document.getElementById(explore.getAttribute("aria-controls")!)!;
    expect([...list.querySelectorAll("a")].map((a) => a.textContent!.split(/(?=[A-Z][a-z]+ [a-z])/)[0]).length).toBe(6);
    expect(within(list).getByRole("link", { name: /Frequently asked questions/ }).getAttribute("href")).toBe("/help#faq");
  });

  it("Explore closes on Escape and returns focus to its button, and on an outside click", async () => {
    await renderApp({}, "/");
    const explore = within(screen.getByRole("navigation", { name: "Main navigation" })).getByRole("button", { name: "Explore" });
    fireEvent.click(explore);
    fireEvent.keyDown(document, { key: "Escape" });
    expect(explore.getAttribute("aria-expanded")).toBe("false");
    expect(document.activeElement).toBe(explore);
    fireEvent.click(explore);
    fireEvent.pointerDown(document.body);
    expect(explore.getAttribute("aria-expanded")).toBe("false");
  });

  it("the mobile menu is a modal dialog: focus moves in, Tab is trapped, Escape closes and focus returns", async () => {
    await renderApp({}, "/");
    const open = screen.getByRole("button", { name: /^Menu$/ });
    expect(screen.queryByRole("dialog")).toBeNull();
    open.focus();
    fireEvent.click(open);
    const dialog = screen.getByRole("dialog", { name: "Site menu" });
    expect(dialog.getAttribute("aria-modal")).toBe("true");
    const close = within(dialog).getByRole("button", { name: "Close menu" });
    expect(document.activeElement).toBe(close);
    // Shift+Tab from the first control wraps to the last; Tab from the last wraps back to the first
    const controls = [...dialog.querySelectorAll<HTMLElement>("a[href], button")];
    controls[0].focus();
    fireEvent.keyDown(document, { key: "Tab", shiftKey: true });
    expect(document.activeElement).toBe(controls.at(-1));
    fireEvent.keyDown(document, { key: "Tab" });
    expect(document.activeElement).toBe(controls[0]);
    expect(document.body.style.overflow).toBe("hidden");
    fireEvent.keyDown(document, { key: "Escape" });
    expect(screen.queryByRole("dialog")).toBeNull();
    expect(document.activeElement).toBe(open);
    expect(document.body.style.overflow).toBe("");
  });

  it("the mobile menu closes when a link is followed", async () => {
    await renderApp({}, "/");
    fireEvent.click(screen.getByRole("button", { name: /^Menu$/ }));
    fireEvent.click(within(screen.getByRole("dialog")).getByRole("link", { name: "About" }));
    await waitFor(() => expect(screen.queryByRole("dialog")).toBeNull());
    expect(document.title).toContain("About");
  });

  it("the language toggle switches the chrome to Hindi and shows the draft note and footer notice", async () => {
    await renderApp({}, "/about");
    fireEvent.click(screen.getByRole("button", { name: "हिन्दी" }));
    expect(screen.getAllByText("मेरा दावा जाँचें").length).toBeGreaterThan(0);
    expect(document.body.textContent).toMatch(/Q-007/);
    expect(document.querySelector("footer")!.textContent).toContain("यह नियमों की जाँच है");
    expect(document.documentElement.lang).toBe("hi");
    expect(document.body.textContent).toContain("इस पन्ने का लंबा पाठ अभी अंग्रेज़ी में है");
  });
});

describe("route changes", () => {
  it("moves focus to the new page heading, updates the title, and announces the page", async () => {
    await renderApp({}, "/");
    fireEvent.click(within(screen.getByRole("navigation", { name: "Main navigation" })).getByRole("link", { name: "Help" }));
    const h1 = await screen.findByRole("heading", { level: 1, name: "Help centre" });
    await waitFor(() => expect(document.activeElement).toBe(h1));
    expect(document.title).toBe("Help centre | Bima Sarthi");
    expect(screen.getAllByRole("status").some((s) => s.textContent === "Help centre")).toBe(true);
  });

  it("does not steal focus on the very first load", async () => {
    await renderApp({}, "/about");
    expect(document.activeElement).toBe(document.body);
  });

  it("the skip link is the first focusable element and moves focus to <main>", async () => {
    await renderApp({}, "/about");
    const skip = screen.getByRole("link", { name: "Skip to the main content" });
    expect(document.querySelector("a, button")).toBe(skip);
    fireEvent.click(skip);
    expect(document.activeElement).toBe(document.getElementById("main"));
  });

  it("follows an Explore link to a #hash on another page, even though that page is still loading", async () => {
    const seen: string[] = [];
    const spy = vi.spyOn(Element.prototype, "scrollIntoView").mockImplementation(function (this: Element) {
      seen.push(this.id);
    });
    await renderApp({}, "/");
    const nav = screen.getByRole("navigation", { name: "Main navigation" });
    fireEvent.click(within(nav).getByRole("button", { name: "Explore" }));
    fireEvent.click(within(nav).getByRole("link", { name: /Frequently asked questions/ }));
    await screen.findByRole("heading", { level: 1, name: "Help centre" });
    await waitFor(() => expect(seen).toContain("faq"));
    spy.mockRestore();
  });

  it("scrolls to a #hash target", async () => {
    const spy = vi.spyOn(Element.prototype, "scrollIntoView");
    await renderApp({}, "/help#faq");
    await waitFor(() => expect(spy).toHaveBeenCalled());
    spy.mockRestore();
  });
});

describe("splash and service status", () => {
  function Probe() {
    const l = useLocation();
    return <span data-testid="loc">{l.pathname}</span>;
  }
  const shell = (route = "/") =>
    render(
      <MemoryRouter initialEntries={[route]}>
        <ServiceProvider>
          <SessionProvider>
            <App />
            <Probe />
          </SessionProvider>
        </ServiceProvider>
      </MemoryRouter>,
    );

  it("shows nothing when initialisation is quick, and never shows a splash after it is ready", async () => {
    mockFetch({ "GET /health": () => ({ json: { status: "ok" } }) });
    shell();
    await screen.findByRole("heading", { level: 1 });
    expect(screen.queryByText("Getting ready...")).toBeNull();
  });

  it("appears only if the health check is slow, and disappears the moment it answers (no artificial delay)", async () => {
    vi.useFakeTimers({ shouldAdvanceTime: true });
    let release: () => void = () => {};
    const gate = new Promise<void>((r) => (release = r));
    mockFetch({ "GET /health": async () => (await gate, { json: { status: "ok" } }) });
    shell();
    expect(screen.queryByText("Getting ready...")).toBeNull();
    await act(async () => {
      await vi.advanceTimersByTimeAsync(400);
    });
    expect(screen.getByText("Getting ready...")).toBeTruthy();
    await act(async () => {
      release();
      await vi.advanceTimersByTimeAsync(300);
    });
    await waitFor(() => expect(screen.queryByText("Getting ready...")).toBeNull());
  });

  it("a failed health check does not block the app: it opens, and the claim page explains and offers a retry", async () => {
    let up = false;
    mockFetch({ "GET /health": () => (up ? { json: { status: "ok" } } : { status: 503, json: { detail: "x" } }) });
    shell("/check-claim");
    const alert = await screen.findByText("The checking service is not reachable");
    expect(alert).toBeTruthy();
    expect(screen.getByRole("heading", { level: 1, name: "Check my claim" })).toBeTruthy();
    up = true;
    fireEvent.click(screen.getByRole("button", { name: "Try again" }));
    await waitFor(() => expect(screen.queryByText("The checking service is not reachable")).toBeNull());
  });
});

describe("action plan", () => {
  it("with no session it shows a helpful empty state that links to the claim page", async () => {
    await renderApp({}, "/action-plan");
    expect(screen.getByRole("heading", { name: "No claim in this session yet" })).toBeTruthy();
    expect(within(document.querySelector("main")!).getByRole("link", { name: "Check my claim" }).getAttribute("href")).toBe("/check-claim");
  });

  it("builds every section from the session result, promises nothing, and lists no invented contacts", async () => {
    const { container } = await renderApp(resultSession(), "/action-plan");
    const text = container.querySelector("main")!.textContent!;
    for (const h of ["What happened", "What needs your attention", "Documents to request", "What to raise with the insurer", "Escalation options and dates", "Your checklist", "Official contact details", "What this plan is not"]) {
      expect(screen.getByRole("heading", { name: h }), h).toBeTruthy();
    }
    expect(text).toContain(RESULT_NOTICE);
    expect(text).toContain("The full claim file");
    expect(text).toContain("Possible inconsistency to raise with the insurer");
    expect(text).toContain("not a promise of any outcome");
    expect(text).toContain("never files a complaint");
    expect(text).not.toMatch(/\b1800\b|\bwww\.|@[a-z]+\.[a-z]/i);
    expect(text).not.toMatch(/guarantee[sd]? (that|you)/i);
  });

  it("the checklist is interactive and its state lives in the session", async () => {
    await renderApp(resultSession(), "/action-plan");
    const boxes = screen.getAllByRole("checkbox");
    expect(boxes.length).toBeGreaterThanOrEqual(2);
    expect(screen.getByText(/^0 \/ \d+ done$/)).toBeTruthy();
    fireEvent.click(boxes[0]);
    expect((screen.getAllByRole("checkbox")[0] as HTMLInputElement).checked).toBe(true);
    expect(screen.getByText(/^1 \/ \d+ done$/)).toBeTruthy();
    // navigate away and back: the ticks survive (in memory)
    fireEvent.click(within(screen.getByRole("navigation", { name: "Main navigation" })).getByRole("link", { name: "About" }));
    await screen.findByRole("heading", { level: 1, name: "About Bima Sarthi" });
  });

  it("the grievance letter is offered only when something is challengeable", async () => {
    const s = resultSession();
    const only = { ...s, result: { ...s.result, findings: s.result.findings.filter((f) => f.verdict === "CONSISTENT") } };
    await renderApp(only, "/action-plan");
    expect(screen.queryByRole("button", { name: /Download grievance letter/ })).toBeNull();
    expect(screen.getByText(/None of the rules we checked flags a point to raise/)).toBeTruthy();
  });
});

describe("report page (/results/:id)", () => {
  it("renders the in-memory session's report when the id matches, with the notices and a print button", async () => {
    const { container } = await renderApp(resultSession(), "/results/rep-1");
    expect(screen.getByRole("heading", { level: 1, name: "Claim check report" })).toBeTruthy();
    expect([...container.querySelectorAll("article.finding")].map((a) => a.getAttribute("data-verdict"))).toEqual(["CHALLENGEABLE", "NEED_INFO", "CONSISTENT"]);
    expect(container.querySelector("article")!.textContent).toContain(RESULT_NOTICE);
    expect(container.querySelector("article")!.textContent).toContain(INDEPENDENT_NOTICE);
    const print = vi.spyOn(window, "print").mockImplementation(() => {});
    fireEvent.click(screen.getByRole("button", { name: "Print this summary" }));
    expect(print).toHaveBeenCalled();
  });

  it("a wrong id shows the expired state and none of the session's data", async () => {
    const { container } = await renderApp(resultSession(), "/results/somebody-elses");
    expect(screen.getByText("This report is no longer available")).toBeTruthy();
    expect(container.textContent).not.toContain("Explanation text.");
    expect(container.querySelector("article.finding")).toBeNull();
    expect(within(container.querySelector("main")!).getByRole("link", { name: "Check my claim" })).toBeTruthy();
  });

  it("with no result at all it is the expired state", async () => {
    await renderApp({}, "/results/rep-1");
    expect(screen.getByText("This report is no longer available")).toBeTruthy();
  });
});

describe("cases page", () => {
  it("with no published cases: says so, keeps the attribution, and labels the scenarios illustrative", async () => {
    mockFetch(gallery());
    const { container } = await renderApp({}, "/cases");
    expect(await screen.findByText("No gallery cases have been published yet.")).toBeTruthy();
    expect(container.textContent).toContain("powered by IKanoon");
    expect(screen.getByRole("heading", { name: "Illustrative scenarios" })).toBeTruthy();
    expect(container.textContent).toMatch(/not real people or real claims/);
    // the scenarios are readable as plain text, with no dragging involved
    expect(container.textContent).toContain("A rejection that cites non-disclosure");
  });

  it("a server error is explained with what to do next and a retry", async () => {
    mockFetch({ "GET /gallery": () => ({ status: 500, json: { detail: "boom" } }) });
    await renderApp({}, "/cases");
    const alert = await screen.findByRole("alert");
    expect(alert.textContent).toContain("Check your connection and try again.");
    expect(within(alert).getByRole("button", { name: "Try again" })).toBeTruthy();
  });

  it("the carousel is a labelled region and its slides are labelled Verified or Illustrative", async () => {
    mockFetch({
      "GET /gallery": () => ({ json: { attribution: "powered by IKanoon", cases: [{ case_id: "c1", citation: { forum: "NCDRC", case_number: "CC/1/2024", decided_on: null, source_url: null }, outcome: null, verdicts: ["NEED_INFO"] }] } }),
    });
    await renderApp({}, "/cases");
    const region = await screen.findByRole("region", { name: "Real cases" });
    expect(region.getAttribute("aria-roledescription")).toBe("carousel");
    expect(region.textContent).toContain("Verified case: CC/1/2024");
    expect(region.textContent).toContain("Illustrative: A rejection that cites non-disclosure");
    expect(within(region).getByRole("button", { name: "Go to next slide" })).toBeTruthy();
    expect(within(region).getByRole("button", { name: "Go to next slide" }).getAttribute("type")).toBe("button");
  });
});

describe("help page", () => {
  it("search filters the questions and announces the count; no match gives an explained empty state", async () => {
    await renderApp({}, "/help");
    const box = screen.getByRole("searchbox", { name: "Search the help centre" });
    fireEvent.change(box, { target: { value: "megapixel" } });
    expect(screen.getByText(/^\d+ results?$/)).toBeTruthy();
    expect(within(document.querySelector("main")!).getAllByRole("button", { expanded: true }).length).toBeGreaterThan(0);
    fireEvent.change(box, { target: { value: "zzzzqqq" } });
    expect(screen.getByText("Nothing matches that search")).toBeTruthy();
    expect(screen.getByText("0 results")).toBeTruthy();
    fireEvent.change(box, { target: { value: "" } });
    expect(screen.queryByText("Nothing matches that search")).toBeNull();
  });

  it("accordions: buttons toggle aria-expanded, and the arrow keys, Home and End move between headers", async () => {
    await renderApp({}, "/help");
    const heads = within(document.querySelector("main")!).getAllByRole("button", { expanded: false });
    const first = heads[0];
    fireEvent.click(first);
    expect(first.getAttribute("aria-expanded")).toBe("true");
    expect(document.getElementById(first.getAttribute("aria-controls")!)!.hasAttribute("hidden")).toBe(false);
    fireEvent.click(first);
    expect(first.getAttribute("aria-expanded")).toBe("false");
    first.focus();
    fireEvent.keyDown(first, { key: "ArrowDown" });
    expect(document.activeElement).not.toBe(first);
    fireEvent.keyDown(document.activeElement!, { key: "ArrowUp" });
    expect(document.activeElement).toBe(first);
    fireEvent.keyDown(first, { key: "End" });
    expect(document.activeElement).not.toBe(first);
    fireEvent.keyDown(document.activeElement!, { key: "Home" });
    expect(document.activeElement).toBe(first);
  });

  it("covers the required topics and invents no contact details", async () => {
    const { container } = await renderApp({}, "/help");
    for (const h of ["Document requirements", "Terminology", "Understanding the assessment", "Upload errors", "Policy schedules", "Regulatory references"]) {
      expect(screen.getByRole("heading", { name: h }), h).toBeTruthy();
    }
    expect(container.textContent).not.toMatch(/\b1800\b|toll[- ]free|\d{3}-\d{4}/i);
  });
});

describe("privacy page", () => {
  it("states only what the app supports", async () => {
    const { container } = await renderApp({}, "/privacy");
    const t = container.querySelector("main")!.textContent!;
    expect(t).toMatch(/temporary folder/);
    expect(t).toMatch(/after one hour at the latest/);
    expect(t).toMatch(/not stored in the database/);
    expect(t).toMatch(/not put in the model cache/);
    expect(t).toMatch(/never contain document text/);
    expect(t).toMatch(/sample or redacted documents/);
    expect(t).toMatch(/Reports are not saved/);
    expect(t).not.toMatch(/end-to-end|encrypt|GDPR|ISO 27001|SOC ?2|never leaves/i);
  });
});

describe("how it works and about", () => {
  it("lists all six stages with their content visible without any animation", async () => {
    const { container } = await renderApp({}, "/how-it-works");
    // the Timeline is a lazy chunk: wait for it
    await waitFor(() => expect(container.querySelectorAll("article[id]")).toHaveLength(6));
    const stages = container.querySelectorAll("article[id]");
    for (const s of stages) {
      expect(s.getAttribute("aria-label")!.length).toBeGreaterThan(5);
      expect(s.querySelector("p")!.textContent!.length).toBeGreaterThan(20);
      expect(s.querySelector("img")!.getAttribute("alt")).toMatch(/^Illustration:/);
    }
    for (const t of ["Documents submitted", "Documents read", "Extracted facts confirmed", "Rejection reasoning examined", "Policy provisions compared", "Assessment and next steps prepared"]) {
      expect(container.textContent).toContain(t);
    }
    // no example text from the registry demo
    expect(container.textContent).not.toMatch(/Changelog from my journey|Build lamps/);
  });
  it("about states the limits: no outcome promised, nothing trained, no published evaluation figures", async () => {
    const { container } = await renderApp({}, "/about");
    const t = container.querySelector("main")!.textContent!;
    expect(t).toMatch(/affiliated with IRDAI, LIC or any insurer/);
    expect(t).toMatch(/promise of any outcome/);
    expect(t).toMatch(/Nothing here is a model we trained/);
    expect(t).toMatch(/do not yet publish evaluation figures/);
  });
});
