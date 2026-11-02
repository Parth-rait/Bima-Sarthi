import type { CheckResponse, ExplainResponse, Fact, FactMap, Finding, PolicyView } from "../api";

export const fact = (key: string, p: Partial<Fact> = {}): Fact => ({
  key,
  label: { en: key.replaceAll("_", " "), hi: key },
  value: "x",
  quote: "a line from the letter",
  page_no: 1,
  confidence: "high",
  status: "verified",
  ...p,
});

export const FACTS: FactMap = {
  rejection_ground: fact("rejection_ground", {
    label: { en: "reason given for rejection", hi: "अस्वीकृति का बताया गया कारण" },
    value: "pre_existing_disease",
    quote: "claim repudiated: pre-existing disease",
    status: "needs_confirmation",
  }),
  inception_date: fact("inception_date", {
    label: { en: "policy start date", hi: "पॉलिसी शुरू होने की तारीख़" },
    value: "01/04/2019",
    quote: "Policy start 01/04/2019",
    page_no: 2,
  }),
  fraud_alleged: fact("fraud_alleged", {
    label: { en: "fraud alleged", hi: "धोखाधड़ी का आरोप" },
    value: false,
    quote: null,
    page_no: null,
    status: "needs_confirmation",
    confidence: "low",
  }),
};

export const finding = (verdict: Finding["verdict"], rule_id = "MORATORIUM_60M"): Finding => ({
  rule_id,
  rule_version: 1,
  verdict,
  reason: null,
  rule_quote: "After sixty continuous months no claim shall be contestable.",
  source_sha256: "ab".repeat(32),
  page_no: 7,
  facts_used: {
    inception_date: { value: "01/04/2019", quote: "Policy start 01/04/2019", page_no: 2 },
  },
  question_en: verdict === "NEED_INFO" ? "Was your cover continuous?" : null,
  question_hi: null,
  action_en: verdict === "CONSISTENT" ? null : "Write to the grievance cell.",
  action_hi: null,
});

export const GRIEVANCE_QUOTE = "The insurer shall reply within fourteen days.";

export const check = (over: Partial<CheckResponse> = {}): CheckResponse => ({
  supported: true,
  product_line: "health",
  findings: [finding("CONSISTENT", "R_OK"), finding("CHALLENGEABLE"), finding("NEED_INFO", "R_ASK")],
  deadlines: {
    available: true,
    letter_available: true,
    letter_date: { iso: "2026-11-02", display: "02/11/2026" },
    insurer_reply_by: { iso: "2026-11-16", display: "16/11/2026" },
    ombudsman_earliest: { iso: "2026-12-02", display: "02/12/2026" },
    ombudsman_latest: { iso: "2027-11-02", display: "02/11/2027" },
    sources: {},
    rule_id: "GRIEVANCE_ROUTE",
    rule_quote: GRIEVANCE_QUOTE,
    page_no: 3,
    source_sha256: "cd".repeat(32),
    note: "Counted from today's date; see the rule quote for the source.",
  },
  plan: null,
  request_checklist: null,
  labels: { inception_date: { en: "policy start date", hi: "पॉलिसी शुरू होने की तारीख़" } },
  reader_backend: "gemini",
  ...over,
});

export const explain = (over: Partial<ExplainResponse> = {}): ExplainResponse => {
  const c = check();
  return {
    text: "On the facts in your documents, there is a documented possible inconsistency.",
    used_model: false,
    findings: c.findings,
    deadlines: c.deadlines,
    plan: c.plan,
    request_checklist: c.request_checklist,
    labels: c.labels,
    reader_backend: "gemini",
    ...over,
  };
};

export const POLICY: PolicyView = {
  verified: true,
  heading: { en: "What your policy says", hi: "आपकी पॉलिसी क्या कहती है" },
  disclaimer: { en: "This shows what the uploaded document says.", hi: "यह दिखाता है।" },
  terms: [
    {
      key: "sum_insured",
      label: { en: "Sum insured", hi: "बीमित राशि" },
      state: "found",
      status: "verified",
      value: 500000,
      display: { en: "₹5,00,000", hi: "₹5,00,000" },
      quote: "Sum Insured: Rs. 5,00,000",
      page_no: 1,
      confidence: "high",
      message: null,
    },
    {
      key: "co_payment",
      label: { en: "Co-payment", hi: "सह-भुगतान" },
      state: "absent",
      status: null,
      value: null,
      display: null,
      quote: null,
      page_no: null,
      confidence: null,
      message: { en: "Not found in the pages we read.", hi: "नहीं मिला।" },
    },
  ],
  text: { en: "", hi: "" },
};

/** A session that has a finished result (what the check screen leaves behind). */
export const resultSession = (over: Record<string, unknown> = {}) => {
  const c = check();
  return {
    view: "result" as const,
    sid: "s1",
    reportId: "rep-1",
    facts: FACTS,
    result: {
      supported: true,
      productLine: "health",
      findings: c.findings,
      deadlines: c.deadlines,
      plan: null,
      checklist: {
        verified: true,
        title: { en: "Documents to request", hi: "x" },
        intro: { en: "Ask the insurer for:", hi: "x" },
        items: [
          { en: "The full claim file", hi: "x" },
          { en: "The policy wording in force on the claim date", hi: "x" },
        ],
        text: { en: "", hi: "" },
      },
      text: "Explanation text.",
      explainFailed: false,
    },
    ...over,
  };
};
