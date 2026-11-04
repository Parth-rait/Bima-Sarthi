"""Rule context: WHAT legal issue a dispute raises vs WHICH approved card(s) can decide it.

1. An issue family (`models.ISSUE_FAMILIES`) names the legal issue. It is not a verdict and not a
   rule id. A model-drafted family never reaches this module as a decision input; callers pass
   only human-reviewed families (or the family of the insurer's reviewed rejection ground).
2. `sarthi/data/rule_families.yaml` lists the CANDIDATE cards of each family.
3. `resolve_rule_context` decides, per candidate and per case, whether the card is applicable:
   product line, approval, verified quote, the rejection ground, fact completeness, the
   applicability date (the card's own `applies_by`; never "claim date for everything") and the
   version in force on it.
Only `applicable` results are handed to the deterministic engine (`applicable_cards`). Everything
else stays a distinct, reported status; nothing is guessed and nothing is silently dropped.
"""
from datetime import date
from pathlib import Path
from typing import Iterable, Literal

import yaml
from pydantic import BaseModel, Field

from sarthi.core.derive import INPUT_FACTS, usable
from sarthi.core.engine import _in_force, _relevant_date
from sarthi.core.expr import names
from sarthi.core.inputs import REJECTION_GROUNDS
from sarthi.core.models import ISSUE_FAMILIES, FactValue, RuleCard

ROOT = Path(__file__).resolve().parents[2]
FAMILY_FILE = ROOT / "sarthi" / "data" / "rule_families.yaml"
SEED_DIR = ROOT / "rules" / "seed"

# Every approved card is a health-insurance regulation card. Any other product line must not run it.
SUPPORTED_PRODUCT_LINES = ("health",)

Status = Literal["applicable", "not_approved", "quote_unverified", "not_in_force",
                 "missing_applicability_date", "missing_required_fact", "unsupported_product",
                 "no_candidate_rule"]
STATUSES = ("applicable", "not_approved", "quote_unverified", "not_in_force",
            "missing_applicability_date", "missing_required_fact", "unsupported_product",
            "no_candidate_rule")


class FamilyMapError(ValueError):
    """rule_families.yaml is inconsistent with the issue families, the grounds or rules/seed."""


class FamilyMap(BaseModel):
    families: dict[str, dict]
    grounds: dict[str, str]

    def cards(self, family: str) -> list[str]:
        return list(self.families[family].get("cards", []))

    def research_needed(self, family: str) -> bool:
        return bool(self.families[family].get("research_needed", False))

    def family_for_ground(self, ground: str | None) -> str | None:
        return self.grounds.get(ground) if ground else None


def seed_rule_ids(seed_dir: Path = SEED_DIR) -> set[str]:
    out = set()
    for p in Path(seed_dir).glob("*.yaml"):
        data = yaml.safe_load(p.read_text(encoding="utf-8")) or {}
        if data.get("rule_id"):
            out.add(data["rule_id"])
    return out


def load_family_map(path: Path = FAMILY_FILE, seed_dir: Path = SEED_DIR) -> FamilyMap:
    """Load and validate: every family present exactly once, every card id exists in rules/seed,
    every rejection ground mapped to a known family."""
    doc = yaml.safe_load(Path(path).read_text(encoding="utf-8")) or {}
    families, grounds = doc.get("families") or {}, doc.get("grounds") or {}
    unknown = sorted(set(families) - set(ISSUE_FAMILIES))
    if unknown:
        raise FamilyMapError(f"unknown issue family in rule_families.yaml: {', '.join(unknown)}")
    missing = [f for f in ISSUE_FAMILIES if f not in families]
    if missing:
        raise FamilyMapError(f"issue family without an entry (use cards: []): {', '.join(missing)}")
    seed = seed_rule_ids(seed_dir)
    for fam, entry in families.items():
        for rid in entry.get("cards") or []:
            if rid not in seed:
                raise FamilyMapError(f"{fam}: rule id {rid} does not exist in rules/seed")
    bad = {g: f for g, f in grounds.items() if g not in REJECTION_GROUNDS or f not in ISSUE_FAMILIES}
    if bad:
        raise FamilyMapError(f"bad ground -> family entries: {bad}")
    absent = [g for g in REJECTION_GROUNDS if g not in grounds]
    if absent:
        raise FamilyMapError(f"rejection grounds without a family: {', '.join(absent)}")
    return FamilyMap(families={f: {"cards": list(e.get("cards") or []),
                                   "research_needed": bool(e.get("research_needed", False))}
                               for f, e in families.items()}, grounds=grounds)


