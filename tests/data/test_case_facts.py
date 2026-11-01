import json
from datetime import date, datetime

import pytest

from sarthi.core.derive import FACT_KEYS
from sarthi.core.inputs import REJECTION_GROUNDS
from sarthi.core.store import Store
from sarthi.data import case_facts, cli
from sarthi.data.case_facts import (CaseFactsOut, ExtractedField, ReviewDecision,
                                    extract_case, load_reviewed_facts, review)
from sarthi.llm.client import ChatResult

SHA = "a" * 64
PAGE = ("The complainant took the policy on 05/01/2019. The insurer repudiated the claim "
        "for non-disclosure. A deduction of Rs. 2,45,000 was made towards consumables.")


@pytest.fixture
def store(tmp_path):
    s = Store(tmp_path / "bima_sarthi.duckdb")
    s.init()
    s.con.execute('INSERT INTO "case" (case_id, source_sha256, outcome) VALUES (?, ?, ?)',
                  ["c1", SHA, "partly_allowed"])
    s.upsert("document_page", [dict(sha256=SHA, page_no=1, text=PAGE, char_count=len(PAGE),
                                    has_text_layer=True, image_path=None)], key=["sha256", "page_no"])
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
    monkeypatch.setattr(case_facts, "chat", fake)
    return calls


def by_field(rows):
    return {r.field: r for r in rows}


def test_fields_match_fact_keys():
    assert set(CaseFactsOut.model_fields) == set(FACT_KEYS) - {"continuity_confirmed",
                                                               "cited_clause_found"}


def test_quote_present_gives_extracted(store, monkeypatch):
    out = CaseFactsOut(rejection_ground=ExtractedField(
        value="non_disclosure", quote="repudiated the claim for  non-disclosure", page_no=1))
    stub(monkeypatch, [result(out)])
    rows = by_field(extract_case("c1", store))
    r = rows["rejection_ground"]
    assert (r.status, r.confidence, r.value) == ("extracted", 1.0, json.dumps("non_disclosure"))
    assert len(rows) == 1  # null fields store nothing
    assert store.con.execute("SELECT status FROM case_fact").fetchall() == [("extracted",)]


def test_quote_absent_gives_needs_review(store, monkeypatch):
    out = CaseFactsOut(rejection_ground=ExtractedField(
        value="non_disclosure", quote="the insurer repudiated for concealment", page_no=1))
    stub(monkeypatch, [result(out)])
    r = by_field(extract_case("c1", store))["rejection_ground"]
    assert r.status == "needs_review"
    assert 0 < r.confidence < 1.0


def test_invalid_ground_needs_review(store, monkeypatch):
    out = CaseFactsOut(rejection_ground=ExtractedField(
        value="made_up", quote="repudiated the claim for non-disclosure", page_no=1))
    stub(monkeypatch, [result(out)])
    assert by_field(extract_case("c1", store))["rejection_ground"].status == "needs_review"
    assert "made_up" not in REJECTION_GROUNDS


def test_amount_and_date_parsed(store, monkeypatch):
    out = CaseFactsOut(
        inception_date=ExtractedField(value="05/01/2019", quote="took the policy on 05/01/2019", page_no=1),
        deductions=ExtractedField(value=[{"item": "consumables", "amount": "Rs. 2,45,000",
                                          "reason": "non_payable", "nonpayable_listed": True}],
                                  quote="A deduction of Rs. 2,45,000 was made", page_no=1))
    stub(monkeypatch, [result(out)])
    rows = by_field(extract_case("c1", store))
    assert json.loads(rows["inception_date"].value) == "2019-01-05"
    assert json.loads(rows["deductions"].value)[0]["amount"] == 245000
    assert rows["deductions"].status == "extracted"


def test_unparseable_date_needs_review(store, monkeypatch):
    out = CaseFactsOut(inception_date=ExtractedField(
        value="sometime in 2019", quote="took the policy on 05/01/2019", page_no=1))
    stub(monkeypatch, [result(out)])
    assert by_field(extract_case("c1", store))["inception_date"].status == "needs_review"


