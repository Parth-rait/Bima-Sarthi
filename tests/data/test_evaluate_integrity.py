"""Evaluation integrity: an unresolved (extracted / needs_review) fact that feeds a triggered card
must make that finding SKIPPED, never an engine verdict ("the Gupta bug", ik_72274767), and only
health cases are evaluated against the health rules."""
import json
from datetime import date
from pathlib import Path

import pytest
import yaml

from sarthi.app.extract import ready_for_rules
from sarthi.core.models import FactValue, RuleCard
from sarthi.core.store import Store
from sarthi.data import evaluate
from sarthi.data.case_facts import load_reviewed_facts, load_unresolved_facts

SEED = Path(__file__).parents[2] / "rules" / "seed"
HQ = "We hold that the moratorium bars repudiation of the claim."


def seed_card(name: str) -> RuleCard:
    data = yaml.safe_load((SEED / f"{name}.yaml").read_text(encoding="utf-8"))
    data.pop("source_id", None)
    data.update(status="approved", source_sha256="a" * 64)
    return RuleCard(**data)


def all_cards():
    return [seed_card(n) for n in ("MORATORIUM_60M", "MORATORIUM_60M.v0", "PED_WAIT_36M",
                                   "PED_WAIT_36M.v0", "CASHLESS_1H", "REJECTION_PROCESS")]


@pytest.fixture
def store(tmp_path):
    s = Store(tmp_path / "t.duckdb")
    s.init()
    return s


def add_case(store, cid, prevailed=True, line="health", excluded=None):
    store.upsert("case", [dict(case_id=cid, source_sha256=None, forum=None, case_number=None,
                               decided_on=None, insurer=None, product_id=None, outcome=None,
                               relief_amount=None, appellant=None, policyholder_prevailed=prevailed,
                               excluded_reason=excluded, product_line=line)], key=["case_id"])


def add_facts(store, cid, facts: dict, status="reviewed"):
    """facts: field -> JSON-able value, or (value, status)."""
    rows = []
    for field, v in facts.items():
        value, st = v if isinstance(v, tuple) else (v, status)
        rows.append(dict(case_id=cid, field=field, value=json.dumps(value), quote="q", page_no=1,
                         confidence=1.0, status=st, reviewer_note=None))
    store.upsert("case_fact", rows, key=["case_id", "field"])


def add_issue(store, cid, issue, holding="for_policyholder", status="reviewed"):
    store.upsert("case_issue", [dict(case_id=cid, issue=issue, holding=holding, holding_quote=HQ,
                                     page_no=2, status=status, reviewer_note=None)],
                 key=["case_id", "issue"])


def run(store, monkeypatch, cards=None):
    monkeypatch.setattr(evaluate, "approved_cards", lambda s, as_of=None: cards or all_cards())
    return evaluate.run_eval("r1", ["rules"], 1, store)


# Gupta shape: ~4 months with this insurer, the earlier cover is in ported_from_date.
GUPTA = {"rejection_ground": "non_disclosure", "fraud_alleged": False,
         "inception_date": "2024-12-01", "claim_date": "2025-04-15"}


def gupta(store, port_status):
    add_case(store, "ik_gupta", prevailed=True)
    add_facts(store, "ik_gupta", GUPTA)
    add_facts(store, "ik_gupta", {"ported_from_date": ("2016-01-01", port_status)})
    add_issue(store, "ik_gupta", "MORATORIUM_60M")


# ---- (a) unresolved port: skipped, never CONSISTENT ----

def test_without_the_fix_the_engine_alone_says_consistent(store):
    """Documents the bug: the reviewed facts alone drop the port and give a wrong CONSISTENT."""
    from sarthi.core.engine import run_rules
    gupta(store, "needs_review")
    out = run_rules(load_reviewed_facts("ik_gupta", store), all_cards())
    assert {f.rule_id: f.verdict for f in out}["MORATORIUM_60M"] == "CONSISTENT"


@pytest.mark.parametrize("status", ["needs_review", "extracted"])
def test_unresolved_ported_from_date_skips_the_finding(store, monkeypatch, status):
    gupta(store, status)
    s = run(store, monkeypatch)
    m = s.by_method["rules"]
    assert m.skipped_unresolved == 1
    assert m.skipped_cases == ["ik_gupta"]
    assert m.finding_n == 0 and m.finding_agreeing == 0 and m.finding_disagreeing == 0
    assert m.finding_abstentions == 0 and m.abstained_cases == 0 and m.abstained_runs == 0
    assert m.answered_runs == 0 and m.agreeing_runs == 0
    row = next(r for r in s.finding_rows if r.result == "skipped")
    assert row.rule_id == "MORATORIUM_60M"
    assert row.skip_reason == "unresolved_facts:ported_from_date"
    assert row.verdict == "SKIPPED"
    case = s.cases[0]
    assert case.verdicts["rules"] == ["SKIPPED_UNRESOLVED"]
    assert case.tag == "skipped"
    assert (s.n_eligible, s.n_skipped, s.n_out_of_scope) == (0, 1, 0)


