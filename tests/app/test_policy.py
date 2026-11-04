"""Policy key-terms explainer: extraction with verified quotes, display templates, safety.

All document text below is SYNTHETIC (invented for these tests, not a real policy).
"""
import re

import pymupdf
import pytest

from sarthi.app import policy
from sarthi.app.session import Session
from sarthi.app.verify import verify
from sarthi.llm.client import ChatResult

# SYNTHETIC policy wording, one clause per line.
L_SUM = "Sum Insured: Rs. 5,00,000 per policy year"
L_PERIOD = "Policy Period: 01/04/2025 to 31/03/2026"
L_PED = "Pre-existing diseases are covered after 36 months of continuous coverage"
L_INIT = "Initial waiting period: 30 days from the first policy start date"
L_SPEC = "Specified illnesses such as cataract have a waiting period of 24 months"
L_ROOM = "Room rent is limited to 1% of the Sum Insured per day"
L_COPAY = "Co-payment of 20% applies to every claim"
L_SUB = "Cataract surgery is limited to Rs. 40,000 per eye"
L_INTIM = "Intimate the claim within 7 days of admission"
L_RENEW = "Renewal is allowed within a grace period for continuity benefits"
PAGE1 = "\n".join([L_SUM, L_PERIOD, L_PED, L_INIT])
PAGE2 = "\n".join([L_SPEC, L_ROOM, L_COPAY, L_SUB, L_INTIM, L_RENEW])


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


def t(value, quote, page_no=1, confidence="high"):
    return policy.PolicyTermOut(value=value, quote=quote, page_no=page_no, confidence=confidence)


class Stub:
    """Reader stub: `outs` is one PolicyTermsOut per page call; `transcripts` per transcription call."""
    def __init__(self, monkeypatch, outs, transcripts=(), needs_review=False):
        self.outs, self.transcripts = iter(outs), iter(transcripts)
        self.needs_review, self.calls = needs_review, []
        monkeypatch.setattr(policy, "chat", self)

    def __call__(self, role, messages, **kw):
        self.calls.append((role, kw))
        if kw.get("schema") is not None:
            return res(next(self.outs), needs_review=self.needs_review)
        return res(text=next(self.transcripts))


def pdf_session(*texts):
    s = Session.create()
    s.add_upload(("policy.pdf", pdf_bytes(*texts)))
    return s


def all_terms_out():
    return (policy.PolicyTermsOut(
        sum_insured=t("Rs. 5,00,000", L_SUM), policy_period=t("01/04/2025 to 31/03/2026", L_PERIOD),
        ped_waiting_months=t(36, L_PED), initial_waiting_days=t("30 days", L_INIT)),
        policy.PolicyTermsOut(
        specific_waiting_months=t("24 months", L_SPEC, 2), room_rent_limit=t("1% of the Sum Insured per day", L_ROOM, 2),
        co_payment=t("20%", L_COPAY, 2), sub_limits=t(["Rs. 40,000 per eye"], L_SUB, 2),
        claim_intimation_days=t(7, L_INTIM, 2), renewal_portability_terms=t("grace period for continuity benefits", L_RENEW, 2)))


# ---------- schema ----------

def test_schema_is_closed_and_has_exactly_the_ten_terms():
    assert list(policy.PolicyTermsOut.model_fields) == list(policy.TERM_KEYS)
    assert len(policy.TERM_KEYS) == 10
    with pytest.raises(Exception):
        policy.PolicyTermsOut(not_a_term=t("x", "x"))
    with pytest.raises(Exception):
        policy.PolicyTermOut(value="x", quote="x", page_no=1, confidence="high", extra="no")


# ---------- (a) all terms verified ----------

def test_text_layer_terms_with_verbatim_quotes_are_verified(monkeypatch):
    stub = Stub(monkeypatch, all_terms_out())
    terms = policy.extract_policy_terms(pdf_session(PAGE1, PAGE2))
    assert set(terms) == set(policy.TERM_KEYS)
    assert all(f.status == "verified" for f in terms.values())
    assert terms["sum_insured"].value == 500000 and terms["sum_insured"].page_no == 1
    assert terms["ped_waiting_months"].value == 36
    assert terms["initial_waiting_days"].value == 30            # "30 days" -> unit-typed 30 days
    assert terms["specific_waiting_months"].value == 24 and terms["specific_waiting_months"].page_no == 2
    assert terms["co_payment"].value == 20
    assert terms["claim_intimation_days"].value == 7
    assert terms["sub_limits"].value == ["Rs. 40,000 per eye"]
    assert terms["sum_insured"].quote == L_SUM
    assert [c[0] for c in stub.calls] == ["reader", "reader"] and terms.backend == "stub"


