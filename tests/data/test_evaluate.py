import json
from datetime import date

import pytest

from sarthi.core.models import FactValue, Finding, RuleCard
from sarthi.core.store import Store
from sarthi.data import evaluate
from sarthi.llm.client import ChatResult

QUOTE = "Clause 4.1 Moratorium period applies after 60 months."
FACT_QUOTE = "The complaint is dismissed and the appeal is allowed in part."


GROUND = "waiting_period"


def _store(tmp_path, prevailed, issues=None, appellant=None):
    """prevailed: case_id -> True/False/None (policyholder_prevailed, NOT the raw outcome).
    issues: case_id -> {issue: (holding, quote)}, stored as human-reviewed."""
    s = Store(tmp_path / "t.duckdb")
    s.init()
    rows = [dict(case_id=cid, source_sha256=None, forum=None, case_number=None, decided_on=None,
                 insurer=None, product_id=None, outcome=None, relief_amount=None,
                 appellant=(appellant or {}).get(cid), policyholder_prevailed=p,
                 product_line="health")
            for cid, p in prevailed.items()]
    s.upsert("case", rows, key=["case_id"])
    _put_issues(s, issues or {})
    return s


def _put_issues(s, issues, status="reviewed"):
    rows = [dict(case_id=cid, issue=iss, holding=h, holding_quote=q, page_no=2, status=status,
                 reviewer_note=None)
            for cid, d in issues.items() for iss, (h, q) in d.items()]
    s.upsert("case_issue", rows, key=["case_id", "issue"])


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
    store = _store(tmp_path, {"c1": True, "c2": False, "c3": True})
    _patch(monkeypatch, {"c1": "CHALLENGEABLE", "c2": "CHALLENGEABLE", "c3": "NEED_INFO"})
    summary = evaluate.run_eval("r1", ["rules"], 1, store)
    m = summary.by_method["rules"]
    assert summary.n_cases == 3
    assert m.agreement == pytest.approx(1 / 2)
    assert m.false_hope_rate == pytest.approx(1 / 2)
    assert m.abstentions == 1


def test_false_hope_none_when_no_challengeable(tmp_path, monkeypatch):
    store = _store(tmp_path, {"c1": False})
    _patch(monkeypatch, {"c1": "CONSISTENT"})
    m = evaluate.run_eval("r1", ["rules"], 1, store).by_method["rules"]
    assert m.false_hope_rate is None
    assert m.agreement == 1.0


def test_rules_stable_and_rows_idempotent(tmp_path, monkeypatch):
    store = _store(tmp_path, {"c1": True, "c2": False})
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


def test_case_level_excludes_and_counts_unknown_policyholder_prevailed(tmp_path, monkeypatch):
    store = _store(tmp_path, {"c1": True, "c2": None})
    _patch(monkeypatch, {"c1": "CHALLENGEABLE", "c2": "CHALLENGEABLE"})
    s = evaluate.run_eval("r1", ["rules"], 1, store)
    m = s.by_method["rules"]
    assert s.n_cases == 2 and s.n_case_level_excluded == 1
    assert (m.answered_runs, m.challengeable_runs, m.agreeing_runs) == (1, 1, 1)


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
    store = _store(tmp_path, {"c1": False})
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
    store = _store(tmp_path, {"c1": True})
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
    store = _store(tmp_path, {"c1": True, "c2": False})
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
    store = _store(tmp_path, {"c1": True, "c2": False, "c3": True})
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
    store = _store(tmp_path, {"c1": True})
    _patch(monkeypatch, {"c1": "CONSISTENT"})
    _stub_chat(monkeypatch, [("CHALLENGEABLE", QUOTE), ("CHALLENGEABLE", QUOTE), None], [])
    s = evaluate.run_eval("r1", ["glimmer_only"], 3, store)
    out = tmp_path / "r.md"
    evaluate.write_report(s, out)
    assert "2×CHALLENGEABLE / 1×NEED_INFO" in out.read_text()


def test_run_eval_upserts_per_case_so_a_mid_run_failure_keeps_earlier_results(tmp_path, monkeypatch):
    store = _store(tmp_path, {"c1": True, "c2": True})
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
    store = _store(tmp_path, {"c1": True, "c2": False, "c3": True, "c4": True,
                              "c5": True})
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
    store = _store(tmp_path, {"c1": True})
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


# ---------- Eval v2: finding-level (PRIMARY) ----------

HQ = "We hold that the insurer failed to prove the alleged non-disclosure."
HQ2 = "The complaint fails because the waiting period had not elapsed."


