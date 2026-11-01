"""Verifier for explanation text: every number, date and rule ID must be supported
by the findings, and no promise / endorsement / treatment / diagnosis comment may appear.

Numbers are unit-typed. A value in the text must match an allowed value of its OWN unit:
  inr (rupees; lakh/crore/hazaar normalised), months (years x 12), days,
  minutes (hours x 60), pct, date (ISO). Bare integers only match page numbers, rule
  versions and facts whose key carries no unit. Date pieces are never loose integers.
Number words ("sixty", "साठ") are never accepted: they cannot be checked, so they fail.
"""
import re
import unicodedata
from dataclasses import dataclass, field
from datetime import date, datetime
from decimal import Decimal
from functools import lru_cache
from pathlib import Path

import yaml

from sarthi.core.models import Finding

_DEV = {ord(c): str(i) for i, c in enumerate("०१२३४५६७८९")}
RULE_ID_RE = re.compile(r"(?<![A-Za-z0-9_])[A-Z][A-Z0-9]*(?:_[A-Z0-9]+)+(?![A-Za-z0-9_])")

# Blocked wording, matched on text with quotes removed, NFC, nukta removed (so ज़रूर == जरूर),
# casefolded, curly apostrophes straightened.
BLOCKED_EN = [
    r"\byou(?:'ll| will| would| should| can expect|'re going to| are going to| are entitled)\b",
    r"\bwill (?:win|rule|have to|pay|refund|reimburse|be (?:approved|paid|accepted|reimbursed|refunded|credited|settled|returned))\b",
    r"\bmust pay\b|\bentitled\b|\bobliged\b|\bobligat\w*|\bliab\w*|\b(?:has|have) to (?:pay|refund)\b",
    r"\bwill (?:succeed|work|help)\b|\bsuccess\w*|\bowed?\b|\bowes\b",
    r"\bshould (?:pay|refund|receive|get)\b|\bought to\b",
    r"\bstrong case\b|\bgood case\b|\blikely\b|\bunlikely\b|\bchances?\b|\bprobabl\w*",
    r"\bget paid\b|\bcome back\b|\bin (?:your|their) favou?r\b",
    r"\bcertain(?:ly)?\b|\bsure(?:ly)?\b|\bdefinite(?:ly)?\b|\bguarantee\w*|\bclearly\b",
    r"\bacted (?:correctly|incorrectly|wrongly|rightly|properly|improperly|unfairly|fairly|unlawfully)\b",
    r"\b(?:is|was|are|were|be|been) (?:(?:clearly|entirely|completely|medically|not|in)\s+)*"
    r"(?:correct\w*|incorrect\w*|wrong\w*|right|justified|unjustified|fair|unfair|improper\w*|proper\w*|"
    r"unlawful|lawful|illegal|legal|valid|invalid|unnecessary|necessary|at fault)\b",
    r"\btreatment (?:is|was)\b", r"\bdiagnosis\b",
]
# Hindi mirrors: you will get / will be approved / must pay / certainly / guarantee /
# decision right-wrong / entitled / liable / likely / treatment / diagnosis.
BLOCKED_HI = [
    r"मिलेगा|मिलेगी|मिल जाएगा|मिल जाएगी|मिल सकता", r"जरूर|निश्चित|पक्का|गारंटी|उम्मीद",
    r"मंजूर (हो )?(होगा|जाएगा)", r"स्वीकार (हो )?(होगा|जाएगा)", r"देना (ही )?होगा",
    r"जीतेंगे|जीत जाएंगे", r"इलाज", r"निदान", r"हकदार|जिम्मेदार|बाध्य|जायज|नाजायज|वापस मिल",
    r"(फैसला|फैसले|अस्वीकृति|कटौती|दावा) (सही|गलत|वैध|अवैध) (है|था)",
]
_BLOCKED = [re.compile(p) for p in BLOCKED_EN + BLOCKED_HI]

