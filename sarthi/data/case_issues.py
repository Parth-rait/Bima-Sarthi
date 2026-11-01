"""Per-issue holdings of real judgments: appellant backfill, model drafting, human review.

Why: a judgment's overall result is not the holding on a rule's issue, and for an appeal
"dismissed" means the policyholder won. Evaluation therefore compares the engine's finding on a
rule with the forum's holding on THAT issue (`case_issue`), confirmed by a human.
The model only drafts; nothing is used by evaluation until a human reviewed it.
"""
import json
import logging
import re
from datetime import date
from pathlib import Path
from typing import Literal

from pydantic import BaseModel, ConfigDict

from sarthi.core.inputs import REJECTION_GROUNDS
from sarthi.core.models import CaseIssue
from sarthi.core.store import Store
from sarthi.data.case_facts import _MARKER, _pages, make_windows
from sarthi.data.parse_docs import normalise_ws
from sarthi.data.rule_cards import approved_cards
from sarthi.llm.client import chat

log = logging.getLogger(__name__)

OVERALL = "_overall"  # reserved issue key: who prevailed overall (never an evaluation issue)
HOLDINGS = ("for_policyholder", "for_insurer", "not_decided")
PROTECTED = ("reviewed", "corrected", "rejected")
REVIEWED = ("reviewed", "corrected")


# ---------- appellant backfill (deterministic) ----------

_FORUM_RE = re.compile(r"consumer disputes redressal|high court", re.I)
_TITLE_DATE = re.compile(r"\s+on\s+\d{1,2}\s+\w+,?\s+\d{4}\s*$", re.I)
_VS = re.compile(r"\s+vs\.?\s+", re.I)
_INSURER_RE = re.compile(
    r"insur|insu\.|assurance|assu\.|\bins\.|\bergo\b|bupa|religare health|star health|care health|"
    r"apollo munich|bharti axa|tata aig|raksha health|aditya birla health|niva|reliance general|"
    r"bajaj allianz|icici lombard", re.I)
_NOT_POLICYHOLDER_RE = re.compile(
    r"government|govt|union of india|state of|state consumer|commission|redressal|commissioner", re.I)


def infer_appellant(title: str | None, forum: str | None) -> str:
    """'insurer' only for an "<Insurer> vs <person>" title in a State Commission / NCDRC / High
    Court (an appeal or revision there). Everything else is 'unknown' for a human."""
    if not title or not forum or not _FORUM_RE.search(forum):
        return "unknown"
    parts = _VS.split(_TITLE_DATE.sub("", title.strip()), maxsplit=1)
    if len(parts) != 2:
        return "unknown"
    first, second = parts
    if _INSURER_RE.search(first) and not _NOT_POLICYHOLDER_RE.search(second):
        return "insurer"
    return "unknown"


def prevailed_from_outcome(appellant: str | None, outcome: str | None) -> bool | None:
    """Direction-corrected policyholder_prevailed, only when unambiguous."""
    if appellant == "insurer":
        return {"dismissed": True, "allowed": False}.get(outcome)
    if appellant == "policyholder":
        return {"allowed": True, "dismissed": False}.get(outcome)
    return None


def _title(case_id: str, store: Store) -> str | None:
    row = store.con.execute("SELECT title FROM source WHERE source_id IN (?, ?) ORDER BY source_id",
                            [case_id, f"local_{case_id}"]).fetchone()
    return row[0] if row else None


