"""Extract case facts from real judgments with a model, then human review.

The model reads the judgment text and returns each fact with a verbatim quote. A quote
found exactly in the text gives status `extracted`; anything else `needs_review`.
Nothing here runs the rule engine; Task 12 uses `load_reviewed_facts`.
"""
import json
import logging
import re
from datetime import date, datetime
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, ValidationError
from rapidfuzz import fuzz

from sarthi.core.derive import FACT_KEYS
from sarthi.core.inputs import REJECTION_GROUNDS
from sarthi.core.models import CaseFact, FactValue
from sarthi.core.parse_values import parse_date_in, parse_inr
from sarthi.core.store import Store
from sarthi.data.parse_docs import normalise_ws, parse_source
from sarthi.llm.client import chat

log = logging.getLogger(__name__)

WINDOW_TOKENS = 12_000
CHARS_PER_TOKEN = 4
USER_ONLY = ("continuity_confirmed", "cited_clause_found")  # user/derived, never extracted
EXTRACTED_KEYS = tuple(k for k in FACT_KEYS if k not in USER_ONLY)

DATE_FIELDS = {"inception_date", "ported_from_date", "claim_date", "admission_date",
               "policy_renewal_date"}
DATETIME_FIELDS = {"cashless_request_at", "decision_at", "discharge_request_at", "final_auth_at"}
BOOL_FIELDS = {"fraud_alleged", "crc_approval_mentioned", "reasons_cite_terms"}

class Deduction(BaseModel):
    model_config = ConfigDict(extra="forbid")
    item: str | None = None
    amount: str | int | float | None = None
    reason: str | None = None
    nonpayable_listed: bool | None = None


class ExtractedField(BaseModel):
    model_config = ConfigDict(extra="forbid")
    value: str | int | float | bool | list[Deduction] | list[str] | None = None
    quote: str | None = None
    page_no: int | None = None


class CaseFactsOut(BaseModel):
    model_config = ConfigDict(extra="forbid")
    inception_date: ExtractedField | None = None
    ported_from_date: ExtractedField | None = None
    claim_date: ExtractedField | None = None
    admission_date: ExtractedField | None = None
    rejection_ground: ExtractedField | None = None
    disclosed_conditions: ExtractedField | None = None
    alleged_undisclosed_condition: ExtractedField | None = None
    fraud_alleged: ExtractedField | None = None
    deductions: ExtractedField | None = None
    cashless_request_at: ExtractedField | None = None
    decision_at: ExtractedField | None = None
    discharge_request_at: ExtractedField | None = None
    final_auth_at: ExtractedField | None = None
    cited_clause: ExtractedField | None = None
    crc_approval_mentioned: ExtractedField | None = None
    reasons_cite_terms: ExtractedField | None = None
    renewal_gap_days: ExtractedField | None = None
    policy_renewal_date: ExtractedField | None = None


def schema_hint(model: type[BaseModel]) -> str:
    """Compact description of the JSON reply shape, generated from the schema."""
    keys = ", ".join(model.model_fields)
    return ("Reply with ONLY one JSON object. Its keys are exactly: " + keys + ". "
            'Each key is null or {"value": ..., "quote": "<verbatim text>", "page_no": <int>}. '
            "Use no other keys.")


SYSTEM_PROMPT = f"""You read one Indian consumer-forum judgment about a health insurance claim and extract facts for a rule engine.
Rules:
- Extract facts as stated or found by the forum, not the parties' claims or arguments.
- If the judgment does not state a field, leave it null. Never guess or infer.
- Each quote must be copied verbatim from the given text (exact words, no paraphrase, no ellipsis).
- Give page_no from the page marker "[Page N]" that precedes the quote.
- Dates as written in the judgment (day-month-year). Amounts as written (for example "Rs. 2,45,000").
- rejection_ground must be exactly one of: {", ".join(REJECTION_GROUNDS)}.
- deductions is a list of objects {{item, amount, reason, nonpayable_listed}}: reason is "non_payable" when the insurer deducted the item as non-payable; nonpayable_listed is true only if the forum finds the item on the standard non-payable list.
- disclosed_conditions is a list of conditions the insured disclosed in the proposal.
- renewal_gap_days is the number of days between expiry and renewal if the forum states a lapse, else null.
- Times (cashless_request_at, decision_at, discharge_request_at, final_auth_at) include date and time.
{schema_hint(CaseFactsOut)}"""


class ReviewDecision(BaseModel):
    action: Literal["accept", "correct", "reject"]
    value: Any = None
    note: str = ""


# ---------- windowing ----------

def _split_long(text: str, limit: int) -> list[str]:
    parts = []
    while len(text) > limit:
        cut = text.rfind(". ", 0, limit)
        cut = cut + 2 if cut > limit // 2 else limit
        parts.append(text[:cut])
        text = text[cut:]
    parts.append(text)
    return parts


