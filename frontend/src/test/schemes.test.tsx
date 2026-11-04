import { fireEvent, screen, waitFor, within } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";
import type { SchemeCatalogue, SchemeGroupKey, SchemeMatch, SchemeResult, SchemeStatus } from "../api";
import { mockFetch } from "./mockFetch";
import { renderApp } from "./render";

afterEach(() => {
  vi.unstubAllGlobals();
});

const bi = (en: string, hi: string) => ({ en, hi });

const STATUS: Record<SchemeStatus, { label: ReturnType<typeof bi>; sentence: ReturnType<typeof bi> }> = {
  likely: { label: bi("Likely eligible", "संभावित पात्र"), sentence: bi("Your answers match the main conditions.", "आपके उत्तर मुख्य शर्तों से मिलते हैं।") },
  check: { label: bi("Check with the office", "कार्यालय से पूछें"), sentence: bi("One condition needs checking.", "एक शर्त जाँचनी होगी।") },
  not_eligible: { label: bi("Not eligible from your answers", "आपके उत्तरों से पात्र नहीं"), sentence: bi("From your answers, this one does not fit.", "आपके उत्तरों से यह योजना नहीं बैठती।") },
};

const GROUPS: Record<SchemeGroupKey, { title: ReturnType<typeof bi>; intro: ReturnType<typeof bi> }> = {
  start: { title: bi("Start with these", "इनसे शुरू करें"), intro: bi("The main conditions match your answers.", "मुख्य शर्तें आपके उत्तरों से मिलती हैं।") },
  ask: { title: bi("Ask about these", "इनके बारे में पूछें"), intro: bi("One condition needs a document.", "एक शर्त के लिए कागज़ चाहिए।") },
  not_now: { title: bi("These do not fit your answers", "ये आपके उत्तरों से नहीं बैठतीं"), intro: bi("Open each one to see why.", "कारण देखने के लिए खोलें।") },
};

const CATALOGUE: SchemeCatalogue = {
  version: 1,
  checked_on: "2026-11-02",
  state: "Maharashtra",
  audience: bi("Agriculture workers", "कृषि श्रमिक"),
  disclaimer: bi("This is information, not an eligibility decision.", "यह जानकारी है, पात्रता का फ़ैसला नहीं।"),
  questions: [
    {
      id: "work",
      text: bi("What work do you do?", "आप क्या काम करते हैं?"),
      hint: bi("Choose the closest one.", "जो सबसे मिलता हो वह चुनें।"),
      options: [
        { value: "own_land", label: bi("I farm my own land", "मैं अपनी ज़मीन पर खेती करता हूँ") },
        { value: "farm_labour", label: bi("I work on other people's farms", "मैं दूसरों के खेत पर काम करता हूँ") },
      ],
    },
    {
      id: "age",
      text: bi("How old are you?", "आपकी उम्र क्या है?"),
      hint: bi("This decides which schemes can accept you.", "इससे पता चलता है कौन सी योजना आपको ले सकती है।"),
      options: [
        { value: "18_50", label: bi("18 to 50", "१८ से ५० साल") },
        { value: "51_70", label: bi("51 to 70", "५१ से ७० साल") },
      ],
    },
    {
      id: "bank",
      text: bi("Do you have your own bank or post office account?", "क्या आपका अपना बैंक या डाकघर खाता है?"),
      hint: bi("Two schemes here work through that account.", "यहाँ दो योजनाएँ उसी खाते से चलती हैं।"),
      options: [
        { value: "yes", label: bi("Yes", "हाँ") },
        { value: "no", label: bi("No", "नहीं") },
      ],
    },
    {
      id: "ration",
      text: bi("Does your family have a ration card?", "क्या आपके परिवार का राशन कार्ड है?"),
      hint: bi("Health cover uses a different list.", "स्वास्थ्य योजना दूसरी सूची देखती है।"),
      options: [
        { value: "yes", label: bi("Yes", "हाँ") },
        { value: "no", label: bi("No", "नहीं") },
      ],
    },
  ],
  statuses: STATUS,
  groups: GROUPS,
  scheme_count: 5,
};

