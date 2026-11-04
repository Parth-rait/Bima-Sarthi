"""Delegated bulk acceptance: only extracted facts whose quote is verbatim in the stored judgment."""
import json

import pytest

from sarthi.core.store import Store
from sarthi.data import case_facts

SHA = "c" * 64
PAGE1 = "The policy ran from 25.12.2021 to 24.12.2022.   The complainant was admitted on 30.01.2023."
PAGE2 = "The insurer rejected the claim under the waiting period exclusion."
NOTE = "bulk-accepted on Parth's delegation (exact quote only)"


@pytest.fixture
def store(tmp_path):
    s = Store(tmp_path / "t.duckdb")
    s.init()
    s.upsert("case", [dict(case_id="c1", source_sha256=SHA)], key=["case_id"])
    s.upsert("case", [dict(case_id="c2", source_sha256=SHA)], key=["case_id"])
    s.upsert("document_page", [dict(sha256=SHA, page_no=1, text=PAGE1, char_count=1, has_text_layer=True,
                                    image_path=None),
                               dict(sha256=SHA, page_no=2, text=PAGE2, char_count=1, has_text_layer=True,
                                    image_path=None)], key=["sha256", "page_no"])
    return s


def put(store, cid, field, value, quote, status="extracted"):
    store.upsert("case_fact", [dict(case_id=cid, field=field, value=json.dumps(value), quote=quote,
                                    page_no=1, confidence=1.0, status=status, reviewer_note=None)],
                 key=["case_id", "field"])


def status(store, cid, field):
    return store.con.execute("SELECT status, reviewer_note FROM case_fact WHERE case_id=? AND field=?",
                             [cid, field]).fetchone()


def test_accepts_extracted_fact_with_verbatim_quote_whitespace_insensitive(store):
    put(store, "c1", "inception_date", "2021-12-25", "from 25.12.2021 to 24.12.2022.  The complainant")
    r = case_facts.accept_exact_quote_facts(store, ["c1"])
    assert status(store, "c1", "inception_date") == ("reviewed", NOTE)
    assert r["c1"].accepted == ["inception_date"] and r["c1"].unresolved == []


def test_quote_must_be_found_verbatim(store):
    put(store, "c1", "cited_clause", "Excl 02", "a sentence that is not in the judgment")
    put(store, "c1", "rejection_ground", "exclusion", "")
    put(store, "c1", "claim_date", "2023-01-30", None)
    r = case_facts.accept_exact_quote_facts(store, ["c1"])
    assert r["c1"].accepted == []
    assert {f for f, _ in r["c1"].unresolved} == {"cited_clause", "rejection_ground", "claim_date"}
    assert status(store, "c1", "cited_clause")[0] == "extracted"


@pytest.mark.parametrize("field", ["fraud_alleged", "crc_approval_mentioned", "reasons_cite_terms",
                                   "cited_clause_found", "continuity_confirmed", "nonpayable_listed"])
def test_yes_no_fields_are_never_accepted(store, field):
    put(store, "c1", field, True, "waiting period exclusion")
    r = case_facts.accept_exact_quote_facts(store, ["c1"])
    assert r["c1"].accepted == [] and status(store, "c1", field)[0] == "extracted"


def test_deductions_with_a_yes_no_listing_judgement_are_not_accepted(store):
    put(store, "c1", "deductions", [{"item": "x", "amount": 5, "reason": "non_payable",
                                     "nonpayable_listed": False}], "waiting period exclusion")
    r = case_facts.accept_exact_quote_facts(store, ["c1"])
    assert r["c1"].accepted == [] and status(store, "c1", "deductions")[0] == "extracted"


def test_date_fields_must_hold_an_iso_date_not_a_raw_string(store):
    put(store, "c1", "claim_date", "30.01.2023", "admitted on 30.01.2023")
    put(store, "c1", "admission_date", "2023-01-30", "admitted on 30.01.2023")
    put(store, "c1", "ported_from_date", "2014", "waiting period exclusion")
    r = case_facts.accept_exact_quote_facts(store, ["c1"])
    assert r["c1"].accepted == ["admission_date"]
    assert {f for f, _ in r["c1"].unresolved} == {"claim_date", "ported_from_date"}


def test_datetime_fields_must_be_iso_datetimes(store):
    put(store, "c1", "decision_at", "04.12.2024", "waiting period exclusion")
    put(store, "c1", "cashless_request_at", "2024-12-04T10:00:00", "waiting period exclusion")
    r = case_facts.accept_exact_quote_facts(store, ["c1"])
    assert r["c1"].accepted == ["cashless_request_at"]


def test_only_extracted_rows_change_and_other_statuses_are_untouched(store):
    put(store, "c1", "cited_clause", "Excl 02", "waiting period exclusion", status="needs_review")
    put(store, "c1", "rejection_ground", "exclusion", "waiting period exclusion", status="rejected")
    put(store, "c1", "inception_date", "2021-12-25", "25.12.2021", status="corrected")
    case_facts.accept_exact_quote_facts(store, ["c1"])
    assert [status(store, "c1", f)[0] for f in ("cited_clause", "rejection_ground", "inception_date")] == \
        ["needs_review", "rejected", "corrected"]


def test_only_the_named_cases_are_touched_and_it_is_idempotent(store):
    put(store, "c1", "cited_clause", "Excl 02", "waiting period exclusion")
    put(store, "c2", "cited_clause", "Excl 02", "waiting period exclusion")
    case_facts.accept_exact_quote_facts(store, ["c1"])
    assert status(store, "c1", "cited_clause")[0] == "reviewed"
    assert status(store, "c2", "cited_clause")[0] == "extracted"
    r = case_facts.accept_exact_quote_facts(store, ["c1"])
    assert r["c1"].accepted == []  # nothing left to accept


def test_holdings_are_never_touched(store):
    store.upsert("case_issue", [dict(case_id="c1", issue="X", holding="for_insurer", holding_quote="q",
                                     page_no=1, status="drafted", reviewer_note=None)],
                 key=["case_id", "issue"])
    put(store, "c1", "cited_clause", "Excl 02", "waiting period exclusion")
    case_facts.accept_exact_quote_facts(store, ["c1"])
    assert store.con.execute("SELECT status, holding FROM case_issue").fetchone() == ("drafted", "for_insurer")


def test_report_flags_a_date_the_quote_does_not_itself_state(store):
    put(store, "c1", "policy_renewal_date", "2022-12-29", "waiting period exclusion")
    put(store, "c1", "inception_date", "2021-12-25", "from 25.12.2021 to 24.12.2022")
    r = case_facts.accept_exact_quote_facts(store, ["c1"])
    assert r["c1"].accepted == ["policy_renewal_date", "inception_date"] or \
        set(r["c1"].accepted) == {"policy_renewal_date", "inception_date"}
    assert r["c1"].quote_lacks_value == ["policy_renewal_date"]
