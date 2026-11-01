import json
from datetime import date

import pytest

from sarthi.core.models import Case, CaseIssue, RuleCard
from sarthi.core.store import Store
from sarthi.data import case_issues, cli
from sarthi.data.case_issues import (IssueDecision, IssuesOut, OVERALL, OutIssue, backfill_appellant,
                                     draft_issues, infer_appellant, prevailed_from_outcome,
                                     review_issues, write_review_sheet)
from sarthi.data.rule_cards import _to_row
from sarthi.llm.client import ChatResult

SHA = "b" * 64
PAGE = ("The insurer repudiated the claim for pre-existing disease. We hold that the "
        "moratorium of 60 months bars repudiation. The appeal is dismissed.")


@pytest.fixture
def store(tmp_path):
    s = Store(tmp_path / "t.duckdb")
    s.init()
    s.upsert("case", [dict(case_id="c1", source_sha256=SHA, forum="State Consumer Disputes Redressal Commission",
                           outcome="dismissed")], key=["case_id"])
    s.upsert("source", [dict(source_id="c1", url="u", publisher="p",
                             title="Care Health Insurance Limited vs Sawraj Tuli on 19 May, 2026",
                             doc_type="judgment", published_on=None, retrieved_at=None,
                             sha256=SHA, licence_note=None)], key=["source_id"])
    s.upsert("document_page", [dict(sha256=SHA, page_no=1, text=PAGE, char_count=len(PAGE),
                                    has_text_layer=True, image_path=None)], key=["sha256", "page_no"])
    card = RuleCard(rule_id="R_MORATORIUM", version=1, title_en="Moratorium", status="approved",
                    triggers=["pre_existing_disease", "non_disclosure"], in_force_from=date(2020, 10, 1))
    s.upsert("rule_card", [_to_row(card)], key=["rule_id", "version"])
    return s


def result(parsed=None, needs_review=False):
    return ChatResult(text=None, parsed=parsed, tool_calls=[], tokens_in=1, tokens_out=1,
                      cost_usd=0.0, cache_hit=False, needs_review=needs_review, backend="stub")


def stub(monkeypatch, outs):
    calls = []
    it = iter(outs)

    def fake(role, messages, **kw):
        calls.append((role, messages, kw))
        return next(it)
    monkeypatch.setattr(case_issues, "chat", fake)
    return calls


def good_out(**kw):
    base = dict(appellant="insurer", prevailed="for_policyholder",
                prevailed_quote="The appeal is dismissed.", prevailed_page_no=1,
                issues=[OutIssue(issue="R_MORATORIUM", holding="for_policyholder",
                                 quote="the moratorium of 60 months bars repudiation", page_no=1)])
    base.update(kw)
    return IssuesOut(**base)


def rows(store):
    return {r[0]: r for r in store.con.execute(
        "SELECT issue, holding, holding_quote, page_no, status, reviewer_note FROM case_issue "
        "WHERE case_id='c1'").fetchall()}


# ---------- schema ----------

def test_schema_has_new_columns_and_is_rerunnable(store):
    store.init()  # second run must be safe
    cols = {r[0] for r in store.con.execute("DESCRIBE \"case\"").fetchall()}
    assert {"appellant", "policyholder_prevailed"} <= cols
    icols = [r[0] for r in store.con.execute("DESCRIBE case_issue").fetchall()]
    assert icols == ["case_id", "issue", "holding", "holding_quote", "page_no", "status",
                     "reviewer_note"]
    assert Case(case_id="x").appellant is None
    assert CaseIssue(case_id="x", issue="i", holding="not_decided").status == "drafted"


def test_case_upsert_does_not_wipe_appellant(store):
    from sarthi.data import cases
    store.con.execute("UPDATE \"case\" SET appellant='insurer', policyholder_prevailed=TRUE")
    case, row = cases._upsert_case("c1", SHA, "text", "forum", None)
    store.upsert("case", [row], key=["case_id"])
    assert store.con.execute('SELECT appellant, policyholder_prevailed FROM "case"').fetchone() == \
        ("insurer", True)


# ---------- appellant backfill ----------

