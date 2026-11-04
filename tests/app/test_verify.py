from datetime import date
from types import SimpleNamespace

import pytest

from sarthi.app import explain as explain_mod
from sarthi.app.explain import explain, rephrase, templated
from sarthi.app.verify import verify
from sarthi.core.models import Finding

RQ = "No claim shall be contested on grounds of non-disclosure after 60 continuous months."


def fact(value, quote, page=1):
    return {"value": value, "quote": quote, "page_no": page}


def moratorium(**kw):
    base = dict(
        rule_id="MORATORIUM_60M", rule_version=1, verdict="CHALLENGEABLE", reason=None,
        rule_quote=RQ, source_sha256="a" * 64, page_no=3,
        facts_used={
            "continuous_cover_months": fact(66, "insured continuously since 01/06/2019 (66 months)", 2),
            "claim_amount_inr": fact(150000, "Claim amount Rs 1,50,000", 1),
            "rejection_date": fact(date(2024, 11, 5), "Date of rejection: 05/11/2024", 1),
        },
        question_en="Is fraud alleged?", question_hi=None,
        action_en="Ask the insurer to withdraw the rejection and cite the moratorium.",
        action_hi=None)
    base.update(kw)
    return Finding(**base)


def consistent():
    return moratorium(rule_id="ROOM_RENT_CAP", verdict="CONSISTENT", rule_quote="Room rent is capped at the policy limit.",
                      facts_used={"room_rent_inr": fact(4000, "Room rent Rs 4,000 per day", 1)})


def need_info(reason):
    return moratorium(rule_id="PED_WAIT_36M", verdict="NEED_INFO", reason=reason,
                      rule_quote="Pre-existing diseases are covered after 36 months.", facts_used={})


FS = [moratorium()]


def test_templated_contains_quotes():
    for lang in ("en", "hi"):
        t = templated(FS, lang, False)
        assert RQ in t
        assert "insured continuously since 01/06/2019 (66 months)" in t
        assert "MORATORIUM_60M" in t


def test_helper_mode_pronouns():
    assert "their claim" in templated(FS, "en", True)
    assert "their claim" not in templated(FS, "en", False)
    assert "उनका दावा" in templated(FS, "hi", True)
    assert "उनका दावा" not in templated(FS, "hi", False)


def test_consistent_wording_no_endorsement():
    t = templated([consistent()], "en", False)
    assert "gives no ground to challenge the decision" in t


def test_challengeable_wording_hedged():
    t = templated(FS, "en", False)
    assert "documented possible inconsistency between this decision and the rule quoted below" in t
    assert "(MORATORIUM_60M" in t  # the id stays as the citation beside the quote
    assert "does not predict any outcome" in t


@pytest.mark.parametrize("lang", ["en", "hi"])
@pytest.mark.parametrize("helper", [False, True])
@pytest.mark.parametrize("fs", [
    FS, [consistent()], [need_info("rule_not_in_force")], [need_info("missing_inputs")],
    [need_info("condition_not_automated")], [need_info("missing_claim_date")], [need_info(None)],
    [need_info("missing_inputs: months_since_inception, claim_amount_inr")],
    [moratorium(), consistent(), need_info("missing_inputs")],
])
def test_templated_always_verifies(lang, helper, fs):
    t = templated(fs, lang, helper)
    r = verify(t, fs)
    assert r.ok, (r.problems, t)


INJECTIONS = [
    # 6 wrong amounts
    "The claim was for ₹2,00,000.", "The claim was Rs 1.5 crore.", "The claim was INR 90,000.",
    "The claim was ₹1,20,000.", "The claim was 2 lakh.", "The claim was Rs. 15,000.",
    # 4 wrong dates
    "Rejected on 10/11/2024.", "Rejected on 2024-11-06.", "Rejected on 5 November 2023.",
    "Cover began 01/06/2018.",
    # 4 wrong month counts
    "Covered for 72 months.", "Covered for 7 years.", "Covered for 48 months.", "Covered for 9 years.",
    # 3 invented rule IDs
    "See WAITING_PERIOD_RULE.", "See SUB_LIMITS.", "See ROOM_RENT_CAP for this.",
    # 3 promises
    "You will get the full amount back.", "This appeal is guaranteed to work.", "You will win this case.",
]


def test_injection_count():
    assert len(INJECTIONS) == 20


@pytest.mark.parametrize("text", INJECTIONS)
def test_injection_rejected(text):
    assert not verify(text, FS).ok


