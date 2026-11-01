"""Grievance letter + deadlines. Pure functions; no promises, no clinical comment."""
from __future__ import annotations

import calendar
import io
from datetime import date, timedelta
from pathlib import Path
from string import Template
from typing import NamedTuple

import pymupdf

from sarthi.app.labels import label

TEMPLATES = Path(__file__).parent / "templates"
LETTER_FACT_KEYS = ("policyholder_name", "policy_number", "claim_number",
                    "claim_amount_inr", "insurer_name", "complaint_sent_date")
_NOT_IN_TEMPLATE = ("claim_amount_inr", "complaint_sent_date")  # the latter only sets the dates
_BLANKS = {
    "en": {"policyholder_name": "[your name]", "policy_number": "[policy number]",
           "claim_number": "[claim number]", "claim_amount_inr": "[claim amount]",
           "insurer_name": "[insurer name]"},
    "hi": {"policyholder_name": "[आपका नाम]", "policy_number": "[पॉलिसी संख्या]",
           "claim_number": "[दावा संख्या]", "claim_amount_inr": "[दावा राशि]",
           "insurer_name": "[बीमाकर्ता का नाम]"},
}
class Deadlines(NamedTuple):
    insurer_reply_by: date
    ombudsman_earliest: date
    ombudsman_latest: date


def _v(params: dict, key: str):
    """Value of a param: nested `{value, ...}` or a legacy flat number. KeyError if absent."""
    p = params[key]
    return p["value"] if isinstance(p, dict) else p


def _has(params: dict, key: str) -> bool:
    return key in params and _v(params, key) is not None


def _need(params: dict) -> None:
    if not _has(params, "insurer_reply_days"):
        raise KeyError("GRIEVANCE_ROUTE param missing: insurer_reply_days")
    if not (_has(params, "ombudsman_wait_months") or _has(params, "ombudsman_wait_days")):
        raise KeyError("GRIEVANCE_ROUTE param missing: ombudsman_wait_months")
    if not _has(params, "ombudsman_limit_months"):
        raise KeyError("GRIEVANCE_ROUTE param missing: ombudsman_limit_months")


def _claim_limit(params: dict):
    for k in ("ombudsman_claim_limit_inr", "ombudsman_cap_inr"):  # second: legacy flat name
        if _has(params, k):
            return _v(params, k)
    return None


def _award_cap(params: dict):
    return _v(params, "ombudsman_award_cap_inr") if _has(params, "ombudsman_award_cap_inr") else None


REPLY_DATE_LABEL = "your insurer's reply date (entered by you)"


def deadline_sources(params: dict, letter_date: date | None = None,
                     insurer_reply_date: date | None = None) -> dict:
    """For each deadline, the quote/page of the param that sets it (nested params only).
    When the user-entered reply date sets `ombudsman_earliest`, that date is the source."""
    pairs = {"insurer_reply_by": "insurer_reply_days", "ombudsman_earliest": "ombudsman_wait_months",
             "ombudsman_latest": "ombudsman_limit_months"}
    out = {}
    for dl, key in pairs.items():
        p = params.get(key)
        if isinstance(p, dict) and p.get("quote"):
            out[dl] = {k: p.get(k) for k in ("quote", "page_no", "source_id", "value", "unit")}
    if (out and letter_date and insurer_reply_date and "ombudsman_earliest" in out
            and _has(params, "ombudsman_wait_months")
            and insurer_reply_date < _add_months(letter_date, int(_v(params, "ombudsman_wait_months")))):
        out["ombudsman_earliest"] = {"quote": None, "page_no": None, "source_id": None,
                                     "value": None, "unit": None, "label": REPLY_DATE_LABEL}
    return out


def _add_months(d: date, months: int) -> date:
    m = d.month - 1 + months
    y, m = d.year + m // 12, m % 12 + 1
    return date(y, m, min(d.day, calendar.monthrange(y, m)[1]))


def deadlines(letter_date: date, insurer_reply_date: date | None, *, params: dict) -> Deadlines:
    _need(params)
    if _has(params, "ombudsman_wait_months"):
        waited = _add_months(letter_date, int(_v(params, "ombudsman_wait_months")))
    else:  # legacy flat days
        waited = letter_date + timedelta(days=_v(params, "ombudsman_wait_days"))
    # A known insurer reply opens the Ombudsman route as soon as it arrives, if that is
    # before letter + wait; otherwise the wait applies.
    earliest = min(insurer_reply_date, waited) if insurer_reply_date else waited
    base = insurer_reply_date or earliest
    return Deadlines(letter_date + timedelta(days=_v(params, "insurer_reply_days")),
                     earliest, _add_months(base, int(_v(params, "ombudsman_limit_months"))))


def _d(d: date) -> str:
    return d.strftime("%d/%m/%Y")


def _inr(n) -> str:
    s = str(int(round(float(n))))
    if len(s) > 3:
        head, tail = s[:-3], s[-3:]
        parts = []
        while len(head) > 2:
            parts.insert(0, head[-2:])
            head = head[:-2]
        if head:
            parts.insert(0, head)
        s = ",".join(parts + [tail])
    return "₹" + s