def test_skipped_findings_never_reach_the_stored_verdicts_as_engine_verdicts(store, monkeypatch):
    gupta(store, "needs_review")
    run(store, monkeypatch)
    verdicts = json.loads(store.con.execute("SELECT verdicts FROM eval_result").fetchone()[0])
    assert "MORATORIUM_60M" not in {k for k, v in verdicts.items()
                                    if v in ("CONSISTENT", "CHALLENGEABLE", "NEED_INFO")}
    assert verdicts["_case"] == "SKIPPED_UNRESOLVED"
    assert verdicts["_skipped"] == {"MORATORIUM_60M": "unresolved_facts:ported_from_date"}


# ---- (b) once reviewed, the finding proceeds ----

def test_reviewed_port_lets_the_finding_proceed_as_need_info(store, monkeypatch):
    gupta(store, "reviewed")
    s = run(store, monkeypatch)
    m = s.by_method["rules"]
    assert m.skipped_unresolved == 0 and m.skipped_cases == []
    # a port without continuity_confirmed is NEED_INFO by the existing derive rules
    assert m.finding_abstentions == 1
    assert (s.n_eligible, s.n_skipped) == (1, 0)
    assert s.cases[0].verdicts["rules"] == ["NEED_INFO"]


def test_corrected_port_also_proceeds(store, monkeypatch):
    gupta(store, "corrected")
    assert run(store, monkeypatch).by_method["rules"].skipped_unresolved == 0


# ---- (c) an unrelated flagged field does not block ----

def test_unrelated_flagged_field_does_not_block(store, monkeypatch):
    add_case(store, "c1")
    add_facts(store, "c1", {"rejection_ground": "non_disclosure", "fraud_alleged": False,
                            "inception_date": "2019-01-10", "claim_date": "2025-04-15",
                            "policy_renewal_date": "2024-06-01"})
    # cashless/discharge times and the cited clause feed no non_disclosure card
    add_facts(store, "c1", {"cashless_request_at": ("2025-04-15T10:00:00", "needs_review"),
                            "cited_clause": ("clause 4", "extracted"),
                            "deductions": ([], "needs_review")})
    add_issue(store, "c1", "MORATORIUM_60M", "for_policyholder")
    s = run(store, monkeypatch)
    m = s.by_method["rules"]
    assert m.skipped_unresolved == 0 and m.skipped_cases == []
    assert m.finding_n == 1 and m.finding_agreement == 1.0       # CHALLENGEABLE vs policyholder
    assert s.n_skipped == 0 and s.n_eligible == 1


def test_flagged_ped_input_blocks_only_a_ped_ground_case(store, monkeypatch):
    add_case(store, "ped")
    add_facts(store, "ped", {"rejection_ground": "pre_existing_disease", "inception_date": "2019-01-10",
                             "claim_date": "2025-04-15", "policy_renewal_date": "2024-06-01",
                             "disclosed_conditions": ["asthma"]})
    add_facts(store, "ped", {"alleged_undisclosed_condition": ("diabetes", "needs_review")})
    add_case(store, "nd")   # same flagged field, but the ground is non_disclosure: not blocking
    add_facts(store, "nd", {"rejection_ground": "non_disclosure", "fraud_alleged": False,
                            "inception_date": "2019-01-10", "claim_date": "2025-04-15",
                            "policy_renewal_date": "2024-06-01"})
    add_facts(store, "nd", {"alleged_undisclosed_condition": ("diabetes", "needs_review")})
    s = run(store, monkeypatch)
    m = s.by_method["rules"]
    assert m.skipped_cases == ["ped"]
    row = next(r for r in s.finding_rows if r.result == "skipped")
    assert row.rule_id == "PED_WAIT_36M"
    assert row.skip_reason == "unresolved_facts:alleged_undisclosed_condition"
    assert {c.case_id: c.verdicts["rules"] for c in s.cases}["nd"] == ["CHALLENGEABLE"]


