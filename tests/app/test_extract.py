import json
import logging
from datetime import date, datetime

import pymupdf
import pytest

from sarthi.app import extract
from sarthi.app.extract import eval_reading, extract_user_facts, ready_for_rules
from sarthi.app.session import Session
from sarthi.core.models import FactValue, RuleCard
from sarthi.data.case_facts import CaseFactsOut, ExtractedField
from sarthi.llm.client import ChatResult

QUOTE = "claim repudiated for non-disclosure of diabetes"
DATE_QUOTE = "Policy inception 05 January 2019"


@pytest.fixture(autouse=True)
def dirs(tmp_path, monkeypatch):
    monkeypatch.setenv("SARTHI_SESSION_ROOT", str(tmp_path / "sessions"))
    monkeypatch.setenv("SARTHI_DATA_DIR", str(tmp_path / "data"))
    return tmp_path


def pdf_bytes(*texts):
    doc = pymupdf.open()
    for t in texts:
        doc.new_page().insert_text((72, 72), t)
    return doc.tobytes()


def png_bytes():
    pix = pymupdf.Pixmap(pymupdf.csRGB, pymupdf.IRect(0, 0, 800, 600), False)
    pix.clear_with(255)
    return pix.tobytes("png")


def res(parsed=None, text=None, needs_review=False):
    return ChatResult(text=text, parsed=parsed, tool_calls=[], tokens_in=1, tokens_out=1,
                      cost_usd=0.0, cache_hit=False, needs_review=needs_review, backend="stub")


def ef(value, quote, page_no=1):
    return ExtractedField(value=value, quote=quote, page_no=page_no)


class Stub:
    """Reader stub: `facts` are CaseFactsOut per page call, `transcripts` per transcription call."""
    def __init__(self, monkeypatch, facts, transcripts=(), needs_review=False):
        self.facts, self.transcripts = iter(facts), iter(transcripts)
        self.needs_review, self.calls = needs_review, []
        monkeypatch.setattr(extract, "chat", self)

    def __call__(self, role, messages, **kw):
        self.calls.append((role, kw))
        if kw.get("schema") is not None:
            return res(next(self.facts), needs_review=self.needs_review)
        return res(text=next(self.transcripts))


def pdf_session(*texts):
    s = Session.create()
    s.add_upload(("a.pdf", pdf_bytes(*texts)))
    return s


def photo_session():
    s = Session.create()
    s.add_upload(("a.png", png_bytes()))
    return s


def test_text_layer_exact_quote_is_verified(monkeypatch):
    s = pdf_session(QUOTE)
    Stub(monkeypatch, [CaseFactsOut(rejection_ground=ef("non_disclosure", QUOTE))])
    f = extract_user_facts(s)["rejection_ground"]
    assert (f.status, f.confidence, f.value, f.page_no) == ("verified", "high", "non_disclosure", 1)


def test_photo_transcription_fuzzy_match_verified_medium_or_high(monkeypatch):
    s = photo_session()
    stub = Stub(monkeypatch, [CaseFactsOut(rejection_ground=ef("non_disclosure", QUOTE))],
                [f"Dear sir, {QUOTE}, regards"])
    f = extract_user_facts(s)["rejection_ground"]
    assert f.status == "verified" and f.confidence == "high"
    assert [kw.get("schema") is not None for _, kw in stub.calls] == [True, False]


def test_low_confidence_needs_confirmation(monkeypatch):
    s = photo_session()
    Stub(monkeypatch, [CaseFactsOut(rejection_ground=ef("non_disclosure", QUOTE))],
         ["completely different words about something else entirely"])
    f = extract_user_facts(s)["rejection_ground"]
    assert f.status == "needs_confirmation" and f.confidence == "low"


def test_quote_missing_from_text_layer_needs_confirmation(monkeypatch):
    s = pdf_session("some unrelated text")
    Stub(monkeypatch, [CaseFactsOut(rejection_ground=ef("non_disclosure", QUOTE))])
    assert extract_user_facts(s)["rejection_ground"].status == "needs_confirmation"


def test_ambiguous_date_needs_confirmation(monkeypatch):
    s = photo_session()
    q = "Inception 03/04/2021"
    Stub(monkeypatch, [CaseFactsOut(inception_date=ef("03/04/2021", q))], [q])
    f = extract_user_facts(s)["inception_date"]
    assert f.status == "needs_confirmation" and f.value == date(2021, 4, 3)