def _lakh(n) -> str:
    x = float(n) / 100000
    return f"₹{x:g} lakh" if x == int(x) or x >= 1 else _inr(n)


def _val(facts: dict, key: str, lang: str) -> str:
    fv = facts.get(key)
    v = getattr(fv, "value", fv)
    if v in (None, ""):
        return _BLANKS[lang][key]
    return _inr(v) if key == "claim_amount_inr" else str(v)


_L = {
    "en": dict(rule="Rule", src="Source", page="page", quote="Rule text", facts="Facts relied on",
               fact_page="page",
               cap="\nNote: your claim amount {amt} is above the Ombudsman's claim-amount limit "
                   "({cap}); consider the consumer commission.\n",
               award="\nNote: the Ombudsman can award at most {cap}.\n"),
    "hi": dict(rule="नियम", src="स्रोत", page="पृष्ठ", quote="नियम का पाठ (अंग्रेज़ी में)",
               facts="जिन तथ्यों पर आधारित", fact_page="पृष्ठ",
               cap="\nटिप्पणी: आपके दावे की राशि {amt} बीमा लोकपाल की दावा-राशि सीमा ({cap}) से अधिक है; "
                   "उपभोक्ता आयोग पर विचार करें।\n",
               award="\nटिप्पणी: बीमा लोकपाल अधिकतम {cap} तक का अवॉर्ड दे सकता है।\n"),
}


def _block(f, lang: str) -> str:
    t = _L[lang]
    pg = f" ({t['page']} {f.page_no})" if f.page_no is not None else ""
    lines = [f"{t['rule']}: {f.rule_id} (v{f.rule_version})",
             f"{t['quote']}{pg}: \"{f.rule_quote}\""]
    used = [(k, v) for k, v in f.facts_used.items() if v.get("quote")]
    if used:
        lines.append(f"{t['facts']}:")
        for k, v in used:
            p = f" ({t['fact_page']} {v['page_no']})" if v.get("page_no") is not None else ""
            lines.append(f"  - {label(k, lang)}: \"{v['quote']}\"{p}")
    return "\n".join(lines) + "\n"


def cap_note_text(amt, params: dict, lang: str) -> str:
    """The Ombudsman limit note for a claim amount ("" when none applies)."""
    limit, award = _claim_limit(params), _award_cap(params)
    if amt in (None, ""):
        return ""
    if limit is not None and float(amt) > float(limit):
        return _L[lang]["cap"].format(amt=_inr(amt), cap=_lakh(limit))
    if award is not None and float(amt) > float(award):
        return _L[lang]["award"].format(cap=_lakh(award))
    return ""


def build_letter(facts: dict, findings: list, lang: str, *, params: dict,
                 letter_date: date, insurer_reply_date: date | None = None) -> str:
    """`params`, `letter_date` (and optional `insurer_reply_date`) are keyword extras
    added to the brief's signature so the output is deterministic and rule-driven."""
    if lang not in _L:
        raise ValueError(f"unsupported language: {lang}")
    ch = [f for f in findings if f.verdict == "CHALLENGEABLE"]
    if not ch:
        raise ValueError("no CHALLENGEABLE finding: nothing to write a grievance about")
    dl = deadlines(letter_date, insurer_reply_date, params=params)
    cap_note = cap_note_text(getattr(facts.get("claim_amount_inr"), "value", None), params, lang)
    raw = (TEMPLATES / f"letter_{lang}.txt").read_text(encoding="utf-8")
    # Lines starting with "#" are template-only comments (e.g. the Q-007 draft marker).
    raw = "\n".join(l for l in raw.split("\n") if not l.startswith("#"))
    tpl = Template(raw)
    return tpl.substitute(
        {k: _val(facts, k, lang) for k in LETTER_FACT_KEYS if k not in _NOT_IN_TEMPLATE},
        claim_amount=_val(facts, "claim_amount_inr", lang),
        letter_date=_d(letter_date), insurer_reply_days=_v(params, "insurer_reply_days"),
        insurer_reply_by=_d(dl.insurer_reply_by), ombudsman_earliest=_d(dl.ombudsman_earliest),
        ombudsman_latest=_d(dl.ombudsman_latest),
        findings_block="\n".join(_block(f, lang) for f in ch), cap_note=cap_note)


def _esc(s: str) -> str:
    return s.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")


def to_pdf(text: str) -> bytes:
    """A4 PDF. Uses insert_htmlbox so MuPDF's bundled Noto fonts cover Devanagari."""
    css = "body{font-family:sans-serif;font-size:10.5pt;line-height:1.35;} p{margin:0 0 0.2em 0;white-space:pre-wrap;}"
    html = "".join(f"<p>{_esc(l) or '&nbsp;'}</p>" for l in text.split("\n"))
    story = pymupdf.Story(html=html, user_css=css)
    page_rect = pymupdf.paper_rect("a4")
    where = page_rect + (56, 56, -56, -56)

    def rectfn(rect_num, filled):
        return page_rect, where, None

    buf = io.BytesIO()
    writer = pymupdf.DocumentWriter(buf)
    story.write(writer, rectfn)
    writer.close()
    return buf.getvalue()
