"""Documents-to-request helper: fixed templates, no model, no amounts, no legal conclusions."""
import re

import pytest

from sarthi.app import checklist
from sarthi.app.verify import verify
from sarthi.core.models import FactValue, Finding


def fv(value):
    return FactValue(value=value, quote="q", page_no=1, confidence="high", status="verified")


def finding(verdict):
    return Finding(rule_id="MORATORIUM_60M", rule_version=1, verdict=verdict, reason=None, rule_quote="q",
                   source_sha256="x", page_no=1, facts_used={})


def test_need_info_finding_triggers_it():
    assert checklist.build([finding("NEED_INFO")], {}) is not None


@pytest.mark.parametrize("verdicts", [[], ["CHALLENGEABLE"], ["CONSISTENT"], ["CHALLENGEABLE", "CONSISTENT"]])
def test_no_need_info_and_no_deduction_means_no_checklist(verdicts):
    facts = {"rejection_ground": fv("non_disclosure")}
    assert checklist.build([finding(v) for v in verdicts], facts) is None


@pytest.mark.parametrize("ground", ["deduction", "room_rent", "sub_limit"])
def test_deduction_grounds_trigger_it(ground):
    assert checklist.build([], {"rejection_ground": fv(ground)}) is not None


@pytest.mark.parametrize("text", ["Room rent proportionate deduction", "co-payment applied", "Co payment 20%",
                                  "sub-limit for cataract", "sublimit", "non-payable item", "Non Payable",
                                  "कमरे का किराया", "सह-भुगतान", "उप-सीमा", "गैर-भुगतान"])
def test_user_reason_mentioning_a_deduction_triggers_it(text):
    facts = {"rejection_ground": fv("other"),
             "deductions": fv([{"item": "Room", "amount": 5000, "reason": text, "nonpayable_listed": None}])}
    assert checklist.build([], facts) is not None


def test_cited_clause_mentioning_co_payment_triggers_it():
    assert checklist.build([], {"rejection_ground": fv("other"), "cited_clause": fv("Clause 4: co-payment")}) is not None


def test_unrelated_deduction_text_does_not_trigger_it():
    facts = {"rejection_ground": fv("other"), "deductions": fv([{"item": "Gloves", "amount": 100, "reason": "x"}])}
    assert checklist.build([finding("CONSISTENT")], facts) is None


def test_checklist_has_the_five_requests_in_both_languages_and_passes_verify():
    c = checklist.build([finding("NEED_INFO")], {})
    assert len(c["items"]) == 5 and c["verified"] is True
    en = " ".join(i["en"] for i in c["items"]).lower()
    for needle in ("itemised", "schedule", "endorsements", "clause", "claim file", "tpa", "medical records", "proposal form"):
        assert needle in en
    for lang in ("en", "hi"):
        assert c["title"][lang] and c["intro"][lang]
        assert verify(c["text"][lang], []).ok, c["text"][lang]
        assert not re.search(r"\b[a-z]+_[a-z_]+\b", c["text"][lang])
        assert not re.search(r"\d", c["text"][lang])                      # no amounts, no invented numbers
    assert all(re.search(r"[ऀ-ॿ]", i["hi"]) for i in c["items"])


def test_text_has_no_legal_conclusion_or_promise():
    c = checklist.build([finding("NEED_INFO")], {})
    low = c["text"]["en"].lower()
    for w in ("must", "entitled", "illegal", "unlawful", "violat", "will be paid", "you will", "deficiency"):
        assert w not in low


def test_a_failing_text_is_not_shown(monkeypatch):
    monkeypatch.setitem(checklist.TITLE, "en", "You will definitely be paid")
    assert checklist.build([finding("NEED_INFO")], {}) is None
