import re
from datetime import date

import pymupdf
import pytest

from sarthi.app.letter import LETTER_FACT_KEYS, build_letter, deadlines, to_pdf
from sarthi.core.models import FactValue, Finding

def _p(value, unit, quote="q", page=1):
    return {"value": value, "unit": unit, "source_id": "s", "page_no": page, "quote": quote}


# Nested, per-parameter-sourced params (Parth's 1 Nov 2026 decision; replaces the plan's
# original 15-day reply / 30-day wait values with the primary text: 14 days / one month).
PARAMS = {"insurer_reply_days": _p(14, "days", "reply quote", 111),
          "ombudsman_wait_months": _p(1, "months", "wait quote", 10),
          "ombudsman_limit_months": _p(12, "months", "limit quote", 10),
          "ombudsman_claim_limit_inr": _p(5000000, "inr", "claim quote", 135),
          "ombudsman_award_cap_inr": _p(3000000, "inr", "award quote", 12)}
# Legacy flat numbers must keep working (old fixtures).
FLAT = {"insurer_reply_days": 15, "ombudsman_wait_days": 30,
        "ombudsman_limit_months": 12, "ombudsman_cap_inr": 5000000}
LD = date(2026, 11, 1)
Q_CH = "Insurer shall not repudiate a claim on the ground of pre-existing disease after sixty months."
Q_OK = "Waiting period for specific illness is two years."


def finding(rule_id, verdict, quote, page=4):
    return Finding(rule_id=rule_id, rule_version=1, verdict=verdict, reason="r",
                   rule_quote=quote, source_sha256="x", page_no=page,
                   facts_used={"policy_start_date": {"value": "2019-01-01",
                                                     "quote": "Policy start 01/01/2019", "page_no": 1}})


def facts(amount=120000):
    d = {
        "policyholder_name": FactValue(value="Asha Rao"),
        "policy_number": FactValue(value="POL-12345"),
        "claim_number": FactValue(value="CLM-998"),
        "claim_amount_inr": FactValue(value=amount),
        "insurer_name": FactValue(value="Example Insurance Co."),
    }
    return d


def fs():
    return [finding("PED_MORATORIUM", "CHALLENGEABLE", Q_CH),
            finding("WAIT_SPECIFIC", "CONSISTENT", Q_OK),
            finding("X", "NEED_INFO", "need info quote")]


def test_deadlines_no_reply():
    d = deadlines(LD, None, params=PARAMS)
    assert d.insurer_reply_by == date(2026, 11, 15)
    assert d.ombudsman_earliest == date(2026, 12, 1)
    assert d.ombudsman_latest == date(2027, 12, 1)


def test_deadlines_with_reply():
    d = deadlines(LD, date(2026, 11, 10), params=PARAMS)
    assert d.ombudsman_latest == date(2027, 11, 10)


def test_deadlines_month_end_wait_clamps():
    d = deadlines(date(2026, 1, 31), None, params=PARAMS)
    assert d.ombudsman_earliest == date(2026, 2, 28)


def test_deadlines_flat_params_still_work():
    d = deadlines(LD, None, params=FLAT)
    assert d.insurer_reply_by == date(2026, 11, 16)
    assert d.ombudsman_earliest == date(2026, 12, 1)


def test_deadline_sources_name_param_that_sets_each_date():
    from sarthi.app.letter import deadline_sources
    src = deadline_sources(PARAMS)
    assert src["insurer_reply_by"]["quote"] == "reply quote" and src["insurer_reply_by"]["page_no"] == 111
    assert src["ombudsman_earliest"]["page_no"] == 10 and src["ombudsman_earliest"]["quote"] == "wait quote"
    assert src["ombudsman_latest"]["quote"] == "limit quote"
    assert deadline_sources(FLAT) == {}


def test_deadline_source_is_reply_date_only_when_it_sets_earliest():
    from sarthi.app.letter import deadline_sources
    early = deadline_sources(PARAMS, letter_date=LD, insurer_reply_date=date(2026, 11, 10))
    assert early["ombudsman_earliest"]["label"] == "your insurer's reply date (entered by you)"
    assert early["ombudsman_earliest"]["quote"] is None
    late = deadline_sources(PARAMS, letter_date=LD, insurer_reply_date=date(2026, 12, 20))
    assert late["ombudsman_earliest"]["quote"] == "wait quote"
    none = deadline_sources(PARAMS, letter_date=LD, insurer_reply_date=None)
    assert none["ombudsman_earliest"]["quote"] == "wait quote"


def test_deadlines_month_end_clamp():
    d = deadlines(LD, date(2026, 2, 28), params={**PARAMS, "ombudsman_limit_months": 12})
    assert d.ombudsman_latest == date(2027, 2, 28)
    d = deadlines(LD, date(2024, 2, 29), params=PARAMS)
    assert d.ombudsman_latest == date(2025, 2, 28)


def test_deadlines_missing_param():
    with pytest.raises(KeyError, match="ombudsman_wait"):
        deadlines(LD, None, params={"insurer_reply_days": _p(14, "days")})


