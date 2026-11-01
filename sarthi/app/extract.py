"""Read a user's uploaded documents into facts for them to confirm, then check readiness.

Privacy: every model call here uses cache=False, and nothing logs document content
(only counts, statuses and the backend).
"""
import base64
import json
import logging
import re
from dataclasses import dataclass
from datetime import date, datetime
from pathlib import Path

from rapidfuzz import fuzz

from sarthi.app.session import Session
from sarthi.core.derive import INPUT_FACTS
from sarthi.core.expr import names
from sarthi.core.models import FactValue, RuleCard
from sarthi.core.parse_values import parse_date_in, parse_inr
from sarthi.data.case_facts import (DATE_FIELDS, DATETIME_FIELDS, EXTRACTED_KEYS, CaseFactsOut,
                                    parse_field, schema_hint)
from sarthi.data.parse_docs import normalise_ws
from sarthi.llm.client import chat

log = logging.getLogger(__name__)

FUZZY_PASS = 90
FUZZY_HIGH = 95

SYSTEM_PROMPT = f"""You read one page of a policyholder's insurance document (a claim rejection letter or a policy schedule) and extract facts for a rule engine.
Rules:
- Extract only what the document states. If a field is not on this page, leave it null. Never guess or infer.
- Each quote must be copied verbatim from the page (exact words, no paraphrase, no ellipsis).
- Dates exactly as written. Amounts exactly as written (for example "Rs. 2,45,000").
- rejection_ground is the insurer's stated reason for rejecting or reducing the claim.
- page_no is 1 for this page.
- deductions is a list of objects {{item, amount, reason, nonpayable_listed}}; disclosed_conditions is a list of strings.
{schema_hint(CaseFactsOut)}"""

TRANSCRIBE_PROMPT = "Transcribe all text on this page exactly as written. Output only the text."


def _image_part(page: Path) -> dict:
    b64 = base64.b64encode(page.read_bytes()).decode()
    return {"type": "image_url", "image_url": {"url": f"data:image/png;base64,{b64}"}}


def _score(quote: str, haystack: str) -> int:
    """0-100 similarity of a quote to a transcription."""
    if not quote or not haystack:
        return 0
    return round(fuzz.partial_ratio(quote, haystack))


_TIME_RE = re.compile(r"(\d{1,2})[:.](\d{2})\s*([ap]\.?m\.?)?", re.I)
_DATE_PATTERNS = (
    re.compile(r"\d{1,2}[/.\-]\d{1,2}[/.\-]\d{4}"),
    re.compile(r"\d{1,2}(?:st|nd|rd|th)?[\s\-]+[A-Za-z]+\.?,?[\s\-]+\d{4}"),
)
_AMOUNT_RE = re.compile(
    r"(?:rs\.?|inr|\u20b9)?\s*\d[\d,]*(?:\.\d+)?(?:\s*(?:lakhs?|lacs?|crores?|cr)\b)?(?:\s*/-)?", re.I)
_ORDINAL = re.compile(r"(\d)(?:st|nd|rd|th)\b", re.I)


def _split_time(s: str) -> tuple[str, tuple[int, int] | None]:
    """(text without the time, (hour, minute) or None)."""
    m = _TIME_RE.search(s)
    if not m:
        return s, None
    h, mi = int(m.group(1)), int(m.group(2))
    if m.group(3):
        h = h % 12 + (12 if m.group(3).lower().startswith("p") else 0)
    if h > 23 or mi > 59:
        return s, None
    return s[:m.start()] + s[m.end():], (h, mi)


def _dates_in(text: str) -> set[date]:
    found = set()
    for pat in _DATE_PATTERNS:
        for m in pat.finditer(text):
            d, _ = parse_date_in(_ORDINAL.sub(r"\1", m.group(0)), from_photo=False)
            if d:
                found.add(d)
    return found


def _convert(field: str, raw, from_photo: bool) -> tuple[object, bool, bool]:
    """(value, parsed_ok, ambiguous)."""
    if field in DATE_FIELDS:
        d, amb = parse_date_in(raw, from_photo=from_photo) if isinstance(raw, str) else (None, False)
        return (d, True, amb) if d else (raw, False, False)
    if field in DATETIME_FIELDS and isinstance(raw, str):
        value, ok = parse_field(field, raw)
        if not ok:
            return raw, False, False
        value = datetime.fromisoformat(value)
        # ambiguity of the day/month order, judged on the date part as written
        date_part, _ = _split_time(raw)
        d, amb = parse_date_in(date_part.strip(), from_photo=from_photo)
        return value, True, bool(d and amb)
    value, ok = parse_field(field, raw)
    return value, ok, False