def _finding_run(tmp_path, monkeypatch, cases, repeats=1, methods=("rules",)):
    """cases: cid -> (engine verdict, {issue: (holding, quote)}); prevailed True for all."""
    store = _store(tmp_path, {cid: True for cid in cases},
                   issues={cid: iss for cid, (_, iss) in cases.items() if iss})
    _patch(monkeypatch, {cid: v for cid, (v, _) in cases.items()})
    return store, evaluate.run_eval("r1", list(methods), repeats, store)


def test_finding_level_agreement_false_hope_abstention_and_excluded(tmp_path, monkeypatch):
    _, s = _finding_run(tmp_path, monkeypatch, {
        "c1": ("CHALLENGEABLE", {"R1": ("for_policyholder", HQ)}),   # agree
        "c2": ("CHALLENGEABLE", {"R1": ("for_insurer", HQ2)}),       # false hope
        "c3": ("CONSISTENT", {"R1": ("for_insurer", HQ2)}),          # agree
        "c4": ("CONSISTENT", {"R1": ("for_policyholder", HQ)}),      # disagree, not false hope
        "c5": ("NEED_INFO", {"R1": ("for_policyholder", HQ)}),       # abstention
        "c6": ("CHALLENGEABLE", {}),                                 # no reviewed issue
        "c7": ("CHALLENGEABLE", {"R1": ("not_decided", None)})})     # not decided
    m = s.by_method["rules"]
    assert m.finding_n == 4
    assert m.finding_agreement == pytest.approx(2 / 4)
    assert m.finding_false_hope_rate == pytest.approx(1 / 2)   # c1, c2 are labelled CHALLENGEABLE
    assert m.finding_abstentions == 1
    assert m.finding_excluded == 2


def test_finding_false_hope_none_without_labelled_challengeable(tmp_path, monkeypatch):
    _, s = _finding_run(tmp_path, monkeypatch, {
        "c1": ("CONSISTENT", {"R1": ("for_insurer", HQ)}),
        "c2": ("CHALLENGEABLE", {})})
    m = s.by_method["rules"]
    assert m.finding_false_hope_rate is None and m.finding_agreement == 1.0


def test_insurer_appeal_dismissed_engine_challengeable_is_agree_not_false_hope(tmp_path, monkeypatch):
    """ik_76647766 shape: Care Health v. Sawraj Tuli. The stored outcome says 'dismissed' (the
    insurer's appeal), but the policyholder won, so CHALLENGEABLE is right."""
    store = _store(tmp_path, {"ik_1": True}, appellant={"ik_1": "insurer"},
                   issues={"ik_1": {"R1": ("for_policyholder", HQ)}})
    store.con.execute("UPDATE \"case\" SET outcome='dismissed' WHERE case_id='ik_1'")
    _patch(monkeypatch, {"ik_1": "CHALLENGEABLE"})
    s = evaluate.run_eval("r1", ["rules"], 1, store)
    m = s.by_method["rules"]
    assert m.finding_agreement == 1.0 and m.finding_false_hope_rate == 0.0
    assert m.false_hope_runs == 0 and m.agreement == 1.0       # case level, direction-corrected
    row = store.con.execute("SELECT agrees_with_outcome, false_hope FROM eval_result").fetchone()
    assert row == (True, False)


def test_finding_matches_issue_on_a_trigger_ground(tmp_path, monkeypatch):
    store = _store(tmp_path, {"c1": True}, issues={"c1": {GROUND: ("for_insurer", HQ2)}})
    card = _card().model_copy(update={"triggers": [GROUND]})
    _patch(monkeypatch, {"c1": "CHALLENGEABLE"})
    monkeypatch.setattr(evaluate, "approved_cards", lambda store, as_of=None: [card])
    m = evaluate.run_eval("r1", ["rules"], 1, store).by_method["rules"]
    assert m.finding_n == 1 and m.finding_agreement == 0.0 and m.finding_false_hope_rate == 1.0


def test_conflicting_trigger_grounds_are_excluded_not_guessed(tmp_path, monkeypatch):
    store = _store(tmp_path, {"c1": True}, issues={"c1": {
        GROUND: ("for_insurer", HQ2), "pre_existing": ("for_policyholder", HQ)}})
    card = _card().model_copy(update={"triggers": [GROUND, "pre_existing"]})
    _patch(monkeypatch, {"c1": "CHALLENGEABLE"})
    monkeypatch.setattr(evaluate, "approved_cards", lambda store, as_of=None: [card])
    m = evaluate.run_eval("r1", ["rules"], 1, store).by_method["rules"]
    assert m.finding_n == 0 and m.finding_excluded == 1