def test_hindi_promise_rejected():
    for t in ["आपको मिलेगा पूरा पैसा।", "यह गारंटी है।", "आप जरूर जीतेंगे।", "निश्चित रूप से गलत।", "यह निदान गलत है।"]:
        assert not verify(t, FS).ok


def test_treatment_phrases_rejected():
    assert not verify("The treatment was unnecessary.", FS).ok
    assert not verify("The diagnosis is doubtful.", FS).ok


def test_quote_may_contain_blocked_word():
    f = moratorium(rule_quote="Diagnosis must be documented within 60 days.")
    assert verify('The rule says: "Diagnosis must be documented within 60 days."', [f]).ok


def test_equivalences_pass():
    f = moratorium(facts_used={"continuous_cover_months": fact(60, "60 months"),
                               "claim_amount_inr": fact(120000, "claim")})
    assert verify("Covered for 5 years.", [f]).ok
    assert verify("Covered for 60 months.", [f]).ok
    assert verify("Claim of ₹1,20,000.", [f]).ok
    assert verify("Claim of 1.2 lakh.", [f]).ok
    assert verify("Claim of ₹१,२०,०००.", [f]).ok
    assert verify("Covered for ६० महीने.", [f]).ok
    assert not verify("Covered for 6 years.", [f]).ok


def test_date_formats_equivalent():
    assert verify("Rejected on 05/11/2024.", FS).ok
    assert verify("Rejected on 2024-11-05.", FS).ok
    assert verify("Rejected on 5 November 2024.", FS).ok
    assert verify("Rejected on ०५/११/२०२४.", FS).ok


def test_hours_minutes_and_days():
    f = moratorium(rule_quote="Authorise within 3 hours.", facts_used={"d": fact(200, "200 minutes")})
    assert verify("Within 180 minutes.", [f]).ok
    assert verify("It took 200 minutes.", [f]).ok
    assert not verify("It took 400 minutes.", [f]).ok


def test_derived_day_difference_allowed():
    f = moratorium(facts_used={"a": fact(date(2024, 1, 1), "q"), "b": fact(date(2024, 1, 31), "q")})
    assert verify("That is 30 days apart.", [f]).ok
    assert not verify("That is 31 days apart.", [f]).ok


def test_rephrase_uses_uncached_writer(monkeypatch):
    seen = {}

    def fake(role, messages, **kw):
        seen.update(role=role, kw=kw)
        return SimpleNamespace(text="NEW", needs_review=False)
    monkeypatch.setattr(explain_mod, "chat", fake)
    assert rephrase("orig", FS, "en") == "NEW"
    assert seen["role"] == "writer" and seen["kw"]["cache"] is False


def test_rephrase_falls_back(monkeypatch):
    monkeypatch.setattr(explain_mod, "chat", lambda *a, **k: SimpleNamespace(text=None, needs_review=True))
    assert rephrase("orig", FS, "en") == "orig"
    monkeypatch.setattr(explain_mod, "chat", lambda *a, **k: SimpleNamespace(text="x", needs_review=True))
    assert rephrase("orig", FS, "en") == "orig"


def test_explain_uses_model_when_verified(monkeypatch):
    monkeypatch.setenv("SARTHI_REPHRASE", "1")
    base = templated(FS, "en", False)
    monkeypatch.setattr(explain_mod, "rephrase", lambda t, f, l: t + "\nPlease keep your papers together.")
    r = explain(FS, "en", False)
    assert r.used_model and "keep your papers" in r.text
    assert r.text.startswith(base)


def test_explain_falls_back_on_bad_model_output(monkeypatch):
    monkeypatch.setenv("SARTHI_REPHRASE", "1")
    base = templated(FS, "en", False)
    monkeypatch.setattr(explain_mod, "rephrase", lambda t, f, l: t + "\nYou will get ₹9,99,999.")
    r = explain(FS, "en", False)
    assert not r.used_model and r.text == base


def test_explain_falls_back_when_quote_dropped(monkeypatch):
    monkeypatch.setenv("SARTHI_REPHRASE", "1")
    monkeypatch.setattr(explain_mod, "rephrase", lambda t, f, l: "Looks challengeable under MORATORIUM_60M.")
    r = explain(FS, "en", False)
    assert not r.used_model