def _amounts_in(text: str) -> set[int]:
    out = set()
    for m in _AMOUNT_RE.finditer(text):
        n = parse_inr(m.group(0).strip())
        if n is not None:
            out.add(n)
    return out


def _supported(field: str, value, raw, quote: str) -> bool:
    """Is the parsed value backed by its own quote?
    dates: the date in the quote equals the value; datetimes: date and, when the value has
    a time, the time too; deductions: each amount appears in the quote; renewal_gap_days:
    the number appears in the quote; disclosed_conditions and other strings: normalised
    value contained in the quote; booleans and rejection_ground (a fixed vocabulary, so the
    quote need not repeat the value): the value is valid (checked by parse_field) and the
    quote is present."""
    q = normalise_ws(quote)
    if not q:
        return False
    if field in DATE_FIELDS:
        return value in _dates_in(q)
    if field in DATETIME_FIELDS:
        rest, t = _split_time(q)
        if value.date() not in _dates_in(rest):
            return False
        return t == (value.hour, value.minute) if (value.hour or value.minute) else True
    if field == "deductions":
        amounts = _amounts_in(q)
        return all(it.get("amount") in amounts for it in value)
    if field == "renewal_gap_days":
        return value in {int(n) for n in re.findall(r"\d+", q)}
    if field == "disclosed_conditions":
        return all(normalise_ws(str(c)).lower() in q.lower() for c in value)
    if field == "rejection_ground" or isinstance(value, bool):
        return True
    return normalise_ws(str(value)).lower() in q.lower()


# Booleans that assert an absence: a quote can never prove "not mentioned", so a False
# from the model is always left for the user to confirm.
ABSENCE_BOOLS = ("crc_approval_mentioned", "reasons_cite_terms", "fraud_alleged")


class ExtractedFacts(dict):
    """field -> FactValue, plus `backend`: which model backend(s) read the documents."""
    backend: str | None = None


def _blank_listing(value):
    """Whether an item is on the standard non-payable list is never taken from the model."""
    return [{**it, "nonpayable_listed": None} if isinstance(it, dict) else it for it in value]


def _page_candidates(session: Session, page: Path, page_no: int,
                     backends: set[str] | None = None) -> list[tuple[str, FactValue]]:
    text_layer = session.page_text(page)
    from_photo = text_layer is None
    image = _image_part(page)
    res = chat(role="reader", cache=False, schema=CaseFactsOut, messages=[
        {"role": "system", "content": SYSTEM_PROMPT},
        {"role": "user", "content": [{"type": "text", "text": "Extract the facts from this page."},
                                     image]}])
    if backends is not None and getattr(res, "backend", None):
        backends.add(res.backend)
    if res.parsed is None:
        return []
    if from_photo:
        t = chat(role="reader", cache=False, messages=[
            {"role": "user", "content": [{"type": "text", "text": TRANSCRIBE_PROMPT}, image]}])
        haystack = normalise_ws(t.text or "")
    else:
        haystack = normalise_ws(text_layer)

    out = []
    for field in EXTRACTED_KEYS:
        ef = getattr(res.parsed, field, None)
        if ef is None or ef.value is None:
            continue
        value, parsed_ok, ambiguous = _convert(field, ef.value, from_photo)
        nq = normalise_ws(ef.quote or "")
        if not nq:
            score = 0
        elif not from_photo:
            score = 100 if nq in haystack else 0
        else:
            score = _score(nq, haystack)
        quote_ok = score >= (100 if not from_photo else FUZZY_PASS)
        confidence = "high" if score >= FUZZY_HIGH else "medium" if score >= FUZZY_PASS else "low"
        verified = (quote_ok and parsed_ok and not ambiguous and not res.needs_review
                    and _supported(field, value, ef.value, ef.quote or ""))
        if field == "deductions" and isinstance(value, list):
            value, verified = _blank_listing(value), False  # the user answers per item
        if field in ABSENCE_BOOLS and value is False:
            verified = False
        out.append((field, FactValue(value=value, quote=ef.quote, page_no=page_no,
                                     confidence=confidence,
                                     status="verified" if verified else "needs_confirmation")))
    return out