class CandidateResolution(BaseModel):
    family: str | None = None
    rule_id: str | None = None  # None: the family has no candidate card ("*": no family at all)
    version: int | None = None  # the version used (applicable / not_in_force), else the latest
    approved: bool = False
    quote_verified: bool = False
    product_applicable: bool = False
    applies_by: str | None = None
    applicability_date: date | None = None
    date_basis: list[str] = Field(default_factory=list)
    in_force_on_date: bool | None = None
    missing_facts: list[str] = Field(default_factory=list)  # present but unreviewed / flagged
    absent_facts: list[str] = Field(default_factory=list)  # not extracted at all
    status: Status
    reason: str
    warnings: list[str] = Field(default_factory=list)


def _triggers(card: RuleCard) -> list:
    return card.triggers if isinstance(card.triggers, list) else list(card.triggers)


def _date_keys(card: RuleCard) -> tuple[str, ...]:
    if card.applies_by == "claim_date":
        return ("claim_date",)
    if card.applies_by == "policy_start_or_renewal":
        return ("claim_date", "inception_date", "policy_renewal_date")
    return ()


def required_fact_keys(card: RuleCard) -> set[str]:
    """Facts a card reads: its applicability-date facts plus INPUT_FACTS of its condition inputs.
    Same set the app's `ready_for_rules` gate checks."""
    keys = set(_date_keys(card))
    for n in (names(card.condition) if card.condition else []):
        keys.update(INPUT_FACTS.get(n, (n,)))
    return keys


def _pending(facts: dict[str, FactValue], unresolved: dict[str, FactValue] | None):
    """(verified-only base facts, pending = flagged facts + unresolved facts as needs_confirmation)."""
    pending = {k: v for k, v in facts.items() if v.status == "needs_confirmation"}
    for k, v in (unresolved or {}).items():  # an unresolved copy wins: the conservative reading
        pending[k] = v if v.status == "needs_confirmation" else v.model_copy(
            update={"status": "needs_confirmation"})
    base = {k: v for k, v in facts.items() if k not in pending}
    return base, pending


def blocking_fields(cards: list[RuleCard], facts: dict[str, FactValue],
                    unresolved: dict[str, FactValue] | None = None) -> list[str]:
    """Fields that block these cards: a pending (unreviewed / flagged) fact blocks a card when
    marking just that field unconfirmed makes the app's `ready_for_rules` say "not ready" for it.
    Unrelated pending fields block nothing. `claim_date` stands for `admission_date` when no
    claim_date exists at all (the engine's own fallback). Assumes a usable rejection_ground."""
    from sarthi.app.extract import ready_for_rules  # lazy: the app gate is the single source
    base, pending = _pending(facts, unresolved)
    flagged_claim = "claim_date" in pending
    if "claim_date" not in base and not flagged_claim and "admission_date" in pending:
        pending["claim_date"] = pending["admission_date"]
    out = {("admission_date" if k == "claim_date" and not flagged_claim else k)
           for k, fv in pending.items()
           if any(not ready_for_rules({**base, k: fv}, [c]) for c in cards)}
    return sorted(out)


def _ground_state(facts, unresolved) -> tuple[str, str | None]:
    """('usable', ground) | ('unreviewed', None) | ('absent', None)."""
    if usable(facts, "rejection_ground"):
        return "usable", facts["rejection_ground"].value
    f = facts.get("rejection_ground")
    if (f is not None and f.value is not None) or "rejection_ground" in (unresolved or {}):
        return "unreviewed", None
    return "absent", None


def _result(family, rid, **kw) -> CandidateResolution:
    return CandidateResolution(family=family, rule_id=rid, **kw)