# ---- fix round 1 ----
HI_AMOUNTS = ["दावा 5 लाख रुपये का था।", "दावा 2 लाख रुपये का था।", "दावा साठ हज़ार रुपये का था।",
              "दावा 90 हज़ार रुपये का था।", "दावा 160000 रुपये का था।"]
NUMBER_WORDS = ["Covered for sixty months.", "Claim of one lakh.", "Two years passed.", "पाँच साल तक कवर।"]
UNIT_MISMATCH = ["Covered for 60 days.", "Covered for 6 months.", "Covered for 11 months.",
                 "Covered for 2019 days.", "Claim was ₹66.", "Pay within 60 days.", "Rejected on 6 Nov.",
                 "The waiting is 66 minutes."]
PROMISES = [
    "You are entitled to a full refund.", "You'll get your money back.", "Your claim will be approved.",
    "The insurer will certainly pay.", "You will surely receive ₹1,50,000.", "This rejection is valid.",
    "The rejection was correct.", "The treatment is unnecessary.", "The insurer must pay within 30 days.",
    "The decision is wrong.", "Your doctor's diagnosis",
    "आपको पूरा पैसा मिलेगा।", "आपका दावा ज़रूर मंज़ूर होगा।", "बीमा कंपनी को पैसा देना ही होगा।",
    "इलाज ज़रूरी नहीं था।", "यह फ़ैसला गलत है।",
]


@pytest.mark.parametrize("text", HI_AMOUNTS + NUMBER_WORDS + UNIT_MISMATCH + PROMISES)
def test_fix1_rejected(text):
    assert not verify(text, FS).ok


def test_fix1_unit_matches_still_pass():
    assert verify("Covered for 66 months.", FS).ok
    assert verify("Claim of ₹1,50,000.", FS).ok
    assert verify("दावा 1.5 लाख रुपये का था।", FS).ok
    assert verify("दावा 150000 रुपये।", FS).ok
    assert verify("See page 3 of the document.", FS).ok


def test_hindi_never_rephrased(monkeypatch):
    def boom(*a, **k):
        raise AssertionError("rephrase called for hi")
    monkeypatch.setattr(explain_mod, "rephrase", boom)
    r = explain(FS, "hi", False)
    assert not r.used_model and r.text == templated(FS, "hi", False)


@pytest.mark.parametrize("lang", ["en", "hi"])
def test_engine_missing_inputs_reason(lang):
    f = need_info("missing_inputs: months_since_inception, claim_amount_inr")
    t = templated([f], lang, False)
    from sarthi.app.labels import label  # fix C: known keys get their plain label
    assert "months since inception" in t and label("claim_amount_inr", lang) in t
    assert "inputs:" not in t
    assert ("a date is missing" not in t) and ("तारीख़ नहीं मिली" not in t)


def test_other_reasons_route():
    assert "not in force" in templated([need_info("rule_not_in_force")], "en", False)
    assert "cannot be checked automatically" in templated([need_info("condition_not_automated")], "en", False)
    t = templated([need_info("missing_claim_date")], "en", False)
    assert "a date is missing: claim date" in t


@pytest.mark.parametrize("fs", [FS, [consistent()], [need_info("missing_inputs: a")]])
def test_disclaimer_present(fs):
    assert "This is a rules check, not legal or medical advice." in templated(fs, "en", False)
    assert "यह नियमों की जाँच है, कानूनी या चिकित्सा सलाह नहीं।" in templated(fs, "hi", False)


# ---- fix round 2 ----
from datetime import datetime  # noqa: E402
from pathlib import Path  # noqa: E402

import yaml  # noqa: E402

from sarthi.core.engine import run_rules  # noqa: E402
from sarthi.core.models import FactValue, RuleCard  # noqa: E402

DISCLAIMER = "This is a rules check, not legal or medical advice."


def test_default_explain_never_calls_chat(monkeypatch):
    monkeypatch.delenv("SARTHI_REPHRASE", raising=False)

    calls = []
    monkeypatch.setattr(explain_mod, "chat", lambda *a, **k: calls.append(1))
    r = explain(FS, "en", False)
    assert calls == []
    assert not r.used_model and r.text == templated(FS, "en", False)


def test_env_enables_rephrase_for_en_only(monkeypatch):
    monkeypatch.setenv("SARTHI_REPHRASE", "1")
    calls = []

    def fake(role, messages, **kw):
        calls.append(role)
        return SimpleNamespace(text=messages[-1]["content"] + "\nKeep your papers together.", needs_review=False)
    monkeypatch.setattr(explain_mod, "chat", fake)
    assert explain(FS, "en", False).used_model
    assert calls == ["writer"]
    assert not explain(FS, "hi", False).used_model
    assert calls == ["writer"]


