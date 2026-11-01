"""Deterministic rule engine: approved rule cards + confirmed facts -> findings.

Only approved, quote-verified cards may be passed in. Missing facts or an
out-of-force rule give NEED_INFO, never a favourable verdict.
"""
from collections import defaultdict
from datetime import date, datetime

from sarthi.core.derive import INPUT_FACTS, claim_key, derive_inputs, usable
from sarthi.core.expr import evaluate, names
from sarthi.core.models import FactValue, Finding, RuleCard


def _jsonable(v):
    if isinstance(v, (date, datetime)):
        return v.isoformat()
    if isinstance(v, (list, tuple)):
        return [_jsonable(x) for x in v]
    if isinstance(v, dict):
        return {str(k): _jsonable(x) for k, x in v.items()}
    return v


def _used(facts: dict[str, FactValue], keys) -> dict[str, dict]:
    return {k: {"value": _jsonable(facts[k].value), "quote": facts[k].quote,
                "page_no": facts[k].page_no}
            for k in dict.fromkeys(keys) if usable(facts, k)}


def _finding(card: RuleCard, verdict, reason, facts, keys) -> Finding:
    return Finding(
        rule_id=card.rule_id, rule_version=card.version, verdict=verdict, reason=reason,
        rule_quote=card.quote, source_sha256=card.source_sha256, page_no=card.page_no,
        facts_used=_used(facts, keys),
        question_en=card.question_en, question_hi=card.question_hi,
        action_en=card.action_en, action_hi=card.action_hi)


def _relevant_date(card: RuleCard, facts) -> tuple[date | None, str | None, list[str]]:
    """(date, missing_field, fact_keys_used)."""
    ck = claim_key(facts)  # "admission_date" stands in when claim_date is absent
    if card.applies_by == "claim_date":
        if usable(facts, ck):
            return facts[ck].value, None, [ck]
        return None, "claim_date", []
    if card.applies_by == "policy_start_or_renewal":
        if not usable(facts, ck):
            return None, "claim_date", []
        if not usable(facts, "inception_date"):
            return None, "inception_date", []
        claim = facts[ck].value
        cands = [("inception_date", facts["inception_date"].value)]
        if usable(facts, "policy_renewal_date"):
            cands.append(("policy_renewal_date", facts["policy_renewal_date"].value))
        # latest policy start/renewal on or before the claim; later renewals are ignored
        cands = [(k, v) for k, v in cands if v <= claim]
        if not cands:
            return None, "inception_date", []  # policy not yet started at claim date
        return max(v for _, v in cands), None, [ck] + [k for k, _ in cands]
    return None, None, []


def _in_force(card: RuleCard, d: date) -> bool:
    return (card.in_force_from is not None and card.in_force_from <= d
            and (card.in_force_to is None or d < card.in_force_to))


def run_rules(facts: dict[str, FactValue], cards: list[RuleCard]) -> list[Finding]:
    for c in cards:
        if c.status != "approved" or not c.quote or not c.source_sha256:
            raise ValueError(
                f"{c.rule_id} v{c.version}: card is not approved or has no quote/source_sha256; "
                "run_rules accepts only approved, verified cards")
    if not usable(facts, "rejection_ground"):
        return []
    ground = facts["rejection_ground"].value
    derived = derive_inputs(facts)

    by_rule: dict[str, list[RuleCard]] = defaultdict(list)
    for c in cards:
        triggers = c.triggers if isinstance(c.triggers, list) else list(c.triggers)
        if ground in triggers:
            by_rule[c.rule_id].append(c)

    findings: list[Finding] = []
    for rule_id in sorted(by_rule):
        versions = sorted(by_rule[rule_id], key=lambda c: c.version)
        latest = versions[-1]
        d, missing, date_keys = _relevant_date(latest, facts)
        if d is None:
            reason = f"missing_{missing}" if missing else "unsupported_applies_by"
            findings.append(_finding(latest, "NEED_INFO", reason, facts, []))
            continue
        in_force = [c for c in versions if _in_force(c, d)]
        if not in_force:
            findings.append(_finding(latest, "NEED_INFO", "rule_not_in_force", facts, date_keys))
            continue
        card = in_force[-1]
        input_names = sorted(names(card.condition)) if card.condition else []
        keys = list(date_keys)
        for n in input_names:
            keys.extend(INPUT_FACTS.get(n, ()))
        keys = [claim_key(facts) if k == "claim_date" else k for k in keys]
        if not card.condition:
            findings.append(_finding(card, "NEED_INFO", "condition_not_automated", facts, keys))
            continue
        result = evaluate(card.condition, derived)
        if result is None:
            miss = [n for n in input_names if derived.get(n) is None]
            findings.append(_finding(
                card, "NEED_INFO", "missing_inputs: " + ", ".join(miss), facts, keys))
        else:
            verdict = card.if_true if result else card.if_false
            findings.append(_finding(
                card, verdict, "condition_met" if result else "condition_not_met", facts, keys))
    return findings