_EN_WORDS = re.compile(
    r"\b(one|two|three|four|five|six|seven|eight|nine|ten|eleven|twelve|thirteen|fourteen|fifteen|"
    r"sixteen|seventeen|eighteen|nineteen|twenty|thirty|forty|fifty|sixty|seventy|eighty|ninety|"
    r"hundred|thousand|lakhs?|lacs?|crores?|double|twice|thrice|triple|half|dozen|couple)\b", re.I)
_D = "ऀ-ॿ"
_HI_WORDS = re.compile(
    rf"(?<![{_D}])(शून्य|एक|दो|तीन|चार|पांच|पाँच|छह|छः|सात|आठ|नौ|दस|ग्यारह|बारह|तेरह|चौदह|पंद्रह|पन्द्रह|"
    rf"सोलह|सत्रह|अठारह|उन्नीस|बीस|तीस|चालीस|पचास|साठ|सत्तर|अस्सी|नब्बे|सौ|हजार|लाख|करोड|आधा|आधी|डेढ|ढाई|दोगुना|दुगुना|दर्जन)(?![{_D}])")

_IMPLICIT = re.compile(
    r"(?<![A-Za-z])(?:a|an|half a|half an|each|every)\s+(?:week|month|year|day|fortnight|hour|minute)s?(?![a-z])", re.I)
_MONTHS = {m: i for i, m in enumerate(
    ["jan", "feb", "mar", "apr", "may", "jun", "jul", "aug", "sep", "oct", "nov", "dec"], 1)}
_NUM = r"\d[\d,]*(?:\.\d+)?"
_RUP = r"(?:रुपये|रुपए|रुपया|rupees?)"
_MAG = r"(?:lakhs?|lacs?|crores?|thousand|लाख|करोड|हजार)"
_UNITS = (r"(?:months?|years?|yrs?|weeks?|fortnights?|days?|hours?|hrs?|minutes?|mins?|"
          r"महीने|महीना|माह|साल|वर्ष|सप्ताह|हफ्ते|हफ्ता|दिन|घंटे|घंटा|मिनट)")
_MON = (r"(?<![A-Za-z])(?:january|february|march|april|may|june|july|august|september|october|november|"
        r"december|sept|jan|feb|mar|apr|jun|jul|aug|sep|oct|nov|dec)\.?(?![a-z])")
_ORD = r"(?:st|nd|rd|th)?"
_ORDW = ("of", "st", "nd", "rd", "th")


def _pattern(lenient: bool) -> re.Pattern:
    gap = r"(?:[A-Za-z]+\s+)?" if lenient else ""
    return re.compile(
        r"(?P<iso>(?<!\d)\d{4}-\d{2}-\d{2}(?!\d))"
        r"|(?P<dmy>(?<!\d)\d{1,2}[/.\-]\d{1,2}[/.\-]\d{4}(?!\d))"
        rf"|(?P<dmyt>(?<!\d)\d{{1,2}}{_ORD}\s+(?:of\s+)?{_MON},?\s+\d{{4}}(?!\d))"
        rf"|(?P<mdyt>{_MON}\s+\d{{1,2}}{_ORD},?\s+\d{{4}}(?!\d))"
        rf"|(?P<my>{_MON},?\s+\d{{4}}(?!\d))"
        rf"|(?P<dm>(?<!\d)\d{{1,2}}{_ORD}\s+(?:of\s+)?{_MON})"
        rf"|(?P<md>{_MON}\s+\d{{1,2}}{_ORD}(?!\d))"
        rf"|(?P<nth>(?<![A-Za-z])the\s+\d{{1,2}}(?:st|nd|rd|th)(?![a-z]))"
        r"|(?P<time>(?<![\d:])\d{1,2}:\d{2}(?::\d{2})?(?:\s*[ap]\.?m\.?)?)"
        r"|(?P<ref>(?<![A-Za-z])(?:section|clause|regulation|article|paragraph|para|rule)s?\s+\d+|(?:धारा|खंड)\s+\d+)"
        rf"|(?P<amt>(?:₹|Rs\.?|INR)\s*{_NUM}(?:\s*{_MAG}(?![a-z]))?(?:\s*{_RUP})?(?:/-)?"
        rf"|{_NUM}\s*{_MAG}(?![a-z])(?:\s*{_RUP})?"
        rf"|{_NUM}\s*{_RUP})"
        rf"|(?P<dur>(?P<dn>{_NUM})\s*-?\s*{gap}(?P<du>{_UNITS})(?![a-z]))"
        rf"|(?P<pct>{_NUM}\s*(?:%|per\s*cent|percent))"
        rf"|(?P<int>{_NUM})", re.I)