@pytest.mark.parametrize("key", ["continuity_confirmed", "fraud_alleged", "cited_clause_found",
                                 "crc_approval_mentioned", "reasons_cite_terms"])
@pytest.mark.parametrize("val", [True, False])
@pytest.mark.parametrize("lang", ["en", "hi"])
def test_boolean_facts_render(key, val, lang):
    f = moratorium(facts_used={key: fact(val, "as stated", 2)})
    t = templated([f], lang, False)
    assert verify(t, [f]).ok


def _card(rule_id, quote):
    d = yaml.safe_load(Path(f"rules/seed/{rule_id}.yaml").read_text())
    d.pop("source_id")
    d.update(quote=quote, source_sha256="a" * 64, page_no=5, status="approved")
    return RuleCard(**d)


def FV(v, q):
    return FactValue(value=v, quote=q, page_no=2)


def _run(card, **facts):
    facts["rejection_ground"] = FV(card.triggers[0], "ground")
    facts.setdefault("claim_date", FV(date(2024, 11, 5), "Claim date 05/11/2024"))
    out = run_rules(facts, [card])
    assert out, card.rule_id
    return out


def _engine_findings():
    out = []
    out += _run(_card("CASHLESS_1H", "The insurer shall decide on a cashless request within one hour."),
                cashless_request_at=FV(datetime(2024, 11, 5, 10, 30), "Request at 10:30 on 05/11/2024"),
                decision_at=FV(datetime(2024, 11, 5, 13, 45), "Decision at 1:45 pm"))
    out += _run(_card("NONPAYABLE_LIST", "Only items on the listed non-payable items may be deducted."),
                deductions=FV([{"item": "gloves", "amount": 500, "reason": "non_payable",
                                "nonpayable_listed": False}], "Gloves Rs 500 non-payable"))
    out += _run(_card("PED_WAIT_36M", "Waiting period shall not exceed 36 months."),
                inception_date=FV(date(2019, 6, 1), "Policy start 01/06/2019"),
                continuity_confirmed=FV(True, "continuity confirmed"),
                policy_renewal_date=FV(date(2024, 6, 1), "Renewed 01/06/2024"),
                renewal_gap_days=FV(0, "no gap"))
    out += _run(_card("EXCLUSION_LISTED", "Cited clause must exist."),
                cited_clause_found=FV(False, "No such clause"))
    ped = _card("MORATORIUM_60M", "Disclosed conditions must be considered.").model_copy(
        update={"rule_id": "PED_DISCLOSED", "condition": "ped_disclosed", "if_true": "CONSISTENT",
                "if_false": "CHALLENGEABLE", "triggers": ["non_disclosure"]})
    out += _run(ped, disclosed_conditions=FV(["Diabetes type 2"], "Declared: Diabetes type 2"),
                alleged_undisclosed_condition=FV("diabetes", "Alleged: diabetes"),
                inception_date=FV(date(2019, 6, 1), "Policy start 01/06/2019"),
                policy_renewal_date=FV(date(2024, 6, 1), "Renewed 01/06/2024"))
    return out


@pytest.mark.parametrize("lang", ["en", "hi"])
@pytest.mark.parametrize("helper", [False, True])
def test_engine_shaped_findings_self_verify(lang, helper):
    fs = _engine_findings()
    assert fs
    for f in fs:
        t = templated([f], lang, helper)
        r = verify(t, [f])
        assert r.ok, (f.rule_id, f.facts_used, r.problems, t)
    t = templated(fs, lang, helper)
    assert verify(t, fs).ok


def test_dict_and_list_facts_readable():
    t = templated(_engine_findings(), "en", False)
    assert "gloves — ₹500" in t and "{" not in t and "[" not in t
    assert "Diabetes type 2" in t


def test_footer_reappended_after_rephrase(monkeypatch):
    monkeypatch.setenv("SARTHI_REPHRASE", "1")
    monkeypatch.setattr(explain_mod, "rephrase", lambda t, f, l: t.replace(
        "This is a rules check, not legal or medical advice. It does not promise any result.",
        "Good luck with your appeal!"))
    r = explain(FS, "en", False)
    assert DISCLAIMER in r.text


