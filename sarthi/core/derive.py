"""Turn extracted facts into rule-card inputs (exactly KNOWN_INPUTS).

Facts with status `needs_confirmation` are treated as missing: rules never run
on unconfirmed facts. Unknown -> None, never a guess.
"""
from datetime import date, datetime

from sarthi.core.inputs import KNOWN_INPUTS
from sarthi.core.models import FactValue

# Canonical fact keys (spec §4 mapping + engine extras). Reused by extraction.
FACT_KEYS: tuple[str, ...] = (
    "inception_date", "ported_from_date", "claim_date", "admission_date",
    "rejection_ground", "disclosed_conditions", "alleged_undisclosed_condition",
    "fraud_alleged", "deductions", "cashless_request_at", "decision_at",
    "discharge_request_at", "final_auth_at", "cited_clause", "crc_approval_mentioned",
    "reasons_cite_terms",
    "renewal_gap_days", "continuity_confirmed", "policy_renewal_date", "cited_clause_found",
)

# Which fact keys feed each derived input (used for facts_used lineage).
INPUT_FACTS: dict[str, tuple[str, ...]] = {
    "continuous_cover_months": ("inception_date", "claim_date", "ported_from_date",
                                "renewal_gap_days", "continuity_confirmed"),
    "claim_date": ("claim_date",),
    "rejection_ground": ("rejection_ground",),
    "ped_disclosed": ("disclosed_conditions", "alleged_undisclosed_condition"),
    "fraud_alleged": ("fraud_alleged",),
    "deduction_items": ("deductions",),
    "nonpayable_overcharge_inr": ("deductions",),
    "cashless_minutes": ("cashless_request_at", "decision_at"),
    "discharge_minutes": ("discharge_request_at", "final_auth_at"),
    "cited_clause_found": ("cited_clause_found",),
    "crc_approval_mentioned": ("crc_approval_mentioned",),
    "reasons_cite_terms": ("reasons_cite_terms",),
}


def usable(facts: dict[str, FactValue], key: str) -> bool:
    """Fact is present, has a value, and is not awaiting confirmation."""
    f = facts.get(key)
    return f is not None and f.value is not None and f.status != "needs_confirmation"


def _get(facts: dict[str, FactValue], key: str):
    return facts[key].value if usable(facts, key) else None


def claim_key(facts: dict[str, FactValue]) -> str:
    """The fact that supplies the claim date: `claim_date`, or `admission_date` only when
    no claim_date was given at all (a claim_date awaiting confirmation is NOT replaced)."""
    f = facts.get("claim_date")
    if (f is None or f.value is None) and usable(facts, "admission_date"):
        return "admission_date"
    return "claim_date"


def whole_months(start: date, end: date) -> int | None:
    """Whole elapsed months: (y2-y1)*12 + (m2-m1), minus 1 if end's day < start's day.
    None if end is before start."""
    months = (end.year - start.year) * 12 + (end.month - start.month)
    if end.day < start.day:
        months -= 1
    return months if months >= 0 else None


def _cover_months(facts: dict[str, FactValue]) -> int | None:
    start, end = _get(facts, "inception_date"), _get(facts, claim_key(facts))
    if not isinstance(start, date) or not isinstance(end, date):
        return None
    continuity = _get(facts, "continuity_confirmed")
    if continuity is False:
        return None  # user states cover was not continuous
    if continuity is not True:
        # A gap or port must never silently count as continuous cover. A gap/port
        # fact that is present but unconfirmed is also treated as "possible break".
        gap = facts.get("renewal_gap_days")
        if gap is not None and gap.value is not None:
            if gap.status == "needs_confirmation" or gap.value > 0:
                return None
        port = facts.get("ported_from_date")
        if port is not None and port.value is not None:
            return None
    return whole_months(start, end)


def _minutes(facts: dict[str, FactValue], start_key: str, end_key: str) -> int | None:
    a, b = _get(facts, start_key), _get(facts, end_key)
    if not isinstance(a, datetime) or not isinstance(b, datetime):
        return None
    secs = (b - a).total_seconds()
    return int(secs // 60) if secs >= 0 else None


def _ped_disclosed(facts: dict[str, FactValue]) -> bool | None:
    disclosed = _get(facts, "disclosed_conditions")
    alleged = _get(facts, "alleged_undisclosed_condition")
    if disclosed is None or not isinstance(alleged, str) or not alleged.strip():
        return None
    items = [disclosed] if isinstance(disclosed, str) else list(disclosed)
    needle = alleged.strip().lower()
    return any(needle in str(i).lower() for i in items)


def _deducted_as_nonpayable(item: dict) -> bool:
    """The insurer deducted this item as non-payable: `reason` normalises
    (case/space/hyphen-insensitive) to "non_payable"."""
    reason = str(item.get("reason") or "").strip().lower().replace("-", "_").replace(" ", "_")
    return reason == "non_payable"


def _nonpayable_total(items) -> int | float | None:
    """Sum of `amount` over items deducted as non-payable that are NOT on the standard
    non-payable list (`nonpayable_listed is False`): the wrongful part of the deduction.
    Listed items (True) contribute nothing. Unknown/missing listing or a missing amount
    on a deducted item gives None (never guess). Unknown deductions give None."""
    if items is None:
        return None
    total = 0
    for it in items:
        if not isinstance(it, dict) or not _deducted_as_nonpayable(it):
            continue
        listed = it.get("nonpayable_listed")
        if listed is True:
            continue
        if listed is not False:
            return None
        amt = it.get("amount")
        if isinstance(amt, bool) or not isinstance(amt, (int, float)):
            return None
        total += amt
    return total


def derive_inputs(facts: dict[str, FactValue]) -> dict:
    items = _get(facts, "deductions")
    out = {
        "continuous_cover_months": _cover_months(facts),
        "claim_date": _get(facts, claim_key(facts)),
        "rejection_ground": _get(facts, "rejection_ground"),
        "ped_disclosed": _ped_disclosed(facts),
        "fraud_alleged": _get(facts, "fraud_alleged"),
        "deduction_items": items,
        "nonpayable_overcharge_inr": _nonpayable_total(items),
        "cashless_minutes": _minutes(facts, "cashless_request_at", "decision_at"),
        "discharge_minutes": _minutes(facts, "discharge_request_at", "final_auth_at"),
        "cited_clause_found": _get(facts, "cited_clause_found"),
        "crc_approval_mentioned": _get(facts, "crc_approval_mentioned"),
        "reasons_cite_terms": _get(facts, "reasons_cite_terms"),
    }
    assert set(out) == KNOWN_INPUTS
    return out