def test_unambiguous_date_in_text_pdf_is_verified(monkeypatch):
    s = pdf_session(DATE_QUOTE)
    Stub(monkeypatch, [CaseFactsOut(inception_date=ef("05 January 2019", DATE_QUOTE))])
    f = extract_user_facts(s)["inception_date"]
    assert f.status == "verified" and f.value == date(2019, 1, 5)


def test_unparseable_value_needs_confirmation(monkeypatch):
    s = pdf_session(DATE_QUOTE)
    Stub(monkeypatch, [CaseFactsOut(inception_date=ef("sometime in 2019", DATE_QUOTE))])
    assert extract_user_facts(s)["inception_date"].status == "needs_confirmation"


def test_model_needs_review_flag_needs_confirmation(monkeypatch):
    s = pdf_session(QUOTE)
    Stub(monkeypatch, [CaseFactsOut(rejection_ground=ef("non_disclosure", QUOTE))], needs_review=True)
    assert extract_user_facts(s)["rejection_ground"].status == "needs_confirmation"


def test_null_fields_are_absent(monkeypatch):
    s = pdf_session(QUOTE)
    Stub(monkeypatch, [CaseFactsOut(fraud_alleged=ExtractedField())])
    assert extract_user_facts(s) == {}


def test_merge_prefers_verified_over_unverified(monkeypatch):
    s = pdf_session("page one text", QUOTE + " and Inception 06 January 2019")
    Stub(monkeypatch, [
        CaseFactsOut(rejection_ground=ef("pre_existing_disease", "not on page"),
                     inception_date=ef("05 January 2019", "Inception 05 January 2019")),
        CaseFactsOut(rejection_ground=ef("non_disclosure", QUOTE, 2),
                     inception_date=ef("06 January 2019", "Inception 06 January 2019", 2))])
    facts = extract_user_facts(s)
    assert facts["rejection_ground"].status == "verified"
    assert facts["rejection_ground"].value == "non_disclosure"
    assert facts["inception_date"].value == date(2019, 1, 6)
    assert facts["inception_date"].status == "verified"


def test_value_contradicting_its_quote_needs_confirmation(monkeypatch):
    q = "Policy inception 05 January 2019"
    s = pdf_session(q)
    Stub(monkeypatch, [CaseFactsOut(inception_date=ef("06 January 2019", q))])
    assert extract_user_facts(s)["inception_date"].status == "needs_confirmation"


def test_datetime_time_must_match_quote(monkeypatch):
    q = "Decision on 04 May 2024 at 10:30"
    s = pdf_session(q)
    Stub(monkeypatch, [CaseFactsOut(decision_at=ef("04 May 2024 11:30", q))])
    assert extract_user_facts(s)["decision_at"].status == "needs_confirmation"


def test_photo_datetime_with_ambiguous_date_needs_confirmation(monkeypatch):
    q = "Decision at 04/05/2024 10:30"
    s = photo_session()
    Stub(monkeypatch, [CaseFactsOut(decision_at=ef("04/05/2024 10:30", q))], [q])
    f = extract_user_facts(s)["decision_at"]
    assert f.status == "needs_confirmation" and f.value == datetime(2024, 5, 4, 10, 30)


def test_text_pdf_datetime_is_verified(monkeypatch):
    q = "Decision at 04/05/2024 10:30"
    s = pdf_session(q)
    Stub(monkeypatch, [CaseFactsOut(decision_at=ef("04/05/2024 10:30", q))])
    f = extract_user_facts(s)["decision_at"]
    assert f.status == "verified" and f.value == datetime(2024, 5, 4, 10, 30)


def test_deduction_amount_must_appear_in_quote(monkeypatch):
    q = "Consumables Rs. 2,45,000 deducted"
    s = pdf_session(q)
    good = [{"item": "consumables", "amount": "Rs. 2,45,000", "reason": "non_payable",
             "nonpayable_listed": False}]
    bad = [{"item": "consumables", "amount": "Rs. 3,45,000", "reason": "non_payable",
            "nonpayable_listed": False}]
    Stub(monkeypatch, [CaseFactsOut(deductions=ef(good, q))])
    assert extract_user_facts(s)["deductions"].status == "needs_confirmation"  # I13: listing is the user's call
    s2 = pdf_session(q)
    Stub(monkeypatch, [CaseFactsOut(deductions=ef(bad, q))])
    assert extract_user_facts(s2)["deductions"].status == "needs_confirmation"


