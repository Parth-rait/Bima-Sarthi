"""What your policy says: a display-only reading of the policy document's key terms.

The reader model only reads. Each term it returns must come with a quote that is found
verbatim (normalise_ws) in the text of the page it was read from, and a value that the
quote supports (unit-typed numbers go through verify.extract, the same typing the
explanation verifier uses). Anything else is `needs_confirmation`: it is shown only as
"we could not find this in your document", never as a value. Terms the model did not return
are "not found in the pages we read".

This module never produces or changes a verdict and never feeds the rule engine; its terms
live apart from the case facts. Privacy: every model call uses cache=False, the page images
are deleted by the caller as soon as the reading is done, and nothing logs document content
(only counts and the backend).

Hindi text is a fixed-template DRAFT pending human review (Q-007).
"""
import logging
import re
from decimal import Decimal, InvalidOperation
from typing import Literal

from pydantic import BaseModel, ConfigDict

from sarthi.app.explain import _inr, _tpl
from sarthi.app.extract import FUZZY_HIGH, FUZZY_PASS, _image_part, _score
from sarthi.app.session import Session
from sarthi.app.verify import extract as typed_values
from sarthi.app.verify import verify
from sarthi.core.models import FactValue
from sarthi.data.parse_docs import normalise_ws
from sarthi.llm.client import chat

log = logging.getLogger(__name__)

# key -> (English, Hindi draft Q-007)
LABELS: dict[str, tuple[str, str]] = {
    "sum_insured": ("Sum insured", "बीमित राशि"),
    "policy_period": ("Policy period", "पॉलिसी की अवधि"),
    "ped_waiting_months": ("Waiting period for pre-existing conditions",
                           "पहले से मौजूद बीमारियों के लिए प्रतीक्षा अवधि"),
    "initial_waiting_days": ("Initial waiting period", "शुरुआती प्रतीक्षा अवधि"),
    "specific_waiting_months": ("Waiting period for specified illnesses",
                                "विशिष्ट बीमारियों के लिए प्रतीक्षा अवधि"),
    "room_rent_limit": ("Room rent limit", "कमरे के किराये की सीमा"),
    "co_payment": ("Co-payment", "सह-भुगतान"),
    "sub_limits": ("Sub-limits", "उप-सीमाएँ"),
    "claim_intimation_days": ("Time allowed to tell the insurer about a claim",
                              "दावे की सूचना बीमाकर्ता को देने की समय-सीमा"),
    "renewal_portability_terms": ("Renewal and portability terms", "नवीनीकरण और पोर्टेबिलिटी की शर्तें"),
}
TERM_KEYS = tuple(LABELS)
# Terms that are one number with a unit; the unit is the key's, never the model's.
KIND = {"sum_insured": "inr", "ped_waiting_months": "months", "initial_waiting_days": "days",
        "specific_waiting_months": "months", "co_payment": "pct", "claim_intimation_days": "days"}
LIST_KEYS = ("sub_limits",)
MAX_TEXT = 300

HEADING = {"en": "What your policy says", "hi": "आपकी पॉलिसी क्या कहती है"}
DISCLAIMER = {
    "en": ("This shows what the uploaded document says. It is not a conclusion about whether your claim is "
           "covered; the schedule, endorsements and other pages may change the meaning."),
    "hi": ("यह दिखाता है कि अपलोड किया गया दस्तावेज़ क्या कहता है। यह इस बारे में कोई निष्कर्ष नहीं है कि आपका "
           "दावा कवर है या नहीं; शेड्यूल, एंडोर्समेंट और दूसरे पन्ने अर्थ बदल सकते हैं।"),
}
MESSAGE = {
    "unverified": {"en": "We could not find this in your document.",
                   "hi": "यह बात हम आपके दस्तावेज़ में नहीं ढूँढ सके।"},
    "absent": {"en": "Not found in the pages we read.", "hi": "हमारे पढ़े पन्नों में नहीं मिला।"},
    "conflict": {"en": "Your document gives different values on different pages, so we are not showing any. "
                       "Please enter the value you want to use.",
                 "hi": "आपके दस्तावेज़ में अलग-अलग पन्नों पर अलग-अलग मान हैं, इसलिए हम कोई मान नहीं दिखा रहे। "
                       "जो मान आप इस्तेमाल करना चाहें, उसे दर्ज करें।"},
}
ENTERED_NOTE = {"en": "entered by you", "hi": "आपने दर्ज किया"}

