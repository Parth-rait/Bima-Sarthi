"""Rule cards: seed loading, verbatim quote verification, approval.

A card may be used only when a human approved it AND its quote is found
verbatim (after whitespace/quote normalisation) on its stored source page.
"""
import json
import logging
from dataclasses import dataclass
from datetime import UTC, date, datetime
from pathlib import Path

import yaml
from rapidfuzz import fuzz

from sarthi.core.expr import names
from sarthi.core.inputs import KNOWN_INPUTS
from sarthi.core.models import RuleCard, missing_grievance_params
from sarthi.core.store import Store
from sarthi.data.parse_docs import normalise_ws

log = logging.getLogger(__name__)

_JSON_COLS = ("triggers", "inputs", "params")
_KEY = ["rule_id", "version"]


class UnknownInput(ValueError):
    """A condition references a name outside KNOWN_INPUTS."""


class NotVerified(Exception):
    """The card's quote was not found verbatim on its source page."""


@dataclass(frozen=True)
class QuoteCheck:
    found: bool
    page_no: int | None
    score: float


def _to_row(card: RuleCard) -> dict:
    row = card.model_dump()
    for k in _JSON_COLS:
        row[k] = json.dumps(row[k])
    return row


def _from_row(cols: list[str], values: tuple) -> RuleCard:
    d = dict(zip(cols, values))
    for k in _JSON_COLS:
        if isinstance(d.get(k), str):
            d[k] = json.loads(d[k])
    return RuleCard(**d)


def _get(store: Store, rule_id: str, version: int) -> RuleCard:
    cur = store.con.execute(
        "SELECT * FROM rule_card WHERE rule_id=? AND version=?", [rule_id, version])
    cols = [c[0] for c in cur.description]
    row = cur.fetchone()
    if row is None:
        raise KeyError(f"no rule card {rule_id} v{version}")
    return _from_row(cols, row)


_LIFECYCLE = {"status", "approved_by", "approved_at", "status_note"}


def _seed_unchanged(card: RuleCard, existing: RuleCard) -> bool:
    """True when every seed-supplied field matches the stored row. Lifecycle fields are
    ignored; an approved row's page_no is set by approve(), so a seed that leaves it null
    still matches."""
    skip = set(_LIFECYCLE)
    if existing.status == "approved" and card.page_no is None:
        skip.add("page_no")
    a, b = card.model_dump(exclude=skip), existing.model_dump(exclude=skip)
    return a == b


def load_seed(dir: Path, store: Store) -> int:
    """Upsert every *.yaml card in `dir`. A new card, or one whose seed content changed,
    is (re)written as draft with approval cleared (fail closed: edited content needs
    re-approval). A card whose seed is unchanged is left untouched, keeping its status
    and approval. Returns the number of cards written (new or changed)."""
    rows = []
    for path in sorted(Path(dir).glob("*.yaml")):
        data = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
        source_id = data.pop("source_id", None)
        card = RuleCard(**data)
        if card.condition:
            for name in sorted(names(card.condition)):
                if name not in KNOWN_INPUTS:
                    raise UnknownInput(name)
        if source_id:
            r = store.con.execute(
                "SELECT sha256 FROM source WHERE source_id=?", [source_id]).fetchone()
            card.source_sha256 = r[0] if r else None
        try:
            existing = _get(store, card.rule_id, card.version)
        except KeyError:
            existing = None
        if existing is not None and _seed_unchanged(card, existing):
            continue
        card.status = "draft"
        card.approved_by = card.approved_at = card.status_note = None
        rows.append(_to_row(card))
    return store.upsert("rule_card", rows, key=_KEY)


def _check_span(sha: str | None, page_no: int | None, quote: str | None,
                store: Store) -> QuoteCheck:
    """Exact substring match on normalised text. `score` (rapidfuzz partial_ratio)
    is a reviewer aid only and never decides."""
    if not quote or not sha:
        return QuoteCheck(False, None, 0.0)
    quote = normalise_ws(quote)
    if not quote:
        return QuoteCheck(False, None, 0.0)
    sql = "SELECT page_no, text FROM document_page WHERE sha256=?"
    args: list = [sha]
    if page_no is not None:
        sql += " AND page_no=?"
        args.append(page_no)
    pages = store.con.execute(sql + " ORDER BY page_no", args).fetchall()
    best = 0.0
    for pn, text in pages:
        norm = normalise_ws(text or "")
        if quote in norm:
            return QuoteCheck(True, pn, 100.0)
        best = max(best, float(fuzz.partial_ratio(quote, norm)))
    return QuoteCheck(False, None, best)


def verify_quote(card: RuleCard, store: Store) -> QuoteCheck:
    return _check_span(card.source_sha256, card.page_no, card.quote, store)