def backfill_appellant(store: Store) -> dict[str, int]:
    """Fill appellant (unknown/NULL only) and policyholder_prevailed (NULL only). Idempotent."""
    counts = dict(cases=0, appellant_inferred=0, appellant_unknown=0, appellant_kept=0,
                  prevailed_known=0, prevailed_unknown=0)
    rows = store.con.execute(
        'SELECT case_id, forum, outcome, appellant, policyholder_prevailed FROM "case" ORDER BY 1'
    ).fetchall()
    for case_id, forum, outcome, appellant, prevailed in rows:
        counts["cases"] += 1
        if appellant in ("insurer", "policyholder"):
            counts["appellant_kept"] += 1
        else:
            appellant = infer_appellant(_title(case_id, store), forum)
            counts["appellant_inferred" if appellant != "unknown" else "appellant_unknown"] += 1
            store.con.execute('UPDATE "case" SET appellant=? WHERE case_id=?', [appellant, case_id])
        if prevailed is None:
            prevailed = prevailed_from_outcome(appellant, outcome)
            if prevailed is not None:
                store.con.execute('UPDATE "case" SET policyholder_prevailed=? WHERE case_id=?',
                                  [prevailed, case_id])
        counts["prevailed_known" if prevailed is not None else "prevailed_unknown"] += 1
    return counts


def backfill_product_line(store: Store) -> dict[str, int]:
    """Evidence-only backfill: a non-excluded case with product_line unset and at least one
    human-reviewed (reviewed/corrected) real rule issue is health, because a human reviewed a
    health-rule issue on it. Nothing else is guessed. Idempotent."""
    ids = [r[0] for r in store.con.execute(
        'SELECT c.case_id FROM "case" c WHERE c.product_line IS NULL AND c.excluded_reason IS NULL '
        "AND EXISTS (SELECT 1 FROM case_issue i WHERE i.case_id = c.case_id "
        "AND i.status IN ('reviewed','corrected') AND i.issue <> ?) ORDER BY 1", [OVERALL]).fetchall()]
    for cid in ids:
        store.con.execute('UPDATE "case" SET product_line=\'health\' WHERE case_id=?', [cid])
    return {"health": len(ids)}


# ---------- drafting ----------

class OutIssue(BaseModel):
    model_config = ConfigDict(extra="forbid")
    issue: str
    holding: Literal["for_policyholder", "for_insurer", "not_decided"]
    quote: str | None = None
    page_no: int | None = None


class IssuesOut(BaseModel):
    model_config = ConfigDict(extra="forbid")
    appellant: Literal["insurer", "policyholder", "unknown"] = "unknown"
    prevailed: Literal["for_policyholder", "for_insurer", "not_decided"] = "not_decided"
    prevailed_quote: str | None = None
    prevailed_page_no: int | None = None
    issues: list[OutIssue] = []


def _issue_keys(store: Store) -> tuple[list[tuple[str, str, list]], list[str]]:
    cards = store.con.execute(
        "SELECT rule_id, max(title_en), any_value(triggers) FROM rule_card "
        "WHERE status IN ('approved','draft') GROUP BY rule_id ORDER BY rule_id").fetchall()
    out = []
    for rid, title, trig in cards:
        try:
            t = json.loads(trig) if isinstance(trig, str) else (trig or [])
        except ValueError:
            t = []
        out.append((rid, title or "", list(t)))
    return out, list(REJECTION_GROUNDS)


def _system_prompt(cards: list[tuple[str, str, list]]) -> str:
    keys = "\n".join(f"- {rid}: {title} (rejection grounds: {', '.join(t) or 'none'})"
                     for rid, title, t in cards)
    return f"""You read one Indian consumer-forum or court judgment about a health insurance claim. You record WHO appealed, WHO won overall, and how the forum decided each insurance issue.
Rules:
- appellant: "insurer" if the insurer brought this appeal/revision/petition, "policyholder" if the insured or complainant did (including an original complaint), else "unknown".
- prevailed: who won overall in THIS judgment: "for_policyholder" or "for_insurer". An insurer's appeal that is dismissed is for_policyholder. If unclear, "not_decided". prevailed_quote: the forum's own words stating the result.
- issues: only insurance issues the forum itself DECIDED. issue must be exactly one of these rule ids or one of these rejection grounds:
{keys}
Rejection grounds: {", ".join(REJECTION_GROUNDS)}
- holding: "for_policyholder" if the forum's finding on that issue favours the insured, "for_insurer" if it favours the insurer, "not_decided" if the forum did not decide it or it is unclear. Never guess. A dismissal for lack of proof or on procedure is not a holding on the issue.
- quote: copied verbatim from the given text (exact words, no paraphrase, no ellipsis): the FORUM's own finding, never the parties' arguments. Null if none.
- page_no from the page marker "[Page N]" preceding the quote.
- Include an issue only if the text supports it; omit issues the judgment never touches.
Reply with ONLY one JSON object. Its keys are exactly: appellant, prevailed, prevailed_quote, prevailed_page_no, issues. Each item of issues has exactly: issue, holding, quote, page_no. Use no other keys."""