SYSTEM_PROMPT = f"""You read one page of a policyholder's health-insurance policy document and extract its key terms for display.
Rules:
- Extract only what this page states. If a term is not stated on this page, leave it null. Never guess, infer or fill in a usual value.
- Each quote must be copied verbatim from the page (exact words, no paraphrase, no ellipsis) and must contain the value.
- Copy values as written (for example "Rs. 5,00,000", "36 months", "30 days", "20%", or the clause words for text terms).
- ped_waiting_months, specific_waiting_months: the waiting period. initial_waiting_days: the initial waiting period. claim_intimation_days: the time allowed to inform the insurer of a claim.
- room_rent_limit, co_payment, sub_limits (a list of the limits as written), renewal_portability_terms, policy_period, sum_insured: as written.
- page_no is 1 for this page. Do not decide what any term means for a claim.
Reply with ONLY one JSON object. Its keys are exactly: {", ".join(TERM_KEYS)}. Each key is null or {{"value": ..., "quote": "<verbatim text>", "page_no": <int>, "confidence": "high"|"medium"|"low"}}. Use no other keys."""

TRANSCRIBE_PROMPT = "Transcribe all text on this page exactly as written. Output only the text."


class PolicyTermOut(BaseModel):
    model_config = ConfigDict(extra="forbid")
    value: str | int | float | list[str] | None = None
    quote: str | None = None
    page_no: int | None = None
    confidence: Literal["high", "medium", "low"] | None = None   # the model's own claim; never used


class PolicyTermsOut(BaseModel):
    model_config = ConfigDict(extra="forbid")
    sum_insured: PolicyTermOut | None = None
    policy_period: PolicyTermOut | None = None
    ped_waiting_months: PolicyTermOut | None = None
    initial_waiting_days: PolicyTermOut | None = None
    specific_waiting_months: PolicyTermOut | None = None
    room_rent_limit: PolicyTermOut | None = None
    co_payment: PolicyTermOut | None = None
    sub_limits: PolicyTermOut | None = None
    claim_intimation_days: PolicyTermOut | None = None
    renewal_portability_terms: PolicyTermOut | None = None


class PolicyTerm(FactValue):
    """A policy term. needs_confirmation terms carry no value and no quote (nothing unverified
    is ever shown); `reason` says why."""
    reason: Literal["unverified", "conflict"] | None = None


class PolicyTerms(dict):
    """key -> PolicyTerm, plus `backend`: which model backend(s) read the document."""
    backend: str | None = None


# ---------- numbers and values ----------

_BARE = re.compile(r"\s*\d[\d,]*(?:\.\d+)?\s*")


def _number(key: str, raw) -> Decimal | None:
    """The number a value stands for, in the unit of its key. A bare number is already in that
    unit; "3 years" for a months key is 36; a value in another unit is not a number for this key."""
    if isinstance(raw, bool) or raw is None:
        return None
    if isinstance(raw, (int, float)):
        return Decimal(str(raw))
    s = str(raw)
    for kind, v in typed_values(s, lenient=True)[0]:
        if kind == KIND[key]:
            return Decimal(v)
    if _BARE.fullmatch(s):
        try:
            return Decimal(s.strip().replace(",", ""))
        except InvalidOperation:
            return None
    return None


def _num_out(d: Decimal) -> int | float:
    return int(d) if d == d.to_integral_value() else float(d)


def _canon(key: str, raw):
    """The value as stored, or None if it is not usable for this key."""
    if key in KIND:
        d = _number(key, raw)
        return None if d is None or d < 0 else _num_out(d)
    if key in LIST_KEYS:
        items = [raw] if isinstance(raw, str) else raw if isinstance(raw, list) else None
        items = [normalise_ws(x) for x in items or [] if isinstance(x, str) and normalise_ws(x)]
        return items or None
    if isinstance(raw, (bool, list)) or raw is None:
        return None
    s = normalise_ws(str(raw))
    return s or None


