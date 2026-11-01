import json
from datetime import date

import pytest

from sarthi.core.models import FactValue, Finding, RuleCard
from sarthi.core.store import Store
from sarthi.data import evaluate
from sarthi.llm.client import ChatResult

QUOTE = "Clause 4.1 Moratorium period applies after 60 months."
FACT_QUOTE = "The complaint is dismissed and the appeal is allowed in part."


def _store(tmp_path, outcomes):
    s = Store(tmp_path / "t.duckdb")
    s.init()
    rows = [dict(case_id=cid, source_sha256=None, forum=None, case_number=None, decided_on=None,
                 insurer=None, product_id=None, outcome=o, relief_amount=None)
            for cid, o in outcomes.items()]
    s.upsert("case", rows, key=["case_id"])
    return s


def _facts(cid):
    return {"policy_age_months": FactValue(value=70, quote=FACT_QUOTE, page_no=1,
                                           confidence="high", status="verified")}


def _card():
    return RuleCard(rule_id="R1", version=1, quote=QUOTE, status="approved",
                    in_force_from=date(2024, 4, 1))


def _finding(rule_id, verdict, quote=QUOTE):
    return Finding(rule_id=rule_id, rule_version=1, verdict=verdict, reason=None,
                   rule_quote=quote, source_sha256="a" * 64, page_no=1, facts_used={})


def _patch(monkeypatch, verdicts_by_case, facts=_facts):
    monkeypatch.setattr(evaluate, "approved_cards", lambda store, as_of=None: [_card()])
    monkeypatch.setattr(evaluate, "load_reviewed_facts", lambda cid, store: facts(cid))
    state = {}

    def fake_rules(f, cards):
        return [_finding("R1", state["cur"])]

    monkeypatch.setattr(evaluate, "run_rules", fake_rules)
    real_load = evaluate.load_reviewed_facts

    def load(cid, store):
        state["cur"] = verdicts_by_case[cid]
        return real_load(cid, store)

    monkeypatch.setattr(evaluate, "load_reviewed_facts", load)


def test_agreement_and_false_hope_arithmetic(tmp_path, monkeypatch):
    store = _store(tmp_path, {"c1": "allowed", "c2": "dismissed", "c3": "allowed"})
    _patch(monkeypatch, {"c1": "CHALLENGEABLE", "c2": "CHALLENGEABLE", "c3": "NEED_INFO"})
    summary = evaluate.run_eval("r1", ["rules"], 1, store)
    m = summary.by_method["rules"]
    assert summary.n_cases == 3
    assert m.agreement == pytest.approx(1 / 2)
    assert m.false_hope_rate == pytest.approx(1 / 2)
    assert m.abstentions == 1


def test_false_hope_none_when_no_challengeable(tmp_path, monkeypatch):
    store = _store(tmp_path, {"c1": "dismissed"})
    _patch(monkeypatch, {"c1": "CONSISTENT"})
    m = evaluate.run_eval("r1", ["rules"], 1, store).by_method["rules"]
    assert m.false_hope_rate is None
    assert m.agreement == 1.0


def test_rules_stable_and_rows_idempotent(tmp_path, monkeypatch):
    store = _store(tmp_path, {"c1": "allowed", "c2": "dismissed"})
    _patch(monkeypatch, {"c1": "CHALLENGEABLE", "c2": "CONSISTENT"})
    s1 = evaluate.run_eval("r1", ["rules"], 3, store)
    assert s1.by_method["rules"].stability == 1.0
    assert s1.by_method["rules"].quote_coverage == 1.0
    evaluate.run_eval("r1", ["rules"], 3, store)
    rows = store.con.execute(
        "SELECT case_id, repeat, backend, verdicts, agrees_with_outcome, false_hope "
        "FROM eval_result ORDER BY case_id, repeat").fetchall()
    assert len(rows) == 6
    assert rows[0][2] == "rules"
    assert json.loads(rows[0][3])["R1"] == "CHALLENGEABLE"
    assert rows[0][4] is True and rows[0][5] is False


