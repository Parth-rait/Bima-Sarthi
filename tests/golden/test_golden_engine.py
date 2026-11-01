"""Golden engine scenarios (tests/golden/scenarios.yaml).

SYNTHETIC code-test fixtures, hand-written to pin the rule engine's behaviour against the seed
cards. They are not data, not court cases and never feed evaluation metrics. The cards are built
in memory from rules/seed/*.yaml (status approved); no database is touched except a throwaway
temp store in the evaluation-level scenarios. A failure names the scenario id.
"""
import json
from datetime import date, datetime
from pathlib import Path

import pytest
import yaml

from sarthi.core.engine import run_rules
from sarthi.core.models import FactValue, RuleCard
from sarthi.core.store import Store
from sarthi.data import case_issues, evaluate

HERE = Path(__file__).parent
SEED = HERE.parents[1] / "rules" / "seed"
DOC = yaml.safe_load((HERE / "scenarios.yaml").read_text(encoding="utf-8"))
BASES = DOC["bases"]
SCENARIOS = DOC["scenarios"]
EVAL_SCENARIOS = DOC["evaluation_scenarios"]
VERDICTS = {"CONSISTENT", "CHALLENGEABLE", "NEED_INFO"}


def seed_cards(stems: list[str] | None = None) -> list[RuleCard]:
    """Approved in-memory cards from the seed files (fake sha: run_rules only needs non-empty)."""
    paths = sorted(SEED.glob("*.yaml")) if stems is None else [SEED / f"{s}.yaml" for s in stems]
    out = []
    for p in paths:
        data = yaml.safe_load(p.read_text(encoding="utf-8"))
        data.pop("source_id", None)
        data.update(status="approved", source_sha256="a" * 64)
        data["quote"] = data.get("quote") or "golden fixture quote"  # some seed cards have none yet
        out.append(RuleCard(**data))
    return out


def to_fact(raw) -> FactValue:
    if isinstance(raw, dict) and "value" in raw and set(raw) <= {"value", "status"}:
        return FactValue(value=raw["value"], quote="golden fixture", page_no=1,
                         status=raw.get("status", "verified"))
    return FactValue(value=raw, quote="golden fixture", page_no=1, confidence="high",
                     status="verified")


def build_facts(base: str | None, overrides: dict | None) -> dict[str, FactValue]:
    merged = dict(BASES[base]) if base else {}
    merged.update(overrides or {})
    return {k: to_fact(v) for k, v in merged.items() if v is not None}


def check(sc: dict, findings) -> list[str]:
    """-> list of mismatch descriptions (empty = pass)."""
    expect = sc["expect"]
    errs = []
    got = {f.rule_id: f for f in findings}
    if set(got) != set(expect):
        errs.append(f"rule ids: expected {sorted(expect)}, got {sorted(got)}")
    for rid, want in expect.items():
        f = got.get(rid)
        if f is None:
            continue
        want = {"verdict": want} if isinstance(want, str) else want
        for key, actual in (("verdict", f.verdict), ("reason", f.reason), ("version", f.rule_version)):
            if key in want and want[key] != actual:
                errs.append(f"{rid} {key}: expected {want[key]!r}, got {actual!r}")
    return errs


def test_at_least_25_scenarios_with_unique_ids_and_descriptions():
    ids = [s["id"] for s in SCENARIOS]
    assert len(SCENARIOS) >= 25
    assert len(ids) == len(set(ids)), "duplicate scenario ids"
    assert all(s.get("description") and "expect" in s for s in SCENARIOS), "id/description/expect"
    for s in SCENARIOS:
        for want in s["expect"].values():
            verdict = want if isinstance(want, str) else want["verdict"]
            assert verdict in VERDICTS, s["id"]


def test_scenario_file_is_labelled_as_code_test_fixtures():
    head = (HERE / "scenarios.yaml").read_text(encoding="utf-8")[:600]
    assert "code-test fixtures, NOT data" in head


