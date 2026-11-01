import re
from datetime import date

import pytest

from sarthi.app import labels
from sarthi.app.explain import templated
from sarthi.app.letter import LETTER_FACT_KEYS, build_letter
from sarthi.core.derive import FACT_KEYS
from sarthi.core.inputs import KNOWN_INPUTS
from sarthi.core.models import Finding

ALL_KEYS = sorted(set(FACT_KEYS) | set(LETTER_FACT_KEYS) | set(KNOWN_INPUTS)
                  | {"item", "amount", "reason", "nonpayable_listed"})
PARAMS = {"insurer_reply_days": 15, "ombudsman_wait_days": 30,
          "ombudsman_limit_months": 12, "ombudsman_cap_inr": 5000000}


@pytest.mark.parametrize("key", ALL_KEYS)
def test_every_key_has_plain_en_and_hi_labels(key):
    en, hi = labels.label(key, "en"), labels.label(key, "hi")
    assert en and hi and "_" not in en and "_" not in hi
    assert re.search(r"[ऀ-ॿ]", hi) and not re.search(r"[ऀ-ॿ]", en)


def test_unknown_key_falls_back_to_spaces():
    assert labels.label("some_new_key") == "some new key"


def test_hindi_labels_are_flagged_as_draft():
    assert "Q-007" in labels.__doc__


def finding(**kw):
    base = dict(rule_id="MORATORIUM_60M", rule_version=1, verdict="CHALLENGEABLE", reason="condition_met",
                rule_quote="No claim shall be contestable after sixty months.", source_sha256="x",
                page_no=4, facts_used={"inception_date": {"value": "2019-01-10", "quote": "Policy start 10/01/2019",
                                                         "page_no": 1},
                                       "continuous_cover_months": {"value": 72, "quote": None, "page_no": None}})
    base.update(kw)
    return Finding(**base)


@pytest.mark.parametrize("lang", ["en", "hi"])
def test_explanation_uses_labels_not_snake_case(lang):
    t = templated([finding()], lang, False)
    assert labels.label("inception_date", lang) in t
    assert "inception_date" not in t and "inception date" not in t
    assert not re.search(r"\b[a-z]+_[a-z_]+\b", t.replace("MORATORIUM_60M", ""))


@pytest.mark.parametrize("lang", ["en", "hi"])
def test_missing_names_in_explanation_are_labelled(lang):
    f = finding(verdict="NEED_INFO", reason="missing_inputs: continuous_cover_months, claim_date", facts_used={})
    t = templated([f], lang, False)
    assert labels.label("continuous_cover_months", lang) in t and "continuous_cover_months" not in t
    f = finding(verdict="NEED_INFO", reason="missing_inception_date", facts_used={})
    assert labels.label("inception_date", lang) in templated([f], lang, False)


def test_deduction_item_keys_are_labelled_in_explanation():
    f = finding(facts_used={"deductions": {"value": [{"item": "gloves", "amount": 500, "reason": "other",
                                                      "nonpayable_listed": False}], "quote": None, "page_no": None},
                            "x": {"value": {"nonpayable_overcharge_inr": 5}, "quote": None, "page_no": None}})
    t = templated([f], "en", False)
    assert "nonpayable_overcharge_inr" not in t and "wrongly deducted non-payable amount" in t


@pytest.mark.parametrize("lang", ["en", "hi"])
def test_letter_uses_labels(lang):
    text = build_letter({}, [finding()], lang, params=PARAMS, letter_date=date(2026, 11, 1))
    assert labels.label("inception_date", lang) in text and "inception_date" not in text


# ---------- fix C / I11: an empty result must not read as "nothing wrong" ----------

EMPTY_EN = "We don't have a checked rule for this reason yet. This does not mean the decision is correct."
EMPTY_HI = "इस कारण के लिए हमारे पास अभी कोई जाँचा हुआ नियम नहीं है। इसका मतलब यह नहीं कि फ़ैसला सही है।"


@pytest.mark.parametrize("lang,text", [("en", EMPTY_EN), ("hi", EMPTY_HI)])
def test_empty_explanation_says_no_checked_rule(lang, text):
    from sarthi.app.verify import verify
    t = templated([], lang, False)
    assert text in t and verify(t, []).ok


def test_ui_empty_result_wording():
    from pathlib import Path
    html = (Path(labels.__file__).parent / "static" / "index.html").read_text(encoding="utf-8")
    assert EMPTY_EN in html and EMPTY_HI in html
    assert "so there is nothing to report" not in html