@pytest.mark.parametrize("title,forum,expected", [
    ("Care Health Insurance Limited vs Sawraj Tuli Son Of Sh Raman Kumar on 19 May, 2026",
     "State Consumer Disputes Redressal Commission", "insurer"),
    ("M/S Star Health And Allied Inurance ... vs Sonia Singh on 29 May, 2026",
     "State Consumer Disputes Redressal Commission", "insurer"),
    ("The Oriental Ins.Co.Ltd vs Vijiayan Ponnu Nadar on 10 May, 2023",
     "State Consumer Disputes Redressal Commission", "insurer"),
    ("Bharti Axa General Insurance Co. Ltd. vs Gursewak Singh on 25 February, 2026",
     "National Consumer Disputes Redressal", "insurer"),
    ("Care Health Insurance Ltd vs Manjula Haresh Joisar And Anr on 23 January, 2026",
     "Bombay High Court", "insurer"),
    ("Smt.Bhagwati vs National Insu.Co.Ltd. on 24 August, 2026",
     "State Consumer Disputes Redressal Commission", "unknown"),
    ("Anil Sharma vs Bhagat Multispecialty Hospital on 5 March, 2024",
     "State Consumer Disputes Redressal Commission", "unknown"),
    ("Max Bupa Health Insurance Co Limited vs Government Of Nct Delhi & Anr. on 6 May, 2021",
     "Delhi High Court", "unknown"),
    ("Star Health And Allied Insurance Co. Ltd vs J & K State Consumer Disputes Redressal on 24 May, 2022",
     "Jammu & Kashmir High Court", "unknown"),
    ("Care Health Insurance Limited vs Kamal Kumar on 9 October, 2024", "District Commission", "unknown"),
    (None, "Bombay High Court", "unknown"),
])
def test_infer_appellant(title, forum, expected):
    assert infer_appellant(title, forum) == expected


@pytest.mark.parametrize("appellant,outcome,expected", [
    ("insurer", "dismissed", True), ("insurer", "allowed", False), ("insurer", "partly_allowed", None),
    ("policyholder", "allowed", True), ("policyholder", "dismissed", False),
    ("policyholder", "partly_allowed", None), ("unknown", "allowed", None),
    ("insurer", None, None), (None, "allowed", None)])
def test_prevailed_from_outcome(appellant, outcome, expected):
    assert prevailed_from_outcome(appellant, outcome) is expected


def test_backfill_sets_and_counts_without_overriding_human(store):
    store.upsert("case", [dict(case_id="c2", source_sha256=None, forum="Bombay High Court",
                               outcome="allowed")], key=["case_id"])
    store.upsert("source", [dict(source_id="c2", url="u", publisher="p", title="Someone vs Star Health on 1 May, 2024",
                                 doc_type="judgment", published_on=None, retrieved_at=None,
                                 sha256=None, licence_note=None)], key=["source_id"])
    store.upsert("case", [dict(case_id="c3", source_sha256=None, forum="Bombay High Court",
                               outcome="dismissed", appellant="policyholder")], key=["case_id"])
    counts = backfill_appellant(store)
    assert counts == {"cases": 3, "appellant_inferred": 1, "appellant_unknown": 1,
                      "appellant_kept": 1, "prevailed_known": 2, "prevailed_unknown": 1}
    got = {r[0]: r[1:] for r in store.con.execute(
        'SELECT case_id, appellant, policyholder_prevailed FROM "case"').fetchall()}
    assert got["c1"] == ("insurer", True)
    assert got["c2"] == ("unknown", None)
    assert got["c3"] == ("policyholder", False)   # human value kept, prevailed derived from it
    assert backfill_appellant(store)["appellant_inferred"] == 0   # idempotent


def test_backfill_never_overwrites_known_prevailed(store):
    store.con.execute("UPDATE \"case\" SET policyholder_prevailed=FALSE WHERE case_id='c1'")
    backfill_appellant(store)
    assert store.con.execute("SELECT policyholder_prevailed FROM \"case\"").fetchone() == (False,)


# ---------- drafting ----------

def test_draft_verified_quote_is_drafted(store, monkeypatch):
    calls = stub(monkeypatch, [result(good_out())])
    out = draft_issues("c1", store)
    r = rows(store)
    assert r["R_MORATORIUM"][1:5] == ("for_policyholder",
                                      "the moratorium of 60 months bars repudiation", 1, "drafted")
    assert r[OVERALL][1] == "for_policyholder" and r[OVERALL][4] == "drafted"
    assert "model appellant: insurer" in r[OVERALL][5]
    assert {x.issue for x in out} == {"R_MORATORIUM", OVERALL}
    role, msgs, kw = calls[0]
    assert role == "reader" and kw["schema"] is IssuesOut and kw["cache"] is True
    prompt = msgs[0]["content"]
    assert "R_MORATORIUM" in prompt and "pre_existing_disease" in prompt
    assert "Reply with ONLY one JSON object" in prompt


