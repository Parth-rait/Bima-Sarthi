from datetime import date, datetime

from sarthi.core.derive import FACT_KEYS, derive_inputs
from sarthi.core.inputs import KNOWN_INPUTS
from sarthi.core.models import FactValue


def F(value, status="verified"):
    return FactValue(value=value, quote="q", page_no=1, confidence="high", status=status)


def test_derive_keys_match_known_inputs():
    d = derive_inputs({})
    assert set(d.keys()) == KNOWN_INPUTS
    assert all(v is None for v in d.values())


def test_fact_keys_contains_spec_fields():
    for k in ("inception_date", "renewal_gap_days", "continuity_confirmed", "cited_clause_found"):
        assert k in FACT_KEYS


def _cover(**kw):
    facts = {"inception_date": F(date(2019, 1, 10)), "claim_date": F(date(2025, 2, 1))}
    facts.update(kw)
    return derive_inputs(facts)["continuous_cover_months"]


def test_cover_months_72():
    assert _cover() == 72


def test_cover_months_day_boundary():
    assert _cover(claim_date=F(date(2025, 2, 10))) == 73
    assert _cover(claim_date=F(date(2025, 2, 9))) == 72


def test_cover_gap_is_none_unless_confirmed():
    assert _cover(renewal_gap_days=F(45)) is None
    assert _cover(renewal_gap_days=F(45), continuity_confirmed=F(True)) == 72
    assert _cover(renewal_gap_days=F(0)) == 72


def test_cover_port_is_none_unless_confirmed():
    assert _cover(ported_from_date=F(date(2015, 1, 1))) is None
    assert _cover(ported_from_date=F(date(2015, 1, 1)), continuity_confirmed=F(True)) == 72


def test_cover_unconfirmed_gap_fact_is_not_silently_ignored():
    assert _cover(renewal_gap_days=F(0, "needs_confirmation")) is None


def test_cover_needs_confirmation_and_negative():
    assert _cover(inception_date=F(date(2019, 1, 10), "needs_confirmation")) is None
    assert _cover(claim_date=F(date(2018, 1, 1))) is None


def test_cashless_and_discharge_minutes():
    f = {"cashless_request_at": F(datetime(2025, 1, 1, 10, 0)),
         "decision_at": F(datetime(2025, 1, 1, 11, 30)),
         "discharge_request_at": F(datetime(2025, 1, 1, 8, 0)),
         "final_auth_at": F(datetime(2025, 1, 1, 7, 0))}
    d = derive_inputs(f)
    assert d["cashless_minutes"] == 90
    assert d["discharge_minutes"] is None  # negative
    assert derive_inputs({"decision_at": F(datetime(2025, 1, 1))})["cashless_minutes"] is None


def test_ped_disclosed():
    def p(disc, alleged):
        f = {}
        if disc is not None:
            f["disclosed_conditions"] = F(disc)
        if alleged is not None:
            f["alleged_undisclosed_condition"] = F(alleged)
        return derive_inputs(f)["ped_disclosed"]
    assert p(["Diabetes", "Hypertension"], "diabetes") is True
    assert p(["Hypertension"], "Diabetes") is False
    assert p([], "Diabetes") is False
    assert p(None, "Diabetes") is None
    assert p(["Diabetes"], None) is None


def test_nonpayable_overcharge_only_counts_unlisted_items():
    items = [{"item": "gloves", "amount": 500, "reason": "non_payable", "nonpayable_listed": True},
             {"item": "bed fee", "amount": 700, "reason": "Non-Payable", "nonpayable_listed": False},
             {"item": "room", "amount": 900, "reason": "room rent cap"}]
    d = derive_inputs({"deductions": F(items)})
    assert d["nonpayable_overcharge_inr"] == 700
    assert d["deduction_items"] == items


def test_nonpayable_listed_item_gives_zero():
    items = [{"item": "gloves", "amount": 500, "reason": "non_payable", "nonpayable_listed": True}]
    assert derive_inputs({"deductions": F(items)})["nonpayable_overcharge_inr"] == 0
    assert derive_inputs({"deductions": F([])})["nonpayable_overcharge_inr"] == 0


def test_nonpayable_unknown_listing_or_amount_is_none():
    unknown = [{"item": "g", "amount": 500, "reason": "non_payable"}]
    assert derive_inputs({"deductions": F(unknown)})["nonpayable_overcharge_inr"] is None
    noamt = [{"item": "g", "amount": None, "reason": "non_payable", "nonpayable_listed": False}]
    assert derive_inputs({"deductions": F(noamt)})["nonpayable_overcharge_inr"] is None
    assert derive_inputs({})["nonpayable_overcharge_inr"] is None


def test_continuity_explicitly_false_is_none():
    assert _cover(continuity_confirmed=F(False)) is None


def test_passthroughs():
    d = derive_inputs({"claim_date": F(date(2025, 1, 1)), "rejection_ground": F("exclusion"),
                       "fraud_alleged": F(False), "cited_clause_found": F(True),
                       "crc_approval_mentioned": F(True), "reasons_cite_terms": F(False)})
    assert d["claim_date"] == date(2025, 1, 1) and d["rejection_ground"] == "exclusion"
    assert d["fraud_alleged"] is False and d["cited_clause_found"] is True
    assert d["crc_approval_mentioned"] is True and d["reasons_cite_terms"] is False


def test_claim_date_falls_back_to_admission_date_only_when_absent():
    d = derive_inputs({"admission_date": F(date(2025, 2, 1))})
    assert d["claim_date"] == date(2025, 2, 1)
    both = derive_inputs({"claim_date": F(date(2025, 3, 1)), "admission_date": F(date(2025, 2, 1))})
    assert both["claim_date"] == date(2025, 3, 1)
    pend = derive_inputs({"claim_date": F(date(2025, 3, 1), "needs_confirmation"),
                          "admission_date": F(date(2025, 2, 1))})
    assert pend["claim_date"] is None


def test_cover_months_use_admission_date_fallback():
    d = derive_inputs({"inception_date": F(date(2019, 1, 10)), "admission_date": F(date(2025, 2, 1))})
    assert d["continuous_cover_months"] == 72
