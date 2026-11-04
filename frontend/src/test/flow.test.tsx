import { fireEvent, screen, waitFor, within } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";
import { FACTS, POLICY, check, explain, fact } from "./fixtures";
import { mockFetch } from "./mockFetch";
import { renderApp } from "./render";

afterEach(() => vi.unstubAllGlobals());

const file = (name = "letter.png") => new File(["x"], name, { type: "image/png" });

function chooseFile(f = file()) {
  const input = document.getElementById("files") as HTMLInputElement;
  fireEvent.change(input, { target: { files: [f] } });
}

describe("upload screen", () => {
  it("reads the documents, shows the loading text, and moves to Confirm with the heading focused", async () => {
    let release: () => void = () => {};
    const gate = new Promise<void>((r) => (release = r));
    const m = mockFetch({
      "POST /session": () => ({ json: { session_id: "s1" } }),
      "POST /session/s1/extract": async () => {
        await gate;
        return { json: { facts: FACTS, needs_confirmation: ["rejection_ground", "fraud_alleged"], pages: 1, reader_backend: "gemini", product_line_hint: "health" } };
      },
    });
    await renderApp();
    expect(screen.getByRole("button", { name: "Read my documents" })).toHaveProperty("disabled", true);
    chooseFile();
    fireEvent.click(screen.getByRole("button", { name: "Read my documents" }));
    expect(await screen.findByText("Reading your documents...")).toBeTruthy();
    release();
    const h = await screen.findByRole("heading", { name: "Confirm what we read" });
    await waitFor(() => expect(document.activeElement).toBe(h));
    expect(m.calls.map((c) => c.key)).toEqual(["POST /session", "POST /session/s1/extract"]);
    // only the server hint is pre-selected
    expect((screen.getByLabelText("Type of insurance") as HTMLSelectElement).value).toBe("health");
    expect(document.querySelector('[aria-current="step"]')!.textContent).toBe("2. Confirm");
  });

  for (const status of [502, 503]) {
    it(`a ${status} offers "Enter the facts myself instead" and starts with empty facts`, async () => {
      mockFetch({
        "POST /session": () => ({ json: { session_id: "s1" } }),
        "POST /session/s1/extract": () => ({ status, json: { detail: "We could not read these documents right now. Please try again." } }),
      });
      await renderApp();
      chooseFile();
      fireEvent.click(screen.getByRole("button", { name: "Read my documents" }));
      const alert = await screen.findByRole("alert");
      expect(alert.textContent).toMatch(/could not read/);
      fireEvent.click(within(alert).getByRole("button", { name: "Enter the facts myself instead" }));
      await screen.findByRole("heading", { name: "Confirm what we read" });
      // the rejection reason is always asked for, even with no facts
      expect(screen.getByRole("heading", { name: /reason given for rejection/ })).toBeTruthy();
      expect(document.querySelectorAll("li.fact")).toHaveLength(1);
    });
  }

  it("other errors do not offer manual entry, but show the message in an alert", async () => {
    mockFetch({
      "POST /session": () => ({ json: { session_id: "s1" } }),
      "POST /session/s1/extract": () => ({ status: 413, json: { detail: "Uploads are limited to 25 MB in total." } }),
    });
    await renderApp();
    chooseFile();
    fireEvent.click(screen.getByRole("button", { name: "Read my documents" }));
    const alert = await screen.findByRole("alert");
    expect(alert.textContent).toMatch(/25 MB/);
    expect(screen.queryByRole("button", { name: "Enter the facts myself instead" })).toBeNull();
  });

  it("lets the user remove a chosen file and offers camera capture", async () => {
    await renderApp();
    chooseFile(file("a.png"));
    expect(document.querySelector(".fname")!.textContent).toBe("a.png");
    fireEvent.click(screen.getByRole("button", { name: /Remove/ }));
    expect(document.querySelector(".fname")).toBeNull();
    const cam = document.querySelector('input[capture="environment"]') as HTMLInputElement;
    expect(cam).toBeTruthy();
    expect(screen.getByText("Take a photo")).toBeTruthy();
  });

  it("accepts jpg, png and pdf, multiple", async () => {
    await renderApp();
    const input = document.getElementById("files") as HTMLInputElement;
    expect(input.multiple).toBe(true);
    expect(input.accept).toMatch(/\.jpg/);
    expect(input.accept).toMatch(/\.png/);
    expect(input.accept).toMatch(/\.pdf/);
  });
});

