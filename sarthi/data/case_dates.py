"""Recover a missing admission/claim date from the stored judgment text (R105).

Deterministic, no model. A date is proposed only when its exact written form appears in the text
and the words around it say it is the admission or the claim date; complaint-filing, order,
repudiation, discharge and policy-period dates are refused. The row is written `needs_review`
with the verbatim quote and page: this module is a proposer, never the reviewer.
"""
import json
import re
from dataclasses import dataclass
from datetime import date

from sarthi.core.store import Store
from sarthi.data.case_facts import _pages
from sarthi.data.parse_docs import normalise_ws

_MONTHS = {m: i for i, m in enumerate(
    ["jan", "feb", "mar", "apr", "may", "jun", "jul", "aug", "sep", "oct", "nov", "dec"], 1)}
_MON = (r"(?:january|february|march|april|may|june|july|august|september|october|november|december|"
        r"jan|feb|mar|apr|jun|jul|aug|sept|sep|oct|nov|dec)")
_NUM = re.compile(r"(?<![\d./\-,])(\d{1,2})([./\-])(\d{1,2})\2(\d{4}|\d{2})(?![\d])")
_DMY = re.compile(rf"(?<!\d)(\d{{1,2}})(?:st|nd|rd|th)?\s+(?:of\s+)?({_MON})\.?,?\s+(\d{{4}})(?!\d)", re.I)
_MDY = re.compile(rf"\b({_MON})\.?\s+(\d{{1,2}})(?:st|nd|rd|th)?,?\s+(\d{{4}})(?!\d)", re.I)

TWO_DIGIT_NOTE = "two-digit year read day-first (DD.MM.YY) and as 20xx"

# Context is read only inside the clause the date sits in (a colon is a label, not a boundary).
_ADMISSION = re.compile(
    r"\bwas\s+admitted\b|\bgot\s+admitted\b|\badmitted\s+(?:to|in|at|into|on|as|himself|herself)\b|"
    r"\bdate\s+of\s+admission|\badmission\s+(?:on|date|in|to)\b|\bhospitali[sz]ed\b|"
    r"\bhospitali[sz]ation\s+(?:on|from|date)\b", re.I)
_CLAIM = re.compile(r"\bclaim\w*.*?(?:lodg|submit|prefer|intimat|regist|raised|made|reported|filed)|"
                    r"(?:lodg|submit|prefer|intimat|regist|raised|reported)\w*.*?\bclaim", re.I | re.S)
_REFUSE = re.compile(
    r"complaint|petition|appeal|revision|instituted|\border\b|judg(?:e)?ment|decided|pronounced|"
    r"reserved|listed|hearing|next date|repudiat|reject|denied|declin|discharg|renew|valid|"
    r"incepti|commenc|\bperiod\b|policy\s+(?:was\s+)?(?:issued|taken|purchased|start)|\bborn\b|"
    r"\bdob\b|death|\bdied\b|notice|reply|replied|rejoinder|\bvakalat|"
    r"\b(?:note|circular|notification|letter|scheme|agreement|settlement|memo|resolution)\b|"
    r"\b(?:within|before|until|till|upto|deadline)\b|\bup\s+to\b|\blast\s+date\b", re.I)


@dataclass
class Candidate:
    field: str
    form: str
    iso: str
    page_no: int
    quote: str
    note: str


def _mk(y: int, mo: int, d: int) -> date | None:
    try:
        return date(y, mo, d)
    except ValueError:
        return None


def find_dates(text: str) -> list[tuple[str, date, int, str]]:
    """(form as written, date, start offset, note) for every readable date, in text order."""
    out: list[tuple[str, date, int, str]] = []
    for m in _NUM.finditer(text):
        a, _, b, y = int(m.group(1)), m.group(2), int(m.group(3)), m.group(4)
        year, note = (int(y), "") if len(y) == 4 else (2000 + int(y), TWO_DIGIT_NOTE)
        d = _mk(year, b, a)  # always day-first
        if d and 1990 <= year <= 2035:
            out.append((m.group(0), d, m.start(), note))
    for m in _DMY.finditer(text):
        mo = _MONTHS[m.group(2).lower()[:3]]
        d = _mk(int(m.group(3)), mo, int(m.group(1)))
        if d:
            out.append((m.group(0), d, m.start(), ""))
    for m in _MDY.finditer(text):
        mo = _MONTHS[m.group(1).lower()[:3]]
        d = _mk(int(m.group(3)), mo, int(m.group(2)))
        if d:
            out.append((m.group(0), d, m.start(), ""))
    out.sort(key=lambda r: r[2])
    return out