def _locate(quote: str | None, window: str, wpages: list[int], page_text: dict[int, str],
            model_page: int | None) -> tuple[bool, int]:
    nq = normalise_ws(quote or "")
    found = bool(nq) and nq in normalise_ws(_MARKER.sub("", window))
    single = next((p for p in wpages if nq and nq in normalise_ws(page_text.get(p, ""))), None)
    if single is not None:
        return found, single
    return found, model_page if model_page in wpages else wpages[0]


def _rank(c: dict) -> int:
    if c["holding"] == "not_decided":
        return 0
    return 2 if c["found"] else 1


def _merge(best: dict, key: str, c: dict) -> None:
    cur = best.get(key)
    if cur is None or _rank(c) > _rank(cur):
        best[key] = c
    elif _rank(c) == 2 == _rank(cur) and c["holding"] != cur["holding"]:
        cur["conflict"] = True


def protected_issues(case_id: str, store: Store) -> list[str]:
    marks = ", ".join("?" for _ in PROTECTED)
    return [r[0] for r in store.con.execute(
        f"SELECT issue FROM case_issue WHERE case_id=? AND status IN ({marks}) ORDER BY 1",
        [case_id, *PROTECTED]).fetchall()]


def draft_issues(case_id: str, store: Store, force: bool = False) -> list[CaseIssue]:
    """Rows written. Issues a human already reviewed are skipped unless force=True."""
    pages = _pages(case_id, store)
    page_text = dict(pages)
    cards, grounds = _issue_keys(store)
    valid = {rid for rid, _, _ in cards} | set(grounds)
    skip = set() if force else set(protected_issues(case_id, store))
    system = _system_prompt(cards)
    best: dict[str, dict] = {}
    appellants: list[str] = []
    for wpages, text in make_windows(pages):
        res = chat(role="reader", schema=IssuesOut, cache=True, max_tokens=4000, messages=[
            {"role": "system", "content": system},
            {"role": "user", "content": f"Judgment text:\n\n{text}"}])
        if res.parsed is None:
            continue
        out = res.parsed
        if out.appellant != "unknown":
            appellants.append(out.appellant)
        cands = [(OVERALL, out.prevailed, out.prevailed_quote, out.prevailed_page_no)]
        for it in out.issues:
            if it.issue not in valid:
                log.warning("case %s: dropped issue %r (not a rule id or ground)", case_id, it.issue)
                continue
            cands.append((it.issue, it.holding, it.quote, it.page_no))
        for key, holding, quote, pg in cands:
            found, page_no = _locate(quote, text, wpages, page_text, pg)
            _merge(best, key, dict(holding=holding, quote=quote or None, page_no=page_no,
                                   found=found, res_review=res.needs_review))
    rows = []
    for key, c in best.items():
        if key in skip:
            continue
        note = None
        decided = c["holding"] != "not_decided"
        ok = (c["found"] or not decided) and not c["res_review"]
        if c.get("conflict"):
            ok, note = False, "conflicting holdings across windows"
        if key == OVERALL:
            who = appellants[0] if appellants else "unknown"
            note = "; ".join(x for x in (note, f"model appellant: {who}") if x)
        rows.append(dict(case_id=case_id, issue=key, holding=c["holding"],
                         holding_quote=c["quote"] if c["quote"] else None,
                         page_no=c["page_no"] if c["quote"] else None,
                         status="drafted" if ok else "needs_review", reviewer_note=note))
    store.upsert("case_issue", rows, key=["case_id", "issue"])
    return [CaseIssue(**r) for r in rows]