def test_failed_window_marks_needs_review_or_nothing(store, monkeypatch):
    out = CaseFactsOut(rejection_ground=ExtractedField(
        value="non_disclosure", quote="repudiated the claim for non-disclosure", page_no=1))
    stub(monkeypatch, [result(out, needs_review=True)])
    assert by_field(extract_case("c1", store))["rejection_ground"].status == "needs_review"
    stub(monkeypatch, [result(None)])
    extract_case("c1", store)  # parsed=None: nothing invented, previous row kept
    assert store.con.execute("SELECT count(*) FROM case_fact").fetchone()[0] == 1


def test_prompt_rules_and_no_outcome(store, monkeypatch):
    calls = stub(monkeypatch, [result(CaseFactsOut())])
    extract_case("c1", store)
    role, messages, kw = calls[0]
    text = " ".join(m["content"] for m in messages)
    assert role == "reader" and kw["schema"] is CaseFactsOut
    assert case_facts.SYSTEM_PROMPT in text
    for phrase in ("as stated", "not the parties' claims", "null", "verbatim", "never guess"):
        assert phrase in case_facts.SYSTEM_PROMPT.lower()
    assert "partly_allowed" not in text and "outcome" not in text.lower()


def test_windows_prefer_exact_quote(store, monkeypatch):
    big = "\n\n".join(f"Para {i} " + "word " * 2000 for i in range(8))  # ~80k chars -> several windows
    store.con.execute("UPDATE document_page SET text=? WHERE sha256=?", [big + "\n\n" + PAGE, SHA])
    wins = case_facts.make_windows([(1, big + "\n\n" + PAGE)])
    assert len(wins) > 1 and all(len(t) <= 12_000 * 4 for _, t in wins)
    outs = [result(CaseFactsOut(rejection_ground=ExtractedField(
        value="exclusion", quote="not in the text", page_no=1)))] + \
           [result(CaseFactsOut())] * (len(wins) - 2) + \
           [result(CaseFactsOut(rejection_ground=ExtractedField(
               value="non_disclosure", quote="repudiated the claim for non-disclosure", page_no=1)))]
    stub(monkeypatch, outs)
    r = by_field(extract_case("c1", store))["rejection_ground"]
    assert r.status == "extracted" and json.loads(r.value) == "non_disclosure"


def seed_fact(store, field, value, status="extracted"):
    store.upsert("case_fact", [dict(case_id="c1", field=field, value=json.dumps(value), quote="q",
                                    page_no=1, confidence=1.0, status=status, reviewer_note=None)],
                 key=["case_id", "field"])


def test_review_correct_records_both_values(store):
    seed_fact(store, "rejection_ground", "exclusion")
    review("c1", {"rejection_ground": ReviewDecision(action="correct", value="non_disclosure",
                                                     note="typo")}, "parth", store)
    row = store.con.execute("SELECT value, status, reviewer_note FROM case_fact").fetchone()
    assert json.loads(row[0]) == "non_disclosure" and row[1] == "corrected"
    assert 'was: "exclusion"' in row[2] and "typo" in row[2] and "parth" in row[2]


def test_review_accept_reject_and_unknown(store):
    seed_fact(store, "rejection_ground", "exclusion")
    seed_fact(store, "fraud_alleged", True)
    review("c1", {"rejection_ground": ReviewDecision(action="accept"),
                  "fraud_alleged": ReviewDecision(action="reject", note="no")}, "p", store)
    st = dict(store.con.execute("SELECT field, status FROM case_fact").fetchall())
    assert st == {"rejection_ground": "reviewed", "fraud_alleged": "rejected"}
    with pytest.raises(KeyError):
        review("c1", {"nope": ReviewDecision(action="accept")}, "p", store)


