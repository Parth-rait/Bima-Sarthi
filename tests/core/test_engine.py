import json
from datetime import date

import pytest

from sarthi.core.engine import run_rules
from sarthi.core.models import FactValue, RuleCard

QUOTE = "No claim shall be contestable after sixty continuous months."


def F(value, status="verified"):
    return FactValue(value=value, quote=f"quote of {value}", page_no=3, confidence="high",
                     status=status)


def card(**kw):
    base = dict(
        rule_id="MORATORIUM_60M", version=1, group="rejection", quote=QUOTE,
        source_sha256="a" * 64, page_no=7, in_force_from=date(2024, 4, 1),
        applies_by="policy_start_or_renewal", triggers=["non_disclosure"],
        inputs=["continuous_cover_months", "fraud_alleged"],
        params={"moratorium_months": 60},
        condition="continuous_cover_months >= 60 and not fraud_alleged",
        if_true="CHALLENGEABLE", if_false="CONSISTENT",
        question_en="How many continuous months?", question_hi="kitne mahine?",
        action_en="Cite the moratorium.", action_hi="hindi action",
        status="approved")
    base.update(kw)
    return RuleCard(**base)


def facts(inception=date(2019, 1, 10), claim=date(2025, 2, 1), renewal=date(2024, 6, 1), **kw):
    # applies_by=policy_start_or_renewal uses the later of inception/renewal, so a 2019
    # policy renewed after the card's in_force_from (2024-04-01) is governed by it.
    f = {"rejection_ground": F("non_disclosure"), "fraud_alleged": F(False)}
    if renewal:
        f["policy_renewal_date"] = F(renewal)
    if inception:
        f["inception_date"] = F(inception)
    if claim:
        f["claim_date"] = F(claim)
    f.update(kw)
    return f


def test_challengeable_with_quote_and_facts():
    out = run_rules(facts(), [card()])
    assert len(out) == 1
    x = out[0]
    assert x.verdict == "CHALLENGEABLE"
    assert x.rule_quote == QUOTE and x.source_sha256 == "a" * 64 and x.page_no == 7
    assert x.question_en == "How many continuous months?" and x.action_hi == "hindi action"
    assert x.facts_used["inception_date"]["value"] == "2019-01-10"
    assert x.facts_used["inception_date"]["quote"] == "quote of 2019-01-10"
    assert x.facts_used["inception_date"]["page_no"] == 3
    assert "fraud_alleged" in x.facts_used
    json.dumps(x.facts_used)


def test_consistent_when_40_months():
    out = run_rules(facts(inception=date(2021, 10, 1)), [card()])
    assert [x.verdict for x in out] == ["CONSISTENT"]


def test_fraud_alleged_is_consistent():
    out = run_rules(facts(fraud_alleged=F(True)), [card()])
    assert out[0].verdict == "CONSISTENT"


def test_unknown_months_need_info_with_question():
    out = run_rules(facts(inception=None), [card()])
    assert len(out) == 1 and out[0].verdict == "NEED_INFO"
    assert out[0].reason == "missing_inception_date"
    f = facts()
    f["renewal_gap_days"] = F(45)
    out = run_rules(f, [card()])
    assert out[0].verdict == "NEED_INFO" and out[0].reason.startswith("missing_inputs")
    assert "continuous_cover_months" in out[0].reason
    assert out[0].question_en == "How many continuous months?"


def test_unconfirmed_fact_is_missing():
    out = run_rules(facts(fraud_alleged=F(False, "needs_confirmation")), [card()])
    assert out[0].verdict == "NEED_INFO" and "fraud_alleged" in out[0].reason


def test_other_ground_not_triggered():
    assert run_rules(facts(rejection_ground=F("exclusion")), [card()]) == []


def test_unknown_or_unconfirmed_ground_returns_empty():
    f = facts()
    del f["rejection_ground"]
    assert run_rules(f, [card()]) == []
    assert run_rules(facts(rejection_ground=F("non_disclosure", "needs_confirmation")),
                     [card()]) == []