def test_unresolved_rejection_ground_skips_the_case(store, monkeypatch):
    add_case(store, "c1")
    add_facts(store, "c1", {"inception_date": "2019-01-10", "claim_date": "2025-04-15"})
    add_facts(store, "c1", {"rejection_ground": ("non_disclosure", "needs_review")})
    s = run(store, monkeypatch)
    m = s.by_method["rules"]
    assert m.skipped_cases == ["c1"] and m.skipped_unresolved == 1
    assert m.no_usable_cases == []
    row = next(r for r in s.finding_rows if r.result == "skipped")
    assert row.skip_reason == "unresolved_facts:rejection_ground"


def test_unresolved_admission_date_stands_in_for_missing_claim_date(store, monkeypatch):
    add_case(store, "c1")
    add_facts(store, "c1", {"rejection_ground": "non_disclosure", "fraud_alleged": False,
                            "inception_date": "2019-01-10", "policy_renewal_date": "2024-06-01"})
    add_facts(store, "c1", {"admission_date": ("2025-04-15", "extracted")})
    s = run(store, monkeypatch)
    m = s.by_method["rules"]
    assert m.skipped_cases == ["c1"] and m.abstained_cases == 0
    assert next(r for r in s.finding_rows if r.result == "skipped").skip_reason == \
        "unresolved_facts:admission_date"


def test_rejected_fact_is_resolved_not_blocking(store, monkeypatch):
    gupta(store, "rejected")
    assert run(store, monkeypatch).by_method["rules"].skipped_unresolved == 0


def test_model_methods_skip_a_skipped_case(store, monkeypatch):
    """The same incomplete facts would feed the model baseline, so it is not run (no spend)."""
    gupta(store, "needs_review")
    monkeypatch.setattr(evaluate, "approved_cards", lambda s, as_of=None: all_cards())
    def boom(*a, **k):
        raise AssertionError("model must not be called for a skipped case")
    monkeypatch.setattr(evaluate, "chat", boom)
    s = evaluate.run_eval("r1", ["rules", "glimmer_only"], 1, store)
    g = s.by_method["glimmer_only"]
    assert g.skipped_cases == ["ik_gupta"] and g.n_runs == 0 and g.cost_usd == 0.0


# ---- (d) app readiness and evaluation readiness agree ----

R = "reviewed"
READINESS_TABLE = [
    # (id, facts, flagged unresolved fields -> JSON value)
    ("nothing_flagged", dict(GUPTA), {}),
    ("port_flagged", dict(GUPTA), {"ported_from_date": "2016-01-01"}),
    ("renewal_gap_flagged", dict(GUPTA), {"renewal_gap_days": 10}),
    ("claim_date_flagged", {k: v for k, v in GUPTA.items() if k != "claim_date"},
     {"claim_date": "2025-04-15"}),
    ("inception_flagged", {k: v for k, v in GUPTA.items() if k != "inception_date"},
     {"inception_date": "2024-12-01"}),
    ("fraud_flagged", {k: v for k, v in GUPTA.items() if k != "fraud_alleged"},
     {"fraud_alleged": False}),
    ("unrelated_flagged", dict(GUPTA), {"cashless_request_at": "2025-04-15T10:00:00",
                                        "cited_clause": "clause 4"}),
    ("ped_input_flagged_other_ground", dict(GUPTA), {"alleged_undisclosed_condition": "diabetes"}),
    ("ped_ground_ped_input_flagged",
     {**GUPTA, "rejection_ground": "pre_existing_disease"}, {"alleged_undisclosed_condition": "diabetes"}),
    ("ped_ground_moratorium_input_flagged",
     {**GUPTA, "rejection_ground": "pre_existing_disease"}, {"renewal_gap_days": 10}),
    ("renewal_date_flagged", {**GUPTA, "policy_renewal_date": "2024-06-01"},
     {"policy_renewal_date": "2024-12-01"}),
    ("ground_flagged", {k: v for k, v in GUPTA.items() if k != "rejection_ground"},
     {"rejection_ground": "non_disclosure"}),
    ("process_ground_cashless_flagged",
     {**GUPTA, "rejection_ground": "cashless_delay"}, {"cashless_request_at": "2025-04-15T10:00:00"}),
]


def _as_fv(facts):
    from sarthi.data.case_facts import _decode
    return {k: FactValue(value=_decode(k, v), status="verified") for k, v in facts.items()}