def test_string_value_must_be_contained_in_quote(monkeypatch):
    s = pdf_session("as per Clause 4.1 of the policy")
    Stub(monkeypatch, [CaseFactsOut(cited_clause=ef("Clause 9", "as per Clause 4.1 of the policy"))])
    assert extract_user_facts(s)["cited_clause"].status == "needs_confirmation"


def test_conflicting_verified_values_need_confirmation(monkeypatch):
    s = pdf_session("Inception 05 January 2019", "Inception 06 January 2019")
    Stub(monkeypatch, [
        CaseFactsOut(inception_date=ef("05 January 2019", "Inception 05 January 2019")),
        CaseFactsOut(inception_date=ef("06 January 2019", "Inception 06 January 2019", 2))])
    f = extract_user_facts(s)["inception_date"]
    assert f.status == "needs_confirmation" and f.value == date(2019, 1, 5)


def test_cache_disabled_for_user_sessions(monkeypatch, dirs):
    s = photo_session()
    stub = Stub(monkeypatch, [CaseFactsOut(rejection_ground=ef("non_disclosure", QUOTE))], [QUOTE])
    extract_user_facts(s)
    assert stub.calls and all(role == "reader" and kw.get("cache") is False
                              for role, kw in stub.calls)
    assert not list((dirs / "data").rglob("*.json")) if (dirs / "data").exists() else True


def test_no_content_in_logs(monkeypatch, caplog):
    s = pdf_session(QUOTE)
    Stub(monkeypatch, [CaseFactsOut(rejection_ground=ef("non_disclosure", QUOTE))])
    with caplog.at_level(logging.DEBUG):
        extract_user_facts(s)
    assert "non-disclosure" not in caplog.text and "diabetes" not in caplog.text


# ---- ready_for_rules ----

def fv(value, status="verified"):
    return FactValue(value=value, status=status)


def card(condition, triggers=("non_disclosure",)):
    return RuleCard(rule_id="r", version=1, triggers=list(triggers), condition=condition,
                    applies_by="claim_date")


def test_ready_requires_rejection_ground():
    assert not ready_for_rules({})
    assert not ready_for_rules({"rejection_ground": fv("non_disclosure", "needs_confirmation")})
    assert ready_for_rules({"rejection_ground": fv("non_disclosure")})


def test_ready_without_cards_blocks_on_any_unconfirmed():
    facts = {"rejection_ground": fv("non_disclosure"),
             "fraud_alleged": fv(True, "needs_confirmation")}
    assert not ready_for_rules(facts)


def test_ready_with_cards_only_blocks_on_relevant_inputs():
    facts = {"rejection_ground": fv("non_disclosure"), "claim_date": fv(date(2021, 1, 1)),
             "fraud_alleged": fv(True, "needs_confirmation"),
             "deductions": fv([], "needs_confirmation")}
    assert ready_for_rules(facts, [card("continuous_cover_months > 60")]) is True
    assert not ready_for_rules(facts, [card("fraud_alleged == False")])
    # untriggered card does not block
    assert ready_for_rules(facts, [card("fraud_alleged == False", triggers=("other",))])


def test_user_confirmed_is_ready():
    facts = {"rejection_ground": fv("non_disclosure"), "fraud_alleged": fv(True, "user_confirmed")}
    assert ready_for_rules(facts)


# ---- eval_reading ----

