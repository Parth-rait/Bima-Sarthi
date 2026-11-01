"""Type of insurance, the general plan (non-health) and "Your plan" (health).

Fixed templates only: no model, no network. Every route statement carries a verbatim quote and
page from a stored official text (CATALOGUE); a test checks each quote against the database.
Dates are computed only from dates the user entered and from the approved GRIEVANCE_ROUTE
card's params; with no such date the plan shows the "Add the date ..." message instead.
Hindi is a DRAFT pending human review (Q-007).
"""
from __future__ import annotations

import copy
import logging
from datetime import date

from sarthi.app.explain import _localised, _tpl
from sarthi.app.letter import _v, cap_note_text, deadline_sources, deadlines
from sarthi.app.verify import verify
from sarthi.core.models import Finding

log = logging.getLogger("sarthi.app")

PPI = "irdai_ppi_master_2024"
OMB = "ombudsman_rules_2017"
SOURCE_TITLES = {
    PPI: "Master Circular on Protection of Policyholders' Interests, 2024",
    OMB: "Insurance Ombudsman Rules, 2017 (as amended till 18.05.2021)",
}

# ---------- type of insurance ----------

PRODUCT_LINE_KEYS = ("health", "life", "accident", "motor", "crop", "credit_life", "other")
# key -> (English, Hindi draft Q-007). The UI select embeds a copy that a test pins to this.
PRODUCT_LABELS = {
    "health": ("Health", "स्वास्थ्य"),
    "life": ("Life", "जीवन"),
    "accident": ("Accident", "दुर्घटना"),
    "motor": ("Motor", "मोटर (वाहन)"),
    "crop": ("Crop (agriculture)", "फ़सल (कृषि)"),
    "credit_life": ("Loan-linked or credit-life", "ऋण से जुड़ा या क्रेडिट-लाइफ़"),
    "other": ("Other", "अन्य"),
}
FIELD_LABEL = {"en": "Type of insurance", "hi": "बीमा का प्रकार"}


def product_label(key: str, lang: str = "en") -> str:
    pair = PRODUCT_LABELS.get(key)
    return key if pair is None else pair[1] if lang == "hi" else pair[0]


# A health ground that only makes sense for a hospital claim, plus a hospital fact.
HEALTH_GROUNDS = {"specific_waiting_period", "initial_waiting_period", "portability", "deduction",
                  "room_rent", "sub_limit", "cashless_delay", "discharge_delay"}
HOSPITAL_FACTS = ("admission_date", "cashless_request_at", "discharge_request_at", "final_auth_at",
                  "deductions")


def product_line_hint(facts: dict) -> str | None:
    """'health' only when hospital facts AND a hospital-type rejection ground were extracted."""
    ground = facts.get("rejection_ground")
    if ground is None or ground.value not in HEALTH_GROUNDS:
        return None
    if any(getattr(facts.get(k), "value", None) not in (None, "", []) for k in HOSPITAL_FACTS):
        return "health"
    return None


# ---------- verified statements (verbatim quote + page) ----------
# `lines`: the product lines for which the stored text supports the statement.
#   life            PPI Part A (Life Insurance Policies, pages 99-112); Rules apply to personal/group lines.
#   motor, accident PPI Part C (Retail General Insurance Policies, pages 126-137: "designed for
#                   individuals or households"; motor is named on page 130); Rules as above.
# crop, credit_life, other: no statement is verified, so none is listed.
SUPPORTED_LINES = ("life", "motor", "accident")
RETAIL = ("motor", "accident")


def _e(lines, source_id, page_no, quote):
    return {"lines": lines, "source_id": source_id, "page_no": page_no, "quote": quote}