def test_draft_quote_not_found_needs_review(store, monkeypatch):
    stub(monkeypatch, [result(good_out(issues=[OutIssue(
        issue="R_MORATORIUM", holding="for_insurer", quote="invented words", page_no=1)]))])
    draft_issues("c1", store)
    assert rows(store)["R_MORATORIUM"][4] == "needs_review"


def test_draft_holding_without_quote_needs_review_but_not_decided_ok(store, monkeypatch):
    stub(monkeypatch, [result(good_out(issues=[
        OutIssue(issue="R_MORATORIUM", holding="for_insurer", quote=None),
        OutIssue(issue="exclusion", holding="not_decided", quote=None)]))])
    draft_issues("c1", store)
    r = rows(store)
    assert r["R_MORATORIUM"][4] == "needs_review"
    assert r["exclusion"][1:5] == ("not_decided", None, None, "drafted")


def test_draft_drops_unknown_issue_keys(store, monkeypatch):
    stub(monkeypatch, [result(good_out(issues=[OutIssue(
        issue="made_up", holding="for_insurer", quote="the moratorium of 60 months bars repudiation")]))])
    draft_issues("c1", store)
    assert "made_up" not in rows(store)


def test_draft_unparsed_result_writes_nothing(store, monkeypatch):
    stub(monkeypatch, [result(None, needs_review=True)])
    assert draft_issues("c1", store) == []
    assert rows(store) == {}


def test_draft_does_not_overwrite_reviewed_unless_force(store, monkeypatch):
    stub(monkeypatch, [result(good_out())])
    draft_issues("c1", store)
    store.con.execute("UPDATE case_issue SET status='reviewed', holding='for_insurer' "
                      "WHERE issue='R_MORATORIUM'")
    stub(monkeypatch, [result(good_out())])
    draft_issues("c1", store)
    assert rows(store)["R_MORATORIUM"][1:5][0] == "for_insurer"
    assert rows(store)["R_MORATORIUM"][4] == "reviewed"
    stub(monkeypatch, [result(good_out())])
    draft_issues("c1", store, force=True)
    assert rows(store)["R_MORATORIUM"][1] == "for_policyholder"
    assert rows(store)["R_MORATORIUM"][4] == "drafted"


def test_draft_multi_window_prefers_verified_and_flags_conflict(store, monkeypatch):
    monkeypatch.setattr(case_issues, "make_windows", lambda pages: [([1], PAGE), ([1], PAGE)])
    a = good_out(issues=[OutIssue(issue="R_MORATORIUM", holding="for_policyholder",
                                  quote="the moratorium of 60 months bars repudiation")])
    b = good_out(issues=[OutIssue(issue="R_MORATORIUM", holding="for_insurer",
                                  quote="The appeal is dismissed.")])
    stub(monkeypatch, [result(a), result(b)])
    draft_issues("c1", store)
    r = rows(store)["R_MORATORIUM"]
    assert r[4] == "needs_review" and "conflict" in r[5]


# ---------- review ----------

def _drafted(store, monkeypatch):
    stub(monkeypatch, [result(good_out())])
    draft_issues("c1", store)


def test_review_accept_correct_reject(store, monkeypatch):
    _drafted(store, monkeypatch)
    store.upsert("case_issue", [dict(case_id="c1", issue="exclusion", holding="for_insurer",
                                     holding_quote="q", page_no=1, status="drafted", reviewer_note=None),
                                dict(case_id="c1", issue="deduction", holding="for_insurer",
                                     holding_quote="q", page_no=1, status="drafted", reviewer_note=None)],
                 key=["case_id", "issue"])
    review_issues("c1", {"R_MORATORIUM": IssueDecision(action="accept"),
                         "exclusion": IssueDecision(action="correct", holding="for_policyholder"),
                         "deduction": IssueDecision(action="reject", note="not about this")},
                  "parth", store)
    r = rows(store)
    assert r["R_MORATORIUM"][4] == "reviewed" and "accepted by parth" in r["R_MORATORIUM"][5]
    assert r["exclusion"][1] == "for_policyholder" and r["exclusion"][4] == "corrected"
    assert r["exclusion"][2] is None and r["exclusion"][3] is None   # quote cleared
    assert "was: for_insurer" in r["exclusion"][5]
    assert r["deduction"][4] == "rejected"


def test_review_correct_with_verbatim_quote_keeps_it(store, monkeypatch):
    _drafted(store, monkeypatch)
    review_issues("c1", {"R_MORATORIUM": IssueDecision(
        action="correct", holding="for_insurer", quote="The appeal is dismissed.")}, "p", store)
    assert rows(store)["R_MORATORIUM"][2] == "The appeal is dismissed."
    assert rows(store)["R_MORATORIUM"][3] == 1