def _supported(key: str, value, quote: str) -> bool:
    """Is the value backed by its own quote? Numbers: the same number in the same unit appears
    in the quote (verify.extract typing). Text: the value is contained in the quote."""
    q = normalise_ws(quote)
    if not q:
        return False
    if key in KIND:
        want = Decimal(str(value)).normalize()
        return any(k == KIND[key] and Decimal(v).normalize() == want for k, v in typed_values(q, lenient=True)[0])
    parts = value if key in LIST_KEYS else [value]
    return all(normalise_ws(p).lower() in q.lower() for p in parts)


def parse_term_input(key: str, raw):
    """Server-side parse of a user-entered value; raises ValueError with a clear message."""
    if key in KIND:
        d = _number(key, raw)
        if d is None or d < 0:
            raise ValueError("Enter a number" + {"inr": " of rupees, for example 5,00,000.",
                                                "months": " of months, for example 36.",
                                                "days": " of days, for example 30.",
                                                "pct": ", for example 20."}[KIND[key]])
        return _num_out(d)
    if key in LIST_KEYS:
        items = re.split(r"[;\n]", raw) if isinstance(raw, str) else raw
        if not isinstance(items, list) or not all(isinstance(x, str) for x in items):
            raise ValueError("Enter the limits separated by semicolons.")
        items = [normalise_ws(x) for x in items if normalise_ws(x)]
        if not items or any(len(x) > MAX_TEXT for x in items):
            raise ValueError(f"Enter the limits separated by semicolons (up to {MAX_TEXT} characters each).")
        return items
    if not isinstance(raw, str) or not normalise_ws(raw) or len(raw) > MAX_TEXT:
        raise ValueError(f"Enter some text (up to {MAX_TEXT} characters).")
    return normalise_ws(raw)


# ---------- extraction ----------

def _page_candidates(session: Session, page, page_no: int, backends: set[str]) -> list[tuple[str, PolicyTerm]]:
    text_layer = session.page_text(page)
    from_photo = text_layer is None
    if from_photo:
        content = [{"type": "text", "text": "Extract the key terms from this page."}, _image_part(page)]
    else:
        # The PDF text layer is quoted verbatim, so read it directly: fewer tokens, no vision dependency.
        content = [{"type": "text", "text": "Extract the key terms from this page. The page text is below.\n\n"
                                            + text_layer}]
    res = chat(role="reader", cache=False, schema=PolicyTermsOut, messages=[
        {"role": "system", "content": SYSTEM_PROMPT},
        {"role": "user", "content": content}])
    if getattr(res, "backend", None):
        backends.add(res.backend)
    if res.parsed is None:
        return []
    if from_photo:
        t = chat(role="reader", cache=False, messages=[
            {"role": "user", "content": [{"type": "text", "text": TRANSCRIBE_PROMPT}, _image_part(page)]}])
        haystack = normalise_ws(t.text or "")
    else:
        haystack = normalise_ws(text_layer)

    out = []
    for key in TERM_KEYS:
        term: PolicyTermOut | None = getattr(res.parsed, key, None)
        if term is None or term.value is None or term.value == "" or term.value == []:
            continue
        nq = normalise_ws(term.quote or "")
        if not nq:
            score = 0
        elif not from_photo:
            score = 100 if nq in haystack else 0
        else:
            score = _score(nq, haystack)
        value = _canon(key, term.value)
        verified = (score >= (100 if not from_photo else FUZZY_PASS) and value is not None
                    and not res.needs_review and _supported(key, value, term.quote or ""))
        if verified:
            confidence = "high" if score >= FUZZY_HIGH else "medium"
            out.append((key, PolicyTerm(value=value, quote=term.quote.strip(), page_no=page_no,
                                        confidence=confidence, status="verified")))
        else:
            out.append((key, PolicyTerm(value=None, quote=None, page_no=page_no, confidence="low",
                                        status="needs_confirmation", reason="unverified")))
    return out