def test_skips_cases_without_outcome(tmp_path, monkeypatch):
    store = _store(tmp_path, {"c1": "allowed", "c2": None})
    _patch(monkeypatch, {"c1": "CHALLENGEABLE", "c2": "CHALLENGEABLE"})
    s = evaluate.run_eval("r1", ["rules"], 1, store)
    assert s.n_cases == 1 and s.n_skipped_no_outcome == 1


def test_case_verdict_rule():
    assert evaluate.case_verdict(["CONSISTENT", "CHALLENGEABLE", "NEED_INFO"]) == "CHALLENGEABLE"
    assert evaluate.case_verdict(["CONSISTENT", "CONSISTENT"]) == "CONSISTENT"
    assert evaluate.case_verdict(["CONSISTENT", "NEED_INFO"]) == "NEED_INFO"
    assert evaluate.case_verdict([]) == "NEED_INFO"


def _stub_chat(monkeypatch, answers, prompts):
    it = iter(answers)

    def fake(role, messages, *, schema=None, cache=True, **kw):
        prompts.append((role, messages, cache))
        a = next(it)
        parsed = None if a is None else schema(verdict=a[0], quote=a[1])
        return ChatResult(text=None, parsed=parsed, tool_calls=[], tokens_in=10, tokens_out=5,
                          cost_usd=0.01, cache_hit=False, needs_review=a is None, backend="stub")

    monkeypatch.setattr(evaluate, "chat", fake)


def test_model_prompt_has_no_leakage(tmp_path, monkeypatch):
    store = _store(tmp_path, {"c1": "dismissed"})
    _patch(monkeypatch, {"c1": "CONSISTENT"})
    prompts = []
    _stub_chat(monkeypatch, [("CONSISTENT", QUOTE)], prompts)
    evaluate.run_eval("r1", ["glimmer_only"], 1, store)
    role, messages, cache = prompts[0]
    text = json.dumps(messages)
    assert role == "judge_glimmer" and cache is False
    assert QUOTE in text and "R1" in text and "70" in text
    for banned in ("dismissed", "allowed", "partly_allowed", FACT_QUOTE):
        assert banned not in text


def test_model_metrics_and_instability(tmp_path, monkeypatch):
    store = _store(tmp_path, {"c1": "allowed"})
    _patch(monkeypatch, {"c1": "CONSISTENT"})
    prompts = []
    _stub_chat(monkeypatch, [("CHALLENGEABLE", QUOTE), ("CONSISTENT", "invented words"), None],
               prompts)
    s = evaluate.run_eval("r1", ["spark_only"], 3, store)
    m = s.by_method["spark_only"]
    assert prompts[0][0] == "judge_spark"
    assert m.stability == 0.0
    assert m.quote_coverage == pytest.approx(1 / 3)
    assert m.abstentions == 1
    assert m.cost_usd == pytest.approx(0.03)
    assert m.agreement == pytest.approx(1 / 2)


def test_write_report(tmp_path, monkeypatch):
    store = _store(tmp_path, {"c1": "allowed", "c2": "dismissed"})
    _patch(monkeypatch, {"c1": "CONSISTENT", "c2": "CHALLENGEABLE"})
    s = evaluate.run_eval("r1", ["rules"], 1, store)
    out = tmp_path / "report.md"
    evaluate.write_report(s, out)
    t = out.read_text()
    assert "agreement under 100% is expected" in t
    assert "c1" in t and "c2" in t and "False-hope" in t


def test_cli_registered():
    from sarthi.data import cli
    args = cli.build_parser().parse_args(
        ["eval", "--methods", "rules", "glimmer_only", "--repeats", "2", "--run-id", "x"])
    assert args.methods == ["rules", "glimmer_only"] and args.repeats == 2 and args.run_id == "x"


def _brief_three(tmp_path, monkeypatch, repeats):
    store = _store(tmp_path, {"c1": "allowed", "c2": "dismissed", "c3": "allowed"})
    _patch(monkeypatch, {"c1": "CHALLENGEABLE", "c2": "CHALLENGEABLE", "c3": "NEED_INFO"})
    return evaluate.run_eval("r1", ["rules"], repeats, store)