D_FAIL = [
    "Reply within 2 weeks.", "Reply within 1 fortnight.", "Reply within a week.", "Reply within a month.",
    "Within half a year.", "Apply by 1 December.", "Apply by December 1.", "Apply by 3 Jan.",
    "Apply by 1st December.", "By the 3rd.", "Under section 45.", "Under clause 2.", "Under section 3.",
    "double the claim", "twice the amount", "In November 2023.",
]


@pytest.mark.parametrize("text", D_FAIL)
def test_fix2_units_dates_refs_rejected(text):
    assert not verify(text, FS).ok


def test_fix2_weeks_dates_pass_when_supported():
    f = moratorium(rule_quote="Reply within 2 weeks and file by 5 November.", page_no=3)
    assert verify("Reply within 14 days.", [f]).ok
    assert verify("Reply within 2 weeks.", [f]).ok
    assert verify("Apply by 5 November.", [f]).ok
    assert verify("Apply by November 5.", [f]).ok
    assert verify("In November 2024.", [f]).ok
    assert not verify("Reply within 3 weeks.", [f]).ok


def test_section_ref_must_be_in_rule_quote():
    f = moratorium(rule_quote="As per section 45 of the Act, claims are protected.")
    assert verify("Under section 45.", [f]).ok
    assert not verify("Under section 3.", [f]).ok  # 3 is the page number only


SOFT = [
    "You should receive the full amount.", "The insurer is obliged to pay.", "The insurer has to pay you.",
    "The insurer will have to pay.", "The insurer should pay you.", "The insurer is liable.",
    "You have a strong case.", "You're going to get paid.", "Your money will come back.",
    "You can expect a refund.", "The ombudsman will rule in your favour.", "The insurer acted correctly.",
    "The insurer was wrong.", "Your claim is valid.", "The rejection was justified.",
    "The rejection was fair.", "The rejection is unlawful.", "The decision is not valid.",
    "The rejection is clearly wrong.", "The deduction was improper.", "The surgery was unnecessary.",
    "Your hospital stay was medically necessary.", "You will be paid.", "100% sure.", "You are owed the money.",
]


@pytest.mark.parametrize("text", SOFT)
def test_fix2_soft_promises_rejected(text):
    assert not verify(text, FS).ok


def test_card_text_excluded_from_phrase_scans():
    f = moratorium(action_en="Ask them to pay within twenty days; the insurer is liable only if you can show it.")
    t = templated([f], "en", False)
    assert verify(t, [f]).ok


# ---- fix round 3 ----
def test_paise_amount_renders_exactly_and_self_verifies():
    f = moratorium(facts_used={"deductions": fact([{"item": "gloves", "amount": 1250.5, "reason": "non_payable",
                                                    "nonpayable_listed": False}], "Gloves Rs 1,250.50"),
                               "claim_amount_inr": fact(99999.75, "Claim Rs 99,999.75")})
    for lang in ("en", "hi"):
        t = templated([f], lang, False)
        assert "₹1,250.50" in t and "₹99,999.75" in t
        assert verify(t, [f]).ok, verify(t, [f]).problems


def test_whole_and_zero_paise_amounts():
    f = moratorium(facts_used={"claim_amount_inr": fact(150000.0, "Claim Rs 1,50,000")})
    assert "₹1,50,000 " in templated([f], "en", False) + " "
    assert "₹1,50,000.0" not in templated([f], "en", False)


def test_truncated_amount_fails_against_paise_fact():
    f = moratorium(facts_used={"claim_amount_inr": fact(1250.5, "Claim Rs 1,250.50")})
    assert verify("Claim of ₹1,250.50.", [f]).ok
    assert not verify("Claim of ₹1,250.", [f]).ok
    assert not verify("Claim of ₹1,251.", [f]).ok


def test_whole_footer_restored_after_rephrase(monkeypatch):
    monkeypatch.setenv("SARTHI_REPHRASE", "1")
    monkeypatch.setattr(explain_mod, "rephrase", lambda t, f, l: t.replace(" It does not promise any result.", ""))
    r = explain(FS, "en", False)
    assert "It does not promise any result." in r.text
    assert r.text.count(DISCLAIMER) == 1 or r.text.endswith("any result.")


def test_will_succeed_rejected():
    assert not verify("Your appeal will succeed.", FS).ok
    assert not verify("A successful appeal is near.", FS).ok