def test_rule_not_in_force():
    out = run_rules(facts(inception=date(2015, 1, 1), claim=date(2022, 6, 1), renewal=None),
                    [card()])
    assert len(out) == 1 and out[0].verdict == "NEED_INFO"
    assert out[0].reason == "rule_not_in_force"


def test_picks_version_in_force_on_date():
    old = card(version=1, in_force_from=date(2010, 1, 1), in_force_to=date(2024, 4, 1),
               condition="continuous_cover_months >= 96")
    new = card(version=2)
    out = run_rules(facts(inception=date(2015, 1, 1), claim=date(2022, 6, 1), renewal=None),
                    [old, new])
    assert [(x.rule_version, x.verdict) for x in out] == [(1, "CONSISTENT")]
    out = run_rules(facts(), [old, new])
    assert [(x.rule_version, x.verdict) for x in out] == [(2, "CHALLENGEABLE")]


def test_applies_by_claim_date_and_missing():
    c = card(applies_by="claim_date", condition="fraud_alleged", inputs=["fraud_alleged"])
    assert run_rules(facts(claim=None), [c])[0].reason == "missing_claim_date"
    assert run_rules(facts(), [c])[0].verdict == "CONSISTENT"


def test_policy_start_uses_later_of_inception_and_renewal():
    c = card(in_force_from=date(2024, 4, 1))
    f = facts()
    f["policy_renewal_date"] = F(date(2024, 5, 1))
    assert run_rules(f, [c])[0].verdict == "CHALLENGEABLE"
    f["policy_renewal_date"] = F(date(2023, 5, 1))
    assert run_rules(f, [c])[0].reason == "rule_not_in_force"


def test_condition_not_automated():
    c = card(condition=None)
    out = run_rules(facts(), [c])
    assert out[0].verdict == "NEED_INFO" and out[0].reason == "condition_not_automated"
    assert out[0].question_en == "How many continuous months?"


def test_unapproved_card_without_quote_raises():
    with pytest.raises(ValueError):
        run_rules(facts(), [card(quote=None)])
    with pytest.raises(ValueError):
        run_rules(facts(), [card(source_sha256=None)])


def test_renewal_after_claim_is_ignored_regression():
    f = facts(inception=date(2015, 1, 1), claim=date(2022, 6, 1), renewal=date(2024, 6, 1))
    out = run_rules(f, [card()])
    assert [(x.verdict, x.reason) for x in out] == [("NEED_INFO", "rule_not_in_force")]


def test_policy_start_requires_claim_date():
    out = run_rules(facts(claim=None), [card()])
    assert [(x.verdict, x.reason) for x in out] == [("NEED_INFO", "missing_claim_date")]


def test_draft_card_rejected():
    with pytest.raises(ValueError):
        run_rules(facts(), [card(status="draft")])
    with pytest.raises(ValueError):
        run_rules(facts(), [card(status="disabled")])


# ---------- fix C / I6: admission_date stands in for an absent claim_date ----------

def test_admission_date_stands_in_for_absent_claim_date_and_is_recorded():
    f = facts(claim=None, admission_date=F(date(2025, 2, 1)))
    (x,) = run_rules(f, [card()])
    assert x.verdict == "CHALLENGEABLE"
    assert "admission_date" in x.facts_used and "claim_date" not in x.facts_used


def test_claim_date_wins_over_admission_date():
    f = facts(claim=date(2025, 2, 1), admission_date=F(date(2019, 2, 1)))
    (x,) = run_rules(f, [card()])
    assert x.verdict == "CHALLENGEABLE" and "claim_date" in x.facts_used
    assert "admission_date" not in x.facts_used


def test_unconfirmed_claim_date_is_not_replaced_by_admission_date():
    f = facts(claim=None, claim_date=F(date(2025, 2, 1), "needs_confirmation"),
              admission_date=F(date(2025, 2, 1)))
    (x,) = run_rules(f, [card()])
    assert x.verdict == "NEED_INFO"


def test_no_dates_at_all_is_still_need_info():
    (x,) = run_rules(facts(claim=None), [card()])
    assert x.verdict == "NEED_INFO" and x.reason == "missing_claim_date"
