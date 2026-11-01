import json

import pytest

from sarthi.core.store import Store
from sarthi.data import case_dates
from sarthi.data.case_dates import find_dates, propose_date, recover_dates

SHA = "c" * 64


def test_find_dates_accepts_numeric_and_written_forms():
    t = "On 12.03.2021 and 13/04/2021 and 2nd August, 2017 and 5 May 2019 and May 6, 2020."
    got = {(f, d.isoformat()) for f, d, _, _ in find_dates(t)}
    assert got == {("12.03.2021", "2021-03-12"), ("13/04/2021", "2021-04-13"),
                   ("2nd August, 2017", "2017-08-02"), ("5 May 2019", "2019-05-05"),
                   ("May 6, 2020", "2020-05-06")}


def test_find_dates_two_digit_year_is_day_first_20xx_and_noted():
    [(form, d, start, note)] = find_dates("admitted on 05.07.21 to hospital")
    assert (form, d.isoformat()) == ("05.07.21", "2021-07-05")
    assert "day-first" in note and "20xx" in note


def test_find_dates_rejects_impossible_dates_and_amounts():
    assert find_dates("on 31.02.2021 or 13.13.2021 or Rs. 1,50,000.00") == []


def test_four_digit_dates_have_no_two_digit_note():
    [(_, _, _, note)] = find_dates("admitted on 05.07.2021")
    assert note == ""


@pytest.mark.parametrize("text,field,iso", [
    ("The complainant was admitted to the hospital on 12.03.2021 with chest pain.",
     "admission_date", "2021-03-12"),
    ("Date of admission: 4th January, 2022.", "admission_date", "2022-01-04"),
    ("The claim was lodged with the insurer on 14/07/2021.", "claim_date", "2021-07-14"),
])
def test_propose_date_finds_admission_or_claim_with_verbatim_quote(text, field, iso):
    c = propose_date([(3, text)])
    assert c is not None
    assert (c.field, c.iso, c.page_no) == (field, iso, 3)
    assert c.form in c.quote and c.quote in text


@pytest.mark.parametrize("text", [
    "The complaint was filed on 12.03.2021 claiming the amount.",
    "Complaint admitted on 12.03.2021 and notice issued.",  # forum 'admitted' the complaint
    "Order dated 12.03.2021 passed by the State Commission is impugned.",
    "The insurer repudiated the claim on 12.03.2021.",
    "The patient was discharged on 12.03.2021.",
    "The policy period was from 01.04.2020 to 31.03.2021.",
    "Judgment reserved on 12.03.2021 and pronounced on 5.4.2021.",
    "He was born on 12.03.1960.",
    "It is an admitted fact that the husband took a policy on 23.03.2004.",
    "Hospitalisation scheme was introduced as per Joint Note dated 25.05.2015.",
    "Hospitals were asked to submit the pending claim details within 25.1.2019.",
])
def test_propose_date_refuses_filing_order_repudiation_discharge_policy_dates(text):
    assert propose_date([(1, text)]) is None


def test_propose_date_takes_the_admission_not_the_later_filing_date_in_one_sentence():
    t = "The insured was admitted on 12.03.2021 and the complaint was filed on 05.05.2022."
    c = propose_date([(1, t)])
    assert c.iso == "2021-03-12" and c.field == "admission_date"


def test_two_digit_year_candidate_carries_note_into_reviewer_note():
    c = propose_date([(2, "The insured was hospitalised on 05.07.21 for dengue.")])
    assert c.iso == "2021-07-05" and "day-first" in c.note


# ---------- store integration ----------

@pytest.fixture
def store(tmp_path):
    s = Store(tmp_path / "t.duckdb")
    s.init()
    return s


def add_case(store, cid, text, sha=None):
    sha = sha or (cid[-1] * 64)
    store.upsert("case", [dict(case_id=cid, source_sha256=sha, forum="X", outcome=None)], key=["case_id"])
    store.upsert("document_page", [dict(sha256=sha, page_no=1, text=text, char_count=len(text),
                                        has_text_layer=True, image_path=None)], key=["sha256", "page_no"])


def facts(store, cid):
    return store.con.execute("SELECT field, value, quote, page_no, status, reviewer_note FROM case_fact "
                             "WHERE case_id=?", [cid]).fetchall()


def test_recover_dates_records_needs_review_fact_with_quote_page_and_note(store):
    add_case(store, "c1", "The insured was hospitalised on 05.07.21 for dengue.")
    out = recover_dates(["c1"], store)
    assert out == {"c1": "admission_date"}
    [(field, value, quote, page, status, note)] = facts(store, "c1")
    assert (field, json.loads(value), page, status) == ("admission_date", "2021-07-05", 1, "needs_review")
    assert "05.07.21" in quote and "day-first" in note and "20xx" in note
    assert "recovered" in note and "not reviewed" in note


def test_recover_dates_skips_cases_that_already_have_a_date_fact_even_flagged(store):
    add_case(store, "c1", "The insured was admitted on 05.07.2021.")
    store.upsert("case_fact", [dict(case_id="c1", field="claim_date", value=json.dumps("2021-08-01"),
                                    quote="q", page_no=1, confidence=0.5, status="needs_review",
                                    reviewer_note=None)], key=["case_id", "field"])
    assert recover_dates(["c1"], store) == {}
    assert [f[0] for f in facts(store, "c1")] == ["claim_date"]


def test_recover_dates_nothing_found_writes_nothing(store):
    add_case(store, "c1", "The complaint was filed on 05.07.2021.")
    assert recover_dates(["c1"], store) == {}
    assert facts(store, "c1") == []


def test_flagged_section_lists_in_scope_case_dates_and_flagged_facts(store):
    add_case(store, "c1", "The insured was admitted on 05.07.2021.")
    recover_dates(["c1"], store)
    store.upsert("case_fact", [dict(case_id="c1", field="rejection_ground", value=json.dumps("other"),
                                    quote="q", page_no=1, confidence=0.1, status="needs_review",
                                    reviewer_note=None)], key=["case_id", "field"])
    text = case_dates.flagged_section(store, ["c1"])
    assert "c1" in text and "2021-07-05" in text and "admission_date" in text
    assert "rejection_ground" in text and "needs_review" in text
