"""Evaluation runs the engine only on cards the resolver found applicable, and records the trace."""
import json
from datetime import date
from pathlib import Path

import pytest
import yaml

from sarthi.core.models import RuleCard
from sarthi.core.store import Store
from sarthi.data import case_issues, evaluate

SEED = Path(__file__).parents[2] / "rules" / "seed"
HQ = "We hold that the moratorium bars repudiation of the claim."


def seed_card(name, status="approved"):
    data = yaml.safe_load((SEED / f"{name}.yaml").read_text(encoding="utf-8"))
    data.pop("source_id", None)
    data.update(status=status, source_sha256="a" * 64, quote="q " + name)
    return RuleCard(**data)


def approved():
    return [seed_card(n) for n in ("MORATORIUM_60M", "MORATORIUM_60M.v0", "PED_WAIT_36M",
                                   "PED_WAIT_36M.v0", "SPECIFIC_WAIT", "SPECIFIC_WAIT.v0",
                                   "PORTABILITY_CREDIT", "CASHLESS_1H", "REJECTION_PROCESS")]


@pytest.fixture
def store(tmp_path):
    s = Store(tmp_path / "t.duckdb")
    s.init()
    return s


def add_case(store, cid, line="health"):
    store.upsert("case", [dict(case_id=cid, source_sha256=None, forum=None, case_number=None,
                               decided_on=None, insurer=None, product_id=None, outcome=None,
                               relief_amount=None, appellant=None, policyholder_prevailed=True,
                               excluded_reason=None, product_line=line)], key=["case_id"])


def add_facts(store, cid, facts, status="reviewed"):
    rows = []
    for field, v in facts.items():
        value, st = v if isinstance(v, tuple) else (v, status)
        rows.append(dict(case_id=cid, field=field, value=json.dumps(value), quote="q", page_no=1,
                         confidence=1.0, status=st, reviewer_note=None))
    store.upsert("case_fact", rows, key=["case_id", "field"])


def add_issue(store, cid, issue, status="reviewed", family=None, fstatus="reviewed"):
    store.upsert("case_issue", [dict(case_id=cid, issue=issue, holding="for_policyholder",
                                     holding_quote=HQ, page_no=2, status=status, reviewer_note=None,
                                     issue_family=family, family_status=fstatus if family else None)],
                 key=["case_id", "issue"])


ND = {"rejection_ground": "non_disclosure", "fraud_alleged": False, "inception_date": "2019-01-10",
      "claim_date": "2025-04-15", "policy_renewal_date": "2024-06-01"}


def run(store, monkeypatch, cards=None, spy=None):
    cards = cards or approved()
    monkeypatch.setattr(evaluate, "approved_cards", lambda s, as_of=None: [c for c in cards
                                                                            if c.status == "approved"])
    monkeypatch.setattr(evaluate, "unapproved_cards", lambda s, exclude=(): [c for c in cards
                                                                             if c.status != "approved"])
    if spy is not None:
        real = evaluate.run_rules

        def wrapped(facts, cs):
            spy.append(sorted((c.rule_id, c.version) for c in cs))
            return real(facts, cs)
        monkeypatch.setattr(evaluate, "run_rules", wrapped)
    return evaluate.run_eval("r1", ["rules"], 1, store)


def test_engine_receives_only_applicable_cards(store, monkeypatch):
    add_case(store, "c1")
    add_facts(store, "c1", ND)
    add_issue(store, "c1", "MORATORIUM_60M")
    spy = []
    s = run(store, monkeypatch, spy=spy)
    assert spy and set(c[0] for c in spy[0]) == {"MORATORIUM_60M"}   # not PED/SPECIFIC/...
    assert s.cases[0].verdicts["rules"] == ["CHALLENGEABLE"]
    assert s.by_method["rules"].finding_agreement == 1.0


def test_trace_is_recorded_in_the_stored_result_and_summary(store, monkeypatch):
    add_case(store, "c1")
    add_facts(store, "c1", ND)
    add_issue(store, "c1", "MORATORIUM_60M")
    s = run(store, monkeypatch)
    stored = json.loads(store.con.execute("SELECT verdicts FROM eval_result").fetchone()[0])
    t = stored["_trace"]
    assert t["family_source"] == "ground" and t["families"] == ["NON_DISCLOSURE"]
    assert t["candidates"][0]["rule_id"] == "MORATORIUM_60M"
    assert t["candidates"][0]["status"] == "applicable" and t["candidates"][0]["version"] == 1
    assert s.traces["c1"]["candidates"][0]["status"] == "applicable"
    assert s.resolver_counts["applicable"] == 1


def test_report_has_a_resolver_trace_section(store, monkeypatch, tmp_path):
    add_case(store, "c1")
    add_facts(store, "c1", ND)
    s = run(store, monkeypatch)
    evaluate.write_report(s, tmp_path / "r.md")
    t = (tmp_path / "r.md").read_text()
    assert "## Rule-context resolver" in t
    assert "c1" in t and "MORATORIUM_60M v1" in t and "applicable" in t