function scheme(id: string, name: string, status: SchemeStatus, group: SchemeGroupKey): SchemeResult {
  return {
    id,
    name: bi(name, `${name} हिंदी`),
    short: bi(`Short line for ${name}`, `${name} छोटी पंक्ति`),
    status,
    status_label: STATUS[status].label,
    status_sentence: STATUS[status].sentence,
    group,
    why: bi(`The reason for ${name}`, `${name} का कारण`),
    what: bi(`What ${name} is`, `${name} क्या है`),
    cover: bi(`Cover for ${name}`, `${name} का कवर`),
    eligibility: bi(`Eligibility for ${name}`, `${name} की पात्रता`),
    steps: [bi(`First step for ${name}`, `${name} का पहला कदम`)],
    fails: [bi(`Failure for ${name}`, `${name} की विफलता`)],
    official_url: `https://example.gov.in/${id}`,
    source: { name: bi(`Official source for ${name}`, `${name} का स्रोत`), url: `https://example.gov.in/source-${id}`, note: bi("Read on 2 November 2026.", "२ नवंबर २०२६ को पढ़ा।") },
    verified_on: "2026-11-02",
  };
}

const MATCH: SchemeMatch = {
  checked_on: "2026-11-02",
  state: "Maharashtra",
  disclaimer: CATALOGUE.disclaimer,
  groups: GROUPS,
  statuses: STATUS,
  results: [
    scheme("gopinath_munde", "Gopinath Munde Shetkari Apghat Suraksha", "likely", "start"),
    { ...scheme("pmfby", "PMFBY", "check", "ask"), claim_product_line: "crop" },
    scheme("pmjjby", "PMJJBY", "not_eligible", "not_now"),
  ],
};

function answers() {
  fireEvent.click(screen.getByLabelText("I farm my own land"));
  fireEvent.click(screen.getByLabelText("18 to 50"));
  const bank = screen.getByRole("group", { name: "Do you have your own bank or post office account?" });
  fireEvent.click(within(bank).getByLabelText("Yes"));
  const ration = screen.getByRole("group", { name: "Does your family have a ration card?" });
  fireEvent.click(within(ration).getByLabelText("Yes"));
}