CATALOGUE = {
    "lodge": [
        _e(("life",), PPI, 110, "Where the policyholder / beneficiary is not satisfied with the services of the "
           "insurer or the distribution channel, he / she can lodge the complaints directly with the insurer"),
        _e(RETAIL, PPI, 134, "Where the policyholder / beneficiary is not satisfied with the services of the "
           "insurer or the distribution channel, he / she can lodge the complaints directly with the insurer"),
    ],
    "resolve14": [
        _e(("life",), PPI, 111, "Insurers should provide resolution to the complaint within 14 days along with "
           "the reasons for not accepting the complaint with specific reference to the relevant terms and "
           "conditions of the policy."),
        _e(RETAIL, PPI, 135, "Insurers should provide resolution to the complaint within 14 days along with "
           "the reasons for not accepting the complaint with specific reference to the relevant terms and "
           "conditions of the policy."),
    ],
    # evidence for which lines the insurer statements cover (checked, not displayed)
    "scope_retail_general": [
        _e(RETAIL, PPI, 126, "This section is applicable in case of retail products ie., an insurance product "
           "designed for individuals or households as also for micro or small businesses."),
        _e(("motor",), PPI, 130, "Motor and Homeowner (Fire) Insurance largely cater to retail customers."),
    ],
    "omb_scope": [
        _e(SUPPORTED_LINES, OMB, 1, "These rules shall apply to all insurers and their agents and intermediaries "
           "in respect of complaints of all personal lines of insurance, group insurance policies, policies "
           "issued to sole proprietorship and micro enterprises."),
    ],
    "omb_personal_lines": [
        _e(SUPPORTED_LINES, OMB, 1, "“personal lines” means an insurance policy taken or given in an individual "
           "capacity;"),
    ],
    "omb_repudiation": [
        _e(SUPPORTED_LINES, OMB, 8, "any partial or total repudiation of claims by the life insurer, General "
           "insurer or the health insurer"),
    ],
    "omb_first_write": [
        _e(SUPPORTED_LINES, OMB, 10, "No complaint to the Insurance Ombudsman shall lie unless— (a) the "
           "complainant has made a representation in writing or through electronic mail or online through "
           "website of the insurer or insurance broker concerned to the insurer or the insurance broker, as "
           "the case may be, named in the complaint"),
    ],
    "omb_wait": [
        _e(SUPPORTED_LINES, OMB, 10, "the complainant had not received any reply within a period of one month "
           "after the insurer or the insurance broker, as the case may be, received his representation"),
    ],
    "omb_year": [
        _e(SUPPORTED_LINES, OMB, 10, "(b) The complaint is made within one year— (i) after the order of the "
           "insurer or the insurance broker, as the case may be, rejecting the representation is received;"),
    ],
    "omb_no_court": [
        _e(SUPPORTED_LINES, OMB, 10, "No complaint before the Insurance Ombudsman shall be maintainable on the "
           "same subject matter on which proceedings are pending before or disposed of by any court or "
           "consumer forum or arbitrator."),
    ],
    "omb_award": [
        _e(SUPPORTED_LINES, OMB, 12, "not award compensation exceeding rupees thirty lakhs (including relevant "
           "expenses, if any)"),
    ],
}
# The params the catalogue wording describes. Dates are computed only when the approved card agrees.
EXPECTED = {"insurer_reply_days": 14, "ombudsman_wait_months": 1, "ombudsman_limit_months": 12}


def _quote(statement: str, line: str) -> dict | None:
    return next((e for e in CATALOGUE[statement] if line in e["lines"]), None)


# ---------- building blocks ----------

def B(en: str, hi: str) -> dict:
    return {"en": en, "hi": hi}


MISSING_COMPLAINT = B("Add the date you sent your complaint to see your Ombudsman dates",
                      "अपनी शिकायत भेजने की तारीख़ जोड़ें, तब आपकी लोकपाल की तारीख़ें दिखेंगी")
NEEDS_CHALLENGEABLE = B("Deadlines apply when a finding is challengeable.",
                        "समय-सीमाएँ तब लागू होती हैं जब कोई निष्कर्ष चुनौती देने योग्य हो।")
NEEDS_CARD = B("Deadlines need the grievance-route rule card to be approved",
               "समय-सीमाओं के लिए शिकायत-मार्ग नियम कार्ड का अनुमोदित होना आवश्यक है")