def make_windows(pages: list[tuple[int, str]]) -> list[tuple[list[int], str]]:
    """Chunks of <= WINDOW_TOKENS tokens (chars/4), split on paragraph boundaries.
    Each window text carries "[Page N]" markers; returns (page numbers covered, text)."""
    limit = WINDOW_TOKENS * CHARS_PER_TOKEN
    pieces: list[tuple[int, str]] = []
    for page_no, text in pages:
        for para in re.split(r"\n\s*\n", text):
            if para.strip():
                pieces += [(page_no, p) for p in _split_long(para, limit - 100)]
    windows: list[tuple[list[int], str]] = []
    cur: list[str] = []
    wpages: list[int] = []
    size, last_page = 0, None
    for page_no, para in pieces:
        marker = f"[Page {page_no}]\n" if page_no != last_page else ""
        add = len(marker) + len(para) + 2
        if cur and size + add > limit:
            windows.append((wpages, "".join(cur).rstrip()))
            cur, wpages, size, last_page = [], [], 0, None
            marker = f"[Page {page_no}]\n"
            add = len(marker) + len(para) + 2
        if page_no not in wpages:
            wpages.append(page_no)
        cur.append(f"{marker}{para}\n\n")
        size += add
        last_page = page_no
    if cur:
        windows.append((wpages, "".join(cur).rstrip()))
    return windows


# ---------- value parsing ----------

def _parse_datetime(s: str) -> datetime | None:
    try:
        return datetime.fromisoformat(s)
    except (TypeError, ValueError):
        pass
    if not isinstance(s, str):
        return None
    m = re.search(r"(\d{1,2})[:.](\d{2})\s*([ap]\.?m\.?)?", s, re.I)
    d, _ = parse_date_in(s[:m.start()] + s[m.end():] if m else s, from_photo=False)
    if d is None:
        return None
    h, mi = (int(m.group(1)), int(m.group(2))) if m else (0, 0)
    if m and m.group(3):
        pm = m.group(3).lower().startswith("p")
        h = h % 12 + (12 if pm else 0)
    if h > 23 or mi > 59:
        return None
    return datetime(d.year, d.month, d.day, h, mi)


def _parse_deductions(v):
    if not isinstance(v, list):
        return None, False
    out = []
    for it in v:
        if isinstance(it, BaseModel):
            it = it.model_dump()
        if not isinstance(it, dict):
            return None, False
        amt = it.get("amount")
        if isinstance(amt, str):
            amt = parse_inr(amt)
        elif isinstance(amt, bool) or not isinstance(amt, (int, float)):
            amt = None
        ok = amt is not None
        out.append({"item": it.get("item"), "amount": amt, "reason": it.get("reason"),
                    "nonpayable_listed": it.get("nonpayable_listed")})
        if not ok:
            return out, False
    return out, True


def parse_field(field: str, v) -> tuple[Any, bool]:
    """Raw model value -> (JSON-able value, valid)."""
    if v is None:
        return None, False
    if field in DATE_FIELDS:
        if isinstance(v, str) and re.fullmatch(r"\d{4}-\d{2}-\d{2}", v.strip()):
            try:  # ISO dates (what the store holds, what a reviewer types) are valid as they are
                return date.fromisoformat(v.strip()).isoformat(), True
            except ValueError:
                return v, False
        d, _ = parse_date_in(v, from_photo=False) if isinstance(v, str) else (None, False)
        return (d.isoformat(), True) if d else (v, False)
    if field in DATETIME_FIELDS:
        dt = _parse_datetime(v)
        return (dt.isoformat(), True) if dt else (v, False)
    if field == "deductions":
        return _parse_deductions(v)
    if field == "rejection_ground":
        return v, v in REJECTION_GROUNDS
    if field in BOOL_FIELDS:
        return v, isinstance(v, bool)
    if field == "renewal_gap_days":
        if isinstance(v, str) and v.strip().isdigit():
            v = int(v.strip())
        return v, isinstance(v, int) and not isinstance(v, bool)
    if field == "disclosed_conditions":
        return v, isinstance(v, list) and all(isinstance(c, str) for c in v)
    return v, isinstance(v, str)


# ---------- extraction ----------

def _pages(case_id: str, store: Store) -> list[tuple[int, str]]:
    row = store.con.execute('SELECT source_sha256 FROM "case" WHERE case_id=?', [case_id]).fetchone()
    if row is None or not row[0]:
        raise KeyError(f"unknown case or no source: {case_id}")
    sha = row[0]
    q = "SELECT page_no, text FROM document_page WHERE sha256=? ORDER BY page_no"
    pages = store.con.execute(q, [sha]).fetchall()
    if not pages:
        parse_source(sha, store)
        pages = store.con.execute(q, [sha]).fetchall()
    return [(p, t or "") for p, t in pages]


