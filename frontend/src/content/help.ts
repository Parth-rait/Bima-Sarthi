import type { QA } from "./faq";

export interface HelpGroup {
  id: string;
  title: string;
  items: QA[];
}

/**
 * Help content, English first. Definitions are general explanations, not legal text. The error rows mirror the app's real
 * error cases (frontend/src/api/client.ts and docs/REACT_MIGRATION_AUDIT.md section 3). No contact details are given because none are sourced.
 */
export const HELP_GROUPS: HelpGroup[] = [
  {
    id: "documents",
    title: "Document requirements",
    items: [
      { id: "doc-what", q: "Which documents should I upload?", a: ["Start with the insurer's rejection or settlement letter, with every page. If you have the policy schedule or policy document, you can add it on the confirm step: it is shown for your reading and never used by the check."] },
      { id: "doc-format", q: "Which file types and sizes are accepted?", a: ["JPG, PNG and PDF. Up to 20 pages and 25 MB in total across all files. A photo can be up to 40 megapixels; larger photos are refused, so use a smaller photo or a PDF."] },
      { id: "doc-photo", q: "How do I take a readable photo?", a: ["Lay the page flat in good light, fill the frame, and keep the text sharp. Take one photo per page. Rotated or blurry pages can be misread, which is why you confirm every fact."] },
      { id: "doc-none", q: "I only have a photo of the letter. Is that enough?", a: ["Yes. The policy document is optional. The check starts from the letter."] },
    ],
  },
  {
    id: "terms",
    title: "Terminology",
    items: [
      { id: "t-repudiation", q: "Repudiation, rejection, disallowance", a: ["Words insurers use when they refuse to pay all or part of a claim. A part-payment means some amounts were deducted or disallowed."] },
      { id: "t-schedule", q: "Policy schedule and policy wording", a: ["The schedule is the short document listing your policy number, dates, insured people and sum insured. The wording is the full terms and conditions."] },
      { id: "t-waiting", q: "Waiting period", a: ["A period after the policy starts, or after a condition is declared, during which some claims are not payable. Which waiting periods apply is stated in your policy."] },
      { id: "t-pre", q: "Pre-existing disease", a: ["A condition that was present before the policy began. Insurers often cite it as a reason for rejection."] },
      { id: "t-nondisclosure", q: "Non-disclosure", a: ["An insurer's statement that something relevant was not declared when the policy was taken."] },
      { id: "t-deductions", q: "Deductions: room rent, sub-limits, non-payable items", a: ["Amounts taken off a bill. A room-rent limit or sub-limit caps what is paid for a particular item. Non-payable items are things an insurer's standard list says it does not cover."] },
      { id: "t-grievance", q: "Grievance and Ombudsman", a: ["A grievance is a formal complaint to the insurer. The Insurance Ombudsman handles complaints from policyholders under the Insurance Ombudsman Rules, 2017. The app shows the dates that apply, counted only from dates you enter."] },
    ],
  },
  {
    id: "assessment",
    title: "Understanding the assessment",
    items: [
      { id: "a-verdicts", q: "What do the three verdicts mean?", a: ["Possible inconsistency to raise with the insurer (a triangle): the facts you confirmed differ from what a rule expects. No ground to challenge under this rule (a square with a tick): the rule gives no ground, which is not the same as good news. Need more information (a circle with a question mark): something is missing, and the app tells you what."] },
      { id: "a-quote", q: "What are the quotes and page numbers?", a: ["Each finding shows the rule's own words and the page they came from, and the facts it used, each with its source line. You can compare them with the originals."] },
      { id: "a-ref", q: "What is a Rule reference?", a: ["A short identifier for the rule card that produced a finding. It is shown for traceability. It is not a legal citation."] },
      { id: "a-dates", q: "Why are my deadline dates missing?", a: ["Dates are shown only when you have entered the date you sent your complaint. The app never assumes a date for you. Add it on the result page and the dates appear."] },
      { id: "a-nofinding", q: "What if the app says it has no checked rule for my reason?", a: ["It means no rule card covers that reason yet. This does not mean the insurer's decision is correct."] },
    ],
  },
  {
    id: "errors",
    title: "Upload errors",
    items: [
      { id: "e-type", q: "\"Only JPG, PNG and PDF files are accepted\"", a: ["What happened: a file of another type was chosen. What to do: choose a JPG, PNG or PDF, or take a photo of the page."] },
      { id: "e-size", q: "\"Uploads are limited to 25 MB in total\"", a: ["What happened: the files together are bigger than the limit. What to do: remove a file, or use smaller photos, then press the read button again."] },
      { id: "e-pages", q: "\"Uploads are limited to 20 pages in total\"", a: ["What happened: the documents have more than 20 pages together. What to do: upload only the pages that matter, starting with the letter."] },
      { id: "e-open", q: "\"This file could not be opened\"", a: ["What happened: the file is damaged or is not really a JPG, PNG or PDF. What to do: save or photograph it again and choose the new file."] },
      { id: "e-reader", q: "The documents could not be read right now", a: ["What happened: the reading service did not answer. What to do: try again in a moment, or choose \"Enter the facts myself instead\" and type the facts from your letter."] },
      { id: "e-expired", q: "\"Your session has expired\"", a: ["Sessions last up to one hour and live in the server's memory. What to do: start again. Your files were deleted, as promised, so you will need to upload them again."] },
      { id: "e-network", q: "\"We could not reach the server\"", a: ["What happened: your connection dropped, or the service is down. What to do: check your connection and try again."] },
    ],
  },
  {
    id: "schedules",
    title: "Policy schedules",
    items: [
      { id: "s-terms", q: "What does \"What your policy says\" show?", a: ["Key terms read from the policy you added, such as the sum insured, each next to its exact words and page. You can confirm or correct each one. They are display only and never change a verdict."] },
      { id: "s-remove", q: "Can I remove the policy terms?", a: ["Yes. \"Remove policy terms\" on the confirm step deletes them from your session."] },
    ],
  },
  {
    id: "sources",
    title: "Regulatory references",
    items: [
      { id: "r-sources", q: "Where do the rules come from?", a: ["Rule cards are written from published regulations and circulars, for example the Insurance Ombudsman Rules, 2017, and IRDAI's regulations and master circulars on health insurance. A person approves every card."] },
      { id: "r-exact", q: "How do I see the exact wording behind a finding?", a: ["Each finding on the result page quotes the rule and its page number. Look for the Rule quote under the verdict. Where the app has no verified source link, it shows none rather than guessing."] },
      { id: "r-contacts", q: "Where are the contact details of the Ombudsman or the insurer?", a: ["They are not listed here, because none have been verified for this app. Your insurer's letter and policy documents name its grievance contact."] },
    ],
  },
];