# ---------- review ----------

class IssueDecision(BaseModel):
    action: Literal["accept", "correct", "reject"]
    holding: str | None = None
    quote: str | None = None
    note: str = ""


def _find_quote(quote: str, pages: list[tuple[int, str]]) -> tuple[bool, int | None]:
    nq = normalise_ws(quote)
    if not nq:
        return False, None
    for p, t in pages:
        if nq in normalise_ws(t):
            return True, p
    return nq in normalise_ws(" ".join(t for _, t in pages)), None


def review_issues(case_id: str, decisions: dict[str, IssueDecision], reviewer: str,
                  store: Store) -> None:
    existing = {r[0]: r[1:] for r in store.con.execute(
        "SELECT issue, holding, holding_quote, page_no FROM case_issue WHERE case_id=?",
        [case_id]).fetchall()}
    unknown = [i for i in decisions if i not in existing]
    if unknown:
        raise KeyError(f"no drafted issue for {case_id}: {', '.join(unknown)}")
    pages = _pages(case_id, store)
    updates = []  # validate everything first; write nothing on a bad batch
    for issue, d in decisions.items():
        holding, quote, page_no = existing[issue]
        if d.action == "accept":
            if holding != "not_decided":
                if not quote:
                    raise ValueError(f"{issue}: cannot accept a holding without a quote; correct it")
                if not _find_quote(quote, pages)[0]:
                    raise ValueError(f"{issue}: quote is not verbatim in the judgment; correct it")
            status = "reviewed"
            note = f"accepted by {reviewer}" + (f"; {d.note}" if d.note else "")
        elif d.action == "correct":
            if d.holding not in HOLDINGS:
                raise ValueError(f"{issue}: corrected holding must be one of {', '.join(HOLDINGS)}, "
                                 f"got {d.holding!r}")
            new_quote, new_page = None, None
            if d.quote:
                ok, new_page = _find_quote(d.quote, pages)
                if not ok:
                    raise ValueError(f"{issue}: corrected quote is not verbatim in the judgment")
                new_quote = d.quote
            status, holding, quote, page_no = "corrected", d.holding, new_quote, new_page
            note = (f"was: {existing[issue][0]}; {d.note}; by {reviewer}"
                    + ("" if new_quote else "; quote cleared on correction"))
        else:
            status = "rejected"
            note = f"rejected by {reviewer}; {d.note}"
        updates.append((issue, status, holding, quote, page_no, note, d.action))
    for issue, status, holding, quote, page_no, note, action in updates:
        store.con.execute(
            "UPDATE case_issue SET status=?, holding=?, holding_quote=?, page_no=?, reviewer_note=? "
            "WHERE case_id=? AND issue=?", [status, holding, quote, page_no, note, case_id, issue])
        if issue == OVERALL and action != "reject":
            store.con.execute('UPDATE "case" SET policyholder_prevailed=? WHERE case_id=?',
                              [{"for_policyholder": True, "for_insurer": False}.get(holding), case_id])


def apply_review_file(case_id: str, raw: dict, reviewer: str, store: Store) -> int:
    from pydantic import ValidationError
    try:
        decisions = {k: IssueDecision.model_validate(v) for k, v in raw.items()}
    except (ValidationError, AttributeError) as e:
        raise ValueError(f"bad decision for {case_id}: {e}") from e
    review_issues(case_id, decisions, reviewer, store)
    return len(decisions)


def load_reviewed_issues(store: Store) -> dict[str, dict[str, dict]]:
    """case_id -> issue -> {holding, quote, page_no}; reviewed/corrected, real issues only."""
    out: dict[str, dict[str, dict]] = {}
    for cid, issue, holding, quote, page in store.con.execute(
            "SELECT case_id, issue, holding, holding_quote, page_no FROM case_issue "
            "WHERE status IN ('reviewed','corrected') AND issue <> ? ORDER BY 1, 2", [OVERALL]).fetchall():
        out.setdefault(cid, {})[issue] = dict(holding=holding, quote=quote, page_no=page)
    return out


