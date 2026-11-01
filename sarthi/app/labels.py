"""User-facing names for fact and input keys, so snake_case never reaches the UI,
explanations or the letter.

Hindi labels are a DRAFT pending human review (Q-007), like the rest of the Hindi text.
"""
# key -> (English, Hindi draft Q-007)
LABELS: dict[str, tuple[str, str]] = {
    # facts
    "inception_date": ("policy start date", "पॉलिसी शुरू होने की तारीख़"),
    "ported_from_date": ("date ported from the previous insurer", "पिछले बीमाकर्ता से पोर्ट की तारीख़"),
    "claim_date": ("claim date", "दावे की तारीख़"),
    "admission_date": ("hospital admission date", "अस्पताल में भर्ती की तारीख़"),
    "rejection_ground": ("reason given for rejection", "अस्वीकृति का बताया गया कारण"),
    "disclosed_conditions": ("conditions disclosed", "बताई गई बीमारियाँ"),
    "alleged_undisclosed_condition": ("condition alleged as not disclosed", "जिस बीमारी को न बताने का आरोप है"),
    "fraud_alleged": ("fraud alleged", "धोखाधड़ी का आरोप"),
    "deductions": ("deductions from the bill", "बिल से कटौतियाँ"),
    "cashless_request_at": ("cashless request time", "कैशलेस अनुरोध का समय"),
    "decision_at": ("insurer decision time", "बीमाकर्ता के फ़ैसले का समय"),
    "discharge_request_at": ("discharge request time", "डिस्चार्ज अनुरोध का समय"),
    "final_auth_at": ("final authorisation time", "अंतिम मंज़ूरी का समय"),
    "cited_clause": ("policy clause cited", "बताई गई पॉलिसी धारा"),
    "crc_approval_mentioned": ("committee approval mentioned", "समिति की मंज़ूरी का ज़िक्र"),
    "reasons_cite_terms": ("reasons cite policy terms", "कारणों में पॉलिसी शर्तों का हवाला"),
    "renewal_gap_days": ("gap before renewal (days)", "नवीनीकरण से पहले अंतराल (दिन)"),
    "continuity_confirmed": ("cover was continuous", "कवर लगातार था"),
    "policy_renewal_date": ("policy renewal date", "पॉलिसी नवीनीकरण की तारीख़"),
    "cited_clause_found": ("cited clause found in the policy", "बताई गई धारा पॉलिसी में मिली"),
    # letter details
    "policyholder_name": ("name on the policy", "पॉलिसी पर नाम"),
    "policy_number": ("policy number", "पॉलिसी संख्या"),
    "claim_number": ("claim number", "दावा संख्या"),
    "claim_amount_inr": ("claim amount", "दावे की राशि"),
    "insurer_name": ("insurer name", "बीमाकर्ता का नाम"),
    "complaint_sent_date": ("date you sent your complaint to the insurer",
                            "बीमाकर्ता को शिकायत भेजने की तारीख़"),
    # derived rule inputs
    "continuous_cover_months": ("months of continuous cover", "लगातार कवर के महीने"),
    "ped_disclosed": ("whether the condition was disclosed", "क्या बीमारी बताई गई थी"),
    "deduction_items": ("deducted items", "कटी हुई मदें"),
    "nonpayable_overcharge_inr": ("wrongly deducted non-payable amount", "गलत तरह से काटी गई गैर-भुगतान योग्य राशि"),
    "cashless_minutes": ("cashless decision time", "कैशलेस फ़ैसले में लगा समय"),
    "discharge_minutes": ("discharge approval time", "डिस्चार्ज मंज़ूरी में लगा समय"),
    # deduction item fields
    "item": ("item", "मद"),
    "amount": ("amount", "राशि"),
    "reason": ("reason", "कारण"),
    "nonpayable_listed": ("on the standard non-payable list", "मानक गैर-भुगतान सूची में"),
}


def label(key: str, lang: str = "en") -> str:
    """Readable name for a key; unknown keys fall back to the key with spaces."""
    pair = LABELS.get(str(key))
    if pair is None:
        return str(key).replace("_", " ")
    return pair[1] if lang == "hi" else pair[0]


def labels_json() -> dict[str, dict[str, str]]:
    return {k: {"en": en, "hi": hi} for k, (en, hi) in LABELS.items()}


# Rejection-ground VALUES (single source; the UI select embeds a copy that a test pins to this).
# Hindi: DRAFT pending human review (Q-007).
GROUND_LABELS: dict[str, tuple[str, str]] = {
    "non_disclosure": ("Non-disclosure of information", "जानकारी न बताना"),
    "pre_existing_disease": ("Pre-existing disease", "पहले से मौजूद बीमारी"),
    "specific_waiting_period": ("Specific-illness waiting period", "विशिष्ट बीमारी की प्रतीक्षा अवधि"),
    "initial_waiting_period": ("Initial waiting period", "शुरुआती प्रतीक्षा अवधि"),
    "portability": ("Portability or continuity", "पोर्टेबिलिटी या निरंतरता"),
    "exclusion": ("Listed exclusion", "सूचीबद्ध अपवर्जन"),
    "deduction": ("Deduction from the bill", "बिल से कटौती"),
    "room_rent": ("Room-rent limit", "कमरे के किराये की सीमा"),
    "sub_limit": ("Sub-limit", "उप-सीमा"),
    "cashless_delay": ("Cashless approval delay", "कैशलेस मंज़ूरी में देरी"),
    "discharge_delay": ("Discharge delay", "डिस्चार्ज में देरी"),
    "process_defect": ("Process defect in the rejection", "अस्वीकृति की प्रक्रिया में कमी"),
    "other": ("Other reason", "अन्य कारण"),
}

def value_label(v: str, lang: str = "en") -> str:
    """Label for a rejection-ground VALUE by exact lookup. Anything else (names, numbers,
    conditions, unknown codes) is returned exactly as stored."""
    pair = GROUND_LABELS.get(v) if isinstance(v, str) else None
    if pair is None:
        return v
    return pair[1] if lang == "hi" else pair[0]