_TEXT_RE, _QUOTE_RE = _pattern(False), _pattern(True)
_MULT = {"lakh": 10**5, "lac": 10**5, "crore": 10**7, "thousand": 1000, "लाख": 10**5, "करोड": 10**7,
         "हजार": 1000}


@dataclass
class VerifyResult:
    ok: bool
    problems: list[str] = field(default_factory=list)


def _fold(s: str) -> str:
    """NFC, no nukta, ASCII digits."""
    return unicodedata.normalize("NFC", s).replace("\u093c", "").translate(_DEV)


def _dec(s: str) -> Decimal:
    return Decimal(s.replace(",", "")).normalize()


def _mk(y: int, m: int, d: int) -> str | None:
    try:
        return date(y, m, d).isoformat()
    except ValueError:
        return None


def _mon(name: str) -> int | None:
    return _MONTHS.get(name.strip(". ").lower()[:3])


def _amount(raw: str) -> Decimal | None:
    m = re.search(_MAG, raw, re.I)
    num = re.search(_NUM, raw)
    if not num:
        return None
    n = _dec(num.group(0))
    if m:
        return (n * _MULT[m.group(0).lower().rstrip("s")]).normalize()
    return n  # exact: paise are kept, never rounded (parse_inr would round to whole rupees)


def _time(raw: str) -> str | None:
    m = re.match(r"(\d{1,2}):(\d{2})(?::\d{2})?\s*([ap])?", raw, re.I)
    h, mi = int(m.group(1)), int(m.group(2))
    if m.group(3):
        h = h % 12 + (12 if m.group(3).lower() == "p" else 0)
    return f"{h:02d}:{mi:02d}" if h < 24 and mi < 60 else None


def extract(text: str, lenient: bool = False) -> tuple[list[tuple[str, object]], list[str]]:
    """Typed values found in `text`: [(kind, value)], plus unreadable tokens."""
    t = _fold(RULE_ID_RE.sub(" ", text))
    out: list[tuple[str, object]] = []
    bad: list[str] = []
    for m in (_QUOTE_RE if lenient else _TEXT_RE).finditer(t):
        kind, raw = m.lastgroup, m.group(0)
        if m.group("dn") is not None:
            kind = "dur"
        k, v = kind, None
        if kind == "iso":
            y, mo, d = map(int, raw.split("-"))
            k, v = "date", _mk(y, mo, d)
        elif kind == "dmy":
            d, mo, y = map(int, re.split(r"[/.\-]", raw))
            k, v = "date", _mk(y, mo, d)
        elif kind in ("dmyt", "mdyt"):
            nums = [int(n) for n in re.findall(r"\d+", raw)]  # [day, year] in both orders
            mon = next((_mon(w) for w in re.findall(r"[A-Za-z]+", raw) if _mon(w) and w.lower() not in _ORDW), None)
            k, v = "date", (_mk(nums[1], mon, nums[0]) if mon else None)
        elif kind == "my":
            mon = _mon(re.findall(r"[A-Za-z]+", raw)[0])
            k, v = "monthyear", (int(re.findall(r"\d{4}", raw)[0]), mon)
        elif kind in ("dm", "md"):
            mon = next(_mon(w) for w in re.findall(r"[A-Za-z]+", raw) if _mon(w) and w.lower() not in _ORDW)
            k, v = "daymonth", (mon, int(re.findall(r"\d+", raw)[0]))
        elif kind == "nth":
            k, v = "dayonly", int(re.findall(r"\d+", raw)[0])
        elif kind == "time":
            k, v = "time", _time(raw)
        elif kind == "ref":
            k, v = "ref", re.findall(r"\d+", raw)[0]
        elif kind == "amt":
            k, v = "inr", _amount(raw)
        elif kind == "dur":
            n, unit = _dec(m.group("dn")), m.group("du").lower()
            if unit.startswith(("year", "yr")) or unit in ("साल", "वर्ष"):
                k, v = "months", n * 12
            elif unit.startswith("month") or unit in ("महीने", "महीना", "माह"):
                k, v = "months", n
            elif unit.startswith("fortnight"):
                k, v = "days", n * 14
            elif unit.startswith("week") or unit in ("सप्ताह", "हफ्ते", "हफ्ता"):
                k, v = "days", n * 7
            elif unit.startswith("day") or unit == "दिन":
                k, v = "days", n
            elif unit.startswith(("hour", "hr")) or unit in ("घंटे", "घंटा"):
                k, v = "minutes", n * 60
            else:
                k, v = "minutes", n
        elif kind == "pct":
            k, v = "pct", _dec(re.search(_NUM, raw).group(0))
        else:
            k, v = "int", _dec(raw)
        if v is None:
            bad.append(raw)
        else:
            out.append((k, v.normalize() if isinstance(v, Decimal) else v))
    return out, bad