def test_counts_runs_vs_cases_with_repeats(tmp_path, monkeypatch):
    m = _brief_three(tmp_path, monkeypatch, 3).by_method["rules"]
    assert (m.n_runs, m.answered_runs, m.challengeable_runs) == (9, 6, 6)
    assert m.abstained_runs == 3 and m.abstained_cases == 1
    assert m.agreement == pytest.approx(1 / 2) and m.false_hope_rate == pytest.approx(1 / 2)


def test_report_shows_counts_pooling_and_disagreement_marks(tmp_path, monkeypatch):
    s = _brief_three(tmp_path, monkeypatch, 3)
    out = tmp_path / "r.md"
    evaluate.write_report(s, out)
    t = out.read_text()
    assert "Agreement 3/6 (50%)" in t and "False-hope 3/6 (50%)" in t
    assert "Abstained 3 runs / 1 case" in t
    assert ("Rates are pooled over 3 repeats per case; for the rules method every repeat "
            "is identical.") in t
    rows = {ln.split("|")[1].strip(): ln for ln in t.splitlines() if ln.startswith("| c")}
    assert "✗" in rows["c2"] and "✗" not in rows["c1"]
    assert "abstain" in rows["c3"]


def test_report_shows_repeat_counts_when_verdicts_differ(tmp_path, monkeypatch):
    store = _store(tmp_path, {"c1": "allowed"})
    _patch(monkeypatch, {"c1": "CONSISTENT"})
    _stub_chat(monkeypatch, [("CHALLENGEABLE", QUOTE), ("CHALLENGEABLE", QUOTE), None], [])
    s = evaluate.run_eval("r1", ["glimmer_only"], 3, store)
    out = tmp_path / "r.md"
    evaluate.write_report(s, out)
    assert "2×CHALLENGEABLE / 1×NEED_INFO" in out.read_text()


def test_run_eval_upserts_per_case_so_a_mid_run_failure_keeps_earlier_results(tmp_path, monkeypatch):
    store = _store(tmp_path, {"c1": "allowed", "c2": "allowed"})
    _patch(monkeypatch, {"c1": "CHALLENGEABLE", "c2": "CHALLENGEABLE"})
    real = evaluate._run_once

    def boom(method, case_id, *a, **k):
        if case_id == "c2":
            raise RuntimeError("model down")
        return real(method, case_id, *a, **k)

    monkeypatch.setattr(evaluate, "_run_once", boom)
    with pytest.raises(RuntimeError):
        evaluate.run_eval("r1", ["rules"], 1, store)
    saved = store.con.execute("SELECT case_id FROM eval_result WHERE run_id='r1'").fetchall()
    assert saved == [("c1",)]


# ---------- explicit out-of-scope category (Parth's 1 Nov 2026 decision) ----------

def _patch_findings(monkeypatch, findings_by_case):
    monkeypatch.setattr(evaluate, "approved_cards", lambda store, as_of=None: [_card()])
    state = {}
    real = lambda cid, store: _facts(cid)

    def load(cid, store):
        state["cur"] = findings_by_case[cid]
        return real(cid, store)

    monkeypatch.setattr(evaluate, "load_reviewed_facts", load)
    monkeypatch.setattr(evaluate, "run_rules", lambda f, cards: list(state["cur"]))


def _oos_finding():
    f = _finding("R1", "NEED_INFO")
    return f.model_copy(update={"reason": "rule_not_in_force"})


def _oos_run(tmp_path, monkeypatch, repeats=1):
    store = _store(tmp_path, {"c1": "allowed", "c2": "dismissed", "c3": "allowed", "c4": "allowed",
                              "c5": "allowed"})
    _patch_findings(monkeypatch, {
        "c1": [_finding("R1", "CHALLENGEABLE")],
        "c2": [_oos_finding()],                      # every finding not in force
        "c3": [],                                    # ground triggers no card
        "c4": [_finding("R1", "NEED_INFO")],         # genuine abstention (reason None)
        "c5": [_oos_finding(), _finding("R2", "NEED_INFO")]})  # mixed: still an abstention
    return evaluate.run_eval("r1", ["rules"], repeats, store)