_MARKER = re.compile(r"\[Page \d+\]\n")


def _candidate(field: str, ef: ExtractedField, window: str, window_pages: list[int],
               page_text: dict[int, str], forced_review: bool) -> dict:
    value, valid = parse_field(field, ef.value)
    quote = ef.quote or ""
    nq, nw = normalise_ws(quote), normalise_ws(_MARKER.sub("", window))
    found = bool(nq) and nq in nw
    single = next((p for p in window_pages if nq and nq in normalise_ws(page_text.get(p, ""))), None)
    if single is not None:
        page_no = single
    elif ef.page_no in window_pages:
        page_no = ef.page_no
    else:
        page_no = window_pages[0]
    exact = found and valid and not forced_review
    conf = 1.0 if exact else (fuzz.partial_ratio(nq, nw) / 100 if nq else 0.0)
    if not exact or single is None:
        conf = min(conf, 0.99)
    return dict(case_id="", field=field, value=json.dumps(value), quote=quote or None,
                page_no=page_no, confidence=conf, status="extracted" if exact else "needs_review",
                reviewer_note=None)


PROTECTED = ("reviewed", "corrected", "rejected")


def protected_fields(case_id: str, store: Store) -> list[str]:
    """Fields a human has already reviewed; extract_case will not overwrite them."""
    marks = ", ".join("?" for _ in PROTECTED)
    return [r[0] for r in store.con.execute(
        f"SELECT field FROM case_fact WHERE case_id=? AND status IN ({marks}) ORDER BY 1",
        [case_id, *PROTECTED]).fetchall()]


