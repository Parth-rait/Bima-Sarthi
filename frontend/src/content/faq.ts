/**
 * Editorial copy, English first. Every statement here is checked against PRODUCT.md, DESIGN.md, sarthi/app/main.py or
 * docs/ground-truth/GROUND_TRUTH.md. No outcome is promised and no figure is stated without its source.
 */
export interface QA {
  id: string;
  q: string;
  a: string[];
}

export const FAQ: QA[] = [
  {
    id: "advice",
    q: "Is this legal or medical advice?",
    a: ["No. This is a rules check, not legal or medical advice. Bima Sarthi is an independent project, not affiliated with IRDAI, LIC or any insurer. It is not a lawyer, a regulator or an insurer, and it says nothing about treatment or diagnosis."],
  },
  {
    id: "decide",
    q: "Does Bima Sarthi decide whether my claim was valid?",
    a: ["No. It compares the insurer's stated reason with written rules and shows exactly what it compared. A finding marked \"Possible inconsistency to raise with the insurer\" is a reason to ask the insurer a question. It is not a promise of any outcome."],
  },
  {
    id: "models",
    q: "Do AI models decide the result?",
    a: [
      "No. Models read the pages and help phrase the explanation. The verdict comes only from the rule engine, using rule cards that a person has approved. Each card quotes its regulation, and that quote is checked word for word against the stored source page.",
      "Written explanations are also checked: one that adds a number or a promise that is not in the findings is rejected.",
    ],
  },
  {
    id: "claims",
    q: "Which claims can it check?",
    a: ["Health-insurance claims: full rejections, part-payments and cashless delays. For other types of insurance you get a general plan and no verdict, and the page says so."],
  },
  {
    id: "confirm",
    q: "Why do I have to confirm what it read?",
    a: ["A photo can be blurry, rotated or ambiguous; a date such as 05/03/2024 can be read two ways. Each fact is shown next to the line it was read from. Facts the app is unsure of are marked Please confirm, and the rules do not run until you have confirmed them."],
  },
  {
    id: "documents",
    q: "What happens to my documents?",
    a: [
      "Your files are kept in a temporary folder on the server, deleted as soon as the check has run, and at the latest after one hour. They are never written to the database, the model cache or the logs.",
      "The page images are sent to a model provider so they can be read. Some free-tier providers may use inputs, so while the project is being tested, please use sample or redacted documents. The Privacy page has the full list.",
    ],
  },
  {
    id: "hindi",
    q: "Is Hindi supported?",
    a: ["Yes, as a toggle in the top bar. The Hindi text is a draft that is still waiting for human review (Q-007), and it is built from fixed templates, not free-form model output. The long reading pages on this site are English-first for now."],
  },
  {
    id: "account",
    q: "Do I need an account?",
    a: ["No. There is no sign-in. You upload, confirm, read the result and leave. Nothing is kept for later: if you reload the page, the session in your browser is gone."],
  },
];