def test_years_in_the_value_are_normalised_to_months_when_the_quote_says_years(monkeypatch):
    quote = "Pre-existing diseases are covered after 3 years of continuous coverage"
    Stub(monkeypatch, [policy.PolicyTermsOut(ped_waiting_months=t("3 years", quote))])
    terms = policy.extract_policy_terms(pdf_session(quote))
    assert terms["ped_waiting_months"].status == "verified" and terms["ped_waiting_months"].value == 36


# ---------- (b) hallucinated / unsupported terms ----------

def test_quote_not_on_the_page_is_needs_confirmation_and_carries_no_value(monkeypatch):
    fake = "Co-payment of 30% applies to every claim"      # not in the document
    Stub(monkeypatch, [policy.PolicyTermsOut(co_payment=t("30%", fake), sum_insured=t(500000, L_SUM))])
    terms = policy.extract_policy_terms(pdf_session(PAGE1))
    assert terms["co_payment"].status == "needs_confirmation"
    assert terms["co_payment"].value is None and terms["co_payment"].quote is None   # never shown as fact
    assert terms["sum_insured"].status == "verified"


def test_value_that_the_quote_does_not_support_is_needs_confirmation(monkeypatch):
    Stub(monkeypatch, [policy.PolicyTermsOut(ped_waiting_months=t(48, L_PED),      # quote says 36
                                             initial_waiting_days=t(30, L_INIT))])
    terms = policy.extract_policy_terms(pdf_session(PAGE1))
    assert terms["ped_waiting_months"].status == "needs_confirmation"
    assert terms["initial_waiting_days"].status == "verified"


def test_wrong_unit_is_needs_confirmation(monkeypatch):
    Stub(monkeypatch, [policy.PolicyTermsOut(initial_waiting_days=t("30 months", L_INIT))])
    assert policy.extract_policy_terms(pdf_session(PAGE1))["initial_waiting_days"].status == "needs_confirmation"


def test_text_value_not_contained_in_quote_is_needs_confirmation(monkeypatch):
    Stub(monkeypatch, [policy.PolicyTermsOut(room_rent_limit=t("2% of the Sum Insured per day", L_ROOM))])
    assert policy.extract_policy_terms(pdf_session(PAGE2))["room_rent_limit"].status == "needs_confirmation"


def test_absent_terms_are_simply_missing(monkeypatch):
    Stub(monkeypatch, [policy.PolicyTermsOut(sum_insured=t(500000, L_SUM))])
    terms = policy.extract_policy_terms(pdf_session(PAGE1))
    assert set(terms) == {"sum_insured"}


def test_null_value_or_missing_quote_is_not_a_term(monkeypatch):
    Stub(monkeypatch, [policy.PolicyTermsOut(co_payment=t(None, L_COPAY), sum_insured=t(500000, None))])
    terms = policy.extract_policy_terms(pdf_session(PAGE1))
    assert "co_payment" not in terms
    assert terms["sum_insured"].status == "needs_confirmation"


def test_conflicting_verified_values_on_two_pages_need_confirmation(monkeypatch):
    other = "Sum Insured: Rs. 10,00,000 per policy year"
    Stub(monkeypatch, [policy.PolicyTermsOut(sum_insured=t(500000, L_SUM)),
                       policy.PolicyTermsOut(sum_insured=t(1000000, other, 2))])
    terms = policy.extract_policy_terms(pdf_session(L_SUM, other))
    assert terms["sum_insured"].status == "needs_confirmation" and terms["sum_insured"].reason == "conflict"
    assert terms["sum_insured"].value is None


def test_a_reader_that_needs_review_never_verifies(monkeypatch):
    Stub(monkeypatch, [policy.PolicyTermsOut(sum_insured=t(500000, L_SUM))], needs_review=True)
    assert policy.extract_policy_terms(pdf_session(PAGE1))["sum_insured"].status == "needs_confirmation"


def test_page_number_comes_from_the_page_read_not_the_model(monkeypatch):
    Stub(monkeypatch, [policy.PolicyTermsOut(), policy.PolicyTermsOut(sum_insured=t(500000, L_SUM, page_no=99))])
    terms = policy.extract_policy_terms(pdf_session("other page", L_SUM))
    assert terms["sum_insured"].page_no == 2