VERDICT_TEXT = {
    "CHALLENGEABLE": B("Challengeable", "चुनौती दी जा सकती है"),
    "CONSISTENT": B("No ground to challenge under this rule", "इस नियम के तहत चुनौती का आधार नहीं"),
    "NEED_INFO": B("Need more information", "और जानकारी चाहिए"),
}
_ORDER = {"CHALLENGEABLE": 0, "NEED_INFO": 1, "CONSISTENT": 2}


def item(text: dict | None = None, *, key=None, rule_id=None, quote=None, page_no=None, source_id=None,
         source_label=None, date_=None, date_label=None, link=None) -> dict:
    text, date_label, source_label = (copy.deepcopy(x) for x in (text, date_label, source_label))  # never shared
    return {"key": key, "rule_id": rule_id, "text": text, "quote": quote, "page_no": page_no,
            "source_id": source_id, "source_title": SOURCE_TITLES.get(source_id) if source_id else None,
            "source_label": source_label,
            "date": {"iso": date_.isoformat(), "display": date_.strftime("%d/%m/%Y")} if date_ else None,
            "date_label": date_label, "link": link}


def step(sid: str, title: dict, items: list[dict]) -> dict:
    return {"id": sid, "title": title, "items": items}


def _cited(statement: str, line: str, text: dict, **kw) -> dict:
    e = _quote(statement, line)
    return item(text, quote=e["quote"], page_no=e["page_no"], source_id=e["source_id"], **kw)


class _Extras:
    """What verify() may accept besides the findings: official quotes, user/param dates, values."""

    def __init__(self):
        self.quotes: list[str] = []
        self.dates: set[date] = set()
        self.values: set[tuple] = set()

    def collect(self, steps: list[dict]):
        self.values.update(("int", n) for n in range(1, len(steps) + 1))  # the step numbers
        for s in steps:
            for i in s["items"]:
                if i["quote"]:
                    self.quotes.append(i["quote"])
                if i["source_title"]:
                    self.quotes.append(i["source_title"])
                if i["page_no"] is not None:
                    self.values.add(("int", i["page_no"]))
                if i["date"]:
                    self.dates.add(date.fromisoformat(i["date"]["iso"]))

    def kwargs(self) -> dict:
        return {"extra_quotes": tuple(self.quotes), "extra_dates": tuple(sorted(self.dates)),
                "extra_values": tuple(sorted(self.values, key=str))}


def _params_ok(params: dict | None) -> bool:
    if not params:
        return False
    try:
        return all(_v(params, k) == v for k, v in EXPECTED.items())
    except KeyError:
        return False


# ---------- general plan (not health) ----------

def _papers() -> dict:
    return step("papers", B("Keep your papers in order", "अपने कागज़ात संभालकर रखें"), [
    item(B("Keep copies of your policy, the claim form, the rejection letter and all bills and reports.",
           "पॉलिसी, दावा फ़ॉर्म, अस्वीकृति पत्र और सभी बिल व रिपोर्ट की प्रतियाँ रखें।")),
    item(B("Write down the date of every call, visit, letter or email with the insurer.",
           "बीमाकर्ता से हर कॉल, मुलाक़ात, पत्र या ईमेल की तारीख़ लिखकर रखें।"))])

ASK_REASONS = B("Ask the insurer in writing for the reasons for its decision, and for the policy terms it relied on.",
                "बीमाकर्ता से उसके फ़ैसले के कारण, और जिन पॉलिसी शर्तों पर वह आधारित है, लिखित में माँगें।")
NOT_VERIFIED = B("We have not verified the complaint route for this type of insurance.",
                 "हमने इस प्रकार के बीमा के लिए शिकायत का रास्ता जाँचा नहीं है।")