def extract_case(case_id: str, store: Store, force: bool = False) -> list[CaseFact]:
    """Rows written. Fields with a human review status are skipped unless force=True."""
    pages = _pages(case_id, store)
    page_text = dict(pages)
    skip = set() if force else set(protected_fields(case_id, store))
    best: dict[str, dict] = {}
    for wpages, text in make_windows(pages):
        res = chat(role="reader", schema=CaseFactsOut, messages=[
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user", "content": f"Judgment text:\n\n{text}"}], max_tokens=4000)
        if res.parsed is None:
            continue
        for field in EXTRACTED_KEYS:
            ef = getattr(res.parsed, field, None)
            if field in skip or ef is None or ef.value is None:
                continue
            c = _candidate(field, ef, text, wpages, page_text, res.needs_review)
            c["case_id"] = case_id
            cur = best.get(field)
            if cur is None or (cur["status"] != "extracted" and c["status"] == "extracted"):
                best[field] = c
    rows = [best[k] for k in EXTRACTED_KEYS if k in best]
    store.upsert("case_fact", rows, key=["case_id", "field"])
    return [CaseFact(**r) for r in rows]


# ---------- review ----------

def _dumps(v) -> str:
    return json.dumps(v, default=lambda o: o.isoformat())


def review(case_id: str, decisions: dict[str, ReviewDecision], reviewer: str, store: Store) -> None:
    existing = {r[0]: r[1] for r in store.con.execute(
        "SELECT field, value FROM case_fact WHERE case_id=?", [case_id]).fetchall()}
    unknown = [f for f in decisions if f not in existing]
    if unknown:
        raise KeyError(f"no extracted fact for {case_id}: {', '.join(unknown)}")
    updates = []  # validate every decision before writing any
    for field, d in decisions.items():
        clear_quote = False
        if d.action == "accept":
            status, value, note = "reviewed", existing[field], f"accepted by {reviewer}"
            if d.note:
                note += f"; {d.note}"
        elif d.action == "correct":
            parsed, valid = parse_field(field, d.value)
            if not valid:
                raise ValueError(f"corrected value for {field} is not a valid {field}: {d.value!r}")
            status, value, clear_quote = "corrected", _dumps(parsed), True
            note = f"was: {existing[field]}; {d.note}; by {reviewer}; quote cleared on correction"
        else:
            status, value, note = "rejected", existing[field], f"rejected by {reviewer}; {d.note}"
        updates.append((status, value, note, clear_quote, field))
    for status, value, note, clear_quote, field in updates:
        store.con.execute(
            "UPDATE case_fact SET status=?, value=?, reviewer_note=?, "
            "quote=CASE WHEN ? THEN NULL ELSE quote END, "
            "page_no=CASE WHEN ? THEN NULL ELSE page_no END WHERE case_id=? AND field=?",
            [status, value, note, clear_quote, clear_quote, case_id, field])


def build_review_form(case_id: str, store: Store) -> dict | None:
    """Review form for one case: EVERY extracted field (extracted and needs_review, and any
    already decided), or None when the case has no facts. Fields with status `extracted` carry a
    default "accept" decision; flagged ones have none and stay flagged until decided."""
    rows = store.con.execute(
        "SELECT field, value, quote, page_no, status FROM case_fact WHERE case_id=? ORDER BY field",
        [case_id]).fetchall()
    if not rows:
        return None
    fields, lines = [], []
    for field, value, quote, page_no, status in rows:
        default = None
        if status == "extracted":
            try:
                default = {"action": "accept", "value": json.loads(value) if value is not None else None,
                           "note": ""}
            except ValueError:
                log.warning("case %s field %s: stored value is not valid JSON; no default decision",
                            case_id, field)
        fields.append({"field": field, "value": value, "quote": quote, "page_no": page_no,
                       "status": status, "default": default})
        lines.append(f"- **{field}** [{status}] = `{value}`  \n  > {quote}")
    body = ("\n".join(lines) + "\n\nFields marked [extracted] are accepted unless you override them. "
            "Fields marked [needs_review] stay flagged unless you decide them. Fill the form with a "
            'JSON object mapping a field to `{"action": "accept|correct|reject", "value": ..., '
            '"note": ""}`.')
    return {"case_id": case_id, "subject": f"Review extracted facts for {case_id}",
            "body": body, "fields": fields}


def apply_review_form(case_id: str, raw: dict, reviewer: str, store: Store) -> int:
    """Apply one form's decisions. Facts still `extracted` default to accept; explicit entries
    override. Returns the number of facts decided. Raises ValueError on a bad entry (nothing written)."""
    form = build_review_form(case_id, store)
    if form is None:
        raise KeyError(f"no extracted facts for {case_id}")
    decisions = {f["field"]: ReviewDecision(**f["default"]) for f in form["fields"] if f["default"]}
    try:
        decisions.update({f: ReviewDecision.model_validate(d) for f, d in raw.items()})
    except (ValidationError, AttributeError) as e:
        raise ValueError(f"bad decision for {case_id}: {e}") from e
    if decisions:
        review(case_id, decisions, reviewer, store)
    return len(decisions)


def apply_review_forms(forms: list[dict], responses: list, store: Store) -> int:
    """Apply many forms independently: a bad entry is logged and that case skipped."""
    n = 0
    for form, resp in zip(forms, responses):
        if not resp:
            continue
        cid = form["case_id"]
        try:
            raw = json.loads((resp.get("params_input") or {}).get("decisions") or "{}")
            if not isinstance(raw, dict):
                raise ValueError("decisions must be a JSON object")
            user = (resp.get("responded_by_user") or {}).get("name") or "unknown"
            apply_review_form(cid, raw, user, store)
            n += 1
        except (ValueError, KeyError, TypeError) as e:
            log.warning("review for case %s skipped: %s", cid, e)
    return n


def _decode(field: str, v):
    if v is None:
        return None
    if field in DATE_FIELDS:
        return date.fromisoformat(v) if isinstance(v, str) else v
    if field in DATETIME_FIELDS:
        return datetime.fromisoformat(v) if isinstance(v, str) else v
    return v


def load_reviewed_facts(case_id: str, store: Store) -> dict[str, FactValue]:
    rows = store.con.execute(
        "SELECT field, value, quote, page_no FROM case_fact WHERE case_id=? "
        "AND status IN ('reviewed','corrected')", [case_id]).fetchall()
    out = {}
    for field, value, quote, page_no in rows:
        try:
            v = _decode(field, json.loads(value)) if value is not None else None
        except (ValueError, TypeError) as e:
            log.warning("case %s field %s: undecodable stored value skipped (%s)", case_id, field, e)
            continue
        if v is None:
            continue
        out[field] = FactValue(value=v, quote=quote, page_no=page_no,
                               confidence="high", status="verified")
    return out


def load_unresolved_facts(case_id: str, store: Store) -> dict[str, FactValue]:
    """Facts that exist for the case but no human has decided yet (status extracted /
    needs_review), as `needs_confirmation` FactValues: the same state the app uses for an
    unconfirmed fact, so the app's readiness check (`ready_for_rules`) applies to them unchanged.
    An undecodable stored value is still unresolved (value None). Rejected facts are resolved."""
    rows = store.con.execute(
        "SELECT field, value, quote, page_no FROM case_fact WHERE case_id=? "
        "AND status IN ('extracted','needs_review')", [case_id]).fetchall()
    out = {}
    for field, value, quote, page_no in rows:
        try:
            v = _decode(field, json.loads(value)) if value is not None else None
        except (ValueError, TypeError):
            v = None
        out[field] = FactValue(value=v, quote=quote, page_no=page_no, confidence="low",
                               status="needs_confirmation")
    return out