def test_out_of_scope_classified_not_abstained(tmp_path, monkeypatch):
    m = _oos_run(tmp_path, monkeypatch).by_method["rules"]
    assert m.out_of_scope_cases == ["c2"]
    assert m.abstained_cases == 2 and m.abstained_runs == 2   # c4, c5 only


def test_out_of_scope_excluded_from_denominators(tmp_path, monkeypatch):
    m = _oos_run(tmp_path, monkeypatch).by_method["rules"]
    assert m.answered_runs == 1 and m.agreeing_runs == 1 and m.agreement == 1.0
    assert m.challengeable_runs == 1 and m.false_hope_runs == 0
    assert m.n_runs == 5


def test_out_of_scope_case_row_and_stored_result(tmp_path, monkeypatch):
    s = _oos_run(tmp_path, monkeypatch)
    row = {c.case_id: c for c in s.cases}["c2"]
    assert row.verdicts["rules"] == ["OUT_OF_SCOPE"]


def test_out_of_scope_repeats_list_case_once(tmp_path, monkeypatch):
    m = _oos_run(tmp_path, monkeypatch, repeats=3).by_method["rules"]
    assert m.out_of_scope_cases == ["c2"]


def test_report_lists_out_of_scope_cases(tmp_path, monkeypatch):
    s = _oos_run(tmp_path, monkeypatch)
    out = tmp_path / "r.md"
    evaluate.write_report(s, out)
    t = out.read_text()
    assert "Out of scope: no rule in force on the claim date — sent to human review" in t
    line = next(ln for ln in t.splitlines() if ln.startswith("Out of scope"))
    assert "c2" in line and "c3" not in line and "c1" not in line
    rows = {ln.split("|")[1].strip(): ln for ln in t.splitlines() if ln.startswith("| c")}
    assert "out of scope" in rows["c2"] and "abstain" not in rows["c2"]
    assert "✗" not in rows["c2"]


def test_model_methods_never_out_of_scope(tmp_path, monkeypatch):
    store = _store(tmp_path, {"c1": "allowed"})
    _patch(monkeypatch, {"c1": "CONSISTENT"})
    _stub_chat(monkeypatch, [None], [])
    m = evaluate.run_eval("r1", ["glimmer_only"], 1, store).by_method["glimmer_only"]
    assert m.out_of_scope_cases == [] and m.abstained_cases == 1


# ---------- round 2 (R98a): empty findings are NOT "out of scope" ----------

def test_empty_findings_go_to_separate_bucket_not_out_of_scope(tmp_path, monkeypatch):
    m = _oos_run(tmp_path, monkeypatch).by_method["rules"]
    assert m.out_of_scope_cases == ["c2"]          # non-empty, all rule_not_in_force
    assert m.no_usable_cases == ["c3"]             # empty findings
    assert m.abstained_cases == 2                  # c4 and the mixed c5
    assert m.answered_runs == 1 and m.agreement == 1.0
    assert m.challengeable_runs == 1 and m.false_hope_runs == 0


def test_mixed_not_in_force_and_other_need_info_stays_abstained(tmp_path, monkeypatch):
    s = _oos_run(tmp_path, monkeypatch)
    rows = {c.case_id: c for c in s.cases}
    assert rows["c5"].verdicts["rules"] == ["NEED_INFO"]
    assert rows["c3"].verdicts["rules"] == ["NO_USABLE_GROUND_OR_RULE"]


def test_report_lists_both_buckets_separately(tmp_path, monkeypatch):
    s = _oos_run(tmp_path, monkeypatch)
    out = tmp_path / "r.md"
    evaluate.write_report(s, out)
    t = out.read_text()
    oos = next(ln for ln in t.splitlines() if ln.startswith("Out of scope"))
    nu = next(ln for ln in t.splitlines() if ln.startswith("No usable rejection ground"))
    assert "c2" in oos and "c3" not in oos
    assert "No usable rejection ground or no rule triggered — sent to human review" in nu
    assert "c3" in nu and "c2" not in nu
    rows = {ln.split("|")[1].strip(): ln for ln in t.splitlines() if ln.startswith("| c")}
    assert "no usable ground or rule" in rows["c3"] and "abstain" not in rows["c3"]