UNVERIFIED_HELP = {
    "crop": B("Government crop schemes can have their own complaint process that this tool has not verified. "
              "Contact the insurer in writing, and ask at the local agriculture office or your bank branch "
              "which process applies to you.",
              "सरकारी फ़सल योजनाओं की अपनी शिकायत प्रक्रिया हो सकती है, जिसे यह टूल जाँच नहीं पाया है। "
              "बीमाकर्ता को लिखित में संपर्क करें, और स्थानीय कृषि कार्यालय या अपनी बैंक शाखा से पूछें "
              "कि आपके लिए कौन-सी प्रक्रिया है।"),
    "credit_life": B("Contact the insurer in writing, and ask the bank branch or lender that arranged the cover "
                     "which complaint process applies to you.",
                     "बीमाकर्ता को लिखित में संपर्क करें, और जिस बैंक शाखा या ऋणदाता ने यह कवर दिलाया उससे पूछें "
                     "कि आपके लिए कौन-सी शिकायत प्रक्रिया है।"),
    "other": B("Contact the insurer in writing and ask which complaint process applies to your policy.",
               "बीमाकर्ता को लिखित में संपर्क करें और पूछें कि आपकी पॉलिसी के लिए कौन-सी शिकायत प्रक्रिया है।"),
}


def _date_items(params, complaint, reply, line):
    """(insurer_reply_by, earliest, latest) items' date parts, or None when not computable."""
    if complaint is None or not _params_ok(params) or (reply and reply < complaint):
        return None
    d = deadlines(complaint, reply, params=params)
    src = deadline_sources(params, complaint, reply)
    return d, src