def _clause(text: str, start: int, end: int) -> tuple[str, str]:
    """Words before and after the date within its own clause (bounded to a short window)."""
    before = text[max(0, start - 110):start]
    cut = [m.end() for m in re.finditer(r";|\.\s+(?=[A-Z])|\band\b|\bbut\b|\bwhereas\b|\bwhile\b", before)]
    if cut:
        before = before[cut[-1]:]
    after = text[end:end + 40]
    m = re.search(r"[;:,]|\.\s|\band\b|\bbut\b", after)
    if m:
        after = after[:m.start()]
    return before, after


def _quote(text: str, start: int, end: int) -> str:
    lo = max(0, start - 140)
    hi = min(len(text), end + 80)
    # snap to word boundaries so the quote is a clean verbatim slice
    if lo > 0:
        sp = text.find(" ", lo)
        lo = sp + 1 if 0 <= sp < start else lo
    if hi < len(text):
        sp = text.rfind(" ", end, hi)
        hi = sp if sp > end else hi
    return text[lo:hi].strip()


def propose_date(pages: list[tuple[int, str]]) -> Candidate | None:
    """Earliest-in-text admission date, else earliest claim date; None when nothing qualifies."""
    best: dict[str, Candidate] = {}
    for page_no, text in pages:
        for form, d, start, note in find_dates(text):
            end = start + len(form)
            before, after = _clause(text, start, end)
            ctx = before + " " + after
            if _REFUSE.search(ctx):
                continue
            field = ("admission_date" if _ADMISSION.search(ctx)
                     else "claim_date" if _CLAIM.search(ctx) else None)
            if field is None or field in best:
                continue
            best[field] = Candidate(field, form, d.isoformat(), page_no, _quote(text, start, end), note)
    return best.get("admission_date") or best.get("claim_date")


def _has_date_fact(case_id: str, store: Store) -> bool:
    return store.con.execute(
        "SELECT 1 FROM case_fact WHERE case_id=? AND field IN ('claim_date','admission_date')",
        [case_id]).fetchone() is not None


def recover_dates(case_ids: list[str], store: Store) -> dict[str, str]:
    """case_id -> field recorded. Cases that already have any claim/admission date row are skipped."""
    done: dict[str, str] = {}
    for cid in case_ids:
        if _has_date_fact(cid, store):
            continue
        c = propose_date(_pages(cid, store))
        if c is None:
            continue
        pages = dict(_pages(cid, store))
        assert c.form in c.quote and normalise_ws(c.quote) in normalise_ws(pages[c.page_no])
        note = (f"recovered by text scan of the judgment (not the model); exact form {c.form!r} "
                f"appears in the quote; {c.note + '; ' if c.note else ''}"
                "not reviewed - check it is the "
                f"{'admission' if c.field == 'admission_date' else 'claim'} date, not a filing/order date")
        store.upsert("case_fact", [dict(case_id=cid, field=c.field, value=json.dumps(c.iso), quote=c.quote,
                                        page_no=c.page_no, confidence=0.5, status="needs_review",
                                        reviewer_note=note)], key=["case_id", "field"])
        done[cid] = c.field
    return done


def flagged_section(store: Store, case_ids: list[str]) -> str:
    """Markdown: each case's date facts and every needs_review fact (for a human to decide)."""
    L = ["", "# Facts to review: new in-scope cases (R105 expansion)", "",
         "Dates recovered by text scan are `needs_review`; nothing below is reviewed.", ""]
    for cid in case_ids:
        L.append(f"## {cid}")
        rows = store.con.execute(
            "SELECT field, value, quote, page_no, status, reviewer_note FROM case_fact "
            "WHERE case_id=? AND (status='needs_review' OR field IN ('claim_date','admission_date')) "
            "ORDER BY field", [cid]).fetchall()
        for field, value, quote, page, status, note in rows:
            where = f" (p.{page})" if page is not None else ""
            L.append(f"- `{field}` = {value} [{status}]{where}" + (f" > \"{quote}\"" if quote else ""))
            if note:
                L.append(f"  - note: {note}")
        L.append("")
    return "\n".join(L) + "\n"
