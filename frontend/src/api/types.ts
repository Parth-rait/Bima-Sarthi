/** Typed shapes of the FastAPI responses (sarthi/app/main.py). Derived from the routes and tests. */

export type Verdict = "CONSISTENT" | "CHALLENGEABLE" | "NEED_INFO";
export type Bilingual = { en: string; hi: string };

export type FactStatus = "verified" | "needs_confirmation" | "user_confirmed";
export type Confidence = "high" | "medium" | "low";

/** One row of a deductions fact. */
export interface DeductionItem {
  item: string;
  amount?: number | string | null;
  reason?: string | null;
  nonpayable_listed?: boolean | null;
  [k: string]: unknown;
}

export type FactScalar = string | number | boolean | null;
export type FactValueData = FactScalar | string[] | DeductionItem[] | Record<string, unknown>[];

export interface Fact {
  key: string;
  label: Bilingual;
  value: FactValueData;
  quote: string | null;
  page_no: number | null;
  confidence: Confidence;
  status: FactStatus;
}
export type FactMap = Record<string, Fact>;

export interface SessionCreated {
  session_id: string;
}

export interface FactsResponse {
  facts: FactMap;
  needs_confirmation: string[];
}

export interface ExtractResponse extends FactsResponse {
  pages: number;
  reader_backend: string | null;
  product_line_hint: string | null;
}

export interface FactEdit {
  value?: unknown;
  confirm?: boolean;
  clear?: boolean;
}
export interface FactsBody {
  facts: Record<string, FactEdit>;
  insurer_reply_date?: string;
}

/** A fact as used by a finding (a subset of Fact, dumped by the rule engine). */
export interface FactUsed {
  value?: unknown;
  quote?: string | null;
  page_no?: number | null;
  [k: string]: unknown;
}

export interface Finding {
  rule_id: string;
  rule_version: number;
  verdict: Verdict;
  reason: string | null;
  rule_quote: string;
  source_sha256: string;
  page_no: number | null;
  facts_used: Record<string, FactUsed>;
  question_en: string | null;
  question_hi: string | null;
  action_en: string | null;
  action_hi: string | null;
}

export interface DateDisplay {
  iso: string;
  display: string;
}

export interface DeadlineSource {
  quote?: string | null;
  page_no?: number | null;
  source_id?: string | null;
  value?: number | null;
  unit?: string | null;
  label?: Bilingual | null;
}

export interface Deadlines {
  available: boolean;
  note?: string;
  letter_available?: boolean;
  letter_date?: DateDisplay | null;
  insurer_reply_by?: DateDisplay | null;
  ombudsman_earliest?: DateDisplay | null;
  ombudsman_latest?: DateDisplay | null;
  ombudsman_note?: string;
  sources?: Partial<
    Record<"insurer_reply_by" | "ombudsman_earliest" | "ombudsman_latest", DeadlineSource>
  >;
  rule_id?: string;
  rule_quote?: string;
  page_no?: number | null;
  source_sha256?: string;
}

export interface PlanItem {
  key: string | null;
  rule_id: string | null;
  text: Bilingual | null;
  quote: string | null;
  page_no: number | null;
  source_id: string | null;
  source_title: string | null;
  source_label: Bilingual | null;
  date: DateDisplay | null;
  date_label: Bilingual | null;
  link: "letter" | null;
}
export interface PlanStep {
  id: string;
  title: Bilingual;
  items: PlanItem[];
}
export interface Plan {
  kind: "health" | "general";
  supported: boolean;
  product_line: string;
  unverified: unknown;
  title: Bilingual;
  steps: PlanStep[];
  text: Bilingual;
  verified: boolean;
}

export interface RequestChecklist {
  verified: boolean;
  title: Bilingual;
  intro: Bilingual;
  items: Bilingual[];
  text: Bilingual;
}

export type LabelMap = Record<string, Bilingual>;

export interface CheckResponse {
  supported: boolean;
  product_line: string;
  findings: Finding[];
  deadlines: Deadlines;
  plan: Plan | null;
  request_checklist: RequestChecklist | null;
  labels: LabelMap;
  reader_backend: string | null;
}

export interface ExplainResponse {
  text: string;
  used_model: boolean | string | null;
  findings: Finding[];
  deadlines: Deadlines;
  plan: Plan | null;
  request_checklist: RequestChecklist | null;
  labels: LabelMap;
  reader_backend: string | null;
}

// ---- policy key terms (display only) ----
export type PolicyState = "found" | "confirmed" | "entered" | "unverified" | "conflict" | "absent";
export interface PolicyTerm {
  key: string;
  label: Bilingual;
  state: PolicyState;
  status: FactStatus | null;
  value: unknown;
  display: Bilingual | null;
  quote: string | null;
  page_no: number | null;
  confidence: Confidence | null;
  message: Bilingual | null;
}
export interface PolicyView {
  verified: boolean;
  heading: Bilingual;
  disclaimer: Bilingual;
  terms: PolicyTerm[];
  text: Bilingual;
}
export interface PolicyResponse {
  policy: PolicyView | null;
}
export interface PolicyExtractResponse extends PolicyResponse {
  pages: number;
  reader_backend: string | null;
}
export interface PolicyBody {
  terms: Record<string, FactEdit>;
}

// ---- gallery ----
export interface GalleryCitation {
  forum: string | null;
  case_number: string | null;
  decided_on: string | null;
  source_url: string | null;
}
export interface GalleryListItem {
  case_id: string;
  citation: GalleryCitation;
  outcome: string | null;
  verdicts: Verdict[];
}
export interface GalleryList {
  attribution: string;
  cases: GalleryListItem[];
}
export interface GalleryCase {
  case_id: string;
  citation: GalleryCitation;
  insurer: string | null;
  outcome: string | null;
  relief_amount: number | null;
  licence_note: string | null;
  findings: Finding[];
  attribution: string;
}

export interface Health {
  status: "ok";
}