def _resolve_card(family, rid, facts, cards, ground_state, unresolved, verified,
                  product_ok) -> CandidateResolution:
    versions = sorted((c for c in cards if c.rule_id == rid), key=lambda c: c.version)
    if not versions:
        return _result(family, rid, product_applicable=product_ok, status="no_candidate_rule",
                       reason=f"{rid}: no card is loaded in the store")
    latest_any = versions[-1]
    approved = [c for c in versions if c.status == "approved"]
    if verified is None:
        eligible = [c for c in approved if c.quote and c.source_sha256]
    else:
        eligible = [c for c in approved if (c.rule_id, c.version) in verified]
    common = dict(version=latest_any.version, approved=bool(approved),
                  quote_verified=bool(eligible), product_applicable=product_ok,
                  applies_by=latest_any.applies_by)
    if not approved:
        states = ", ".join(f"v{c.version} {c.status}" for c in versions)
        return _result(family, rid, status="not_approved", reason=f"no approved version ({states})",
                       **common)
    if not eligible:
        return _result(family, rid, status="quote_unverified",
                       reason="approved, but the quote is not verified verbatim on its source page",
                       **common)
    latest = eligible[-1]
    common.update(version=latest.version, applies_by=latest.applies_by)
    kind, ground = ground_state
    if kind == "unreviewed":
        return _result(family, rid, status="missing_required_fact", missing_facts=["rejection_ground"],
                       reason="rejection_ground is not yet reviewed", **common)
    if kind == "absent":
        return _result(family, rid, status="missing_required_fact", absent_facts=["rejection_ground"],
                       reason="no rejection_ground fact", **common)
    if not any(ground in _triggers(c) for c in eligible):
        return _result(family, rid, status="no_candidate_rule",
                       reason=f"rejection ground '{ground}' is not a trigger of {rid}", **common)
    triggered = [c for c in eligible if ground in _triggers(c)]
    blockers = blocking_fields(triggered, facts, unresolved)
    if blockers:
        return _result(family, rid, status="missing_required_fact", missing_facts=blockers,
                       reason="unreviewed fact(s) feed this card: " + ", ".join(blockers), **common)
    latest = triggered[-1]
    d, missing, date_keys = _relevant_date(latest, facts)
    if d is None:
        reason = f"missing_{missing}" if missing else "unsupported_applies_by"
        return _result(family, rid, status="missing_applicability_date", reason=reason, **common)
    basis = list(dict.fromkeys(date_keys))
    warnings = []
    if (latest.applies_by == "policy_start_or_renewal" and "policy_renewal_date" not in basis
            and usable(facts, "inception_date") and (d - facts["inception_date"].value).days == 0
            and usable(facts, "claim_date") and (facts["claim_date"].value - d).days > 366):
        warnings.append("no policy_renewal_date: the version was chosen from inception_date, but "
                        "the claim is more than a year later (a renewal may fall under a later version)")
    in_force = [c for c in triggered if _in_force(c, d)]
    if not in_force:
        starts = ", ".join(sorted({c.in_force_from.isoformat() for c in triggered if c.in_force_from}))
        return _result(family, rid, status="not_in_force", applicability_date=d, date_basis=basis,
                       in_force_on_date=False, warnings=warnings,
                       reason=f"no version in force on {d.isoformat()} (in force from {starts})",
                       **common)
    chosen = in_force[-1]
    common.update(version=chosen.version, applies_by=chosen.applies_by)
    return _result(family, rid, status="applicable", applicability_date=d, date_basis=basis,
                   in_force_on_date=True, warnings=warnings,
                   reason=f"v{chosen.version} in force on {d.isoformat()} ({chosen.applies_by})",
                   **common)