def general_plan(line: str, *, params: dict | None, complaint_date: date | None,
                 reply_date: date | None) -> tuple[dict, dict]:
    """The non-health plan. NOT a verdict. Returns (plan, verify-extras)."""
    supported = line in SUPPORTED_LINES
    steps = [_papers()]
    ask = [item(ASK_REASONS)]
    unverified = None
    if supported:
        card_ok = _params_ok(params)
        timing = bool(reply_date and complaint_date is None)
        dated = _date_items(params, complaint_date, reply_date, line) if card_ok else None
        d, src = dated if dated else (None, None)
        ask.append(_cited("lodge", line, B(
            "You can lodge the complaint directly with the insurer.",
            "आप शिकायत सीधे बीमाकर्ता के पास दर्ज करा सकते हैं।")))
        ask.append(_cited("resolve14", line, B(
            "The insurer should give a resolution within 14 days, with the reasons if it does not accept the complaint.",
            "बीमाकर्ता को 14 दिनों में समाधान देना चाहिए, और शिकायत न मानने पर कारण भी बताने चाहिए।"),
            key="insurer_reply_by", date_=d.insurer_reply_by if d else None,
            date_label=B("Insurer should reply by", "बीमाकर्ता को जवाब देना चाहिए"),
        ))
        miss = item(MISSING_COMPLAINT, key="missing_dates")
        if card_ok and (complaint_date is None or timing):
            ask.append(miss)
        steps.append(step("insurer", B("Write to the insurer", "बीमाकर्ता को लिखें"), ask))

        e_label = src["ombudsman_earliest"].get("label") if src else None
        omb_wait = _quote("omb_wait", line)
        earliest_kw = ({"source_label": B("your insurer's reply date (entered by you)",
                                          "बीमाकर्ता के जवाब की तारीख़ (आपके द्वारा दी गई)")}
                       if e_label else {})
        repud = ("by a life insurer" if line == "life" else "by a general insurer")
        omb = [
            _cited("omb_scope", line, B(
                "The Rules cover complaints about personal lines of insurance (policies taken in an individual "
                "capacity), group insurance policies, and policies of sole proprietorships and micro enterprises. "
                "Check which of these your policy is.",
                "ये नियम व्यक्तिगत बीमा (व्यक्ति के रूप में ली गई पॉलिसियाँ), समूह बीमा पॉलिसियों, और एकल "
                "स्वामित्व व सूक्ष्म उद्यमों की पॉलिसियों से जुड़ी शिकायतों पर लागू हैं। देखें कि आपकी पॉलिसी इनमें से कौन-सी है।")),
            _cited("omb_repudiation", line, B(
                f"The Insurance Ombudsman can receive complaints about partial or total repudiation of claims {repud}.",
                "बीमा लोकपाल दावे के आंशिक या पूर्ण अस्वीकार (दावा ठुकराए जाने) से जुड़ी शिकायतें ले सकता है।")),
            _cited("omb_first_write", line, B(
                "The Ombudsman takes a complaint only after you have first made a written representation to the insurer.",
                "लोकपाल शिकायत तभी लेता है जब आप पहले बीमाकर्ता को लिखित में अपनी बात दे चुके हों।")),
            _cited("omb_wait", line, B(
                "You can go to the Insurance Ombudsman if the insurer rejects the complaint, or does not reply "
                "within 1 month of receiving it, or you are not satisfied with its reply.",
                "बीमाकर्ता शिकायत ठुकरा दे, या मिलने के 1 महीने में जवाब न दे, या उसके जवाब से आप संतुष्ट न हों, "
                "तो आप बीमा लोकपाल के पास जा सकते हैं।"),
                key="ombudsman_earliest", date_=d.ombudsman_earliest if d else None,
                date_label=B("Ombudsman complaint earliest from", "लोकपाल में शिकायत कम से कम इस तारीख़ से"),
                **earliest_kw),
            _cited("omb_year", line, B(
                "The complaint to the Ombudsman must be made within 1 year, counted as the rule below says.",
                "लोकपाल को शिकायत 1 वर्ष के भीतर करनी होती है, जैसा नीचे दिए नियम में लिखा है।"),
                key="ombudsman_latest", date_=d.ombudsman_latest if d else None,
                date_label=B("Ombudsman complaint no later than", "लोकपाल में शिकायत अधिकतम इस तारीख़ तक")),
            _cited("omb_no_court", line, B(
                "An Ombudsman complaint is not maintainable on a subject that a court, consumer forum or "
                "arbitrator is already hearing or has decided. Take this into account before going elsewhere.",
                "जिस विषय पर कोई अदालत, उपभोक्ता मंच या मध्यस्थ पहले से सुनवाई कर रहा हो या फ़ैसला दे चुका हो, "
                "उस पर लोकपाल की शिकायत स्वीकार्य नहीं है। कहीं और जाने से पहले इसका ध्यान रखें।")),
        ]
        if card_ok and (complaint_date is None or timing):
            omb.append(miss)
        steps.append(step("ombudsman", B("If the insurer rejects the complaint, does not reply, or you are not "
                                         "satisfied", "यदि बीमाकर्ता शिकायत ठुकरा दे, जवाब न दे, या आप संतुष्ट न हों"),
                          omb))
        steps.append(step("limit", B("What the Ombudsman can award", "लोकपाल क्या अवॉर्ड दे सकता है"), [
            _cited("omb_award", line, B(
                "The Ombudsman cannot award more than the amount in the rule below, including expenses. "
                "This tool has not checked other routes for larger claims.",
                "लोकपाल नीचे दिए नियम में लिखी राशि (खर्चों सहित) से अधिक अवॉर्ड नहीं दे सकता। "
                "बड़े दावों के लिए अन्य रास्ते इस टूल ने जाँचे नहीं हैं।"))]))
    else:
        unverified = NOT_VERIFIED
        steps.append(step("ask", B("Ask the insurer in writing", "बीमाकर्ता से लिखित में पूछें"), ask))
        steps.append(step("route", B("Complaint route", "शिकायत का रास्ता"),
                          [item(NOT_VERIFIED, key="not_verified"), item(UNVERIFIED_HELP[line])]))
    ex = _Extras()
    ex.collect(steps)
    if complaint_date and supported:
        ex.dates.add(complaint_date)
    if supported:  # "1 month" / "1 year" in the prose: the quotes spell these as words
        ex.values |= {("months", 1), ("months", 12)}
    plan = {"kind": "general", "supported": False, "product_line": line, "unverified": unverified,
            "title": B(_tpl("en")["labels"]["general_title"], _tpl("hi")["labels"]["general_title"]),
            "steps": steps}
    return plan, ex.kwargs()


# ---------- "Your plan" (health) ----------

def _cited_param(src: dict | None, text: dict, **kw) -> dict:
    src = src or {}
    return item(text, quote=src.get("quote"), page_no=src.get("page_no") if src.get("quote") else None,
                source_id=src.get("source_id") if src.get("quote") else None, **kw)