# ---------- (d) scanned pages ----------

def test_photographed_page_uses_a_transcription_and_a_fuzzy_quote_match(monkeypatch):
    s = Session.create()
    s.add_upload(("scan.png", png_bytes()))
    stub = Stub(monkeypatch, [policy.PolicyTermsOut(sum_insured=t(500000, L_SUM), co_payment=t("30%", "Co-payment of 30% for all"))],
                transcripts=[PAGE1])
    terms = policy.extract_policy_terms(s)
    assert terms["sum_insured"].status == "verified" and terms["sum_insured"].page_no == 1
    assert terms["co_payment"].status == "needs_confirmation"
    assert [kw.get("schema") is not None for _, kw in stub.calls] == [True, False]
    assert all(kw["cache"] is False for _, kw in stub.calls)


# ---------- (f) privacy ----------

def test_every_model_call_bypasses_the_cache(monkeypatch):
    stub = Stub(monkeypatch, all_terms_out())
    policy.extract_policy_terms(pdf_session(PAGE1, PAGE2))
    assert stub.calls and all(kw["cache"] is False for _, kw in stub.calls)


def test_no_document_text_or_values_are_logged(monkeypatch, caplog):
    import logging
    Stub(monkeypatch, all_terms_out())
    with caplog.at_level(logging.DEBUG):
        policy.extract_policy_terms(pdf_session(PAGE1, PAGE2))
    logged = " ".join(r.getMessage() for r in caplog.records)
    assert "5,00,000" not in logged and "Sum Insured" not in logged and "500000" not in logged


# ---------- user input ----------

@pytest.mark.parametrize("key,raw,want", [
    ("sum_insured", "5,00,000", 500000), ("sum_insured", "Rs. 5 lakh", 500000), ("sum_insured", 750000, 750000),
    ("ped_waiting_months", "36", 36), ("ped_waiting_months", "3 years", 36),
    ("initial_waiting_days", "30 days", 30), ("co_payment", "20%", 20), ("co_payment", "0", 0),
    ("room_rent_limit", " 1% of SI ", "1% of SI"), ("sub_limits", "a; b", ["a", "b"]),
])
def test_user_values_are_parsed_by_unit(key, raw, want):
    assert policy.parse_term_input(key, raw) == want


@pytest.mark.parametrize("key,raw", [
    ("sum_insured", "lots"), ("sum_insured", -5), ("ped_waiting_months", "30 days"), ("co_payment", True),
    ("room_rent_limit", ""), ("room_rent_limit", "x" * 301), ("sub_limits", []), ("policy_period", None)])
def test_bad_user_values_are_rejected(key, raw):
    with pytest.raises(ValueError):
        policy.parse_term_input(key, raw)


# ---------- display ----------

def verified_terms(monkeypatch):
    Stub(monkeypatch, all_terms_out())
    return policy.extract_policy_terms(pdf_session(PAGE1, PAGE2))


def test_policy_json_has_label_value_quote_page_and_fixed_disclaimer(monkeypatch):
    j = policy.policy_json(verified_terms(monkeypatch))
    assert j["verified"] is True
    assert j["disclaimer"]["en"] == ("This shows what the uploaded document says. It is not a conclusion about whether "
                                     "your claim is covered; the schedule, endorsements and other pages may change the meaning.")
    by = {x["key"]: x for x in j["terms"]}
    assert list(by) == list(policy.TERM_KEYS)
    s = by["sum_insured"]
    assert (s["state"], s["quote"], s["page_no"]) == ("found", L_SUM, 1)
    assert s["label"]["en"] == "Sum insured" and s["display"]["en"] == "₹5,00,000"
    assert by["ped_waiting_months"]["display"]["en"] == "36 months"
    assert by["ped_waiting_months"]["display"]["hi"] == "36 महीने"
    assert by["co_payment"]["display"]["en"] == "20%"
    assert by["claim_intimation_days"]["display"]["en"] == "7 days"
    assert by["sub_limits"]["display"]["en"] == "Rs. 40,000 per eye"


