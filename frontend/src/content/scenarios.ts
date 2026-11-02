/**
 * Illustrative scenarios: invented to show what the app asks and shows, never real people or real claims,
 * and with no outcome. The real, cited cases come from GET /gallery.
 */
export interface Scenario {
  id: string;
  title: string;
  body: string;
  art: "letter" | "timeline" | "schedule";
  artAlt: string;
}

export const SCENARIOS: Scenario[] = [
  {
    id: "disclosure",
    title: "A rejection that cites non-disclosure",
    body: "The letter says a condition was not declared when the policy began. The app asks you to confirm the policy start date and the claim date, then shows which rule it compared, with the quote and the page. Whether anything is flagged depends on the dates you confirm.",
    art: "letter",
    artAlt: "Illustration: a letter with a highlighted quoted passage and a verdict stamp.",
  },
  {
    id: "gap",
    title: "A gap in cover after a port",
    body: "The policy was ported between insurers and the dates show a gap. The rules cannot tell whether the gap was real, so the app does not guess: it asks you to confirm whether cover was continuous, and shows Need more information until you do.",
    art: "timeline",
    artAlt: "Illustration: a ruled timeline strip with dated notes pinned above and below it.",
  },
  {
    id: "deductions",
    title: "A part-payment with deductions",
    body: "The settlement letter lists deducted items. The app shows each one and asks whether it is on the insurer's standard list of non-payable items. Your answers are what the rules then use, and the result says which rule it compared and where the quote comes from.",
    art: "schedule",
    artAlt: "Illustration: a banded schedule with one row outlined in a dashed line.",
  },
];