describe("scheme finder", () => {
  it("asks four questions, then shows the three groups in order with a reason and an official source", async () => {
    const calls = mockFetch({
      "GET /api/schemes": () => ({ json: CATALOGUE }),
      "POST /api/schemes/match": () => ({ json: MATCH }),
    });
    await renderApp({}, "/schemes");
    expect(await screen.findByRole("heading", { name: "Four questions" })).toBeTruthy();
    expect(screen.getByText("5 schemes. Each one linked to its official source. Checked on 2 November 2026.")).toBeTruthy();
    answers();
    fireEvent.click(screen.getByRole("button", { name: "Show my schemes" }));

    expect(await screen.findByText("3 schemes: 1 to start, 1 to ask about, 1 that does not fit.")).toBeTruthy();
    const start = screen.getByRole("region", { name: "Start with these" });
    const ask = screen.getByRole("region", { name: "Ask about these" });
    const notNow = screen.getByRole("region", { name: "These do not fit your answers" });
    expect(start.compareDocumentPosition(ask) & Node.DOCUMENT_POSITION_FOLLOWING).toBeTruthy();
    expect(ask.compareDocumentPosition(notNow) & Node.DOCUMENT_POSITION_FOLLOWING).toBeTruthy();

    expect(within(start).getByRole("heading", { name: "Gopinath Munde Shetkari Apghat Suraksha" })).toBeTruthy();
    expect(within(start).getByText("Likely eligible")).toBeTruthy();
    expect(within(start).getByText("The reason for Gopinath Munde Shetkari Apghat Suraksha")).toBeTruthy();
    expect(within(ask).getByText("Check with the office")).toBeTruthy();
    expect(within(notNow).getByText("Not eligible from your answers")).toBeTruthy();
    expect(within(start).getByRole("link", { name: /Open the official page/ }).getAttribute("href")).toBe("https://example.gov.in/gopinath_munde");
    expect(within(start).getByRole("link", { name: /Official source for Gopinath Munde/ }).getAttribute("href")).toBe("https://example.gov.in/source-gopinath_munde");

    // an insurance scheme hands over to the claim check with its type preset; a benefit scheme does not
    expect(within(ask).getByRole("link", { name: "Check the rejection letter" }).getAttribute("href")).toBe("/check-claim?type=crop");
    expect(within(start).queryByRole("link", { name: "Check the rejection letter" })).toBeNull();

    const posted = calls.calls.find((x) => x.key === "POST /api/schemes/match");
    expect(posted?.body).toEqual({ work: "own_land", age: "18_50", bank: "yes", ration: "yes" });
    expect(document.activeElement).toBe(screen.getByRole("heading", { name: "Your schemes" }));
  });

  it("will not send an incomplete form; it marks the first unanswered question", async () => {
    mockFetch({ "GET /api/schemes": () => ({ json: CATALOGUE }) });
    await renderApp({}, "/schemes");
    await screen.findByRole("heading", { name: "Four questions" });
    fireEvent.click(screen.getByRole("button", { name: "Show my schemes" }));
    expect(screen.getByRole("alert").textContent).toContain("Answer all four questions first.");
    expect(document.activeElement).toBe(screen.getByLabelText("I farm my own land"));
  });

  it("explains a load failure and retries", async () => {
    let up = false;
    mockFetch({
      "GET /api/schemes": () => (up ? { json: CATALOGUE } : { status: 503, json: { detail: "down" } }),
    });
    await renderApp({}, "/schemes");
    expect((await screen.findByRole("alert")).textContent).toContain("The questions could not load.");
    up = true;
    fireEvent.click(screen.getByRole("button", { name: "Try again" }));
    expect(await screen.findByRole("heading", { name: "Four questions" })).toBeTruthy();
  });

  it("shows a composed empty state before the first answer", async () => {
    mockFetch({ "GET /api/schemes": () => ({ json: CATALOGUE }) });
    await renderApp({}, "/schemes");
    await screen.findByRole("heading", { name: "Four questions" });
    expect(screen.getByRole("heading", { name: "Your answers will appear here" })).toBeTruthy();
    expect(screen.getByText("Answer the four questions above. The schemes are grouped by what to do next.")).toBeTruthy();
    expect(screen.getByText("Start with these")).toBeTruthy();
    expect(screen.getByText("Ask about these")).toBeTruthy();
    expect(screen.getByText("These do not fit your answers")).toBeTruthy();
  });

  it("is bilingual: the questions, empty state and controls follow the language toggle", async () => {
    mockFetch({ "GET /api/schemes": () => ({ json: CATALOGUE }) });
    await renderApp({ lang: "hi" }, "/schemes");
    expect(await screen.findByRole("heading", { name: "चार सवाल" })).toBeTruthy();
    expect(screen.getByText("आप क्या काम करते हैं?")).toBeTruthy();
    expect(screen.getByRole("button", { name: "मेरी योजनाएँ दिखाएँ" })).toBeTruthy();
    expect(screen.getByRole("heading", { name: "आपके जवाब यहाँ दिखेंगे" })).toBeTruthy();
  });

  it("does not call the matcher until the form is complete", async () => {
    const calls = mockFetch({
      "GET /api/schemes": () => ({ json: CATALOGUE }),
      "POST /api/schemes/match": () => ({ json: MATCH }),
    });
    await renderApp({}, "/schemes");
    await screen.findByRole("heading", { name: "Four questions" });
    fireEvent.click(screen.getByRole("button", { name: "Show my schemes" }));
    await waitFor(() => expect(calls.count("POST /api/schemes/match")).toBe(0));
  });
});
