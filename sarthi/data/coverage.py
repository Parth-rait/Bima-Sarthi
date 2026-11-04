"""Coverage of the issue-family / rule-card resolution over the case corpus.

This is COVERAGE, not accuracy: every number states what it counts and out of what. Nothing here
is a model output; drafted families are listed apart from reviewed ones and never merged.
"""
from collections import Counter
from pathlib import Path

from sarthi.core.context import load_family_map, resolve_case_context
from sarthi.core.engine import run_rules
from sarthi.core.models import ISSUE_FAMILIES
from sarthi.core.store import Store
from sarthi.data.case_facts import load_reviewed_facts, load_unresolved_facts
from sarthi.data.case_issues import (OVERALL, REVIEWED, load_reviewed_families,
                                     load_reviewed_issues)
from sarthi.data.evaluate import _resolve_issue
from sarthi.data.rule_cards import approved_cards, unapproved_cards


def compute_coverage(store: Store) -> dict:
    q = store.con.execute
    live = {r[0]: r[1] for r in q('SELECT case_id, product_line FROM "case" '
                                  "WHERE excluded_reason IS NULL").fetchall()}
    n_excluded = q('SELECT count(*) FROM "case" WHERE excluded_reason IS NOT NULL').fetchone()[0]
    rows = [r for r in q("SELECT case_id, issue, status, issue_family, family_status FROM case_issue "
                         "WHERE issue <> ?", [OVERALL]).fetchall() if r[0] in live]
    fam_rev, fam_dr = Counter(), Counter()
    for _, _, _, fam, fst in rows:
        if fam and fst == "reviewed":
            fam_rev[fam] += 1
        elif fam and fst == "drafted":
            fam_dr[fam] += 1
    cards = approved_cards(store)
    verified = {(c.rule_id, c.version) for c in cards}
    pool = cards + unapproved_cards(store, exclude=verified)
    fm = load_family_map()
    approved_ids = {c.rule_id for c in cards}
    families = {f: {"candidates": fm.cards(f),
                    "approved_cards": [r for r in fm.cards(f) if r in approved_ids],
                    "research_needed": fm.research_needed(f)} for f in ISSUE_FAMILIES}
    reviewed_fams = load_reviewed_families(store)
    reviewed_issues = load_reviewed_issues(store)
    universe, statuses = [], Counter()
    unsupported, unknown, missing, oos, applicable, scorable = set(), set(), set(), set(), set(), 0
    sources = Counter()
    for cid, line in sorted(live.items()):
        facts = load_reviewed_facts(cid, store)
        fams = list(reviewed_fams.get(cid, {}).values())
        if not facts and not fams:
            continue
        universe.append(cid)
        ctx, engine = resolve_case_context(fams, facts, pool, line,
                                           unresolved=load_unresolved_facts(cid, store),
                                           verified=verified, family_map=fm)
        sources[ctx.family_source] += 1
        for r in ctx.trace:
            statuses[r.status] += 1
        if ctx.results("unsupported_product"):
            (unknown if line in (None, "unknown") else unsupported).add(cid)
        if ctx.skips():
            missing.add(cid)
        if ctx.results("applicable"):
            applicable.add(cid)
        trig = ctx.results("not_in_force", "missing_applicability_date", "applicable")
        if trig and all(r.status == "not_in_force" for r in trig):
            oos.add(cid)
        issues = reviewed_issues.get(cid, {})
        if facts and not ctx.skips():
            for f in run_rules(facts, engine):
                card = next((c for c in engine if c.rule_id == f.rule_id and c.version == f.rule_version), None)
                hit = _resolve_issue(f.rule_id, list(card.triggers) if card else [], issues)
                if f.verdict in ("CONSISTENT", "CHALLENGEABLE") and hit and hit[1]["holding"] != "not_decided":
                    scorable += 1
    return {
        "cases_total": len(live) + n_excluded, "cases_excluded": n_excluded,
        "issue_rows_total": len(rows),
        "reviewed_issue_rows": sum(r[2] in REVIEWED for r in rows),
        "rows_with_reviewed_family": sum(fam_rev.values()), "rows_with_drafted_family": sum(fam_dr.values()),
        "family_reviewed": dict(fam_rev), "family_drafted": dict(fam_dr),
        "families": families,
        "cases_in_universe": len(universe), "family_sources": dict(sources),
        "resolver_candidate_statuses": dict(statuses),
        "historically_applicable_cases": len(applicable),
        "findings_eligible_for_scoring": scorable,
        "missing_fact_skip_cases": len(missing), "unsupported_product_cases": len(unsupported),
        "product_line_unknown_cases": len(unknown),
        "out_of_scope_cases": len(oos),
        "universe": universe,
    }


