"""`cases issues families` coverage report: counts with stated denominators, never 'accuracy'."""
import json
from pathlib import Path

import pytest
import yaml

from sarthi.core.models import RuleCard
from sarthi.core.store import Store
from sarthi.data import coverage

SEED = Path(__file__).parents[2] / "rules" / "seed"
HQ = "We hold that the moratorium bars repudiation of the claim."


def seed_card(name, status="approved"):
    data = yaml.safe_load((SEED / f"{name}.yaml").read_text(encoding="utf-8"))
    data.pop("source_id", None)
    data.update(status=status, source_sha256="a" * 64, quote="q " + name)
    return RuleCard(**data)


@pytest.fixture
def store(tmp_path, monkeypatch):
    s = Store(tmp_path / "t.duckdb")
    s.init()
    cards = [seed_card(n) for n in ("MORATORIUM_60M", "MORATORIUM_60M.v0", "PED_WAIT_36M",
                                    "PED_WAIT_36M.v0", "SPECIFIC_WAIT", "SPECIFIC_WAIT.v0",
                                    "PORTABILITY_CREDIT")] + [seed_card("EXCLUSION_LISTED", "draft")]
    monkeypatch.setattr(coverage, "approved_cards", lambda st, as_of=None: [c for c in cards if c.status == "approved"])
    monkeypatch.setattr(coverage, "unapproved_cards", lambda st, exclude=(): [c for c in cards if c.status != "approved"])
    return s


def add_case(store, cid, line="health", excluded=None):
    store.upsert("case", [dict(case_id=cid, source_sha256=None, forum=None, case_number=None,
                               decided_on=None, insurer=None, product_id=None, outcome=None,
                               relief_amount=None, appellant=None, policyholder_prevailed=True,
                               excluded_reason=excluded, product_line=line)], key=["case_id"])


def add_issue(store, cid, issue, status="reviewed", family=None, fstatus="reviewed", holding="for_policyholder"):
    store.upsert("case_issue", [dict(case_id=cid, issue=issue, holding=holding, holding_quote=HQ, page_no=2,
                                     status=status, reviewer_note=None, issue_family=family,
                                     family_status=fstatus if family else None)], key=["case_id", "issue"])


def add_facts(store, cid, facts):
    rows = []
    for field, v in facts.items():
        value, st = v if isinstance(v, tuple) else (v, "reviewed")
        rows.append(dict(case_id=cid, field=field, value=json.dumps(value), quote="q", page_no=1,
                         confidence=1.0, status=st, reviewer_note=None))
    store.upsert("case_fact", rows, key=["case_id", "field"])


ND = {"rejection_ground": "non_disclosure", "fraud_alleged": False, "inception_date": "2019-01-10",
      "claim_date": "2025-04-15", "policy_renewal_date": "2024-06-01"}


def build(store):
    add_case(store, "a")                                  # complete, scorable
    add_facts(store, "a", ND)
    add_issue(store, "a", "MORATORIUM_60M", family="NON_DISCLOSURE")
    add_case(store, "b")                                  # unreviewed port fact -> missing-fact skip
    add_facts(store, "b", {**ND, "ported_from_date": ("2014", "needs_review")})
    add_issue(store, "b", "MORATORIUM_60M", family="NON_DISCLOSURE")
    add_case(store, "c", line="life")                     # unsupported product
    add_issue(store, "c", "SPECIFIC_WAIT", status="rejected", family="OTHER")
    add_case(store, "d")                                  # old claim before any card
    add_facts(store, "d", {**ND, "claim_date": "2015-04-15", "inception_date": "2010-01-10",
                           "policy_renewal_date": "2015-01-10"})
    add_issue(store, "d", "MORATORIUM_60M", family="NON_DISCLOSURE")
    add_case(store, "e")                                  # drafted family only
    add_issue(store, "e", "EXCLUSION_LISTED", status="drafted", family="EXCLUSION", fstatus="drafted")
    add_case(store, "u", line=None)                       # product line not yet known: not 'non-health'
    add_issue(store, "u", "SPECIFIC_WAIT", family="WAITING_PERIOD")
    add_case(store, "x", excluded="duplicate")            # excluded: outside every denominator
    add_issue(store, "x", "MORATORIUM_60M", family="NON_DISCLOSURE")


def test_counts_and_denominators(store):
    build(store)
    c = coverage.compute_coverage(store)
    assert c["reviewed_issue_rows"] == 4 and c["issue_rows_total"] == 6   # a,b,d,u reviewed; c rejected, e drafted; x excluded
    assert c["family_reviewed"]["NON_DISCLOSURE"] == 3 and c["family_reviewed"]["WAITING_PERIOD"] == 1
    assert c["family_reviewed"].get("OTHER") == 1
    assert c["family_drafted"] == {"EXCLUSION": 1}
    assert c["cases_in_universe"] == 5            # a,b,c,d,u; x is excluded, e has no facts and only a drafted family
    assert c["unsupported_product_cases"] == 1     # c: life (known, not health)
    assert c["product_line_unknown_cases"] == 1    # u: product_line NULL, kept apart from 'not health'
    assert c["missing_fact_skip_cases"] == 1
    assert c["out_of_scope_cases"] == 1
    assert c["findings_eligible_for_scoring"] == 1
    assert c["historically_applicable_cases"] == 1


def test_families_with_approved_cards_vs_research_needed(store):
    build(store)
    fam = coverage.compute_coverage(store)["families"]
    assert fam["NON_DISCLOSURE"]["approved_cards"] == ["MORATORIUM_60M"]
    assert fam["EXCLUSION"]["approved_cards"] == [] and fam["EXCLUSION"]["research_needed"] is True
    assert fam["WAITING_PERIOD"]["approved_cards"] == ["PED_WAIT_36M", "SPECIFIC_WAIT"]
    assert fam["CASHLESS_PROCESS"]["approved_cards"] == []   # no CASHLESS card in this fixture


def test_report_text_states_denominators_and_never_says_accuracy(store, tmp_path):
    build(store)
    out = tmp_path / "coverage.md"
    coverage.write_coverage(store, out)
    t = out.read_text()
    assert "accuracy" not in t.lower().replace("not an accuracy", "").replace("not accuracy", "") \
        or "not an accuracy" in t.lower()
    assert "Coverage is not accuracy" in t
    for needle in ("reviewed issue rows", "Issue-family distribution", "research_needed",
                   "historically applicable", "eligible for scoring", "missing-fact", "unsupported-product",
                   "out-of-scope", "of 5 cases", "product line unknown"):
        assert needle.lower() in t.lower(), needle
    assert "drafted" in t and "reviewed" in t


def test_a_drafted_family_is_never_counted_as_reviewed(store):
    build(store)
    c = coverage.compute_coverage(store)
    assert "EXCLUSION" not in c["family_reviewed"]
