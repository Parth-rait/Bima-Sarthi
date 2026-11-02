// Ported from the legacy page; a test pins these to sarthi/app/labels.py and sarthi/app/plan.py.
// DRAFT: Hindi text is pending human review (Q-007).
export const REJECTION_GROUNDS = ["non_disclosure","pre_existing_disease","specific_waiting_period","initial_waiting_period","portability","exclusion","deduction","room_rent","sub_limit","cashless_delay","discharge_delay","process_defect","other"] as const;
export type RejectionGround = (typeof REJECTION_GROUNDS)[number];

export const GROUND_LABEL: Record<'en' | 'hi', Record<RejectionGround, string>> = {
  en: {
    non_disclosure: "Non-disclosure of information",
    pre_existing_disease: "Pre-existing disease",
    specific_waiting_period: "Specific-illness waiting period",
    initial_waiting_period: "Initial waiting period",
    portability: "Portability or continuity",
    exclusion: "Listed exclusion",
    deduction: "Deduction from the bill",
    room_rent: "Room-rent limit",
    sub_limit: "Sub-limit",
    cashless_delay: "Cashless approval delay",
    discharge_delay: "Discharge delay",
    process_defect: "Process defect in the rejection",
    other: "Other reason",
  },
  hi: {
    non_disclosure: "जानकारी न बताना",
    pre_existing_disease: "पहले से मौजूद बीमारी",
    specific_waiting_period: "विशिष्ट बीमारी की प्रतीक्षा अवधि",
    initial_waiting_period: "शुरुआती प्रतीक्षा अवधि",
    portability: "पोर्टेबिलिटी या निरंतरता",
    exclusion: "सूचीबद्ध अपवर्जन",
    deduction: "बिल से कटौती",
    room_rent: "कमरे के किराये की सीमा",
    sub_limit: "उप-सीमा",
    cashless_delay: "कैशलेस मंज़ूरी में देरी",
    discharge_delay: "डिस्चार्ज में देरी",
    process_defect: "अस्वीकृति की प्रक्रिया में कमी",
    other: "अन्य कारण",
  },
};

export const PRODUCT_KEYS = ["health","life","accident","motor","crop","credit_life","other"] as const;
export type ProductLine = (typeof PRODUCT_KEYS)[number];

export const PRODUCT_LABEL: Record<'en' | 'hi', Record<ProductLine, string>> = {
  en: {
    health: "Health",
    life: "Life",
    accident: "Accident",
    motor: "Motor",
    crop: "Crop (agriculture)",
    credit_life: "Loan-linked or credit-life",
    other: "Other",
  },
  hi: {
    health: "स्वास्थ्य",
    life: "जीवन",
    accident: "दुर्घटना",
    motor: "मोटर (वाहन)",
    crop: "फ़सल (कृषि)",
    credit_life: "ऋण से जुड़ा या क्रेडिट-लाइफ़",
    other: "अन्य",
  },
};