def write_coverage(store: Store, path: Path) -> dict:
    c = compute_coverage(store)
    U, R = c["cases_in_universe"], c["issue_rows_total"]
    L = ["# Issue-family coverage", "",
         "**Coverage is not accuracy.** These counts say how much of the corpus the family and "
         "rule-card resolver can currently reach, and why the rest is not decided. They say nothing "
         "about whether a verdict is right. Each line states its denominator.", "",
         f"Corpus: {c['cases_total']} cases, {c['cases_excluded']} excluded by the reviewer "
         f"(outside every count below). Real-issue rows (excluding `_overall`) in the other cases: {R}.", "",
         "## Reviewed issues", "",
         f"- {c['reviewed_issue_rows']} reviewed issue rows (status reviewed or corrected) of {R} issue rows.",
         f"- {c['rows_with_reviewed_family']} of {R} issue rows carry a human-reviewed issue family "
         "(this includes rows whose rule-label was rejected: the family names the real issue, the "
         "rejected label is never scored).",
         f"- {c['rows_with_drafted_family']} of {R} issue rows carry only a model-drafted family "
         "(not counted as reviewed, not used).", "",
         "## Issue-family distribution (issue rows)", "",
         "| Family | Reviewed | Drafted |", "|---|---|---|"]
    for f in ISSUE_FAMILIES:
        L.append(f"| {f} | {c['family_reviewed'].get(f, 0)} | {c['family_drafted'].get(f, 0)} |")
    L += ["", "## Families with approved cards vs research_needed", "",
          "| Family | Candidate cards | Approved and verified | Status |", "|---|---|---|---|"]
    for f, d in c["families"].items():
        status = ("has approved card(s)" if d["approved_cards"]
                  else "research_needed (no approved regulation card)" if d["research_needed"]
                  else "no candidate card" if not d["candidates"] else "candidate cards not approved")
        L.append(f"| {f} | {', '.join(d['candidates']) or '-'} | {', '.join(d['approved_cards']) or '-'} "
                 f"| {status} |")
    s = c["resolver_candidate_statuses"]
    L += ["", f"## Resolver outcomes (over {U} cases)", "",
          f"Universe: {U} of {c['cases_total'] - c['cases_excluded']} non-excluded cases that have "
          "reviewed facts or a reviewed issue family. Family source: "
          + (", ".join(f"{k} {v}" for k, v in sorted(c["family_sources"].items())) or "none") + ".", "",
          f"- historically applicable: {c['historically_applicable_cases']} of {U} cases have at least one "
          "candidate card with a version in force on the case's applicability date and all required "
          "facts reviewed.",
          f"- findings eligible for scoring: {c['findings_eligible_for_scoring']} engine findings "
          "(CONSISTENT or CHALLENGEABLE) that match a human-reviewed, decided holding (denominator: "
          "findings, not cases).",
          f"- missing-fact skips: {c['missing_fact_skip_cases']} of {U} cases (a fact a candidate card "
          "needs is unreviewed or flagged).",
          f"- unsupported-product skips: {c['unsupported_product_cases']} of {U} cases (a known product "
          "line other than health, so no health card may run).",
          f"- product line unknown: {c['product_line_unknown_cases']} of {U} cases (product_line not "
          "set; evaluation never runs them until a human sets it with `cases set-product-line`).",
          f"- out-of-scope skips: {c['out_of_scope_cases']} of {U} cases (every triggered candidate "
          "has no version in force on its date).", "",
          "Candidate cards by resolution status (a case can have several candidates): "
          + (", ".join(f"{k} {v}" for k, v in sorted(s.items())) or "none") + "."]
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(L) + "\n", encoding="utf-8")
    return c
