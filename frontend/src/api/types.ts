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

// ---- scheme finder (Maharashtra agriculture workers) ----
export type SchemeStatus = "likely" | "check" | "not_eligible";
export type SchemeGroupKey = "start" | "ask" | "not_now";
export type SchemeQuestionId = "work" | "age" | "bank" | "ration";

export interface SchemeQuestionOption {
  value: string;
  label: Bilingual;
}
export interface SchemeQuestion {
  id: SchemeQuestionId;
  text: Bilingual;
  hint: Bilingual;
  options: SchemeQuestionOption[];
}
export interface SchemeGroup {
  title: Bilingual;
  intro: Bilingual;
}
export interface SchemeStatusMeta {
  label: Bilingual;
  sentence: Bilingual;
}
export interface SchemeCatalogue {
  version: number;
  checked_on: string;
  state: string;
  audience: Bilingual;
  disclaimer: Bilingual;
  questions: SchemeQuestion[];
  statuses: Record<SchemeStatus, SchemeStatusMeta>;
  groups: Record<SchemeGroupKey, SchemeGroup>;
  scheme_count: number;
}
export interface SchemeSource {
  name: Bilingual;
  url: string;
  note: Bilingual;
}
export interface SchemeResult {
  id: string;
  name: Bilingual;
  short: Bilingual;
  status: SchemeStatus;
  status_label: Bilingual;
  status_sentence: Bilingual;
  group: SchemeGroupKey;
  why: Bilingual;
  what: Bilingual;
  cover: Bilingual;
  eligibility: Bilingual;
  steps: Bilingual[];
  fails: Bilingual[];
  official_url: string;
  source: SchemeSource;
  verified_on: string;
  premium?: Bilingual;
  deadline?: Bilingual;
  /** Present only on insurance schemes: the claim check's type of insurance for a rejected claim. */
  claim_product_line?: "health" | "life" | "accident" | "motor" | "crop" | "credit_life" | "other";
}
export interface SchemeAnswers {
  work: string;
  age: string;
  bank: string;
  ration: string;
}
export interface SchemeMatch {
  checked_on: string;
  state: string;
  disclaimer: Bilingual;
  groups: Record<SchemeGroupKey, SchemeGroup>;
  statuses: Record<SchemeStatus, SchemeStatusMeta>;
  results: SchemeResult[];
}

// ---- gallery ----
export interface EvidenceRate {
  of: number;
  rate: number;
  agree?: number;
  false_hope?: number;
}
export interface EvidenceMethod {
  scorable_findings: number;
  agreement: EvidenceRate | null;
  false_hope_rate: EvidenceRate | null;
  abstained_findings: number;
  excluded_findings: number;
  quote_coverage: number | null;
  stability: number | null;
  safe_abstention: { safe: number; of: number } | null;
  cost_usd: number;
}
export interface EvidenceSummary {
  run_id: string | null;
  generated_on: string;
  repeats: number;
  n_cases: number;
  n_skipped_no_facts: number;
  n_eligible: number;
  n_skipped_unresolved: number;
  n_out_of_scope: number;
  n_no_usable: number;
  methods: Record<string, EvidenceMethod>;
  limitation: string;
}
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
  /** Direction-corrected winner; the raw `outcome` can say "dismissed" for a policyholder win (an insurer's appeal). */
  policyholder_prevailed?: boolean | null;
  rejection_ground?: string | null;
  days_to_decision?: number | null;
  policy_years_at_claim?: number | null;
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
  policyholder_prevailed?: boolean | null;
  relief_amount: number | null;
  rejection_ground?: string | null;
  days_to_decision?: number | null;
  policy_years_at_claim?: number | null;
  licence_note: string | null;
  findings: Finding[];
  attribution: string;
}

export interface Health {
  status: "ok";
}
