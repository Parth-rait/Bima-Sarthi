"""Verdict copy must never read as a prediction. CHALLENGEABLE = a documented possible
inconsistency worth raising with the insurer; NEED_INFO says what is missing."""
import re
from pathlib import Path

import pytest

from sarthi.app import plan
from sarthi.app.explain import _tpl, templated
from sarthi.app.verify import verify
from sarthi.core.models import Finding

OUTCOME_EN = re.compile(r"\b(win|won|succeed|success\w*|overturn\w*|reverse\w*|illegal|wrong|unfair|reject\w*|"
                        r"refund\w*|pay\w*|claim will|you will|entitled|guarantee\w*|likely|strong)\b", re.I)
OUTCOME_HI = re.compile(r"जीत|सफल|गारंटी|हकदार|मिलेगा|ज़रूर|गलत|अवैध")


def _finding(verdict, reason=None):
    return Finding(rule_id="MORATORIUM_60M", rule_version=1, verdict=verdict, reason=reason,
                   rule_quote="No claim shall be contestable after sixty continuous months.",
                   source_sha256="x", page_no=7, facts_used={}, question_en="q", action_en="act")


@pytest.mark.parametrize("who", ["self", "helper"])
def test_challengeable_en_is_a_documented_possible_inconsistency_to_raise(who):
    t = _tpl("en")["CHALLENGEABLE"][who]
    assert "documented possible inconsistency" in t and "worth raising with the insurer" in t
    assert "does not predict any outcome" in t
    assert "challengeable" not in t.lower() and not OUTCOME_EN.search(t.replace("does not predict any outcome", ""))


@pytest.mark.parametrize("who", ["self", "helper"])
def test_challengeable_hi_is_a_documented_possible_inconsistency_to_raise(who):
    t = _tpl("hi")["CHALLENGEABLE"][who]
    assert "संभावित असंगति" in t and "बीमाकर्ता के सामने उठाना" in t and "अनुमान नहीं" in t
    assert "चुनौती देने लायक" not in t and not OUTCOME_HI.search(t)


def test_verdict_tags_in_ui_and_plan_do_not_say_challengeable():
    for lang in ("en", "hi"):
        tag = plan.VERDICT_TEXT["CHALLENGEABLE"][lang]
        assert "inconsisten" in tag.lower() if lang == "en" else "असंगति" in tag
        assert "challengeable" not in tag.lower() and "चुनौती दी जा सकती" not in tag
    html = (Path(plan.__file__).parent / "static" / "index.html").read_text(encoding="utf-8")
    assert f'CHALLENGEABLE:"{plan.VERDICT_TEXT["CHALLENGEABLE"]["en"]}"' in html
    assert f'CHALLENGEABLE:"{plan.VERDICT_TEXT["CHALLENGEABLE"]["hi"]}"' in html


def test_deadline_notes_do_not_call_a_finding_challengeable():
    assert "challengeable" not in plan.NEEDS_CHALLENGEABLE["en"].lower()
    assert "चुनौती देने योग्य" not in plan.NEEDS_CHALLENGEABLE["hi"]


@pytest.mark.parametrize("lang", ["en", "hi"])
@pytest.mark.parametrize("helper", [False, True])
@pytest.mark.parametrize("reason,needle_en,needle_hi", [
    ("missing_inputs: months_since_inception", "months since inception", None),
    ("missing_claim_date", "claim date", None),
    ("rule_not_in_force", "not in force", "लागू नहीं था"),
    ("condition_not_automated", "cannot be checked automatically", "अपने-आप नहीं जाँचा"),
    (None, "information", "जानकारी"),
    ("unsupported_applies_by", "information", "जानकारी"),
])
def test_need_info_says_what_is_missing(lang, helper, reason, needle_en, needle_hi):
    f = _finding("NEED_INFO", reason)
    t = templated([f], lang, helper)
    if lang == "en":
        assert needle_en in t.lower()
    elif needle_hi:
        assert needle_hi in t
    assert verify(t, [f]).ok


def test_consistent_does_not_endorse_the_decision():
    for lang in ("en", "hi"):
        t = templated([_finding("CONSISTENT")], lang, False)
        assert verify(t, [_finding("CONSISTENT")]).ok
        assert "only this rule" in t or "सिर्फ़ इसी नियम" in t