def test_the_exemption_covers_only_the_fixed_sentence():
    from sarthi.app.verify import verify
    assert not verify("The insurer's decision is correct.", []).ok
    assert not verify(EMPTY_EN + " Also, the decision is correct.", []).ok


# ---------- round 2: enum VALUES are labelled too (rejection_ground etc.) ----------

from sarthi.core.inputs import REJECTION_GROUNDS  # noqa: E402

SNAKE = re.compile(r"\b[a-z0-9]+(?:_[a-z0-9]+)+\b")


@pytest.mark.parametrize("g", REJECTION_GROUNDS)
def test_every_rejection_ground_has_plain_en_hi_labels(g):
    en, hi = labels.value_label(g, "en"), labels.value_label(g, "hi")
    assert "_" not in en and "_" not in hi and en != g
    assert re.search(r"[ऀ-ॿ]", hi) and not re.search(r"[ऀ-ॿ]", en)
    assert g in labels.GROUND_LABELS


def test_value_label_is_exact_lookup_only():
    assert labels.value_label("some_new_code", "en") == "some_new_code"
    assert labels.value_label("pol_123456", "hi") == "pol_123456"
    assert labels.value_label("constructor", "en") == "constructor"


def ground_finding(g="pre_existing_disease"):
    return finding(facts_used={
        "rejection_ground": {"value": g, "quote": "repudiated for PED", "page_no": 1},
        "deductions": {"value": [{"item": "gloves", "amount": 500, "reason": "proportionate",
                                  "nonpayable_listed": False}], "quote": "gloves 500", "page_no": 1}})


@pytest.mark.parametrize("lang", ["en", "hi"])
@pytest.mark.parametrize("g", REJECTION_GROUNDS)
def test_explanation_shows_ground_label_and_no_snake_token(lang, g):
    t = templated([ground_finding(g)], lang, False)
    assert labels.value_label(g, lang) in t
    assert not SNAKE.findall(t.replace("MORATORIUM_60M", ""))


@pytest.mark.parametrize("lang", ["en", "hi"])
def test_letter_has_no_snake_token_for_a_ground_finding(lang):
    text = build_letter({}, [ground_finding()], lang, params=PARAMS, letter_date=date(2026, 11, 1))
    assert not SNAKE.findall(text.replace("MORATORIUM_60M", ""))


def test_ui_ground_labels_come_from_the_single_source_and_display_uses_them():
    import json
    from pathlib import Path
    html = (Path(labels.__file__).parent / "static" / "index.html").read_text(encoding="utf-8")
    m = re.search(r"const GROUND_LABEL=(\{.*?\});\n", html, re.S)
    ui = json.loads(re.sub(r"(\w+):", r'"\1":', m.group(1)))
    assert ui == {"en": {g: labels.value_label(g, "en") for g in REJECTION_GROUNDS},
                  "hi": {g: labels.value_label(g, "hi") for g in REJECTION_GROUNDS}}
    assert "function showVal(" in html and "GROUND_LABEL[lang][v]" in html
    assert "valText(v.value)" not in html           # verdict cards display via showVal


# ---------- round 3: free text is shown exactly as stored ----------

def free_text_finding():
    return finding(facts_used={
        "policy_number": {"value": "pol_123456", "quote": "Policy pol_123456", "page_no": 1},
        "alleged_undisclosed_condition": {"value": "type_2", "quote": "type_2 diabetes", "page_no": 1},
        "rejection_ground": {"value": "constructor", "quote": "q", "page_no": 1},
        "deductions": {"value": [{"item": "gloves_xl", "amount": 500, "reason": "weird_code",
                                  "nonpayable_listed": False}], "quote": "gloves_xl 500", "page_no": 1}})


@pytest.mark.parametrize("lang", ["en", "hi"])
def test_free_text_values_are_not_rewritten_in_the_explanation(lang):
    t = templated([free_text_finding()], lang, False)
    for verbatim in ("pol_123456", "type_2", "constructor", "gloves_xl", "weird_code"):
        assert verbatim in t
    assert "pol 123456" not in t and "type 2" not in t


def test_ui_free_text_and_safe_lookups():
    from pathlib import Path
    html = (Path(labels.__file__).parent / "static" / "index.html").read_text(encoding="utf-8")
    i = html.index("function showVal(")
    body = html[i:html.index("\n", html.index("return String(v);}", i))]
    assert "replaceAll" not in body and "test(v)" not in body
    assert "Object.hasOwn(GROUND_LABEL[lang],v)" in body
    assert "GROUND_LABEL[lang][v]||" not in html
