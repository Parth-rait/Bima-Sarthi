# Plan of Action: current behaviour and the personalisation seam

Date: 2 Nov 2026. Scope: documentation of the existing Plan of Action pipeline and the seam
where future personalisation would attach. This pass recorded the existing behaviour; the
template-based personalisation it describes was then implemented on the same date (section 5).

## 1. What the plan is today

The plan is generated automatically by the backend as part of the check response. The user
never asks for it and there is no separate endpoint.

| Path | Builder | Returned when | Key behaviour |
|---|---|---|---|
| General (non-health) | `sarthi/app/plan.py:general_plan` | `product_line` is `life`, `motor`, `accident`, `crop`, `credit_life` or `other` | No rules run and no verdict is produced. `life`, `motor` and `accident` get insurer/Ombudsman steps with verbatim quoted sources; `crop`, `credit_life` and `other` explicitly say the route is not verified and list no route claims. |
| Health | `sarthi/app/plan.py:health_plan` | `product_line` is `health`, all facts are confirmed and the rule cards load | Findings are ordered CHALLENGEABLE, NEED_INFO, CONSISTENT; asks are built from each finding's question/action; letter and Ombudsman steps appear only when there is a CHALLENGEABLE finding and the approved grievance card exists. |

Both builders return the same `Plan` shape (`kind`, `supported`, `product_line`, `unverified`,
`title`, `steps`, `text`, `verified`). Steps and items are fixed bilingual templates; no model
and no network are used. Every route statement carries a `quote`, `page_no` and `source_id`
from the stored official texts. Dates are computed only from dates the user entered and from
the approved `GRIEVANCE_ROUTE` card's nested params; with no complaint date the plan shows
"Add the date you sent your complaint..." instead of a date.

`plan.finalize` (`sarthi/app/plan.py:488`) renders the plan to plain text in English and Hindi
and runs the existing `verify()` self-check on both. A plan that fails verification is dropped
(`plan: null`) and the result screen simply omits the section. In the UI, `ResultScreen`
renders `result.plan` unconditionally when present (`frontend/src/screens/ResultScreen.tsx:113`)
via `PlanSection` (`frontend/src/components/Plan.tsx:68`). The component only maps the existing
shape; it computes no dates and makes no decisions.

Related response fields are independent of the plan: `request_checklist` (NEED_INFO or a
deduction-related reason) and `deadlines` (CHALLENGEABLE finding plus an approved grievance
card). The frontend shows deadline dates only after the user has entered the complaint-sent
date (`DeadlinesBox`, `frontend/src/components/Plan.tsx:113`).

## 2. Verified in this pass

- Plan builder tests: 69 passed (`tests/app/test_plan.py`).
- API tests for both plan paths: 24 passed (`tests/app/test_api.py`, product-line, health and
  general cases).
- Checklist and deadline tests: 32 backend passed (`tests/app/test_checklist.py` plus the
  deadline/complaint selections in `tests/app/test_api.py`); 25 frontend passed
  (`frontend/src/test/screens.test.tsx`, including the "deadlines never show an assumed date"
  group).
- Grievance PDF and its 409 paths: 5 passed (`tests/app/test_api.py`, letter/PDF selections).
- Corrected values in the actual PDF: a full flow was run with initial facts
  (Asha Rao / POL-OLD-1 / OLD-123 / Old Insurer Ltd / 1,00,000), then corrected facts
  (Asha R Rao / POL-NEW-9 / CLM-2026-777 / Corrected General Insurance Co / 2,50,000) and a
  fresh check. Text extracted from the returned PDF contains all five corrected values and
  none of the old ones.
- Editing facts clears `st["findings"]` (`sarthi/app/main.py:425`), so the letter returns 409
  until the check is run again. This is existing, intended behaviour: plan, letter and
  deadlines always derive from the latest facts and the latest check.

## 3. The personalisation seam

The seam is the **builder boundary**, not the rules engine, the API contract or the UI.

- Inputs a future adapter may read, already present in the request/session state:
  `product_line`; user-confirmed `facts`; `findings` with `facts_used`; the approved
  grievance card params; `complaint_sent_date`; `insurer_reply_date`; `claim_amount_inr`;
  and the calculated deadlines.
- Output a future adapter must return: the existing `Plan` dict shape, unchanged. The frontend
  is not expected to change. `PlanSection` already handles both `kind` values, optional dates,
  source labels/quotes, rule chips and the inline letter link.
- Placement: `sarthi/app/main.py:health_plan_json` and `_general_check` are the two call
  sites that turn a builder result into the response. A personalised builder would replace
  the builder call there, not the response object. `plan.finalize` must remain the final gate.
- Verification rules a personalised plan must keep: quotes verbatim with page/source; no
  verdict changes; no legal or medical promises; no dates that are not user-entered or
  derived from approved params; bilingual English and Hindi; the existing `verify()` must pass
  or the plan is omitted.

Examples of personalisation that fit this seam without new product functionality:

- Ordering or emphasising existing steps based on which facts are confirmed or missing.
- Wording that references the user's product line or the insurer's stated reason, using only
  labels and values already in the facts.
- Choosing which existing cited step to surface first when several findings exist.

Examples that do **not** fit: inventing new deadlines, adding unsourced route advice, changing
a finding's verdict, or generating text with a model without a new review, safety and privacy
decision. Hindi plan text is also still a draft pending human review (Q-007).

## 4. Open decisions before personalisation

1. Whether personalisation stays template-based (recommended: it preserves the current
   offline, verifiable properties) or introduces a model, which would need its own safety,
   privacy, caching and evaluation work.
2. Whether a personalised plan should ever differ from the printed text; today the plan text
   is verified in both languages and is what `verify()` checks.
3. Who reviews Hindi wording before any new template ships.

## 5. Implemented: template-based personalisation (2 Nov 2026)

Decision 1 was taken as recommended: **template-based, no model**. The builder boundary and the
`Plan` shape are unchanged; the frontend is unchanged and renders the new step through the
existing `PlanSection` loop.

- **New first step.** Both builders now open with `case` ("Your case" / "आपका मामला"). It names
  the product line and, when the user recorded a reviewed rejection ground that is not awaiting
  confirmation, the reason label. Values come only from `sarthi/app/labels.py`
  (`product_label`, `value_label`); unreviewed, free-text or unconfirmed reason values are
  ignored, so no user-typed text enters the plan.
- **Personalised ask.** When a reviewed ground is present, the generic "ask for the reasons"
  item is replaced by one that names the recorded reason and asks which policy clause the
  insurer relied on. Both languages. No fact, date, quote or verdict is added.
- **Wiring.** `sarthi/app/main.py` passes `st["facts"]` to `health_plan` at `health_plan_json`
  and to `general_plan` in `_general_check`. The builders default to `facts=None`, so callers
  without facts produce the previous output plus the product-line line.
- **Safety gate unchanged.** `plan.finalize` still renders both languages and drops the plan if
  `verify()` fails. Tests cover every reviewed ground in English and Hindi for both plans, plus
  the no-reason and unreviewed-value cases.
- **Decision 2.** The plan text remains the single verified artefact; there is no separate
  personalised string that bypasses `verify()`.
- **Decision 3 (open).** The new Hindi strings are draft pending human review, like the rest of
  the Hindi plan text (Q-007).

Tests: 1,425 backend passed (including 99 in `tests/app/test_plan.py`); frontend typecheck and
250 tests passed with no frontend change.