def health_plan(findings: list[Finding], *, params: dict | None, complaint_date: date | None,
                reply_date: date | None, claim_amount) -> tuple[dict, dict]:
    ordered = sorted(findings, key=lambda f: _ORDER[f.verdict])
    steps = []
    s1 = [item(VERDICT_TEXT[f.verdict], rule_id=f.rule_id, quote=f.rule_quote, page_no=f.page_no)
          for f in ordered]
    if not s1:
        s1 = [item(B(_tpl("en")["labels"]["no_rule"], _tpl("hi")["labels"]["no_rule"]))]
    steps.append(step("findings", B("What the check found", "जाँच में क्या मिला"), s1))

    asks = []
    for f in ordered:
        if f.verdict == "CONSISTENT":
            continue
        parts = {}
        for lang in ("en", "hi"):
            lb = _tpl(lang)["labels"]
            bits = []
            if f.verdict == "NEED_INFO" and (q := _localised(f, lang, "question", lb["english_marker"])):
                bits.append(f'{lb["question_label"]}: {q}')
            if a := _localised(f, lang, "action", lb["english_marker"]):
                bits.append(f'{lb["action_label"]}: {a}')
            parts[lang] = " ".join(bits)
        if parts["en"]:
            asks.append(item(B(parts["en"], parts["hi"]), rule_id=f.rule_id))
    asks.append(item(ASK_REASONS))
    steps.append(step("ask", B("What to ask your insurer for", "बीमाकर्ता से क्या माँगें"), asks))

    challengeable = any(f.verdict == "CHALLENGEABLE" for f in findings)
    d = src = None
    letter, omb = [], []
    if not challengeable:
        letter, omb = [item(NEEDS_CHALLENGEABLE)], [item(NEEDS_CHALLENGEABLE)]
    elif not params:
        letter, omb = [item(NEEDS_CARD)], [item(NEEDS_CARD)]
    else:
        if reply_date and complaint_date is None:
            letter, omb = [item(MISSING_COMPLAINT)], [item(MISSING_COMPLAINT)]
        else:
            letter.append(item(B("Download the grievance letter, check it, and send it to your insurer.",
                                 "शिकायत पत्र डाउनलोड करें, उसे जाँचें, और अपने बीमाकर्ता को भेजें।"),
                               key="letter", link="letter"))
            if complaint_date is None:
                letter.append(item(MISSING_COMPLAINT, key="missing_dates"))
                omb.append(item(MISSING_COMPLAINT, key="missing_dates"))
            else:
                d = deadlines(complaint_date, reply_date, params=params)
                src = deadline_sources(params, complaint_date, reply_date)
                letter.append(item(B("Date you sent your complaint (entered by you)",
                                     "आपके द्वारा दी गई शिकायत भेजने की तारीख़"),
                                   key="complaint_sent", date_=complaint_date))
                letter.append(_cited_param(
                    src.get("insurer_reply_by"),
                    B("The insurer should reply by this date, counted from the date you sent your complaint.",
                      "बीमाकर्ता को शिकायत भेजने की तारीख़ से गिनकर इस तारीख़ तक जवाब देना चाहिए।"),
                    key="insurer_reply_by", date_=d.insurer_reply_by,
                    date_label=B("Insurer should reply by", "बीमाकर्ता को जवाब देना चाहिए")))
                e = src.get("ombudsman_earliest") or {}
                omb.append(_cited_param(
                    e, B("If the insurer has not replied, rejects your complaint, or its reply does not satisfy "
                         "you, you can take the complaint to the Insurance Ombudsman from this date.",
                         "यदि बीमाकर्ता जवाब न दे, आपकी शिकायत ठुकरा दे, या उसका जवाब आपको संतुष्ट न करे, तो आप "
                         "इस तारीख़ से शिकायत बीमा लोकपाल के पास ले जा सकते हैं।"),
                    key="ombudsman_earliest", date_=d.ombudsman_earliest,
                    date_label=B("Ombudsman complaint earliest from", "लोकपाल में शिकायत कम से कम इस तारीख़ से"),
                    source_label=(B("your insurer's reply date (entered by you)",
                                    "बीमाकर्ता के जवाब की तारीख़ (आपके द्वारा दी गई)") if e.get("label") else None)))
                omb.append(_cited_param(
                    src.get("ombudsman_latest"),
                    B("The complaint to the Ombudsman must be made by this date.",
                      "लोकपाल को शिकायत इस तारीख़ तक करनी होती है।"),
                    key="ombudsman_latest", date_=d.ombudsman_latest,
                    date_label=B("Ombudsman complaint no later than", "लोकपाल में शिकायत अधिकतम इस तारीख़ तक")))
    steps.append(step("letter", B("Send your grievance letter", "अपना शिकायत पत्र भेजें"), letter))
    steps.append(step("ombudsman", B("If there is no reply, or it does not settle the matter: Insurance Ombudsman",
                                     "जवाब न मिले या बात न सुलझे तो: बीमा लोकपाल"), omb))
    values = set()
    if params and claim_amount not in (None, ""):
        notes = {lang: cap_note_text(claim_amount, params, lang).strip() for lang in ("en", "hi")}
        if notes["en"]:
            steps.append(step("commission", B("If your claim is larger than the Ombudsman's limit",
                                              "यदि आपका दावा लोकपाल की सीमा से बड़ा हो"),
                              [item(B(notes["en"], notes["hi"]), key="commission")]))
            values.add(("inr", float(claim_amount)))
            for k in ("ombudsman_claim_limit_inr", "ombudsman_award_cap_inr"):
                if k in params:
                    values.add(("inr", _v(params, k)))
    ex = _Extras()
    ex.collect(steps)
    ex.values |= values
    if complaint_date:
        ex.dates.add(complaint_date)
    if reply_date:
        ex.dates.add(reply_date)
    plan = {"kind": "health", "supported": True, "product_line": "health", "unverified": None,
            "title": B("Your plan", "आपकी योजना"), "steps": steps}
    return plan, ex.kwargs()