def test_eval_reading_arithmetic(monkeypatch, dirs):
    docs = dirs / "docs"
    docs.mkdir()
    (docs / "doc_01.pdf").write_bytes(pdf_bytes("x"))
    (docs / "doc_02.pdf").write_bytes(pdf_bytes("y"))
    truth = {
        "doc_01": {"rejection_ground": "non_disclosure", "inception_date": "2019-01-05",
                   "claim_date": "2021-03-01", "fraud_alleged": False, "cited_clause": "Clause 4.1"},
        "doc_02": {"rejection_ground": "pre_existing_disease", "inception_date": "2018-02-01",
                   "claim_date": "2020-05-05", "fraud_alleged": None, "cited_clause": "clause   5"},
    }
    tp = dirs / "truth.json"
    tp.write_text(json.dumps(truth))
    out = {
        "doc_01": {"rejection_ground": fv("non_disclosure"), "inception_date": fv(date(2019, 1, 5)),
                   "claim_date": fv(date(2021, 3, 2), "needs_confirmation"),  # wrong, flagged
                   "fraud_alleged": fv(False), "cited_clause": fv("clause 4.1")},
        "doc_02": {"rejection_ground": fv("pre_existing_disease"),
                   "inception_date": fv(date(2018, 2, 2)),  # wrong, not flagged
                   "claim_date": fv(date(2020, 5, 5)), "cited_clause": fv("Clause 5")},
    }
    state = {}

    def fake_extract(session):
        assert session.path.exists()
        state.setdefault("paths", []).append(session.path)
        return out[f"doc_0{len(state['paths'])}"]
    monkeypatch.setattr(extract, "extract_user_facts", fake_extract)
    rep = eval_reading(docs, tp)
    assert rep.n_docs == 2
    assert rep.field_accuracy == 0.8
    assert rep.flagged_wrong_share == 0.5
    assert not any(p.exists() for p in state["paths"])
    assert not hasattr(rep, "values")


def test_eval_reading_no_wrong_fields(monkeypatch, dirs):
    docs = dirs / "docs"
    docs.mkdir()
    (docs / "d.pdf").write_bytes(pdf_bytes("x"))
    tp = dirs / "t.json"
    tp.write_text(json.dumps({"d": {"rejection_ground": "non_disclosure"}}))
    monkeypatch.setattr(extract, "extract_user_facts",
                        lambda s: {"rejection_ground": fv("non_disclosure")})
    rep = eval_reading(docs, tp)
    assert rep.field_accuracy == 1.0 and rep.flagged_wrong_share is None


def test_app_prompt_names_every_field_and_the_shape():
    from sarthi.app import extract
    from sarthi.data import case_facts
    assert case_facts.schema_hint(CaseFactsOut) in extract.SYSTEM_PROMPT


# ---------- fix C / I13: no false hope from model-asserted absences or listings ----------

def test_nonpayable_listed_is_never_taken_from_the_model(monkeypatch):
    q = "Consumables Rs. 2,45,000 deducted"
    s = pdf_session(q)
    items = [{"item": "consumables", "amount": "Rs. 2,45,000", "reason": "non_payable",
              "nonpayable_listed": False},
             {"item": "gloves", "amount": "Rs. 2,45,000", "reason": "non_payable",
              "nonpayable_listed": True}]
    Stub(monkeypatch, [CaseFactsOut(deductions=ef(items, q))])
    f = extract_user_facts(s)["deductions"]
    assert f.status == "needs_confirmation"
    assert all(it["nonpayable_listed"] is None for it in f.value)
    assert [it["amount"] for it in f.value] == [245000, 245000]


@pytest.mark.parametrize("field", ["crc_approval_mentioned", "reasons_cite_terms", "fraud_alleged"])
def test_absence_booleans_set_false_need_confirmation_even_with_a_quote(monkeypatch, field):
    q = "The reasons for repudiation are stated above."
    s = pdf_session(q)
    Stub(monkeypatch, [CaseFactsOut(**{field: ef(False, q)})])
    f = extract_user_facts(s)[field]
    assert f.value is False and f.status == "needs_confirmation"


def test_a_true_boolean_with_a_verbatim_quote_can_still_be_verified(monkeypatch):
    q = "The CRC approval was obtained before repudiation."
    s = pdf_session(q)
    Stub(monkeypatch, [CaseFactsOut(crc_approval_mentioned=ef(True, q))])
    assert extract_user_facts(s)["crc_approval_mentioned"].status == "verified"


# ---------- fix C: which backend read the documents ----------

def test_extraction_records_the_reading_backend(monkeypatch):
    s = pdf_session(QUOTE)
    Stub(monkeypatch, [CaseFactsOut(rejection_ground=ef("non_disclosure", QUOTE))])
    assert extract_user_facts(s).backend == "stub"
