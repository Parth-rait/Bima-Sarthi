# React migration audit

Date: 2 Nov 2026. Scope: replace the single static page `sarthi/app/static/index.html` with a React 19 + TypeScript + Vite client in `frontend/`, with full functional parity. No Python behaviour, rule card, test or ground-truth value was changed.

## 1. Current architecture

- One FastAPI app, `sarthi/app/main.py`. `GET /` returns `sarthi/app/static/index.html` with `<!--FOOTER-->` replaced by the two required notices (and "Built with Muse Spark Open" when `WRITER_MODEL` or `READER_MODEL` is Spark Open).
- The page is 400 lines of hand-written DOM code (`el()` helper, `textContent` only, no `innerHTML`). It holds all state in module variables (`lang, helper, sid, facts, result, labelMap, backend, productChoice, plHint, policy`) and re-renders whole sections on every change.
- Session state is in server memory (`_SESSIONS`) plus a session folder for page images. TTL 1 hour, swept every 5 minutes. Images are deleted after the check. Nothing about a user is written to the data store, the LLM cache or logs.
- Verdicts come only from the rule engine (`run_rules`) over approved rule cards in `data/bima_sarthi.duckdb` (read-only). Explanations are fixed templates (`templates/en.yaml`, `hi.yaml`), verified by `verify()`. Hindi is a draft pending review (Q-007).
- Deploy: `deploy/Dockerfile.space` (Hugging Face Space, `python:3.12-slim`, uvicorn on 7860). It copies `sarthi/`, `rules/`, `gallery/`, `models.yaml` and the DuckDB snapshot. It does not build or copy a frontend yet.

## 2. Backend routes (the contract the client uses)

All JSON unless noted. Session ids are UUID strings. Examples below come from a real run against the local server with the synthetic letter (values are synthetic).

### `GET /health`
`200 {"status":"ok"}`

### `POST /session`
`200 {"session_id":"83d8dcf1-0bd8-47dd-842b-9501b61b0f52"}`

### `DELETE /session/{sid}`
`200 {"deleted":true}`. `404` if unknown.

### `POST /session/{sid}/extract` (multipart, field `files`, repeated)
Needs a `Content-Length` header (411 otherwise); over 25 MB + 256 KB is 413. Unsupported type or too many pages: 415. Reader failure: 502.
```json
{"facts":{
  "admission_date":{"key":"admission_date","label":{"en":"hospital admission date","hi":"अस्पताल में भर्ती की तारीख़"},
    "value":"10/09/2024","quote":"10/09/2024","page_no":1,"confidence":"high","status":"needs_confirmation"},
  "fraud_alleged":{"key":"fraud_alleged","label":{...},"value":false,"quote":"This letter does not allege fraud.","page_no":1,"confidence":"high","status":"needs_confirmation"},
  "rejection_ground":{"key":"rejection_ground","value":"non-disclosure: diabetes was not declared in the proposal ...","status":"needs_confirmation", ...}
 },
 "needs_confirmation":["inception_date","admission_date","rejection_ground","fraud_alleged","policy_renewal_date"],
 "pages":1,"reader_backend":"gemini_flash","product_line_hint":null}
```
Notes the client relies on: facts are ordered pending-first; `value` is a string (dates DD/MM/YYYY), number, boolean, list of strings, or list of objects (`deductions`: `{item, amount, reason, nonpayable_listed}`); the extracted `rejection_ground` is free text from the document, not one of the 13 listed grounds, so the user must choose a listed one; `product_line_hint` may be null.

### `PUT /session/{sid}/facts`
Request:
```json
{"facts":{
   "product_line":{"value":"health"},
   "rejection_ground":{"value":"non_disclosure"},
   "fraud_alleged":{"value":"no"},
   "inception_date":{"confirm":true},
   "continuity_confirmed":{"clear":true},
   "claim_number":{"value":"CL-1"}},
 "insurer_reply_date":"01/11/2026"}
```
Response `200 {"facts":{...same shape...},"needs_confirmation":[]}`. `422 {"detail":{"message":"Some entries could not be read.","errors":{"claim_date":"Enter a real date as DD/MM/YYYY, for example 05/03/2024.","insurer_reply_date":"The date the insurer replied cannot be in the future. / बीमाकर्ता के जवाब की तारीख़ भविष्य की नहीं हो सकती।"}}}`. Allowed keys: the fact keys, the six letter fields, `product_line`.
**Side effect:** every successful PUT clears the stored findings, so `explain` and `letter.pdf` return 409 until `check` runs again. The client therefore always re-runs the check after saving dates on the Result screen.

