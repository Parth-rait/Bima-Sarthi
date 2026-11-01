"""Closed vocabularies shared by rule cards, the engine and extraction."""

# The only names a rule-card condition may reference. Task 7's derive_inputs
# must produce exactly these keys.
KNOWN_INPUTS: frozenset[str] = frozenset({
    "continuous_cover_months",
    "claim_date",
    "rejection_ground",
    "ped_disclosed",
    "fraud_alleged",
    "deduction_items",
    "nonpayable_overcharge_inr",
    "cashless_minutes",
    "discharge_minutes",
    "cited_clause_found",
    "crc_approval_mentioned",
    "reasons_cite_terms",
})

# rejection_ground vocabulary used in card `triggers` (and reused by extraction).
REJECTION_GROUNDS: tuple[str, ...] = (
    "non_disclosure",
    "pre_existing_disease",
    "specific_waiting_period",
    "initial_waiting_period",
    "portability",
    "exclusion",
    "deduction",
    "room_rent",
    "sub_limit",
    "cashless_delay",
    "discharge_delay",
    "process_defect",
    "other",
)
