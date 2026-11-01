from datetime import date, datetime
from typing import Any, Literal

from pydantic import BaseModel, Field, field_validator

Verdict = Literal["CONSISTENT", "CHALLENGEABLE", "NEED_INFO"]
DocType = Literal["regulation", "circular", "wording", "judgment", "report"]


class Source(BaseModel):
    source_id: str
    url: str
    publisher: str | None = None
    title: str | None = None
    doc_type: DocType | None = None
    published_on: date | None = None
    retrieved_at: datetime | None = None
    sha256: str | None = None
    licence_note: str | None = None


class DocumentPage(BaseModel):
    sha256: str
    page_no: int
    text: str = ""
    char_count: int = 0
    has_text_layer: bool = False
    image_path: str | None = None


GRIEVANCE_PARAMS = ("insurer_reply_days", "ombudsman_wait_months", "ombudsman_limit_months",
                    "ombudsman_claim_limit_inr", "ombudsman_award_cap_inr")
PARAM_KEYS = ("value", "unit", "source_id", "page_no", "quote")


class RuleCard(BaseModel):
    rule_id: str
    version: int
    group: str | None = None
    title_en: str | None = None
    title_hi: str | None = None
    source_sha256: str | None = None
    page_no: int | None = None
    quote: str | None = None
    in_force_from: date | None = None
    in_force_to: date | None = None
    applies_by: str | None = None
    triggers: list | dict = Field(default_factory=list)
    inputs: list | dict = Field(default_factory=list)
    params: dict = Field(default_factory=dict)
    condition: str | None = None
    if_true: str | None = None
    if_false: str | None = None
    question_en: str | None = None
    question_hi: str | None = None
    action_en: str | None = None
    action_hi: str | None = None
    status: Literal["draft", "approved", "disabled"] = "draft"
    approved_by: str | None = None
    approved_at: datetime | None = None
    status_note: str | None = None

    @field_validator("params")
    @classmethod
    def _nested_params_sourced(cls, params: dict) -> dict:
        """A param given as a mapping must carry its own source; flat values stay allowed."""
        for name, p in params.items():
            if isinstance(p, dict):
                missing = [k for k in PARAM_KEYS if k not in p]
                if missing:
                    raise ValueError(f"param {name} missing {missing}")
                if not p["source_id"] or not p["quote"]:
                    raise ValueError(f"param {name} needs a source_id and a quote")
        return params


def missing_grievance_params(card: "RuleCard") -> list[str]:
    """GRIEVANCE_ROUTE must carry all five params as sourced (nested) mappings."""
    if card.rule_id != "GRIEVANCE_ROUTE":
        return []
    return [k for k in GRIEVANCE_PARAMS if not isinstance(card.params.get(k), dict)]


class PolicyProduct(BaseModel):
    product_id: str
    insurer: str | None = None
    product_name: str | None = None
    uin: str | None = None
    wording_sha256: str | None = None
    cis_sha256: str | None = None
    is_standard_product: bool = False


class PolicyClause(BaseModel):
    product_id: str
    clause_no: str
    heading: str | None = None
    text: str = ""
    page_no: int | None = None
    normalised_hash: str | None = None


class Case(BaseModel):
    case_id: str
    source_sha256: str | None = None
    forum: str | None = None
    case_number: str | None = None
    decided_on: date | None = None
    insurer: str | None = None
    product_id: str | None = None
    outcome: Literal["allowed", "partly_allowed", "dismissed"] | None = None
    relief_amount: float | None = None
    appellant: Literal["insurer", "policyholder", "unknown"] | None = None
    policyholder_prevailed: bool | None = None


class CaseIssue(BaseModel):
    case_id: str
    issue: str
    holding: Literal["for_policyholder", "for_insurer", "not_decided"]
    holding_quote: str | None = None
    page_no: int | None = None
    status: Literal["drafted", "needs_review", "reviewed", "corrected", "rejected"] = "drafted"
    reviewer_note: str | None = None


class CaseFact(BaseModel):
    case_id: str
    field: str
    value: str | None = None
    quote: str | None = None
    page_no: int | None = None
    confidence: float | None = None
    status: Literal["extracted", "needs_review", "reviewed", "corrected", "rejected"] = "extracted"
    reviewer_note: str | None = None


class InsurerStat(BaseModel):
    insurer: str
    year: str
    metric: str
    value: float | None = None
    unit: str | None = None
    source_sha256: str | None = None
    page_no: int | None = None


class EvalResult(BaseModel):
    run_id: str
    case_id: str
    method: Literal["rules", "glimmer_only", "spark_only"]
    repeat: int = 0
    backend: str | None = None
    verdicts: dict | list = Field(default_factory=dict)
    agrees_with_outcome: bool | None = None
    false_hope: bool | None = None
    latency_ms: int | None = None
    tokens: int | None = None


class FreshnessAlert(BaseModel):
    alert_id: str
    rule_id: str | None = None
    found_url: str | None = None
    found_title: str | None = None
    found_on: date | None = None
    status: Literal["open", "dismissed", "actioned"] = "open"


class Finding(BaseModel):
    rule_id: str
    rule_version: int
    verdict: Verdict
    reason: str | None
    rule_quote: str
    source_sha256: str
    page_no: int | None
    facts_used: dict[str, dict]
    question_en: str | None = None
    question_hi: str | None = None
    action_en: str | None = None
    action_hi: str | None = None


class FactValue(BaseModel):
    """One extracted/entered fact. `value` is an already-parsed Python value
    (date, datetime, int, bool, str, list)."""
    value: Any = None
    quote: str | None = None
    page_no: int | None = None
    confidence: Literal["high", "medium", "low"] = "high"
    status: Literal["verified", "needs_confirmation", "user_confirmed"] = "verified"
