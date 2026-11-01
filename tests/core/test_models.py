import pytest
from pydantic import ValidationError

from sarthi.core.models import CaseFact, Finding, RuleCard


def test_case_fact_rejects_unknown_status():
    with pytest.raises(ValidationError):
        CaseFact(case_id="c", field="f", status="bogus")
    assert CaseFact(case_id="c", field="f", status="needs_review").status == "needs_review"


def test_finding_verdict_is_constrained():
    kw = dict(rule_id="R", rule_version=1, reason=None, rule_quote="q",
              source_sha256="s", page_no=None, facts_used={})
    assert Finding(verdict="NEED_INFO", **kw).verdict == "NEED_INFO"
    with pytest.raises(ValidationError):
        Finding(verdict="MAYBE", **kw)


def test_rule_card_defaults_to_draft_and_accepts_params():
    card = RuleCard(rule_id="R", version=1, params={"months": 60})
    assert card.status == "draft"
    assert card.params == {"months": 60}