def test_load_reviewed_facts(store):
    seed_fact(store, "claim_date", "2024-05-02", "reviewed")
    seed_fact(store, "decision_at", "2024-05-02T10:30:00", "corrected")
    seed_fact(store, "fraud_alleged", False, "reviewed")
    seed_fact(store, "rejection_ground", "exclusion", "extracted")
    seed_fact(store, "cited_clause", "x", "rejected")
    f = load_reviewed_facts("c1", store)
    assert set(f) == {"claim_date", "decision_at", "fraud_alleged"}
    assert f["claim_date"].value == date(2024, 5, 2)
    assert f["decision_at"].value == datetime(2024, 5, 2, 10, 30)
    assert f["fraud_alleged"].value is False
    assert (f["claim_date"].status, f["claim_date"].confidence) == ("verified", "high")


def test_cli_extract(store, monkeypatch, tmp_path, capsys):
    monkeypatch.setenv("SARTHI_DATA_DIR", str(tmp_path))
    stub(monkeypatch, [result(CaseFactsOut(rejection_ground=ExtractedField(
        value="non_disclosure", quote="repudiated the claim for non-disclosure", page_no=1)))])
    store.con.close()
    assert cli.main(["cases", "extract", "--all-unextracted"]) == 0
    assert "c1" in capsys.readouterr().out


def _extract_ground(store, monkeypatch, value="non_disclosure"):
    stub(monkeypatch, [result(CaseFactsOut(
        rejection_ground=ExtractedField(value=value, quote="repudiated the claim for non-disclosure", page_no=1),
        cited_clause=ExtractedField(value="Clause 4", quote="took the policy on 05/01/2019", page_no=1)))])
    return by_field(extract_case("c1", store))


@pytest.mark.parametrize("status", ["reviewed", "corrected", "rejected"])
def test_reextract_keeps_human_review(store, monkeypatch, status):
    seed_fact(store, "rejection_ground", "exclusion", status)
    store.con.execute("UPDATE case_fact SET reviewer_note='n' WHERE field='rejection_ground'")
    rows = _extract_ground(store, monkeypatch)
    assert "rejection_ground" not in rows and "cited_clause" in rows
    assert store.con.execute("SELECT value, status, reviewer_note FROM case_fact "
                             "WHERE field='rejection_ground'").fetchone() == (json.dumps("exclusion"), status, "n")


def test_force_overwrites_review(store, monkeypatch):
    seed_fact(store, "rejection_ground", "exclusion", "reviewed")
    stub(monkeypatch, [result(CaseFactsOut(rejection_ground=ExtractedField(
        value="non_disclosure", quote="repudiated the claim for non-disclosure", page_no=1)))])
    extract_case("c1", store, force=True)
    assert store.con.execute("SELECT value, status FROM case_fact").fetchone() == (
        json.dumps("non_disclosure"), "extracted")


def test_page_no_comes_from_window_pages(store, monkeypatch):
    q = "the insurer repudiated the claim"
    pad = "filler " * 6000  # ~42k chars: forces page 3 into its own window
    store.con.execute("DELETE FROM document_page")
    store.upsert("document_page", [
        dict(sha256=SHA, page_no=1, text=f"{q} early. " + pad, char_count=1, has_text_layer=True, image_path=None),
        dict(sha256=SHA, page_no=2, text=pad, char_count=1, has_text_layer=True, image_path=None),
        dict(sha256=SHA, page_no=3, text=f"Last page: {q} again.", char_count=1, has_text_layer=True,
             image_path=None)], key=["sha256", "page_no"])
    wins = case_facts.make_windows([(1, f"{q} early. " + pad), (2, pad), (3, f"Last page: {q} again.")])
    assert wins[-1][0] == [3] or wins[-1][0][-1] == 3 and 1 not in wins[-1][0]
    outs = [result(CaseFactsOut())] * (len(wins) - 1) + [result(CaseFactsOut(
        rejection_ground=ExtractedField(value="exclusion", quote=q, page_no=1)))]
    stub(monkeypatch, outs)
    assert by_field(extract_case("c1", store))["rejection_ground"].page_no == 3