def test_unreviewed_issues_are_not_used(tmp_path, monkeypatch):
    store = _store(tmp_path, {"c1": True})
    _put_issues(store, {"c1": {"R1": ("for_insurer", HQ)}}, status="drafted")
    _patch(monkeypatch, {"c1": "CHALLENGEABLE"})
    m = evaluate.run_eval("r1", ["rules"], 1, store).by_method["rules"]
    assert m.finding_n == 0 and m.finding_excluded == 1


def test_model_only_compares_when_exactly_one_reviewed_issue(tmp_path, monkeypatch):
    store = _store(tmp_path, {"c1": True, "c2": True, "c3": True}, issues={
        "c1": {"R1": ("for_policyholder", HQ)},
        "c2": {"R1": ("for_policyholder", HQ), GROUND: ("for_insurer", HQ2)},
        "c3": {}})
    _patch(monkeypatch, {"c1": "CONSISTENT", "c2": "CONSISTENT", "c3": "CONSISTENT"})
    _stub_chat(monkeypatch, [("CHALLENGEABLE", QUOTE)] * 3, [])
    m = evaluate.run_eval("r1", ["spark_only"], 1, store).by_method["spark_only"]
    assert m.finding_n == 1 and m.finding_agreement == 1.0
    assert m.finding_excluded == 2


def test_dataset_tags_and_safe_abstention(tmp_path, monkeypatch):
    store = _store(tmp_path, {"c1": True, "c2": True, "c3": True, "c4": True},
                   issues={"c1": {"R1": ("for_policyholder", HQ)}})
    _patch_findings(monkeypatch, {
        "c1": [_finding("R1", "CHALLENGEABLE")],
        "c2": [_oos_finding()],     # out of scope
        "c3": [],                   # no usable ground or rule
        "c4": [_finding("R1", "CHALLENGEABLE")]})   # in scope, no reviewed issue
    _stub_chat(monkeypatch, [("CHALLENGEABLE", QUOTE), ("CONSISTENT", QUOTE),
                             ("CONSISTENT", QUOTE), ("CHALLENGEABLE", QUOTE)], [])
    s = evaluate.run_eval("r1", ["rules", "glimmer_only"], 1, store)
    assert s.n_primary == 1 and s.n_abstention_set == 2
    assert {c.case_id: c.tag for c in s.cases} == {
        "c1": "primary", "c2": "abstention", "c3": "abstention", "c4": "untagged"}
    assert s.by_method["rules"].safe_abstention_rate == 1.0
    # stub answers in case order c1..c4: CONSISTENT on both abstention cases
    assert s.by_method["glimmer_only"].safe_abstention_rate == 1.0


def test_safe_abstention_counts_model_challengeable_on_abstention_cases(tmp_path, monkeypatch):
    store = _store(tmp_path, {"c1": True, "c2": True})
    _patch_findings(monkeypatch, {"c1": [], "c2": [_oos_finding()]})
    _stub_chat(monkeypatch, [("CHALLENGEABLE", QUOTE), ("CONSISTENT", QUOTE)], [])
    m = evaluate.run_eval("r1", ["glimmer_only"], 1, store).by_method["glimmer_only"]
    assert m.safe_abstention_rate == pytest.approx(1 / 2)


def test_report_puts_finding_level_first_lists_disagreements_with_quote(tmp_path, monkeypatch):
    _, s = _finding_run(tmp_path, monkeypatch, {
        "c1": ("CHALLENGEABLE", {"R1": ("for_policyholder", HQ)}),
        "c2": ("CHALLENGEABLE", {"R1": ("for_insurer", HQ2)})})
    out = tmp_path / "r.md"
    evaluate.write_report(s, out)
    t = out.read_text()
    i_find = t.index("## Finding-level")
    i_case = t.index("## Case-level")
    i_abst = t.index("## Abstention set")
    assert i_find < i_case < i_abst
    assert "Agreement 1/2 (50%)" in t[i_find:i_case]
    assert "False-hope 1/2 (50%)" in t[i_find:i_case]
    dis = t[i_find:i_case]
    assert "c2" in dis and "R1" in dis and HQ2 in dis and "false hope" in dis
    assert HQ not in dis.split("Disagreements")[1]
    assert "policyholder_prevailed" in t[i_case:i_abst]
    assert "secondary" in t[i_case:i_abst].lower()