def test_reviewed_family_overrides_the_ground_and_unblocks_nothing_else(store, monkeypatch):
    """The reviewer named the real issue OTHER: the moratorium card must not decide the case."""
    add_case(store, "c1")
    add_facts(store, "c1", ND)
    add_issue(store, "c1", "MORATORIUM_60M", status="rejected", family="OTHER")
    spy = []
    s = run(store, monkeypatch, spy=spy)
    assert spy[0] == []
    assert s.cases[0].verdicts["rules"] == ["NO_USABLE_GROUND_OR_RULE"]
    assert s.traces["c1"]["family_source"] == "reviewed"
    assert s.traces["c1"]["candidates"][0]["status"] == "no_candidate_rule"


def test_drafted_family_is_ignored_by_evaluation(store, monkeypatch):
    add_case(store, "c1")
    add_facts(store, "c1", ND)
    add_issue(store, "c1", "MORATORIUM_60M", status="drafted", family="OTHER", fstatus="drafted")
    s = run(store, monkeypatch)
    assert s.traces["c1"]["family_source"] == "ground"
    assert s.cases[0].verdicts["rules"] == ["CHALLENGEABLE"]


def test_rejected_label_with_reviewed_family_is_never_scored(store, monkeypatch):
    add_case(store, "c1")
    add_facts(store, "c1", ND)
    add_issue(store, "c1", "MORATORIUM_60M", status="rejected", family="NON_DISCLOSURE")
    s = run(store, monkeypatch)
    m = s.by_method["rules"]
    assert m.finding_n == 0 and m.finding_excluded == 1   # an engine finding, but no scored holding
    assert s.cases[0].tag == "untagged"


def test_draft_card_is_reported_not_approved_and_nothing_runs(store, monkeypatch):
    add_case(store, "c1")
    add_facts(store, "c1", {"rejection_ground": "exclusion", "claim_date": "2025-04-15",
                            "cited_clause_found": True})
    cards = approved() + [seed_card("EXCLUSION_LISTED", "draft")]
    spy = []
    s = run(store, monkeypatch, cards=cards, spy=spy)
    assert spy[0] == []
    assert s.cases[0].verdicts["rules"] == ["NO_USABLE_GROUND_OR_RULE"]
    assert s.traces["c1"]["candidates"][0]["status"] == "no_candidate_rule"
    assert s.n_no_usable == 1


def test_not_in_force_is_out_of_scope_from_the_trace(store, monkeypatch):
    add_case(store, "c1")
    add_facts(store, "c1", {**ND, "claim_date": "2015-04-15", "inception_date": "2010-01-10",
                            "policy_renewal_date": "2015-01-10"})
    spy = []
    s = run(store, monkeypatch, spy=spy)
    assert spy[0] == []
    assert s.cases[0].verdicts["rules"] == ["OUT_OF_SCOPE"]
    assert s.n_out_of_scope == 1 and s.by_method["rules"].out_of_scope_cases == ["c1"]
    assert s.traces["c1"]["candidates"][0]["status"] == "not_in_force"


def test_missing_applicability_date_is_an_abstention_not_no_usable(store, monkeypatch):
    add_case(store, "c1")
    add_facts(store, "c1", {k: v for k, v in ND.items() if k != "inception_date"})
    s = run(store, monkeypatch)
    assert s.cases[0].verdicts["rules"] == ["NEED_INFO"]
    assert s.traces["c1"]["candidates"][0]["status"] == "missing_applicability_date"
    assert s.n_eligible == 1 and s.n_no_usable == 0


def test_unreviewed_fact_skips_via_the_resolver(store, monkeypatch):
    add_case(store, "c1")
    add_facts(store, "c1", {**ND, "ported_from_date": ("2014", "needs_review")})
    spy = []
    s = run(store, monkeypatch, spy=spy)
    assert spy[0] == []
    assert s.cases[0].verdicts["rules"] == ["SKIPPED_UNRESOLVED"]
    assert s.n_skipped == 1 and s.resolver_counts["missing_required_fact"] == 1


def test_non_health_cases_never_reach_the_resolver(store, monkeypatch):
    add_case(store, "life", line="life")
    add_facts(store, "life", ND)
    spy = []
    s = run(store, monkeypatch, spy=spy)
    assert spy == [] and s.n_cases == 0
    assert s.not_health == [("life", "life")]


def test_reviewed_waiting_period_family_runs_the_matching_card(store, monkeypatch):
    add_case(store, "c1")
    add_facts(store, "c1", {"rejection_ground": "specific_waiting_period", "claim_date": "2025-04-15",
                            "inception_date": "2024-06-01"})
    add_issue(store, "c1", "SPECIFIC_WAIT", family="WAITING_PERIOD")
    s = run(store, monkeypatch)
    t = s.traces["c1"]
    assert t["family_source"] == "reviewed" and t["families"] == ["WAITING_PERIOD"]
    st = {c["rule_id"]: c["status"] for c in t["candidates"]}
    assert st["SPECIFIC_WAIT"] == "applicable" and st["PED_WAIT_36M"] == "no_candidate_rule"