def extract_policy_terms(session: Session) -> PolicyTerms:
    """One reader call per page (plus one transcription call per photographed page).
    Merge: a verified value beats unverified ones; different verified values for the same
    term become a conflict (needs_confirmation, no value)."""
    per_key: dict[str, list[PolicyTerm]] = {}
    backends: set[str] = set()
    pages = session.pages()
    for i, page in enumerate(pages, start=1):
        for key, term in _page_candidates(session, page, i, backends):
            per_key.setdefault(key, []).append(term)
    terms = PolicyTerms()
    terms.backend = ", ".join(sorted(backends)) or None
    for key, cands in per_key.items():
        verified = [c for c in cands if c.status == "verified"]
        if not verified:
            terms[key] = cands[0]
        elif any(c.value != verified[0].value for c in verified[1:]):
            terms[key] = PolicyTerm(value=None, quote=None, page_no=None, confidence="low",
                                    status="needs_confirmation", reason="conflict")
        else:
            terms[key] = verified[0]
    log.info("policy read pages=%d terms=%d needs_confirmation=%d", len(pages), len(terms),
             sum(t.status == "needs_confirmation" for t in terms.values()))
    return terms


# ---------- display ----------

def _display(key: str, value, lang: str) -> str:
    if key == "sum_insured":
        return _inr(value)
    if key == "co_payment":
        return f"{value}%"
    if key in KIND:
        unit = KIND[key]
        return f'{value} {_tpl(lang)["labels"]["units"][unit]}'
    return "; ".join(value) if isinstance(value, list) else str(value)


def _state(f: PolicyTerm | None) -> str:
    if f is None:
        return "absent"
    if f.status == "needs_confirmation":
        return "conflict" if f.reason == "conflict" else "unverified"
    if f.status == "user_confirmed":
        return "confirmed" if f.quote else "entered"
    return "found"


def _line(x: dict, lang: str) -> str:
    if x["display"] is None:
        return f'- {x["label"][lang]}: {x["message"][lang]}'
    line = f'- {x["label"][lang]}: {x["display"][lang]}'
    if x["quote"]:
        page = f' ({_tpl(lang)["labels"]["page"]} {x["page_no"]})' if x["page_no"] is not None else ""
        line += f' — "{x["quote"]}"{page}'
    else:
        line += f' ({ENTERED_NOTE[lang]})'
    return line


def policy_json(terms: dict[str, PolicyTerm]) -> dict | None:
    """Terms with fixed-template labels, values, quotes and pages, in both languages, plus the
    plain text of the section. None if the text fails the verify() self-check (then the
    section is not shown)."""
    rows = []
    for key in TERM_KEYS:
        f = terms.get(key)
        state = _state(f)
        shown = state in ("found", "confirmed", "entered")
        rows.append({
            "key": key, "label": {"en": LABELS[key][0], "hi": LABELS[key][1]}, "state": state,
            "status": f.status if f else None, "value": f.value if shown else None,
            "display": {l: _display(key, f.value, l) for l in ("en", "hi")} if shown else None,
            "quote": f.quote if shown else None, "page_no": f.page_no if shown else None,
            "confidence": f.confidence if shown and f.quote else None,
            "message": MESSAGE[state] if not shown else None})
    texts = {l: "\n".join([HEADING[l], *(_line(x, l) for x in rows), DISCLAIMER[l]]) for l in ("en", "hi")}
    shown = [x for x in rows if x["display"]]
    quotes = [x["quote"] for x in shown if x["quote"]]
    quotes += [x["display"]["en"] for x in shown if x["key"] not in KIND]      # document or user words
    values = [("int", x["page_no"]) for x in shown if x["page_no"] is not None]
    for x in shown:
        if x["key"] in KIND:
            values.append((KIND[x["key"]], x["value"]))
    for lang, text in texts.items():
        r = verify(text, [], extra_quotes=quotes, extra_values=values)
        if not r.ok:
            log.error("policy section failed verify lang=%s problems=%d", lang, len(r.problems))
            return None
    return {"verified": True, "heading": HEADING, "disclaimer": DISCLAIMER, "terms": rows, "text": texts}
