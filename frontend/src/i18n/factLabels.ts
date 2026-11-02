// Fallback names for the few facts the Confirm screen must label before the API has sent any
// (manual entry starts with no facts). Copied from sarthi/app/labels.py LABELS; a test pins them there.
// DRAFT: Hindi text is pending human review (Q-007).
export const FALLBACK_LABELS: Record<string, { en: string; hi: string }> = {
  rejection_ground: { en: "reason given for rejection", hi: "अस्वीकृति का बताया गया कारण" },
  claim_date: { en: "claim date", hi: "दावे की तारीख़" },
  admission_date: { en: "hospital admission date", hi: "अस्पताल में भर्ती की तारीख़" },
  inception_date: { en: "policy start date", hi: "पॉलिसी शुरू होने की तारीख़" },
  policy_renewal_date: { en: "policy renewal date", hi: "पॉलिसी नवीनीकरण की तारीख़" },
  continuity_confirmed: { en: "cover was continuous", hi: "कवर लगातार था" },
};