@pytest.mark.parametrize("lang", ["en", "hi"])
def test_section_text_passes_verify_and_has_no_blocked_phrases(monkeypatch, lang):
    j = policy.policy_json(verified_terms(monkeypatch))
    text = j["text"][lang]
    quotes = [x["quote"] for x in j["terms"] if x["quote"]]
    assert all(q in text for q in quotes) and j["disclaimer"][lang] in text
    assert verify(text, [], extra_quotes=quotes + [x["display"]["en"] for x in j["terms"] if x["display"]],
                  extra_values=[("int", 1), ("int", 2), ("inr", 500000), ("months", 36), ("months", 24),
                                ("days", 30), ("days", 7), ("pct", 20)]).ok


def test_disclaimer_and_labels_pass_verify_on_their_own():
    for lang in ("en", "hi"):
        assert verify(policy.DISCLAIMER[lang], []).ok, policy.DISCLAIMER[lang]
        for k in policy.TERM_KEYS:
            assert verify(policy.LABELS[k][0 if lang == "en" else 1], []).ok


# ---------- (e) Hindi labels ----------

@pytest.mark.parametrize("key", policy.TERM_KEYS)
def test_labels_are_plain_en_and_hi_without_snake_case(key):
    en, hi = policy.LABELS[key]
    assert en and hi and "_" not in en and "_" not in hi
    assert re.search(r"[ऀ-ॿ]", hi) and not re.search(r"[ऀ-ॿ]", en)


def test_no_snake_case_anywhere_in_the_json_text(monkeypatch):
    terms = verified_terms(monkeypatch)
    terms["co_payment"] = terms["co_payment"].model_copy(update={"value": None, "quote": None, "status": "needs_confirmation", "reason": "unverified"})
    del terms["room_rent_limit"]
    j = policy.policy_json(terms)
    for lang in ("en", "hi"):
        assert not re.search(r"\b[a-z]+_[a-z_]+\b", j["text"][lang])
        for x in j["terms"]:
            assert "_" not in x["label"][lang] and not (x["message"] and "_" in x["message"][lang])


def test_hindi_text_is_a_marked_draft():
    assert "Q-007" in policy.__doc__


# ---------- unverified and absent display ----------

def test_unverified_term_says_it_could_not_be_found_and_shows_no_value_or_quote(monkeypatch):
    Stub(monkeypatch, [policy.PolicyTermsOut(co_payment=t("30%", "Co-payment of 30% for all"),
                                             sum_insured=t(500000, L_SUM))])
    j = policy.policy_json(policy.extract_policy_terms(pdf_session(PAGE1)))
    by = {x["key"]: x for x in j["terms"]}
    c = by["co_payment"]
    assert c["state"] == "unverified" and c["value"] is None and c["quote"] is None and c["display"] is None
    assert c["message"]["en"] == "We could not find this in your document."
    assert "30" not in j["text"]["en"]
    a = by["room_rent_limit"]
    assert a["state"] == "absent" and a["message"]["en"] == "Not found in the pages we read."


def test_conflict_term_is_explained_without_a_value(monkeypatch):
    other = "Sum Insured: Rs. 10,00,000 per policy year"
    Stub(monkeypatch, [policy.PolicyTermsOut(sum_insured=t(500000, L_SUM)),
                       policy.PolicyTermsOut(sum_insured=t(1000000, other, 2))])
    j = policy.policy_json(policy.extract_policy_terms(pdf_session(L_SUM, other)))
    s = next(x for x in j["terms"] if x["key"] == "sum_insured")
    assert s["state"] == "conflict" and s["display"] is None and "different" in s["message"]["en"]


def test_user_entered_and_confirmed_states(monkeypatch):
    terms = verified_terms(monkeypatch)
    terms["sum_insured"] = terms["sum_insured"].model_copy(update={"status": "user_confirmed"})
    terms["co_payment"] = policy.PolicyTerm(value=10, quote=None, page_no=None, confidence="high",
                                            status="user_confirmed")
    by = {x["key"]: x for x in policy.policy_json(terms)["terms"]}
    assert by["sum_insured"]["state"] == "confirmed" and by["sum_insured"]["quote"] == L_SUM
    assert by["co_payment"]["state"] == "entered" and by["co_payment"]["display"]["en"] == "10%"
    assert by["co_payment"]["quote"] is None


def test_section_that_fails_verify_is_not_shown(monkeypatch):
    terms = verified_terms(monkeypatch)
    monkeypatch.setitem(policy.DISCLAIMER, "en", "You will definitely be paid. " + policy.DISCLAIMER["en"])
    assert policy.policy_json(terms) is None