### `POST /session/{sid}/check`
Health (`supported:true`):
```json
{"supported":true,"product_line":"health",
 "findings":[{"rule_id":"MORATORIUM_60M","rule_version":1,"verdict":"CHALLENGEABLE","reason":null,
   "rule_quote":"...","source_sha256":"...","page_no":7,
   "facts_used":{"admission_date":{"value":"2024-09-10","quote":"10/09/2024","page_no":1}},
   "question_en":null,"question_hi":null,"action_en":"...","action_hi":"..."}],
 "deadlines":{"available":true,"letter_available":true,"letter_date":{"iso":"2026-11-01","display":"01/11/2026"},
   "insurer_reply_by":{...},"ombudsman_earliest":{...},"ombudsman_latest":{...},
   "rule_id":"GRIEVANCE_ROUTE","rule_quote":"...","page_no":10,"source_sha256":"...",
   "sources":{"insurer_reply_by":{"quote":"...","page_no":..,"source_id":"..","value":14,"unit":"days"}},
   "note":"Counted from the date you sent your complaint; see the rule quote for the source."},
 "plan":{"kind":"health","supported":true,"product_line":"health","unverified":null,"title":{"en":"Your plan","hi":"..."},
   "steps":[{"id":"findings","title":{"en":"...","hi":"..."},"items":[{"key":null,"rule_id":"MORATORIUM_60M","text":{"en":"..","hi":".."},
     "quote":"..","page_no":7,"source_id":null,"source_title":null,"source_label":null,"date":null,"date_label":null,"link":null}]}],
   "text":{"en":"..","hi":".."},"verified":true},
 "request_checklist":null,
 "labels":{"inception_date":{"en":"policy start date","hi":"..."}, ...},
 "reader_backend":"gemini_flash"}
```
Other types (`life`, `accident`, `motor`, `crop`, `credit_life`, `other`): `{"supported":false,"product_line":"motor","findings":[],"plan":{"kind":"general",...},"labels":{...},"request_checklist":...,"deadlines":{"available":false,"note":"..."}}`. No verdict is produced. Deadlines with no complaint date entered are counted from today's date by the server; **the client never shows such a date** (it requires `complaint_sent_date` in the facts).
Errors: `409 {"detail":{"message":"Please choose the type of insurance before the check runs.","needs_product_line":true,"needs_confirmation":[]}}`, `409 {"detail":{"message":"Please confirm these facts before the check runs.","needs_confirmation":["claim_date"]}}`, `503 {"detail":"The rules are not available right now. Please try again later."}`, `404` expired.

### `POST /session/{sid}/explain?lang=en|hi&helper=0|1`
`200 {"text":"On the facts in your documents, there is a documented possible inconsistency ...","used_model":false,"findings":[...],"deadlines":{...},"plan":{...},"request_checklist":null,"labels":{...},"reader_backend":"gemini_flash"}`. `409 "Run the check first."` if findings are not stored. `422` for a bad `lang` or `helper`.

### `GET /session/{sid}/letter.pdf?lang=en|hi`
`200 application/pdf` (`Content-Disposition: attachment; filename="grievance-letter.pdf"`). `409` with a plain-string detail: "Run the check first.", "Deadlines need the grievance-route rule card to be approved", "Add the date you sent your complaint to see your Ombudsman dates", "There is no challengeable finding, so there is no letter to write."

### Policy key terms (display only; never feeds the check)
- `POST /session/{sid}/policy/extract` (multipart `files`) -> `{"policy":{"verified":true,"heading":{...},"disclaimer":{...},"terms":[{"key":"sum_insured","label":{"en":"Sum insured","hi":"..."},"state":"found","status":"verified","value":500000,"display":{"en":"...","hi":"..."},"quote":"...","page_no":1,"confidence":"high","message":null}],"text":{...}},"pages":1,"reader_backend":"..."}`. States: `found | confirmed | entered | unverified | conflict | absent`.
- `GET /session/{sid}/policy` -> `{"policy":null | {...}}`
- `PUT /session/{sid}/policy` `{"terms":{"sum_insured":{"confirm":true}}}` or `{"value":"..."}` -> `{"policy":{...}}`; `422` with `errors` per term key.
- `DELETE /session/{sid}/policy` -> `{"deleted":true}`

### `GET /gallery`
`200 {"attribution":"powered by IKanoon","cases":[{"case_id":"..","citation":{"forum":..,"case_number":..,"decided_on":..,"source_url":..},"outcome":..,"verdicts":["CHALLENGEABLE",...]}]}`. Currently `cases` is empty in the local checkout (no gallery JSON files built).

### `GET /gallery/{case_id}`
`200 {"case_id":..,"citation":{...},"insurer":..,"outcome":..,"relief_amount":..,"licence_note":..,"findings":[Finding],"attribution":"powered by IKanoon"}`; `404 "This case is not in the gallery."`.