def test_quote_spanning_pages_never_full_confidence(store, monkeypatch):
    store.con.execute("DELETE FROM document_page")
    store.upsert("document_page", [
        dict(sha256=SHA, page_no=1, text="The claim was repudiated for", char_count=1,
             has_text_layer=True, image_path=None),
        dict(sha256=SHA, page_no=2, text="non-disclosure of diabetes.", char_count=1,
             has_text_layer=True, image_path=None)], key=["sha256", "page_no"])
    stub(monkeypatch, [result(CaseFactsOut(rejection_ground=ExtractedField(
        value="non_disclosure", quote="repudiated for non-disclosure", page_no=9)))])
    r = by_field(extract_case("c1", store))["rejection_ground"]
    assert r.page_no == 1 and r.confidence <= 0.99


# ---------- C1: the schema reaches the model, off-shape replies are rejected ----------

def test_schemas_forbid_extra_keys():
    from pydantic import ValidationError
    with pytest.raises(ValidationError):
        CaseFactsOut.model_validate({"rejection_grounds": {"value": "exclusion"}})
    with pytest.raises(ValidationError):
        ExtractedField.model_validate({"value": "x", "quotes": "y"})


def test_off_shape_deduction_items_are_rejected():
    from pydantic import ValidationError
    with pytest.raises(ValidationError):
        ExtractedField.model_validate({"value": [{"thing": "x", "cost": 5}]})
    ok = ExtractedField.model_validate({"value": [{"item": "gloves", "amount": "Rs. 50",
                                                    "reason": "non_payable", "nonpayable_listed": True}]})
    assert ok.value[0].item == "gloves"


def test_prompt_names_every_field_and_the_shape():
    hint = case_facts.schema_hint(CaseFactsOut)
    for field in CaseFactsOut.model_fields:
        assert field in hint
    assert "value" in hint and "quote" in hint and "page_no" in hint
    assert hint in case_facts.SYSTEM_PROMPT


# ---------- C2 / I1: review form for every fact, shared by the DAG and the CLI ----------

def seed_other_case(store, case_id="c2"):
    store.con.execute('INSERT INTO "case" (case_id, source_sha256, outcome) VALUES (?, ?, ?)',
                      [case_id, SHA, "allowed"])
    store.upsert("case_fact", [dict(case_id=case_id, field="claim_date", value=json.dumps("2024-05-02"),
                                    quote="q", page_no=1, confidence=1.0, status="extracted",
                                    reviewer_note=None)], key=["case_id", "field"])


def test_review_form_lists_every_fact_and_defaults_extracted_to_accept(store):
    seed_fact(store, "rejection_ground", "exclusion", "extracted")
    seed_fact(store, "fraud_alleged", True, "needs_review")
    form = case_facts.build_review_form("c1", store)
    assert {f["field"] for f in form["fields"]} == {"rejection_ground", "fraud_alleged"}
    by = {f["field"]: f for f in form["fields"]}
    assert by["rejection_ground"]["default"] == {"action": "accept", "value": "exclusion", "note": ""}
    assert by["fraud_alleged"]["default"] is None and by["fraud_alleged"]["status"] == "needs_review"
    assert "rejection_ground" in form["body"] and "fraud_alleged" in form["body"]


def test_review_form_none_for_case_without_facts(store):
    assert case_facts.build_review_form("c1", store) is None


def test_clean_case_gets_reviewed_facts_after_empty_decisions(store):
    seed_fact(store, "claim_date", "2024-05-02", "extracted")
    seed_fact(store, "fraud_alleged", True, "needs_review")
    n = case_facts.apply_review_form("c1", {}, "parth", store)
    assert n == 1
    st = dict(store.con.execute("SELECT field, status FROM case_fact").fetchall())
    assert st == {"claim_date": "reviewed", "fraud_alleged": "needs_review"}
    assert set(load_reviewed_facts("c1", store)) == {"claim_date"}


def test_explicit_decision_overrides_default(store):
    seed_fact(store, "claim_date", "2024-05-02", "extracted")
    case_facts.apply_review_form("c1", {"claim_date": {"action": "correct", "value": "2024-05-03"}},
                                 "parth", store)
    assert store.con.execute("SELECT status FROM case_fact").fetchone() == ("corrected",)