def extract_user_facts(session: Session) -> ExtractedFacts:
    """One reader call per page (plus one transcription call per photographed page).
    Merge: a verified value beats unverified ones; conflicting verified values for the
    same field become needs_confirmation with the first value."""
    per_field: dict[str, list[FactValue]] = {}
    backends: set[str] = set()
    pages = session.pages()
    for i, page in enumerate(pages, start=1):
        for field, fv in _page_candidates(session, page, i, backends):
            per_field.setdefault(field, []).append(fv)

    facts = ExtractedFacts()
    facts.backend = ", ".join(sorted(backends)) or None
    for field, cands in per_field.items():
        verified = [c for c in cands if c.status == "verified"]
        if not verified:
            facts[field] = cands[0]
        elif any(c.value != verified[0].value for c in verified[1:]):
            facts[field] = verified[0].model_copy(update={"status": "needs_confirmation"})
        else:
            facts[field] = verified[0]
    log.info("extracted pages=%d fields=%d needs_confirmation=%d", len(pages), len(facts),
             sum(f.status == "needs_confirmation" for f in facts.values()))
    return facts


def _date_keys(card: RuleCard) -> tuple[str, ...]:
    if card.applies_by == "claim_date":
        return ("claim_date",)
    if card.applies_by == "policy_start_or_renewal":
        return ("claim_date", "inception_date", "policy_renewal_date")
    return ()


def ready_for_rules(facts: dict[str, FactValue], cards: list[RuleCard] | None = None) -> bool:
    """False while rejection_ground is missing/unconfirmed, or while a fact feeding a
    triggered card is unconfirmed. With cards=None every fact must be confirmed."""
    def pending(key: str) -> bool:
        f = facts.get(key)
        return f is not None and f.status == "needs_confirmation"

    ground = facts.get("rejection_ground")
    if ground is None or ground.value is None or ground.status == "needs_confirmation":
        return False
    if cards is None:
        return not any(f.status == "needs_confirmation" for f in facts.values())
    for card in cards:
        triggers = card.triggers if isinstance(card.triggers, list) else list(card.triggers)
        if ground.value not in triggers:
            continue
        keys = set(_date_keys(card))
        for n in (names(card.condition) if card.condition else []):
            keys.update(INPUT_FACTS.get(n, (n,)))
        if any(pending(k) for k in keys):
            return False
    return True


# ---------- reading accuracy (consented documents) ----------

@dataclass
class ReadingReport:
    n_docs: int
    field_accuracy: float | None
    flagged_wrong_share: float | None


def _norm(v):
    if isinstance(v, bool) or v is None:
        return v
    if isinstance(v, (datetime, date)):
        return v.isoformat()
    if isinstance(v, float) and v.is_integer():
        return int(v)
    if isinstance(v, str):
        for parse in (date.fromisoformat, datetime.fromisoformat):
            try:
                return parse(v.strip()).isoformat()
            except ValueError:
                pass
        return normalise_ws(v).lower()
    if isinstance(v, dict):
        return {k: _norm(x) for k, x in v.items()}
    if isinstance(v, list):
        return sorted((_norm(x) for x in v), key=lambda x: json.dumps(x, sort_keys=True, default=str))
    return v


def _load_truth(truth_path: Path, stem: str) -> dict | None:
    """truth_path is one JSON {doc_stem: {field: value}} or a folder of <doc_stem>.json."""
    if truth_path.is_dir():
        f = truth_path / f"{stem}.json"
        return json.loads(f.read_text(encoding="utf-8")) if f.exists() else None
    return json.loads(truth_path.read_text(encoding="utf-8")).get(stem)


def eval_reading(docs_dir: Path, truth_path: Path) -> ReadingReport:
    """Compare extraction with hand labels. Returns aggregate numbers only."""
    total = correct = wrong = wrong_flagged = n_docs = 0
    for doc in sorted(Path(docs_dir).iterdir()):
        truth = _load_truth(Path(truth_path), doc.stem) if doc.is_file() else None
        if truth is None:
            continue
        n_docs += 1
        session = Session.create()
        try:
            session.add_upload(doc)
            facts = extract_user_facts(session)
        finally:
            session.delete()
        for field, expected in truth.items():
            got = facts.get(field)
            total += 1
            if _norm(got.value if got else None) == _norm(expected):
                correct += 1
            else:
                wrong += 1
                wrong_flagged += bool(got and got.status == "needs_confirmation")
    return ReadingReport(n_docs, correct / total if total else None,
                         wrong_flagged / wrong if wrong else None)