## 3. Error contract (what `ApiError.kind` means)

| Status | Detail | `kind` | UI behaviour |
|---|---|---|---|
| 409 | object with `needs_confirmation[]` | `needs_confirmation` | message + the named facts listed and marked; stay on Confirm |
| 409 | object with `needs_product_line:true` | `needs_product_line` | message; focus the type-of-insurance select |
| 409 | plain string | `conflict` | shown as is (letter, "Run the check first.") |
| 404 | any | `expired` | "Your session has expired. Please start again." banner with a Start again button; client state is dropped |
| 413 | "Uploads are limited to 25 MB in total." | `too_large` | alert with the message |
| 415 | unsupported file / too many pages | `unsupported_file` | alert with the message |
| 422 | `{message, errors:{key:msg}}` | `validation` | "Please fix:" list and each message under its own field (`aria-describedby`, `aria-invalid`) |
| 502, 503 | reader or rules unavailable | `reader_unavailable` | alert, plus the "Enter the facts myself instead" button on the upload step (starts Confirm with empty facts) |
| none | fetch failed | `network` | alert |
| other | | `unknown` | alert with the server message or "Something went wrong" |

## 4. Legacy screens and controls to preserve (parity checklist)

Ticked = built and covered by a DOM or unit test (`frontend/src/test`). "+" marks a deliberate addition.

**Shell**
- [x] Language toggle English / हिन्दी (`aria-pressed`, English default, `<html lang>` updates)
- [x] Hindi draft note (Q-007) shown in Hindi
- [x] Helper-mode toggle (self / helper), third-person strings, `helper=1` on explain
- [x] Printable summary button in helper mode (print stylesheet hides controls)
- [x] "Real cases" link (`#gallery`), back button returns to the screen it came from
- [x] Step indicator with `aria-current="step"`
- [x] Footer notices on every screen: independent-project line; rules-check line on results
- [x] + Skip link, step announcer (`role=status`), focus moves to the screen heading on every step change
- [ ] "Built with Muse Spark Open" footer line: needs the controller (see risks). The client shows it when built with `VITE_BUILT_WITH_SPARK=1`.

**Step 1 Upload**
- [x] File picker (jpg, png, pdf; multiple), label, "Read my documents"
- [x] + Camera capture (`capture="environment"`), chosen-file list with Remove
- [x] Loading text "Reading your documents..." (`role=status`)
- [x] Error in `role=alert`; on 502/503 the "Enter the facts myself instead" button

**Step 2 Confirm**
- [x] Heading, intro; type-of-insurance select with the 7 types; only the server hint is pre-selected; hint and "why" text; required before the check
- [x] Rejection-ground select (13 grounds, always shown). Free-text grounds from the reader are not pre-selected
- [x] Every fact with API label (EN/HI), status tag, source quote, page, edit box, "This is correct" checkbox; pending first
- [x] Yes/No radios for absence booleans, no default answer
- [x] Deductions: per-item Yes / No / Not sure
- [x] Tri-state continuity (Yes / No / Not sure); unanswered sends nothing; Not sure clears a stored answer
- [x] "Add a missing fact": claim_date, admission_date, inception_date, policy_renewal_date (only those not read)
- [x] Letter details (name, policy no., claim no., amount, insurer, complaint-sent date) and insurer reply date
- [x] Optional policy key-terms card: upload, edit, confirm, save, remove (display only)
- [x] PUT /facts, then check, then explain; 422 shown per field; 409 lists the facts; 404 recovery
- [x] Back button
- [x] + Client-side gate: the check does not run while a pending fact is unanswered, and lists them
- [x] + A pre-filled rejection ground and a pending deductions list need an explicit tick (legacy confirmed them by pressing Run)
- [x] + Continuity fact is asked once (tri-state), not twice as in the legacy list when it was extracted

**Step 3 Result**
- [x] Verdict cards sorted CHALLENGEABLE, NEED_INFO, CONSISTENT: word + shape + sentence, rule quote + page, facts used with quotes, "What we need", "What you can do"
- [x] Rule ids only as a muted "Rule reference" chip (the API sends no rule title)
- [x] ISO dates from the rule engine shown as DD/MM/YYYY
- [x] Explanation text (EN/HI, helper), re-fetched when the language or helper mode changes
- [x] Documents-to-request checklist
- [x] "Documents read by" backend line
- [x] Deadlines box with GRIEVANCE_ROUTE quote, page, source; dates only when the user entered the complaint date
- [x] "Your plan" steps (health) / "A general plan" (other types) with dates only when the API returns them, else the "Add the date..." text
- [x] "This is a general plan, not a rules check" label for unsupported types, no verdict cards
- [x] "What your policy says" read-only section
- [x] Grievance letter download via fetch: 409 messages shown; blob saved as `grievance-letter.pdf`
- [x] + Complaint-sent and insurer-reply date entry (PUT facts, re-check, re-explain)
- [x] Delete my data (DELETE session), confirmation, Start again
- [x] 404 recovery

