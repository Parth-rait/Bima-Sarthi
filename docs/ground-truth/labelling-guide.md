# Labelling guide (eval_reading)

How Parth labels the consented documents for the reading-accuracy evaluation.

- One JSON file per document, named after the document (for example `doc_01.json`).
- Field names are exactly those of `CaseFactsOut` (see `sarthi/data/case_facts.py`). Do not rename or add fields. The fields are: inception_date, ported_from_date, claim_date, admission_date, rejection_ground, disclosed_conditions, alleged_undisclosed_condition, fraud_alleged, deductions, cashless_request_at, decision_at, discharge_request_at, final_auth_at, cited_clause, crc_approval_mentioned, reasons_cite_terms, renewal_gap_days, policy_renewal_date.
- Dates: ISO `YYYY-MM-DD`. Times: 24-hour `HH:MM` where the document gives a time.
- Amounts: plain numbers in rupees, no `₹`, commas or words (write `150000`, not `₹1,50,000` or `1.5 lakh`).
- If a field is not in the document, leave it `null`. Never guess.
- Booleans are `true` or `false`; use `null` if the document does not say.
- Label from the document only, not from what you know about the case.
- The labelled files and the consented documents stay outside the repo (never under the project folder, never committed).