# ---------- review sheet ----------

def _claim_date(case_id: str, store: Store) -> date | None:
    for field in ("claim_date", "admission_date"):
        row = store.con.execute(
            "SELECT value FROM case_fact WHERE case_id=? AND field=? AND status<>'rejected'",
            [case_id, field]).fetchone()
        if row and row[0]:
            try:
                v = json.loads(row[0])
                return date.fromisoformat(v) if isinstance(v, str) else None
            except ValueError:
                continue
    return None


def in_scope_case_ids(store: Store, case_ids: list[str]) -> set[str]:
    cards = approved_cards(store)
    out = set()
    for cid in case_ids:
        d = _claim_date(cid, store)
        if d and any(c.in_force_from and c.in_force_from <= d
                     and (c.in_force_to is None or d < c.in_force_to) for c in cards):
            out.add(cid)
    return out


def write_review_sheet(store: Store, path: Path) -> int:
    """Markdown sheet, in-scope cases first. Returns the number of cases listed. Lists only cases
    still awaiting review: not excluded, and with no issue a human has already decided."""
    marks = ", ".join("?" for _ in PROTECTED)
    ids = [r[0] for r in store.con.execute(
        "SELECT DISTINCT i.case_id FROM case_issue i LEFT JOIN \"case\" c USING (case_id) "
        "WHERE c.excluded_reason IS NULL AND i.case_id NOT IN "
        f"(SELECT case_id FROM case_issue WHERE status IN ({marks})) ORDER BY 1", list(PROTECTED)).fetchall()]
    scope = in_scope_case_ids(store, ids)
    ordered = [c for c in ids if c in scope] + [c for c in ids if c not in scope]
    L = ["# Case issue review sheet", "",
         "Model-drafted; nothing here is used by evaluation until you review it "
         "(`cases issues review <id> --json file`). Decision file: "
         '`{"<issue>": {"action": "accept|correct|reject", "holding": "...", "quote": "...", '
         '"note": ""}}`. Use issue `_overall` to confirm who prevailed.', "",
         f"{len(scope)} in-scope case(s) listed first (claim/admission date inside an approved "
         f"card's in-force window); {len(ids) - len(scope)} other(s).", ""]
    for cid in ordered:
        forum, appellant, prevailed, outcome, line = store.con.execute(
            'SELECT forum, appellant, policyholder_prevailed, outcome, product_line FROM "case" '
            "WHERE case_id=?", [cid]).fetchone() or (None, None, None, None, None)
        L += [f"## {cid}{' [in scope]' if cid in scope else ''}: {_title(cid, store) or '(no title)'}",
              f"- Forum: {forum}; claim/admission date: {_claim_date(cid, store) or 'missing'}; "
              f"court outcome field: {outcome}",
              f"- Appealed by: {appellant or 'unknown'}; Product line: {line or 'unknown'}"]
        issues = store.con.execute(
            "SELECT issue, holding, holding_quote, page_no, status, reviewer_note FROM case_issue "
            "WHERE case_id=? ORDER BY issue <> ?, issue", [cid, OVERALL]).fetchall()
        for issue, holding, quote, page, status, note in issues:
            where = f" (p.{page})" if page is not None else ""
            q = f' > "{quote}"{where}' if quote else " > (no quote)"
            if issue == OVERALL:
                pv = {True: "yes", False: "no", None: "unknown"}[prevailed]
                L.append(f"- Policyholder prevailed (database): {pv}. Model draft: {holding} "
                         f"[{status}] ({note or ''}){q}")
            else:
                L.append(f"- Issue `{issue}`: {holding} [{status}]{q}")
        L.append("")
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(L) + "\n", encoding="utf-8")
    return len(ordered)
