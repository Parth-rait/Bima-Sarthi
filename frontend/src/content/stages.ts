/** The six stages of a check. Used by the landing page (short form) and /how-it-works (long form). */
export interface Stage {
  id: string;
  title: string;
  short: string;
  long: string[];
  yourPart: string;
  art: "letter" | "schedule" | "timeline" | "folder" | "evidence" | "medical";
  artAlt: string;
}

export const STAGES: Stage[] = [
  {
    id: "upload",
    title: "Documents submitted",
    short: "Photos or PDFs of the rejection or settlement letter, and the policy if you have it.",
    long: [
      "Start with the letter the insurer sent you. If you also have the policy document or schedule, add it: it lets the app show the policy's key terms beside the words they came from.",
      "Files can be JPG, PNG or PDF, up to 20 pages and 25 MB in total. The page checks type and size before anything is sent, and you can preview, replace or remove any file.",
    ],
    yourPart: "folder",
    art: "letter",
    artAlt: "Illustration: a folder of loose sheets with a gold seal, on a soft peach and sky-blue background.",
  },
  {
    id: "extract",
    title: "Documents read",
    short: "A model reads the pages and proposes facts, each with the line it came from.",
    long: [
      "A model reads the page images and proposes facts: dates, the reason given, amounts. Every fact keeps the exact line it was read from and its page number.",
      "The model only reads. It does not decide anything about your claim. If the reader is unavailable you can enter the facts yourself instead.",
    ],
    yourPart: "letter",
    art: "folder",
    artAlt: "Illustration: a letter with a highlighted quoted paragraph and a rose-coloured stamp.",
  },
  {
    id: "confirm",
    title: "Extracted facts confirmed",
    short: "Every fact sits next to its source line. Anything uncertain must be confirmed by you.",
    long: [
      "Each fact is shown with its source line, the page, and an edit box. Facts the reader was unsure of are marked Please confirm and come first.",
      "The rules do not run while a fact is waiting for you. You also choose the type of insurance and the reason the insurer gave from a fixed list, so the app never guesses either.",
    ],
    yourPart: "evidence",
    art: "schedule",
    artAlt: "Illustration: a letter with one highlighted passage and a magnifying glass with a check mark over it.",
  },
  {
    id: "reasoning",
    title: "Rejection reasoning examined",
    short: "The insurer's stated reason is matched to the rules that apply to that kind of reason.",
    long: [
      "The reason the insurer gave decides which rules are relevant: for example a waiting period, a deduction, or a disclosure question. Only rules in force on the claim date are applied.",
      "A recorded gap in cover, or a port between insurers, gives Need information unless you confirm that cover was continuous. The app asks instead of assuming.",
    ],
    yourPart: "timeline",
    art: "timeline",
    artAlt: "Illustration: a ruled timeline strip with five dated notes pinned above and below it.",
  },
  {
    id: "compare",
    title: "Policy provisions compared",
    short: "Confirmed facts are compared with approved rule cards, each quoting its source.",
    long: [
      "The rule engine compares your confirmed facts with approved rule cards. Each card carries a verbatim quote from a regulation and the page it came from, and that quote is verified against the stored page.",
      "If you added the policy, its key terms are shown next to the words and page they came from. They are for your reading only: they never change a verdict.",
    ],
    yourPart: "schedule",
    art: "schedule",
    artAlt: "Illustration: a policy schedule page with banded rows, one row outlined, and a gold seal in the corner.",
  },
  {
    id: "assessment",
    title: "Assessment and next steps prepared",
    short: "A verdict per finding, deadlines from your own dates, a plan, and a letter to download.",
    long: [
      "Each finding gets one of three verdicts, shown as a shape, a word and a sentence: Possible inconsistency to raise with the insurer, No ground to challenge under this rule, or Need more information.",
      "Deadlines are counted only from dates you entered. The plan lists what to ask the insurer, which documents to request, and the escalation route. Where there is something to raise, you can download a grievance letter. The app never sends anything for you.",
    ],
    yourPart: "medical",
    art: "letter",
    artAlt: "Illustration: a medical record sheet with a heartbeat line and a small cross, and a note slipped in front.",
  },
];
