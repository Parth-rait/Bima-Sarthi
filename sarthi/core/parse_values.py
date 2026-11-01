"""Indian-format value parsing: rupee amounts and dates.

Both functions return None on anything they cannot read with certainty
(fail closed: an unparsed value becomes a missing fact, never a guess).
"""
import re
from datetime import date
from decimal import ROUND_HALF_UP, Decimal, InvalidOperation

_DEVANAGARI = {ord(c): str(i) for i, c in enumerate("०१२३४५६७८९")}
_MULT = {"lakh": 10**5, "lakhs": 10**5, "lac": 10**5, "lacs": 10**5,
         "crore": 10**7, "crores": 10**7, "cr": 10**7}
_INR_RE = re.compile(
    r"^(?:rs\.?|inr|₹)?\s*(\d[\d,]*(?:\.\d+)?|\.\d+)\s*(lakhs?|lacs?|crores?|cr)?\s*(?:/-)?$")
_MONTHS = {m: i for i, m in enumerate(
    ["jan", "feb", "mar", "apr", "may", "jun", "jul", "aug", "sep", "oct", "nov", "dec"], 1)}
_NUM_DATE = re.compile(r"^(\d{1,2})[/.\-](\d{1,2})[/.\-](\d{4})$")
_TXT_DATE = re.compile(r"^(\d{1,2})[\s\-]+([A-Za-z]+)\.?,?[\s\-]+(\d{4})$")


def parse_inr(s: str) -> int | None:
    """Rupee amount to whole rupees (paise rounded half up). None if unreadable."""
    if not isinstance(s, str):
        return None
    t = s.translate(_DEVANAGARI).strip().lower()
    m = _INR_RE.match(t)
    if not m:
        return None
    try:
        amount = Decimal(m.group(1).replace(",", ""))
    except InvalidOperation:
        return None
    if m.group(2):
        amount *= _MULT[m.group(2)]
    return int(amount.to_integral_value(rounding=ROUND_HALF_UP))


def _mk(y: int, mo: int, d: int) -> date | None:
    try:
        return date(y, mo, d)
    except ValueError:
        return None


def parse_date_in(s: str, *, from_photo: bool) -> tuple[date | None, bool]:
    """Parse an Indian-format date. Numeric dates are always DD-MM-YYYY (never MM/DD).

    Returns (date, ambiguous). `ambiguous` is True only when the text came from a
    photo (OCR can swap/misread digits) AND day and month are both <= 12 AND
    day != month, i.e. a DD/MM vs MM/DD misreading would yield a different valid
    date. Month-name dates are never ambiguous.
    """
    if not isinstance(s, str):
        return None, False
    t = s.translate(_DEVANAGARI).strip()
    m = _NUM_DATE.match(t)
    if m:
        d, mo, y = int(m.group(1)), int(m.group(2)), int(m.group(3))
        parsed = _mk(y, mo, d)
        if parsed is None:
            return None, False
        return parsed, bool(from_photo and d <= 12 and mo <= 12 and d != mo)
    m = _TXT_DATE.match(t)
    if m:
        mo = _MONTHS.get(m.group(2)[:3].lower())
        if mo is None:
            return None, False
        return _mk(int(m.group(3)), mo, int(m.group(1))), False
    return None, False