@pytest.mark.parametrize("sc", SCENARIOS, ids=[s["id"] for s in SCENARIOS])
def test_engine_scenario(sc):
    facts = build_facts(sc.get("base"), sc.get("facts"))
    findings = run_rules(facts, seed_cards(sc.get("cards")))
    errs = check(sc, findings)
    assert not errs, f"scenario {sc['id']} ({sc['description']}): " + "; ".join(errs)


def test_every_seed_card_family_is_covered():
    covered = {rid for s in SCENARIOS for rid in s["expect"]}
    assert {"MORATORIUM_60M", "PED_WAIT_36M", "CASHLESS_1H", "DISCHARGE_3H",
            "REJECTION_PROCESS"} <= covered


def test_both_card_versions_are_exercised_for_moratorium_and_ped():
    versions = {(rid, want.get("version")) for s in SCENARIOS for rid, want in s["expect"].items()
                if isinstance(want, dict)}
    for rid in ("MORATORIUM_60M", "PED_WAIT_36M"):
        assert (rid, 0) in versions and (rid, 1) in versions


def test_a_wrong_expectation_would_name_the_scenario():
    sc = {"id": "demo_wrong", "description": "d", "expect": {"MORATORIUM_60M": "CONSISTENT"}}
    facts = build_facts("nd_v1", None)   # engine says CHALLENGEABLE
    errs = check(sc, run_rules(facts, seed_cards()))
    assert errs and "verdict" in errs[0]
    with pytest.raises(AssertionError, match="demo_wrong"):
        assert not errs, f"scenario {sc['id']}: " + "; ".join(errs)


def test_engine_rejects_unapproved_cards():
    card = seed_cards(["MORATORIUM_60M"])[0].model_copy(update={"status": "draft"})
    with pytest.raises(ValueError):
        run_rules(build_facts("nd_v1", None), [card])


# ---------- evaluation level: the appeal inversion ----------

@pytest.mark.parametrize("sc", EVAL_SCENARIOS, ids=[s["id"] for s in EVAL_SCENARIOS])
def test_evaluation_scenario(sc, tmp_path, monkeypatch):
    store = Store(tmp_path / "golden.duckdb")
    store.init()
    cid = "golden_case"
    appellant, outcome = sc["case"]["appellant"], sc["case"]["outcome"]
    prevailed = case_issues.prevailed_from_outcome(appellant, outcome)
    store.upsert("case", [dict(case_id=cid, source_sha256=None, forum=None, case_number=None,
                               decided_on=None, insurer=None, product_id=None, outcome=outcome,
                               relief_amount=None, appellant=appellant,
                               policyholder_prevailed=prevailed, product_line="health")],
                 key=["case_id"])
    merged = dict(BASES[sc["facts"]])
    merged.update(sc.get("facts_override") or {})
    rows = []
    for field, v in merged.items():
        enc = v.isoformat() if isinstance(v, (date, datetime)) else v
        rows.append(dict(case_id=cid, field=field, value=json.dumps(enc), quote="golden fixture",
                         page_no=1, confidence=1.0, status="reviewed", reviewer_note=None))
    store.upsert("case_fact", rows, key=["case_id", "field"])
    store.upsert("case_issue", [dict(case_id=cid, issue=issue, holding=holding,
                                     holding_quote="golden fixture", page_no=1, status="reviewed",
                                     reviewer_note=None)
                                for issue, holding in sc["issues"].items()],
                 key=["case_id", "issue"])
    monkeypatch.setattr(evaluate, "approved_cards", lambda s, as_of=None: seed_cards())
    m = evaluate.run_eval("golden", ["rules"], 1, store).by_method["rules"]
    want = sc["expect"]
    got = {"policyholder_prevailed": prevailed, "finding_agreeing": m.finding_agreeing,
           "finding_false_hope_runs": m.finding_false_hope_runs,
           "case_false_hope_runs": m.false_hope_runs, "case_agreeing_runs": m.agreeing_runs}
    assert got == want, f"scenario {sc['id']} ({sc['description'].strip()}): expected {want}, got {got}"