def resolve_rule_context(issue_family: str, facts: dict[str, FactValue], cards: list[RuleCard],
                         product_line: str | None, *, unresolved: dict[str, FactValue] | None = None,
                         verified: set[tuple[str, int]] | None = None,
                         family_map: FamilyMap | None = None) -> list[CandidateResolution]:
    """One result per candidate card of `issue_family` (or one `no_candidate_rule` /
    `unsupported_product` result when the family has none).

    cards: every loaded card, any status. verified: (rule_id, version) pairs whose quote was
    re-verified verbatim (None: a card counts as verified when it has a quote and a source hash,
    the engine's own guard). unresolved: facts that exist but no human has decided (extracted /
    needs_review); flagged facts inside `facts` (status needs_confirmation) count the same."""
    if issue_family not in ISSUE_FAMILIES:
        raise ValueError(f"unknown issue family {issue_family!r}")
    fm = family_map or load_family_map()
    cand = fm.cards(issue_family)
    product_ok = product_line in SUPPORTED_PRODUCT_LINES
    if not product_ok:
        why = f"product line {product_line or 'unknown'!s}: health rule cards do not apply"
        return [_result(issue_family, rid, status="unsupported_product", reason=why) for rid in cand] \
            or [_result(issue_family, None, status="unsupported_product", reason=why)]
    if not cand:
        extra = " (research_needed: no approved regulation card yet)" if fm.research_needed(issue_family) else ""
        return [_result(issue_family, None, product_applicable=True, status="no_candidate_rule",
                        reason=f"issue family {issue_family} has no candidate card{extra}")]
    state = _ground_state(facts, unresolved)
    return [_resolve_card(issue_family, rid, facts, cards, state, unresolved, verified, True)
            for rid in cand]


def applicable_cards(results: Iterable[CandidateResolution], cards: list[RuleCard]) -> list[RuleCard]:
    """The cards the engine may run: every approved version of each `applicable` rule (the engine
    re-selects the version in force by the same date, so it lands on the version reported here)."""
    rids = {r.rule_id for r in results if r.status == "applicable"}
    return [c for c in cards if c.rule_id in rids and c.status == "approved"
            and c.quote and c.source_sha256]


class CaseContext(BaseModel):
    families: list[str] = Field(default_factory=list)
    family_source: Literal["reviewed", "ground", "none"] = "none"
    trace: list[CandidateResolution] = Field(default_factory=list)

    def results(self, *statuses: str) -> list[CandidateResolution]:
        return [r for r in self.trace if r.status in statuses]

    def skips(self) -> dict[str, list[str]]:
        """rule_id -> unreviewed fields that block it; "*" when the ground itself is unreviewed."""
        if any("rejection_ground" in r.missing_facts for r in self.trace):
            return {"*": ["rejection_ground"]}
        out: dict[str, set[str]] = {}
        for r in self.trace:
            if r.status == "missing_required_fact" and r.missing_facts and r.rule_id:
                out.setdefault(r.rule_id, set()).update(r.missing_facts)
        return {k: sorted(v) for k, v in sorted(out.items())}


def resolve_case_context(reviewed_families: Iterable[str], facts: dict[str, FactValue],
                         cards: list[RuleCard], product_line: str | None, *,
                         unresolved: dict[str, FactValue] | None = None,
                         verified: set[tuple[str, int]] | None = None,
                         family_map: FamilyMap | None = None) -> tuple[CaseContext, list[RuleCard]]:
    """Resolve every family of a case. Families come from the human-reviewed issue families; a
    case with none falls back to the family of its (reviewed) rejection ground, which keeps the
    ground-driven behaviour. -> (context with the full trace, cards the engine may run)."""
    fm = family_map or load_family_map()
    fams = list(dict.fromkeys(reviewed_families))
    source = "reviewed" if fams else "none"
    state, ground = _ground_state(facts, unresolved)
    if not fams and ground:
        fam = fm.family_for_ground(ground)
        if fam:
            fams, source = [fam], "ground"
    trace: list[CandidateResolution] = []
    for fam in fams:
        trace += resolve_rule_context(fam, facts, cards, product_line, unresolved=unresolved,
                                      verified=verified, family_map=fm)
    if not fams:
        if product_line not in SUPPORTED_PRODUCT_LINES:
            trace.append(_result(None, None, status="unsupported_product",
                                 reason=f"product line {product_line or 'unknown'!s}: "
                                        "health rule cards do not apply"))
        elif state == "unreviewed":
            trace.append(_result(None, "*", status="missing_required_fact",
                                 missing_facts=["rejection_ground"],
                                 reason="rejection_ground is not yet reviewed and no issue family is reviewed"))
        else:
            trace.append(_result(None, None, status="no_candidate_rule",
                                 reason="no reviewed issue family and no usable rejection ground"))
    return CaseContext(families=fams, family_source=source, trace=trace), \
        applicable_cards(trace, cards)
