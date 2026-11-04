"""Documents to ask the insurer for: a short fixed checklist, no model.

Shown when a finding needs more information, or when the user's reason for the decision
mentions a deduction (room rent, co-payment, sub-limit, non-payable items). It names what to
ask for in writing; it states no amounts and no legal conclusion, and never changes a verdict.

Hindi text is a fixed-template DRAFT pending human review (Q-007).
"""
import logging
import re

from sarthi.app.verify import verify
from sarthi.core.models import FactValue, Finding

log = logging.getLogger(__name__)

TITLE = {"en": "What to ask the insurer for, in writing", "hi": "बीमाकर्ता से लिखित में क्या माँगें"}
INTRO = {"en": "Ask for these in writing and keep a copy of your request.",
         "hi": "इन्हें लिखित में माँगें और अपने अनुरोध की प्रति अपने पास रखें।"}
ITEMS = [
    {"en": "An itemised settlement calculation that shows how each amount was worked out.",
     "hi": "पूरा हिसाब मदवार, जिसमें दिखे कि हर राशि कैसे निकाली गई।"},
    {"en": "The policy schedule and all endorsements that apply to your policy.",
     "hi": "आपकी पॉलिसी का शेड्यूल और उस पर लागू सभी एंडोर्समेंट।"},
    {"en": "The exact policy clause the insurer relied on for its decision.",
     "hi": "बीमाकर्ता ने अपने फ़ैसले में पॉलिसी की जिस धारा का सहारा लिया, वह धारा ठीक-ठीक।"},
    {"en": "The claim file and any TPA letters about your claim.",
     "hi": "आपके दावे की क्लेम फ़ाइल और TPA के सभी पत्र।"},
    {"en": "Copies of the medical records and the proposal form held on file.",
     "hi": "फ़ाइल में रखे चिकित्सा रिकॉर्ड और प्रपोज़ल फ़ॉर्म की प्रतियाँ।"},
]

DEDUCTION_GROUNDS = {"deduction", "room_rent", "sub_limit"}
_DEDUCTION_WORDS = re.compile(
    r"room[\s_-]*rent|co[\s_-]*pay|sub[\s_-]*limit|non[\s_-]*payable|"
    r"कमरे का किराया|कमरे के किराये|सह-भुगतान|को-पेमेंट|उप-सीमा|गैर-भुगतान", re.I)


def _texts(v):
    if isinstance(v, str):
        yield v
    elif isinstance(v, dict):
        for x in v.values():
            yield from _texts(x)
    elif isinstance(v, (list, tuple)):
        for x in v:
            yield from _texts(x)


def mentions_deduction(facts: dict[str, FactValue]) -> bool:
    """Whether the user's reason (ground, deduction lines, cited clause) is about a deduction."""
    ground = facts.get("rejection_ground")
    if ground is not None and ground.value in DEDUCTION_GROUNDS:
        return True
    for key in ("deductions", "cited_clause"):
        f = facts.get(key)
        if f is not None and any(_DEDUCTION_WORDS.search(t) for t in _texts(f.value)):
            return True
    return False


def build(findings: list[Finding], facts: dict[str, FactValue]) -> dict | None:
    if not (any(f.verdict == "NEED_INFO" for f in findings) or mentions_deduction(facts)):
        return None
    texts = {l: "\n".join([TITLE[l], INTRO[l], *(f"- {i[l]}" for i in ITEMS)]) for l in ("en", "hi")}
    for lang, t in texts.items():
        r = verify(t, [])
        if not r.ok:
            log.error("request checklist failed verify lang=%s problems=%d", lang, len(r.problems))
            return None
    return {"verified": True, "title": TITLE, "intro": INTRO, "items": [dict(i) for i in ITEMS], "text": texts}