def test_letter_content_en():
    t = build_letter(facts(), fs(), "en", params=PARAMS, letter_date=LD)
    assert "POL-12345" in t and "CLM-998" in t
    assert Q_CH in t and "PED_MORATORIUM" in t
    assert "Policy start 01/01/2019" in t
    assert Q_OK not in t and "need info quote" not in t
    assert "Grievance Redressal Officer" in t
    assert "01/11/2026" in t and "15/11/2026" in t and "01/12/2026" in t and "01/12/2027" in t
    assert "₹1,20,000" in t
    assert "Prepared with Bima Sarthi, an independent project, not affiliated with IRDAI, LIC or any insurer." in t
    assert "above the Ombudsman" not in t
    for w in ("will ", "guarantee", "entitled", "diagnos", "treatment"):
        assert w not in t.lower().replace("will not", ""), w


def test_claim_limit_note():
    t = build_letter(facts(6000000), fs(), "en", params=PARAMS, letter_date=LD)
    assert "above the Ombudsman's claim-amount limit (₹50 lakh); consider the consumer commission" in t
    assert "₹60,00,000" in t
    assert "can award at most" not in t


def test_award_cap_info_note():
    t = build_letter(facts(4000000), fs(), "en", params=PARAMS, letter_date=LD)
    assert "the Ombudsman can award at most ₹30 lakh" in t
    assert "claim-amount limit" not in t


def test_no_note_under_award_cap():
    t = build_letter(facts(120000), fs(), "en", params=PARAMS, letter_date=LD)
    assert "claim-amount limit" not in t and "award at most" not in t


def test_flat_cap_note_legacy():
    t = build_letter(facts(6000000), fs(), "en", params=FLAT, letter_date=LD)
    assert "claim-amount limit (₹50 lakh)" in t


def test_missing_numbers_are_blanks():
    f = facts()
    del f["policy_number"]
    f["claim_number"] = FactValue(value=None)
    t = build_letter(f, fs(), "en", params=PARAMS, letter_date=LD)
    assert "[policy number]" in t and "[claim number]" in t


def test_no_challengeable_raises():
    with pytest.raises(ValueError):
        build_letter(facts(), [finding("A", "CONSISTENT", Q_OK)], "en", params=PARAMS, letter_date=LD)


def test_letter_hi_keeps_english_quote():
    t = build_letter(facts(), fs(), "hi", params=PARAMS, letter_date=LD)
    assert Q_CH in t and "CLM-998" in t
    assert re.search(r"[ऀ-ॿ]{3,}", t)


def test_pdf_roundtrip_en():
    t = build_letter(facts(), fs(), "en", params=PARAMS, letter_date=LD)
    data = to_pdf(t)
    doc = pymupdf.open("pdf", data)
    assert doc[0].rect.width == pytest.approx(595, abs=2)
    text = " ".join(p.get_text() for p in doc)
    assert "CLM-998" in text


def test_pdf_roundtrip_hi():
    t = build_letter(facts(), fs(), "hi", params=PARAMS, letter_date=LD)
    doc = pymupdf.open("pdf", to_pdf(t))
    text = " ".join(p.get_text() for p in doc)
    assert re.search(r"[ऀ-ॿ]{3,}", text)
    assert "CLM-998" in text


def test_fact_keys():
    assert set(LETTER_FACT_KEYS) == {"policyholder_name", "policy_number", "claim_number",
                                     "claim_amount_inr", "insurer_name", "complaint_sent_date"}


@pytest.mark.parametrize("lang", ["en", "hi"])
def test_template_comment_lines_never_leak(lang):
    t = build_letter(facts(), fs(), lang, params=PARAMS, letter_date=LD)
    pdf_text = " ".join(p.get_text() for p in pymupdf.open("pdf", to_pdf(t)))
    for out in (t, pdf_text):
        assert "Q-007" not in out
        assert "draft" not in out.lower()
        assert not any(l.lstrip().startswith("#") for l in out.splitlines())


# ---------- fix C / R57: earliest Ombudsman date uses a known, earlier insurer reply ----------

def test_earliest_is_reply_date_when_earlier_than_letter_plus_wait():
    d = deadlines(LD, date(2026, 11, 10), params=PARAMS)
    assert d.ombudsman_earliest == date(2026, 11, 10)
    assert d.ombudsman_latest == date(2027, 11, 10)


def test_earliest_is_letter_plus_wait_when_reply_is_later():
    d = deadlines(LD, date(2026, 12, 20), params=PARAMS)
    assert d.ombudsman_earliest == date(2026, 12, 1)
    assert d.ombudsman_latest == date(2027, 12, 20)


def test_letter_text_shows_reply_based_earliest_date():
    text = build_letter(facts(), fs(), "en", params=PARAMS, letter_date=LD,
                        insurer_reply_date=date(2026, 11, 10))
    assert "earliest date for that is 10/11/2026" in text