def test_review_bad_batch_writes_nothing(store, monkeypatch):
    _drafted(store, monkeypatch)
    with pytest.raises(ValueError):
        review_issues("c1", {"R_MORATORIUM": IssueDecision(action="accept"),
                             OVERALL: IssueDecision(action="correct", holding="bogus")}, "p", store)
    assert rows(store)["R_MORATORIUM"][4] == "drafted"
    with pytest.raises(ValueError):
        review_issues("c1", {"R_MORATORIUM": IssueDecision(
            action="correct", holding="for_insurer", quote="not in the judgment")}, "p", store)
    with pytest.raises(KeyError):
        review_issues("c1", {"nope": IssueDecision(action="accept")}, "p", store)
    assert rows(store)["R_MORATORIUM"][4] == "drafted"


def test_review_accept_needs_quote_unless_not_decided(store, monkeypatch):
    stub(monkeypatch, [result(good_out(issues=[
        OutIssue(issue="R_MORATORIUM", holding="for_insurer", quote=None)]))])
    draft_issues("c1", store)
    with pytest.raises(ValueError, match="quote"):
        review_issues("c1", {"R_MORATORIUM": IssueDecision(action="accept")}, "p", store)


def test_review_overall_sets_policyholder_prevailed(store, monkeypatch):
    _drafted(store, monkeypatch)
    review_issues("c1", {OVERALL: IssueDecision(action="accept")}, "p", store)
    assert store.con.execute("SELECT policyholder_prevailed FROM \"case\"").fetchone() == (True,)
    review_issues("c1", {OVERALL: IssueDecision(action="correct", holding="for_insurer")}, "p", store)
    assert store.con.execute("SELECT policyholder_prevailed FROM \"case\"").fetchone() == (False,)


# ---------- review sheet ----------

def test_sheet_in_scope_first_and_contents(store, monkeypatch, tmp_path):
    _drafted(store, monkeypatch)
    store.upsert("case", [dict(case_id="c0", source_sha256=None, forum="X", outcome=None)],
                 key=["case_id"])
    store.upsert("case_issue", [dict(case_id="c0", issue="exclusion", holding="not_decided",
                                     holding_quote=None, page_no=None, status="drafted",
                                     reviewer_note=None)], key=["case_id", "issue"])
    backfill_appellant(store)
    store.upsert("case_fact", [dict(case_id="c1", field="claim_date", value=json.dumps("2023-01-05"),
                                    quote="q", page_no=1, confidence=1.0, status="extracted",
                                    reviewer_note=None)], key=["case_id", "field"])
    monkeypatch.setattr(case_issues, "approved_cards", lambda s: [RuleCard(
        rule_id="R", version=1, status="approved", quote="x", in_force_from=date(2020, 10, 1))])
    out = tmp_path / "sheet.md"
    write_review_sheet(store, out)
    t = out.read_text()
    assert t.index("c1") < t.index("c0")
    assert "Care Health Insurance Limited vs Sawraj Tuli" in t
    assert "Appealed by: insurer" in t
    assert "The appeal is dismissed." in t
    assert "R_MORATORIUM" in t and "for_policyholder" in t
    assert "the moratorium of 60 months bars repudiation" in t and "p.1" in t


# ---------- CLI ----------

def test_cli_registered():
    p = cli.build_parser()
    a = p.parse_args(["cases", "issues", "draft", "c1", "c2"])
    assert a.case_ids == ["c1", "c2"]
    assert p.parse_args(["cases", "issues", "draft", "--all"]).all is True
    assert p.parse_args(["cases", "issues", "review", "c1", "--json", "f.json"]).json == "f.json"
    assert p.parse_args(["cases", "issues", "sheet", "--out", "x.md"]).out.name == "x.md"
    a = p.parse_args(["cases", "set-appellant", "c1", "insurer"])
    assert (a.case_id, a.appellant) == ("c1", "insurer")
    assert p.parse_args(["cases", "backfill-appellant"]).cases_command == "backfill-appellant"


def test_cli_set_appellant_derives_prevailed(store, monkeypatch, capsys):
    monkeypatch.setattr(cli, "open_store", lambda: store)
    args = cli.build_parser().parse_args(["cases", "set-appellant", "c1", "insurer"])
    assert args.func(args) == 0
    assert store.con.execute('SELECT appellant, policyholder_prevailed FROM "case"').fetchone() == \
        ("insurer", True)