describe("confirm screen", () => {
  const start = (over = {}) => renderApp({ view: "confirm", sid: "s1", facts: FACTS, productHint: "health", ...over });

  it("cannot run the check while facts need confirming: no network call, alert lists them", async () => {
    const m = mockFetch({});
    await start();
    fireEvent.click(screen.getByRole("button", { name: "Run the check" }));
    const alert = screen.getByRole("alert");
    expect(alert.textContent).toMatch(/Please answer or confirm/);
    expect(alert.textContent).toMatch(/fraud alleged/);
    expect(alert.textContent).toMatch(/reason given for rejection/);
    expect(m.fn).not.toHaveBeenCalled();
  });

  it("cannot run without choosing the type of insurance", async () => {
    const m = mockFetch({});
    await start({ productHint: null });
    expect((screen.getByLabelText("Type of insurance") as HTMLSelectElement).value).toBe("");
    fireEvent.click(screen.getByRole("button", { name: "Run the check" }));
    expect(screen.getByRole("alert").textContent).toBe("Please choose the type of insurance before the check runs.");
    expect(m.fn).not.toHaveBeenCalled();
  });

  it("shows every fact with its source quote and page, pending facts first, and API labels", async () => {
    await start();
    const items = [...document.querySelectorAll("li.fact")].map((li) => li.getAttribute("data-key"));
    expect(items).toEqual(["rejection_ground", "fraud_alleged", "inception_date"]);
    const row = document.querySelector('li[data-key="inception_date"]')!;
    expect(row.textContent).toMatch(/policy start date/);
    expect(row.textContent).toMatch(/Policy start 01\/04\/2019/);
    expect(row.textContent).toMatch(/page 2/);
    expect(document.body.textContent).not.toMatch(/inception_date|fraud_alleged|rejection_ground/);
  });

  it("absence booleans have no default answer", async () => {
    await start();
    const radios = within(document.querySelector('li[data-key="fraud_alleged"]') as HTMLElement).getAllByRole("radio") as HTMLInputElement[];
    expect(radios.map((r) => r.checked)).toEqual([false, false]);
  });

  it("lists the insurance types and only those", async () => {
    await start();
    const opts = [...(screen.getByLabelText("Type of insurance") as HTMLSelectElement).options].map((o) => o.text);
    expect(opts).toEqual(["Choose the type of insurance...", "Health", "Life", "Accident", "Motor", "Crop (agriculture)", "Loan-linked or credit-life", "Other"]);
  });

  it("the full happy path: PUT facts, POST check, POST explain, then the Result screen", async () => {
    const m = mockFetch({
      "PUT /session/s1/facts": () => ({ json: { facts: { ...FACTS, rejection_ground: { ...FACTS.rejection_ground, status: "user_confirmed" }, fraud_alleged: { ...FACTS.fraud_alleged, status: "user_confirmed" } }, needs_confirmation: [] } }),
      "POST /session/s1/check": () => ({ json: check() }),
      "POST /session/s1/explain": () => ({ json: explain() }),
    });
    await start();
    const ground = document.querySelector('li[data-key="rejection_ground"]') as HTMLElement;
    fireEvent.click(within(ground).getByLabelText("This is correct"));
    const fraud = document.querySelector('li[data-key="fraud_alleged"]') as HTMLElement;
    fireEvent.click(within(fraud).getByLabelText("No"));
    fireEvent.change(screen.getByLabelText("Claim number"), { target: { value: "CL-1" } });
    fireEvent.change(screen.getByLabelText(/Date the insurer replied/), { target: { value: "01/11/2026" } });
    fireEvent.click(screen.getByRole("button", { name: "Run the check" }));
    const h = await screen.findByRole("heading", { name: "Result" });
    await waitFor(() => expect(document.activeElement).toBe(h));
    const put = m.calls[0].body as { facts: Record<string, unknown>; insurer_reply_date: string };
    expect(put.facts.product_line).toEqual({ value: "health" });
    expect(put.facts.rejection_ground).toEqual({ value: "pre_existing_disease" });
    expect(put.facts.fraud_alleged).toEqual({ value: "no" });
    expect(put.facts.claim_number).toEqual({ value: "CL-1" });
    expect(put.facts).not.toHaveProperty("inception_date"); // unchanged verified fact is not resent
    expect(put.insurer_reply_date).toBe("01/11/2026");
    await waitFor(() => expect(document.body.textContent).toMatch(/documented possible inconsistency/));
    expect(m.calls.map((c) => c.key)).toEqual(["PUT /session/s1/facts", "POST /session/s1/check", "POST /session/s1/explain"]);
    // the result links on to the plan and to a printable report whose address is NOT the server session id
    // (the plan is offered twice on purpose: once in the sticky summary, once in the actions at the end)
    const plans = screen.getAllByRole("link", { name: "Open my action plan" });
    expect(plans.length).toBeGreaterThan(0);
    expect(plans[0].getAttribute("href")).toBe("/action-plan");
    const report = screen.getByRole("link", { name: "Open the printable report" }).getAttribute("href")!;
    expect(report).toMatch(/^\/results\/[0-9a-f-]{8,}$/);
    expect(report).not.toContain("s1");
  });

  it("shows 422 field errors next to their fields", async () => {
    mockFetch({
      "PUT /session/s1/facts": () => ({ status: 422, json: { detail: { message: "Some entries could not be read.", errors: { claim_date: "Enter a real date as DD/MM/YYYY, for example 05/03/2024.", insurer_reply_date: "The date the insurer replied cannot be in the future." } } } }),
    });
    await start({ facts: { ...FACTS, rejection_ground: { ...FACTS.rejection_ground, status: "user_confirmed" }, fraud_alleged: { ...FACTS.fraud_alleged, status: "user_confirmed" } } });
    fireEvent.change(screen.getByLabelText("claim date"), { target: { value: "99/99/9999" } });
    fireEvent.change(screen.getByLabelText(/Date the insurer replied/), { target: { value: "01/01/2099" } });
    fireEvent.click(screen.getByRole("button", { name: "Run the check" }));
    const alert = await screen.findByRole("alert");
    expect(alert.textContent).toMatch(/Please fix:/);
    const claim = screen.getByLabelText("claim date");
    expect(claim.getAttribute("aria-invalid")).toBe("true");
    expect(document.getElementById(claim.getAttribute("aria-describedby")!)!.textContent).toMatch(/Enter a real date/);
    const reply = screen.getByLabelText(/Date the insurer replied/);
    expect(document.getElementById(reply.getAttribute("aria-describedby")!)!.textContent).toMatch(/cannot be in the future/);
  });

  it("a 409 from the check lists the facts that still need confirming", async () => {
    mockFetch({
      "PUT /session/s1/facts": () => ({ json: { facts: FACTS, needs_confirmation: [] } }),
      "POST /session/s1/check": () => ({ status: 409, json: { detail: { message: "Please confirm these facts before the check runs.", needs_confirmation: ["claim_date"] } } }),
    });
    await start({ facts: { ...FACTS, rejection_ground: { ...FACTS.rejection_ground, status: "user_confirmed" }, fraud_alleged: { ...FACTS.fraud_alleged, status: "user_confirmed" } } });
    fireEvent.click(screen.getByRole("button", { name: "Run the check" }));
    const alert = await screen.findByRole("alert");
    expect(alert.textContent).toMatch(/Please confirm these facts/);
    expect(alert.textContent).toMatch(/claim date/);
    expect(screen.getByRole("heading", { name: "Confirm what we read" })).toBeTruthy(); // stays on Confirm
  });

  it("a 409 asking for the product line focuses the select", async () => {
    mockFetch({
      "PUT /session/s1/facts": () => ({ json: { facts: FACTS, needs_confirmation: [] } }),
      "POST /session/s1/check": () => ({ status: 409, json: { detail: { message: "Please choose the type of insurance before the check runs.", needs_product_line: true, needs_confirmation: [] } } }),
    });
    await start({ facts: { ...FACTS, rejection_ground: { ...FACTS.rejection_ground, status: "user_confirmed" }, fraud_alleged: { ...FACTS.fraud_alleged, status: "user_confirmed" } } });
    fireEvent.click(screen.getByRole("button", { name: "Run the check" }));
    await screen.findByRole("alert");
    expect(document.activeElement).toBe(screen.getByLabelText("Type of insurance"));
  });

  it("a non-health product goes through the check and lands on the general plan", async () => {
    mockFetch({
      "PUT /session/s1/facts": () => ({ json: { facts: FACTS, needs_confirmation: [] } }),
      "POST /session/s1/check": () => ({ json: check({ supported: false, product_line: "motor", findings: [], plan: null }) }),
      "POST /session/s1/explain": () => ({ status: 409, json: { detail: "Run the check first." } }),
    });
    await start({ productHint: null, productChoice: "motor", facts: { ...FACTS, rejection_ground: { ...FACTS.rejection_ground, status: "user_confirmed" }, fraud_alleged: { ...FACTS.fraud_alleged, status: "user_confirmed" } } });
    fireEvent.click(screen.getByRole("button", { name: "Run the check" }));
    await screen.findByRole("heading", { name: "Result" });
    expect(document.body.textContent).toMatch(/not a rules check/);
  });

  it("asks the continuity question as Yes / No / Not sure, unanswered by default", async () => {
    await start();
    const group = screen.getByRole("group", { name: /My cover was continuous/ });
    const radios = within(group).getAllByRole("radio") as HTMLInputElement[];
    expect(radios.map((r) => r.parentElement!.textContent)).toEqual(["Yes", "No", "Not sure"]);
    expect(radios.every((r) => !r.checked)).toBe(true);
  });

  it("'Add a missing fact' offers only the dates that were not read", async () => {
    await start({ facts: { ...FACTS, claim_date: fact("claim_date", { value: "05/03/2024" }) } });
    const box = screen.getByRole("heading", { name: "Add a missing fact" }).closest("section")!;
    const labels = [...box.querySelectorAll("label")].map((l) => l.textContent);
    expect(labels).toEqual(["hospital admission date", "policy start date", "policy renewal date"].filter((l) => l !== "policy start date"));
  });

  it("policy key terms: upload, edit, confirm and remove", async () => {
    const m = mockFetch({
      "POST /session/s1/policy/extract": () => ({ json: { policy: POLICY, pages: 1, reader_backend: "gemini" } }),
      "PUT /session/s1/policy": () => ({ json: { policy: { ...POLICY, terms: [{ ...POLICY.terms[0], state: "confirmed" }, POLICY.terms[1]] } } }),
      "DELETE /session/s1/policy": () => ({ json: { deleted: true } }),
    });
    await start();
    fireEvent.change(document.getElementById("policy-files") as HTMLInputElement, { target: { files: [file("policy.pdf")] } });
    fireEvent.click(screen.getByRole("button", { name: "Read my policy" }));
    expect((await screen.findAllByText("Sum insured", { exact: false })).length).toBeGreaterThan(0);
    fireEvent.click(screen.getByLabelText("This is correct", { selector: "#policy-box input" }));
    fireEvent.click(screen.getByRole("button", { name: "Save changes to policy terms" }));
    await waitFor(() => expect(m.count("PUT /session/s1/policy")).toBe(1));
    expect(m.calls.find((c) => c.key === "PUT /session/s1/policy")!.body).toEqual({ terms: { sum_insured: { confirm: true } } });
    await screen.findByText("Confirmed by you");
    fireEvent.click(screen.getByRole("button", { name: "Remove policy terms" }));
    expect(await screen.findByText("Policy terms removed.")).toBeTruthy();
    expect(screen.queryAllByText("Sum insured", { exact: false })).toHaveLength(0);
  });

  it("the Hindi labels of facts come from the API", async () => {
    await start();
    fireEvent.click(screen.getByRole("button", { name: "हिन्दी" }));
    expect(screen.getAllByText(/अस्वीकृति का बताया गया कारण/).length).toBeGreaterThan(0);
    expect(screen.getByText("Hindi text is a draft pending review.", { exact: false })).toBeTruthy();
  });
});