# ---------- text, verification ----------

def plan_text(plan: dict, lang: str) -> str:
    """Plain text of the whole plan in one language: what verify() checks and what prints."""
    page = "पृष्ठ" if lang == "hi" else "page"
    lines = [plan["title"][lang], ""]
    for n, s in enumerate(plan["steps"], 1):
        lines.append(f"{n}. {s['title'][lang]}")
        for i in s["items"]:
            head = (i["rule_id"] + ": ") if i["rule_id"] else ""
            if i["text"]:
                lines.append(f"- {head}{i['text'][lang]}")
            elif head:
                lines.append(f"- {head.rstrip(': ')}")
            if i["date"]:
                lines.append(f"  {i['date_label'][lang] if i['date_label'] else ''}: {i['date']['display']}".replace(
                    "  : ", "  "))
            if i["quote"]:
                src = i["source_title"] or ""
                pg = f"{page} {i['page_no']}" if i["page_no"] is not None else ""
                tail = ", ".join(x for x in (src, pg) if x)
                suffix = " (अंग्रेज़ी में)" if lang == "hi" else ""
                lines.append(f'  "{i["quote"]}"' + (f" — {tail}" if tail else "") + suffix)
            if i["source_label"]:
                lines.append(f"  {i['source_label'][lang]}")
        lines.append("")
    lines.append(_tpl(lang)["labels"]["footer"])
    return "\n".join(lines)


def finalize(plan: dict, extras: dict, findings: list[Finding]) -> dict | None:
    """Attach the plain text and run the existing verify() on both languages. A plan whose
    text does not pass is not shown (None): the UI then simply has no plan section."""
    texts = {lang: plan_text(plan, lang) for lang in ("en", "hi")}
    for lang, t in texts.items():
        r = verify(t, findings, **extras)
        if not r.ok:
            log.error("plan failed verify lang=%s problems=%d", lang, len(r.problems))
            return None
    plan["text"] = texts
    plan["verified"] = True
    return plan