def test_apply_review_forms_isolates_a_bad_entry(store, caplog):
    seed_fact(store, "claim_date", "2024-05-02", "extracted")
    seed_other_case(store, "c2")
    forms = [{"case_id": "c1"}, {"case_id": "c2"}]
    responses = [{"params_input": {"decisions": '{"claim_date": {"action": "explode"}}'}},
                 {"params_input": {"decisions": "{}"}, "responded_by_user": {"name": "p"}}]
    with caplog.at_level("WARNING"):
        n = case_facts.apply_review_forms(forms, responses, store)
    assert n == 1
    st = dict(store.con.execute("SELECT case_id, status FROM case_fact").fetchall())
    assert st == {"c1": "extracted", "c2": "reviewed"}
    assert "c1" in caplog.text


# ---- I12: review validation, quote cleared on correction, tolerant loads ----

def test_correct_with_bad_value_names_the_field_and_writes_nothing(store):
    seed_fact(store, "claim_date", "2024-05-02", "extracted")
    seed_fact(store, "rejection_ground", "exclusion", "extracted")
    with pytest.raises(ValueError, match="claim_date"):
        review("c1", {"rejection_ground": ReviewDecision(action="accept"),
                      "claim_date": ReviewDecision(action="correct", value="not a date")}, "p", store)
    rows = store.con.execute("SELECT field, value, status FROM case_fact ORDER BY field").fetchall()
    assert rows == [("claim_date", '"2024-05-02"', "extracted"),
                    ("rejection_ground", '"exclusion"', "extracted")]


def test_correct_stores_the_parsed_value(store):
    seed_fact(store, "claim_date", "2024-05-02", "extracted")
    review("c1", {"claim_date": ReviewDecision(action="correct", value="03/05/2024")}, "p", store)
    assert json.loads(store.con.execute("SELECT value FROM case_fact").fetchone()[0]) == "2024-05-03"


def test_correct_clears_old_quote_and_page_and_says_so(store):
    seed_fact(store, "rejection_ground", "exclusion", "extracted")
    review("c1", {"rejection_ground": ReviewDecision(action="correct", value="non_disclosure")}, "p", store)
    quote, page, note = store.con.execute("SELECT quote, page_no, reviewer_note FROM case_fact").fetchone()
    assert quote is None and page is None and "quote cleared on correction" in note
    assert load_reviewed_facts("c1", store)["rejection_ground"].quote is None


def test_accept_keeps_quote(store):
    seed_fact(store, "rejection_ground", "exclusion", "extracted")
    review("c1", {"rejection_ground": ReviewDecision(action="accept")}, "p", store)
    assert store.con.execute("SELECT quote, page_no FROM case_fact").fetchone() == ("q", 1)


def test_load_reviewed_facts_skips_and_logs_undecodable_value(store, caplog):
    seed_fact(store, "claim_date", "2024-05-02", "reviewed")
    store.con.execute("UPDATE case_fact SET value='{not json' WHERE field='claim_date'")
    seed_fact(store, "decision_at", "garbage", "reviewed")
    seed_fact(store, "fraud_alleged", False, "reviewed")
    with caplog.at_level("WARNING"):
        f = load_reviewed_facts("c1", store)
    assert set(f) == {"fraud_alleged"}
    assert "claim_date" in caplog.text and "decision_at" in caplog.text


def test_review_form_survives_a_corrupt_stored_value(store):
    seed_fact(store, "claim_date", "2024-05-02", "extracted")
    store.con.execute("UPDATE case_fact SET value='{not json'")
    seed_fact(store, "fraud_alleged", True, "extracted")
    form = case_facts.build_review_form("c1", store)
    by = {f["field"]: f for f in form["fields"]}
    assert by["claim_date"]["default"] is None  # not auto-accepted: stays flagged for a human
    assert by["fraud_alleged"]["default"]["action"] == "accept"


def test_parse_field_accepts_iso_dates_and_rejects_impossible_ones():
    assert case_facts.parse_field("claim_date", "2024-05-03") == ("2024-05-03", True)
    assert case_facts.parse_field("claim_date", "2024-13-45")[1] is False