@pytest.mark.parametrize("name,facts,flagged", READINESS_TABLE, ids=[r[0] for r in READINESS_TABLE])
def test_app_readiness_and_evaluation_readiness_agree(store, name, facts, flagged):
    cards = all_cards()
    add_case(store, "c1")
    add_facts(store, "c1", facts)
    add_facts(store, "c1", flagged, status="needs_review")
    reviewed = load_reviewed_facts("c1", store)
    unresolved = load_unresolved_facts("c1", store)
    assert set(unresolved) == set(flagged)
    # the app sees every fact it holds; unresolved ones are 'needs_confirmation'
    app_view = {**reviewed, **unresolved}
    assert all(f.status == "needs_confirmation" for f in unresolved.values())
    assert evaluate.evaluation_ready(reviewed, unresolved, cards) == ready_for_rules(app_view, cards)


# ---- product line handling in evaluation ----

def _ok_case(store, cid, line, prevailed=True):
    add_case(store, cid, prevailed=prevailed, line=line)
    add_facts(store, cid, {"rejection_ground": "non_disclosure", "fraud_alleged": False,
                           "inception_date": "2019-01-10", "claim_date": "2025-04-15",
                           "policy_renewal_date": "2024-06-01"})
    add_issue(store, cid, "MORATORIUM_60M")


def test_only_health_cases_are_scored(store, monkeypatch):
    _ok_case(store, "c_health", "health")
    _ok_case(store, "c_life", "life")
    _ok_case(store, "c_motor", "motor")
    _ok_case(store, "c_null", None)
    _ok_case(store, "c_unknown", "unknown")
    s = run(store, monkeypatch)
    assert s.n_cases == 1 and [c.case_id for c in s.cases] == ["c_health"]
    assert s.by_method["rules"].finding_n == 1
    assert sorted(s.not_health) == [("c_life", "life"), ("c_motor", "motor")]
    assert sorted(s.product_line_unknown) == ["c_null", "c_unknown"]


def test_non_health_cases_do_not_add_eval_rows_or_spend(store, monkeypatch):
    _ok_case(store, "c_life", "life")
    def boom(*a, **k):
        raise AssertionError("no model call for a non-health case")
    monkeypatch.setattr(evaluate, "chat", boom)
    monkeypatch.setattr(evaluate, "approved_cards", lambda s, as_of=None: all_cards())
    s = evaluate.run_eval("r1", ["rules", "spark_only"], 1, store)
    assert store.con.execute("SELECT count(*) FROM eval_result").fetchone() == (0,)
    assert s.by_method["rules"].n_runs == 0


def test_report_lists_not_health_and_counts_unknown(store, monkeypatch, tmp_path):
    _ok_case(store, "ik_140785688", "life")
    _ok_case(store, "ik_177454999", "motor")
    _ok_case(store, "c_null", None)
    s = run(store, monkeypatch)
    out = tmp_path / "r.md"
    evaluate.write_report(s, out)
    t = out.read_text()
    assert "Not health: ik_140785688 (life)" in t
    assert "Not health: ik_177454999 (motor)" in t
    assert "Product line unknown: 1 case" in t and "c_null" in t


def test_excluded_motor_case_still_listed_as_not_health(store, monkeypatch, tmp_path):
    add_case(store, "ik_177454999", line="motor", excluded="motor insurance")
    s = run(store, monkeypatch)
    assert s.not_health == [("ik_177454999", "motor")]
    assert s.excluded_by_reviewer == [("ik_177454999", "motor insurance")]


# ---- report: separate denominators and a distinct skipped bucket ----

def test_report_has_separate_denominators_and_skipped_section(store, monkeypatch, tmp_path):
    gupta(store, "needs_review")                       # skipped
    _ok_case(store, "c_ok", "health")                  # eligible (CHALLENGEABLE)
    _ok_case(store, "c_oos", "health")                 # out of scope: policy start in 2018
    add_facts(store, "c_oos", {"inception_date": "2018-01-10", "policy_renewal_date": "2018-06-01"})
    s = run(store, monkeypatch)
    assert (s.n_eligible, s.n_skipped, s.n_out_of_scope, s.n_no_usable) == (1, 1, 1, 0)
    out = tmp_path / "r.md"
    evaluate.write_report(s, out)
    t = out.read_text()
    assert "Eligible: 1" in t and "Skipped (unresolved facts): 1" in t and "Out of scope: 1" in t
    assert "Skipped, unresolved facts" in t
    line = next(ln for ln in t.splitlines() if "ik_gupta" in ln and "unresolved_facts:" in ln)
    assert "MORATORIUM_60M" in line and "ported_from_date" in line
    row = next(ln for ln in t.splitlines() if ln.startswith("| ik_gupta"))
    assert "skipped" in row.lower() and "CONSISTENT" not in row and "abstain" not in row