def kind_of_key(name: str) -> tuple[str, int, str] | None:
    """Unit implied by a fact/param key name: (kind, multiplier to base, display unit)."""
    toks = set(name.lower().split("_"))
    if toks & {"inr", "amount", "rupees", "rs", "premium"}:
        return "inr", 1, "inr"
    for pre, k, mul, disp in (("month", "months", 1, "months"), ("year", "months", 12, "years"),
                              ("fortnight", "days", 14, "fortnights"), ("week", "days", 7, "weeks"),
                              ("day", "days", 1, "days"), ("minute", "minutes", 1, "minutes"),
                              ("hour", "minutes", 60, "hours"), ("pct", "pct", 1, "pct"),
                              ("percent", "pct", 1, "pct")):
        if any(t.startswith(pre) for t in toks):
            return k, mul, disp
    return None


_ISO_STR = re.compile(r"^\d{4}-\d{2}-\d{2}(?:[T ]\d{2}:\d{2}(?::\d{2})?)?$")


def parse_iso(x) -> datetime | None:
    if isinstance(x, str) and _ISO_STR.match(x.strip()):
        try:
            return datetime.fromisoformat(x.strip())
        except ValueError:
            return None
    return None


class _Allowed:
    def __init__(self, findings: list[Finding]):
        self.typed: set = set()
        self.plain: set = set()
        self.refs: set[str] = set()
        self.ids: set[str] = set()
        self.quotes: list[str] = []
        self.card_text: list[str] = []
        stamps: list[datetime] = []

        for f in findings:
            self.ids.add(f.rule_id)
            self.plain.add(Decimal(f.rule_version).normalize())
            if f.page_no is not None:
                self.plain.add(Decimal(f.page_no).normalize())
            self._text(f.rule_quote)
            self.quotes.append(f.rule_quote)
            self.refs.update(re.findall(r"\d+", _fold(f.rule_quote or "")))
            for s in (f.question_en, f.question_hi, f.action_en, f.action_hi):
                self._text(s)
                if s:
                    self.card_text.append(s)
            for key, fv in f.facts_used.items():
                if fv.get("page_no") is not None:
                    self.plain.add(Decimal(fv["page_no"]).normalize())
                if fv.get("quote"):
                    self._text(fv["quote"])
                    self.quotes.append(fv["quote"])
                self._value(key, fv.get("value"), stamps)
        dates = sorted({s.date() for s in stamps})
        for i, a in enumerate(dates):
            for b in dates[i + 1:]:
                self.typed.add(("days", Decimal((b - a).days)))
                self.typed.add(("months", Decimal(
                    (b.year - a.year) * 12 + b.month - a.month - (b.day < a.day))))
        full = sorted(s for s in stamps if s.time() != datetime.min.time())
        for i, a in enumerate(full):
            for b in full[i + 1:]:
                self.typed.add(("minutes", Decimal(int((b - a).total_seconds() // 60))))

    def _add_date(self, d: date):
        self.typed.update({("date", d.isoformat()), ("daymonth", (d.month, d.day)),
                           ("monthyear", (d.year, d.month)), ("dayonly", d.day)})

    def _text(self, s: str | None, as_value: bool = False):
        if not s:
            return
        self.ids.update(RULE_ID_RE.findall(s))
        for k, v in extract(s, lenient=True)[0]:
            if k == "date":
                self._add_date(date.fromisoformat(v))
            elif k == "int":
                if as_value:
                    self.plain.add(v)
            elif k != "ref":
                self.typed.add((k, v))

    def _value(self, key: str, v, stamps: list):
        if v is None or isinstance(v, bool):
            return
        if isinstance(v, (list, tuple)):
            for x in v:
                self._value(key, x, stamps)
        elif isinstance(v, dict):
            for k2, x in v.items():
                self._value(str(k2), x, stamps)
        elif isinstance(v, (datetime, date)) or parse_iso(v):
            dt = v if isinstance(v, datetime) else parse_iso(v) if isinstance(v, str) else datetime.combine(v, datetime.min.time())
            has_time = isinstance(v, datetime) and v.time() != datetime.min.time() or (
                isinstance(v, str) and (":" in v))
            stamps.append(dt)
            self._add_date(dt.date())
            if has_time:
                self.typed.add(("time", f"{dt.hour:02d}:{dt.minute:02d}"))
        elif isinstance(v, (int, float, Decimal)):
            d = Decimal(str(v))
            if kk := kind_of_key(key):
                self.typed.add((kk[0], (d * kk[1]).normalize()))
            else:
                self.plain.add(d.normalize())
        elif isinstance(v, str):
            self._text(v, as_value=True)


@lru_cache(maxsize=1)
def _no_rule_sentences() -> tuple[str, ...]:
    """The fixed "no checked rule yet" sentences (en, hi). They deny that the decision is
    correct, which the blocked-phrase scan would otherwise flag; exempt only these exact texts."""
    d = Path(__file__).parent / "templates"
    return tuple(yaml.safe_load((d / f"{l}.yaml").read_text(encoding="utf-8"))["labels"]["no_rule"]
                 for l in ("en", "hi"))


def verify(text: str, findings: list[Finding]) -> VerifyResult:
    al = _Allowed(findings)
    problems: list[str] = []

    def strip(t: str, parts) -> str:
        for q in sorted(filter(None, parts), key=len, reverse=True):
            t = t.replace(q, " ")
        return t

    scan = strip(text, al.quotes)
    words = strip(scan, al.card_text)  # card wording is exempt from phrase and number-word scans
    words = strip(words, _no_rule_sentences())

    for rid in sorted(set(RULE_ID_RE.findall(scan)) - al.ids):
        problems.append(f"rule id not in findings: {rid}")

    found, bad = extract(scan)
    problems += [f"unreadable number: {b}" for b in bad]
    for kind, v in found:
        shown = format(v, "f") if isinstance(v, Decimal) else v
        if kind == "int":
            if v not in al.plain:
                problems.append(f"number not supported by findings: {shown}")
        elif kind == "ref":
            if v not in al.refs:
                problems.append(f"reference number not in the rule quote: {v}")
        elif (kind, v) not in al.typed:
            problems.append(f"{kind} value not supported by findings: {shown}")

    # number words / implicit quantities cannot be checked: reject them
    folded = _fold(RULE_ID_RE.sub(" ", words))
    words_text = _TEXT_RE.sub(" ", folded)
    for rx in (_EN_WORDS, _HI_WORDS, _IMPLICIT):
        for m in rx.finditer(words_text):
            problems.append(f"number written in words: {m.group(0)}")

    low = folded.casefold().replace("\u2019", "'")
    for rx in _BLOCKED:
        if (m := rx.search(low)):
            problems.append(f"blocked phrase: {m.group(0)}")
    return VerifyResult(ok=not problems, problems=problems)