def verify_params(card: RuleCard, store: Store) -> list[tuple[str, QuoteCheck]]:
    """Check every sourced (nested) param's quote verbatim on its own stated page of its
    own source. Flat params carry no source and are not listed."""
    out = []
    for name, p in card.params.items():
        if not isinstance(p, dict):
            continue
        r = store.con.execute(
            "SELECT sha256 FROM source WHERE source_id=?", [p.get("source_id")]).fetchone()
        out.append((name, _check_span(r[0] if r else None, p.get("page_no"),
                                      p.get("quote"), store)))
    return out


def _all_verified(card: RuleCard, store: Store) -> bool:
    return not missing_grievance_params(card) and verify_quote(card, store).found and all(
        qc.found for _, qc in verify_params(card, store))


def approve(rule_id: str, version: int, approver: str, store: Store) -> None:
    card = _get(store, rule_id, version)
    qc = verify_quote(card, store)
    if not qc.found:
        raise NotVerified(
            f"{rule_id} v{version}: quote not found on source page (score {qc.score:.0f})")
    absent = missing_grievance_params(card)
    if absent:
        raise NotVerified(f"{rule_id} v{version}: params must each carry their own source "
                          f"(value, unit, source_id, page_no, quote); missing or flat: "
                          f"{', '.join(absent)}")
    bad = [f"{n} (score {pq.score:.0f})" for n, pq in verify_params(card, store) if not pq.found]
    if bad:
        raise NotVerified(
            f"{rule_id} v{version}: param quote not found on its stated page: {', '.join(bad)}")
    store.con.execute(
        "UPDATE rule_card SET status='approved', approved_by=?, approved_at=?, page_no=?, "
        "status_note=NULL WHERE rule_id=? AND version=?",
        [approver, datetime.now(UTC).replace(tzinfo=None), qc.page_no, rule_id, version])


def disable(rule_id: str, version: int, reason: str, store: Store) -> None:
    _get(store, rule_id, version)
    store.con.execute(
        "UPDATE rule_card SET status='disabled', status_note=? WHERE rule_id=? AND version=?",
        [reason, rule_id, version])


def approved_cards(store: Store, as_of: date | None = None) -> list[RuleCard]:
    """Approved cards whose quote still verifies verbatim. `as_of=None` applies no
    date filter (the engine needs every version to detect "rule_not_in_force").
    A card that fails re-verification is dropped with a warning."""
    sql = "SELECT * FROM rule_card WHERE status='approved'"
    args: list = []
    if as_of is not None:
        sql += " AND in_force_from <= ? AND (in_force_to IS NULL OR ? < in_force_to)"
        args = [as_of, as_of]
    cur = store.con.execute(sql + " ORDER BY rule_id, version", args)
    cols = [c[0] for c in cur.description]
    out = []
    for r in cur.fetchall():
        card = _from_row(cols, r)
        if _all_verified(card, store):
            out.append(card)
        else:
            log.warning("dropping approved card %s v%s: quote (or a param quote) not found verbatim",
                        card.rule_id, card.version)
    return out


def unapproved_cards(store: Store, exclude=()) -> list[RuleCard]:
    """Every stored card NOT in `exclude` ((rule_id, version) pairs): drafts, disabled cards and
    approved cards whose quote no longer verifies. The resolver reports these (never runs them)."""
    skip = set(exclude)
    cur = store.con.execute("SELECT * FROM rule_card ORDER BY rule_id, version")
    cols = [c[0] for c in cur.description]
    return [c for c in (_from_row(cols, r) for r in cur.fetchall()) if (c.rule_id, c.version) not in skip]


def verify_all(store: Store) -> list[tuple[RuleCard, QuoteCheck]]:
    cur = store.con.execute("SELECT * FROM rule_card ORDER BY rule_id, version")
    cols = [c[0] for c in cur.description]
    cards = [_from_row(cols, r) for r in cur.fetchall()]
    return [(c, verify_quote(c, store)) for c in cards]


def approval_body(card: RuleCard, page_no: int | None) -> str:
    """Everything a reviewer needs to approve a card: what it says and what it decides."""
    end = card.in_force_to.isoformat() if card.in_force_to else "no end date"
    return "\n".join([
        f"**{card.title_en or card.rule_id}** ({card.rule_id} v{card.version})",
        "", f"> {card.quote}", "",
        f"Source page {page_no}. Verified verbatim.", "",
        f"- Condition: `{card.condition}`",
        f"- If true: {card.if_true}; if false: {card.if_false}",
        f"- In force: {card.in_force_from.isoformat()} to {end}",
        f"- Applies by: {card.applies_by}",
        f"- Triggers: {json.dumps(card.triggers)}",
        f"- Params: {json.dumps(card.params, sort_keys=True)}",
        "", "Reject to disable the card (give a reason).",
    ])