def test_report_abstention_section_and_finding_counts(tmp_path, monkeypatch):
    store = _store(tmp_path, {"c1": True, "c2": True, "c3": True},
                   issues={"c1": {"R1": ("for_policyholder", HQ)}})
    _patch_findings(monkeypatch, {"c1": [_finding("R1", "CHALLENGEABLE")],
                                  "c2": [_oos_finding()], "c3": []})
    s = evaluate.run_eval("r1", ["rules"], 1, store)
    out = tmp_path / "r.md"
    evaluate.write_report(s, out)
    t = out.read_text()
    ab = t[t.index("## Abstention set"):]
    assert "Safe abstention 2/2 (100%)" in ab
    assert "Out of scope: no rule in force on the claim date" in ab and "c2" in ab
    assert "No usable rejection ground" in ab and "c3" in ab
    head = t[:t.index("## Case-level")]
    assert "primary: 1" in head and "abstention: 2" in head


# ---------- reviewer exclusions (case.excluded_reason) ----------

def test_schema_has_excluded_reason_and_migrates_an_old_case_table(tmp_path):
    import duckdb
    from sarthi.core.store import SCHEMA_PATH
    con = duckdb.connect(str(tmp_path / "old.duckdb"))
    con.execute('CREATE TABLE "case" (case_id VARCHAR PRIMARY KEY, source_sha256 VARCHAR)')
    con.close()
    s = Store(tmp_path / "old.duckdb")
    s.init()
    s.init()  # idempotent
    cols = {r[1] for r in s.con.execute("PRAGMA table_info('case')").fetchall()}
    assert "excluded_reason" in cols
    assert "excluded_reason" in SCHEMA_PATH.read_text()


def _excluded(store, cid, reason):
    store.con.execute('UPDATE "case" SET excluded_reason=? WHERE case_id=?', [reason, cid])


def test_reviewer_excluded_case_is_left_out_of_every_metric(tmp_path, monkeypatch):
    store = _store(tmp_path, {"c1": True, "c2": False, "c3": False},
                   issues={"c1": {"R1": ("for_policyholder", "q")},
                           "c2": {"R1": ("for_insurer", "q")},
                           "c3": {"R1": ("for_insurer", "q")}})
    _excluded(store, "c2", "motor insurance")
    _patch(monkeypatch, {"c1": "CHALLENGEABLE", "c2": "CHALLENGEABLE", "c3": "CHALLENGEABLE"})
    s = evaluate.run_eval("r1", ["rules"], 1, store)
    m = s.by_method["rules"]
    assert s.n_cases == 2 and [c.case_id for c in s.cases] == ["c1", "c3"]
    assert s.excluded_by_reviewer == [("c2", "motor insurance")]
    # c2 (a false hope) must not count anywhere
    assert (m.false_hope_runs, m.challengeable_runs, m.n_runs) == (1, 2, 2)
    assert (m.finding_n, m.finding_false_hope_runs) == (2, 1)
    assert not any(r.case_id == "c2" for r in s.finding_rows)
    n = store.con.execute("SELECT count(*) FROM eval_result WHERE case_id='c2'").fetchone()[0]
    assert n == 0


def test_reviewer_excluded_case_without_facts_is_still_listed(tmp_path, monkeypatch):
    store = _store(tmp_path, {"c1": True, "c2": None})
    _excluded(store, "c2", "duplicate of c1")
    _patch(monkeypatch, {"c1": "CHALLENGEABLE", "c2": "CHALLENGEABLE"},
           facts=lambda cid: _facts(cid) if cid == "c1" else {})
    s = evaluate.run_eval("r1", ["rules"], 1, store)
    assert s.excluded_by_reviewer == [("c2", "duplicate of c1")]
    assert s.n_skipped_no_facts == 0 and s.n_case_level_excluded == 0


def test_report_lists_reviewer_exclusions(tmp_path, monkeypatch):
    store = _store(tmp_path, {"c1": True, "c2": False})
    _excluded(store, "c2", "government employee scheme")
    _patch(monkeypatch, {"c1": "CHALLENGEABLE", "c2": "CHALLENGEABLE"})
    s = evaluate.run_eval("r1", ["rules"], 1, store)
    out = tmp_path / "r.md"
    evaluate.write_report(s, out)
    assert "Excluded by reviewer: c2 — government employee scheme" in out.read_text()


def test_report_without_exclusions_has_no_excluded_line(tmp_path, monkeypatch):
    s = _brief_three(tmp_path, monkeypatch, 1)
    out = tmp_path / "r.md"
    evaluate.write_report(s, out)
    assert "Excluded by reviewer" not in out.read_text()