**Gallery**
- [x] List with citation, forum, date, verdict stamps; open a case; findings; https-only source link; "powered by IKanoon"; empty state

## 5. Dependencies (exact versions; licences)

| Package | Version | Licence | Role |
|---|---|---|---|
| react, react-dom | 19.3.1 | MIT | UI |
| @fontsource/newsreader | 5.3.0 | OFL-1.1 | serif display and quotes (latin) |
| @fontsource/source-sans-3 | 5.3.1 | OFL-1.1 | UI sans (latin) |
| @fontsource/noto-sans-devanagari | 5.3.0 | OFL-1.1 | Hindi UI text, and the rupee sign |
| @fontsource/noto-serif-devanagari | 5.3.0 | OFL-1.1 | Hindi headings and quotes |
| vite | 8.3.5 | MIT | build and dev server |
| @vitejs/plugin-react | 6.1.2 | MIT | JSX transform |
| typescript | 7.0.2 | Apache-2.0 | type checking |
| vitest | 5.0.5 | MIT | tests |
| jsdom | 30.1.3 | MIT | DOM for tests |
| @testing-library/react | 16.3.3 | MIT | component tests |
| @testing-library/dom | 10.4.2 | MIT | peer of the above |
| @types/react, @types/react-dom | 19.3.0 | MIT | types |
| @types/node | 26.6.6 | MIT | types for test file reads |

Not installed: three, @react-three/*, rapier, motion, any router or state library. Transitive dependencies come from the lockfile (`frontend/package-lock.json`); `npm audit` reported 0 vulnerabilities at install. The OFL fonts are self-hosted and bundled by Vite into `dist/assets`. Add these rows to `LICENSES.md` at the next commit.

## 6. Risks

1. **Hindi is a draft** (Q-007). The dictionary keeps every legacy Hindi string and marks it draft; about 32 new client strings (and 6 helper-mode variants) have Hindi drafts written for this phase and need the same human review.
2. **Footer credit.** The legacy server injected "Built with Muse Spark Open" at request time. A static bundle cannot know. The controller either serves the built `index.html` through a small template step or adds a field to `/health`.
3. **Deadline dates.** The API still computes deadlines from today's date when no complaint date was entered (backend behaviour, untouched). The client hides those dates. If the backend later stops sending them, nothing breaks.
4. **Re-check after every date change.** `PUT /facts` clears findings. A failed second check leaves the Result screen showing the earlier result while the letter route returns 409; the error is shown, but this is a server design quirk to keep in mind.
5. **Rule titles.** The API sends no plain-language title per rule. Until the rule cards carry one and the API exposes it, the card heading is the verdict sentence and the rule id is a "Rule reference" chip. Owner decision needed on adding titles to the cards.
6. **No real-browser verification yet.** Layout, fonts and the 375px view are verified by CSS review and DOM tests only. The owner runs the Chrome-extension pass.
7. **TypeScript 7 / Vite 8 / Vitest 5** are very recent majors. They install and build clean here; pin and do not float.
8. **Large Devanagari fonts** (about 210 KB of woff2) load on every visit, because English-mode users can still have Hindi quotes from their documents.
9. **Bundle also ships `.woff` fallbacks** (Vite follows the `@fontsource` CSS). Harmless but about 450 KB of dead weight in `dist`; can be trimmed with a Vite plugin later.

## 7. Rollback and switching

- The old page is untouched at `sarthi/app/static/index.html`. It becomes the `/legacy` fallback when the controller wires FastAPI.
- Proposed switch for the controller (not implemented here): environment variable `SARTHI_UI=react|legacy`. `react` (default once accepted) serves `frontend/dist/index.html` at `/` and `/assets/*`, and the old page at `/legacy`. `legacy` serves the old page at `/` (the pre-migration behaviour). Rolling back is one env change and a restart; no data or API changes are involved.
- Dev: `cd frontend && npm run dev` serves on 5173 and proxies `/session`, `/gallery`, `/health`, `/legacy` to `localhost:8000`.
- Production: `npm run build` writes `frontend/dist` with base `/`. The Space Dockerfile needs a Node build stage (or the committed `dist`) and `COPY frontend/dist`; that is the controller's change.
- Exact API paths are unchanged, so the legacy page and the React client can run side by side against the same server.
