"""Evaluation v2: deterministic rules vs model-only baselines against real forum holdings.

PRIMARY (finding level): each engine finding on a rule is compared with the human-reviewed
holding on THAT issue (`case_issue`). False hope = CHALLENGEABLE where the forum held for the
insurer. SECONDARY (case level): the case verdict is compared with `case.policyholder_prevailed`
(direction-corrected: an insurer's appeal that was dismissed is a policyholder win), never with
the raw `case.outcome`. The abstention set (out of scope / no usable ground or rule) is reported
as a safe-abstention rate.
"""
import json
import time
from pathlib import Path
from typing import Literal

from pydantic import BaseModel, ConfigDict

from sarthi.app.extract import ready_for_rules
from sarthi.core.context import CaseContext, blocking_fields, load_family_map, resolve_case_context
from sarthi.core.engine import run_rules
from sarthi.core.models import FactValue, RuleCard, Verdict
from sarthi.core.store import Store
from sarthi.data.case_facts import load_reviewed_facts, load_unresolved_facts
from sarthi.data.case_issues import load_reviewed_families, load_reviewed_issues
from sarthi.data.parse_docs import normalise_ws
from sarthi.data.rule_cards import approved_cards, unapproved_cards
from sarthi.llm.client import chat

Method = Literal["rules", "glimmer_only", "spark_only"]
ROLES = {"glimmer_only": "judge_glimmer", "spark_only": "judge_spark"}
OUT_OF_SCOPE = "OUT_OF_SCOPE"
NO_USABLE = "NO_USABLE_GROUND_OR_RULE"
SKIPPED = "SKIPPED_UNRESOLVED"  # not an engine verdict, not an abstention: a fact it needs is unreviewed
HEALTH = "health"
NO_USABLE_LINE = ("No usable rejection ground or no rule triggered \u2014 sent to human review")
OUT_OF_SCOPE_LINE = "Out of scope: no rule in force on the claim date \u2014 sent to human review"
LIMITATION = ("Courts weigh evidence that rules don't see, so agreement under 100% is expected. "
              "Disagreements are reported case by case.")


class ModelAnswer(BaseModel):
    model_config = ConfigDict(extra="forbid")
    verdict: Verdict
    quote: str


class Metrics(BaseModel):
    n_runs: int = 0
    answered_runs: int = 0
    challengeable_runs: int = 0
    false_hope_runs: int = 0
    agreeing_runs: int = 0
    abstained_runs: int = 0
    abstained_cases: int = 0
    out_of_scope_runs: int = 0
    out_of_scope_cases: list[str] = []
    no_usable_runs: int = 0
    no_usable_cases: list[str] = []
    skipped_unresolved: int = 0  # findings skipped because an input fact is unreviewed (pooled over repeats)
    skipped_cases: list[str] = []
    agreement: float | None = None
    false_hope_rate: float | None = None
    abstentions: int = 0
    quote_coverage: float | None = None
    stability: float | None = None
    mean_latency_ms: float | None = None
    cost_usd: float = 0.0
    # finding level (primary)
    finding_agreeing: int = 0
    finding_disagreeing: int = 0
    finding_n: int = 0  # findings compared with a reviewed holding = agreeing + disagreeing
    finding_challengeable: int = 0  # CHALLENGEABLE findings with a reviewed, decided holding
    finding_false_hope_runs: int = 0
    finding_agreement: float | None = None
    finding_false_hope_rate: float | None = None
    finding_abstentions: int = 0
    finding_excluded: int = 0  # no reviewed issue, or not_decided, or ambiguous
    # abstention set (out of scope / no usable ground or rule, as judged by the rules method)
    abstention_set_runs: int = 0
    safe_abstention_runs: int = 0
    safe_abstention_rate: float | None = None


class CaseRow(BaseModel):
    case_id: str
    outcome: str | None = None  # raw stored outcome, informational only
    policyholder_prevailed: bool | None = None
    tag: Literal["primary", "abstention", "untagged", "skipped"] = "untagged"
    verdicts: dict[str, list[str]]  # method -> case-level verdict per repeat


class FindingRow(BaseModel):
    method: str
    case_id: str
    rule_id: str
    verdict: str
    result: Literal["agree", "disagree", "false_hope", "abstain", "excluded", "skipped"]
    issue: str | None = None
    holding: str | None = None
    quote: str | None = None
    page_no: int | None = None
    why_excluded: str | None = None
    skip_reason: str | None = None  # "unresolved_facts:<field,...>" when result == "skipped"
    count: int = 1


class EvalSummary(BaseModel):
    n_cases: int
    n_skipped_no_facts: int = 0
    excluded_by_reviewer: list[tuple[str, str]] = []  # (case_id, reason): left out of ALL metrics
    n_case_level_excluded: int = 0  # policyholder_prevailed unknown
    # denominators over the health cases that have reviewed facts (rules method decides the bucket)
    n_eligible: int = 0  # an engine verdict (CONSISTENT / CHALLENGEABLE / NEED_INFO) was produced
    n_skipped: int = 0  # at least one finding needs an unreviewed fact
    n_out_of_scope: int = 0  # every triggered card is not in force on the claim date
    n_no_usable: int = 0  # no usable ground, or no card triggered
    not_health: list[tuple[str, str]] = []  # (case_id, product_line): never evaluated
    product_line_unknown: list[str] = []  # product_line NULL / unknown: never evaluated
    n_primary: int = 0
    n_abstention_set: int = 0
    n_untagged: int = 0
    repeats: int = 1
    by_method: dict[str, Metrics]
    cases: list[CaseRow] = []
    finding_rows: list[FindingRow] = []
    # rule-context resolver (per case trace; counts are candidate cards by resolution status)
    traces: dict[str, dict] = {}
    resolver_counts: dict[str, int] = {}
    family_sources: dict[str, int] = {}


def case_verdict(verdicts: list[str]) -> str:
    if "CHALLENGEABLE" in verdicts:
        return "CHALLENGEABLE"
    if "CONSISTENT" in verdicts and "NEED_INFO" not in verdicts:
        return "CONSISTENT"
    return "NEED_INFO"


def _rules_out_of_scope(findings) -> bool:
    """At least one card was triggered, and none has a version in force on the claim's
    relevant date. Empty findings (no usable ground / no card triggered) are NOT this."""
    return bool(findings) and all(f.verdict == "NEED_INFO" and f.reason == "rule_not_in_force" for f in findings)


def skipped_findings(facts: dict[str, FactValue], unresolved: dict[str, FactValue],
                     cards: list[RuleCard], findings=None) -> dict[str, list[str]]:
    """rule_id -> unresolved fields that feed a triggered card of that rule.

    Readiness is the app's own `ready_for_rules` (which reads `INPUT_FACTS`): a field blocks a
    rule when marking just that field unconfirmed makes the app say "not ready" for one of the
    rule's cards (`sarthi.core.context.blocking_fields`). `"*"` stands for every rule: the
    rejection ground itself is unresolved, so which cards are triggered is not known. Unrelated
    unresolved fields block nothing. Kept as the standalone check; evaluation itself now reads
    the same answer from the resolver trace."""
    if not unresolved:
        return {}
    if findings is None:
        findings = run_rules(facts, cards)
    if not findings:
        return {"*": ["rejection_ground"]} if ("rejection_ground" in unresolved
                                               and "rejection_ground" not in facts) else {}
    out: dict[str, list[str]] = {}
    for f in findings:
        blockers = blocking_fields([c for c in cards if c.rule_id == f.rule_id], facts, unresolved)
        if blockers:
            out[f.rule_id] = blockers
    return out


def evaluation_ready(facts: dict[str, FactValue], unresolved: dict[str, FactValue],
                     cards: list[RuleCard]) -> bool:
    """True when no finding of this case is skipped for an unresolved fact. Agrees with
    `ready_for_rules` over the reviewed plus unresolved facts."""
    return not skipped_findings(facts, unresolved, cards)


def skip_reason(fields: list[str]) -> str:
    return "unresolved_facts:" + ",".join(fields)


def build_prompt(cards: list[RuleCard], facts: dict) -> list[dict]:
    """Regulation quotes + fact VALUES only. No case row, no fact quotes (judgment text)."""
    regs = "\n".join(f"[{c.rule_id}] {c.quote}" for c in cards if c.quote)
    vals = json.dumps({k: _jsonable(v.value) for k, v in sorted(facts.items())}, indent=1)
    user = (
        "Regulation text:\n" + regs + "\n\nFacts of the claim:\n" + vals + "\n\n"
        'Decide whether the insurer\'s rejection is CHALLENGEABLE, CONSISTENT with the '
        "regulation, or whether you NEED_INFO. Answer JSON only: "
        '{"verdict": "CHALLENGEABLE" | "CONSISTENT" | "NEED_INFO", '
        '"quote": "<verbatim quote from the regulation text above that supports it>"}')
    return [{"role": "system", "content": "You assess health-insurance claim rejections in India "
             "using only the regulation text given."},
            {"role": "user", "content": user}]


def _jsonable(v):
    return v.isoformat() if hasattr(v, "isoformat") else v


def _agrees(verdict: str, prevailed: bool | None) -> bool | None:
    """Case level: CHALLENGEABLE agrees with a policyholder win, CONSISTENT with an insurer win."""
    if verdict in ("NEED_INFO", OUT_OF_SCOPE, NO_USABLE, SKIPPED) or prevailed is None:
        return None
    return (verdict == "CHALLENGEABLE") == prevailed


def _not_engine_findings(ctx: CaseContext | None):
    """Triggered candidates the engine was not asked about: no version in force, or no
    applicability date. They behave as the engine's own NEED_INFO findings used to."""
    return ctx.results("not_in_force", "missing_applicability_date") if ctx is not None else []


def _rules_case_verdict(findings, ctx: CaseContext | None = None) -> str:
    vs = [f.verdict for f in findings]
    extra = _not_engine_findings(ctx)
    if not findings and extra and all(r.status == "not_in_force" for r in extra):
        return OUT_OF_SCOPE
    if not findings and not extra:
        return NO_USABLE
    return (OUT_OF_SCOPE if _rules_out_of_scope(findings)
            else case_verdict(vs + ["NEED_INFO"] * len(extra)))


def _resolve_issue(rule_id: str, triggers: list, issues: dict[str, dict]) -> tuple[str, dict] | None:
    """The reviewed issue behind a rule: its own rule_id, else the decided holdings on the grounds
    in the card's triggers. Conflicting grounds -> None (excluded, never guessed)."""
    if rule_id in issues:
        return rule_id, issues[rule_id]
    hits = [(g, issues[g]) for g in triggers if g in issues and issues[g]["holding"] != "not_decided"]
    if hits and len({h["holding"] for _, h in hits}) == 1:
        return hits[0]
    return None


def _classify(verdict: str, holding: str) -> str:
    if verdict == "CHALLENGEABLE":
        return "agree" if holding == "for_policyholder" else "false_hope"
    return "agree" if holding == "for_insurer" else "disagree"


def _run_once(method, case_id, facts, cards, quotes_norm, engine_cards=None, ctx=None):
    """-> (per-finding verdicts, case verdict, quote_hits, quote_total, backend, ms, tokens, cost)

    `engine_cards`: for the rules method, only the cards the resolver found applicable."""
    t0 = time.perf_counter()
    if method == "rules":
        findings = run_rules(facts, cards if engine_cards is None else engine_cards)
        ms = int((time.perf_counter() - t0) * 1000)
        vs = {f.rule_id: f.verdict for f in findings}
        for r in _not_engine_findings(ctx):
            vs.setdefault(r.rule_id, "NEED_INFO")
        hits = sum(bool(f.rule_quote and f.rule_quote.strip()) for f in findings)
        return vs, _rules_case_verdict(findings, ctx), hits, len(findings), "rules", ms, 0, 0.0
    res = chat(ROLES[method], build_prompt(cards, facts), schema=ModelAnswer, cache=False)
    ms = int((time.perf_counter() - t0) * 1000)
    toks = res.tokens_in + res.tokens_out
    if res.parsed is None or res.needs_review:
        return {"model": "NEED_INFO"}, "NEED_INFO", 0, 1, res.backend, ms, toks, res.cost_usd
    q = normalise_ws(res.parsed.quote)
    hit = int(bool(q) and q in quotes_norm)
    return {"model": res.parsed.verdict}, res.parsed.verdict, hit, 1, res.backend, ms, toks, \
        res.cost_usd


def _finding_results(method, case_id, vs, cards, issues):
    """Per-finding comparison with the reviewed holding. -> list[FindingRow] (count=1 each)."""
    triggers = {c.rule_id: (c.triggers if isinstance(c.triggers, list) else list(c.triggers))
                for c in cards}
    decided = {k: v for k, v in issues.items() if v["holding"] != "not_decided"}
    rows = []
    for rid, verdict in vs.items():
        if verdict == "NEED_INFO":
            rows.append(FindingRow(method=method, case_id=case_id, rule_id=rid, verdict=verdict,
                                   result="abstain"))
            continue
        if method == "rules":
            hit = _resolve_issue(rid, triggers.get(rid, []), issues)
        else:  # model-only: one verdict, usable only against a single decided issue
            hit = next(iter(decided.items())) if len(decided) == 1 else None
        if hit is None or hit[1]["holding"] == "not_decided":
            why = ("no reviewed issue" if not issues
                   else "holding not decided" if hit else "no single matching reviewed issue")
            rows.append(FindingRow(method=method, case_id=case_id, rule_id=rid, verdict=verdict,
                                   result="excluded", why_excluded=why))
            continue
        issue, h = hit
        rows.append(FindingRow(method=method, case_id=case_id, rule_id=rid, verdict=verdict,
                               result=_classify(verdict, h["holding"]), issue=issue,
                               holding=h["holding"], quote=h["quote"], page_no=h["page_no"]))
    return rows


def run_eval(run_id: str, methods: list[Method], repeats: int, store: Store) -> EvalSummary:
    all_cases = store.con.execute(
        'SELECT case_id, outcome, policyholder_prevailed, excluded_reason, product_line FROM "case" '
        'ORDER BY case_id').fetchall()
    by_reviewer = [(cid, reason) for cid, _, _, reason, _ in all_cases if reason]
    # only health cases are evaluated against the health rules; the rest are listed, not scored
    not_health = [(cid, line) for cid, _, _, _, line in all_cases
                  if line not in (None, HEALTH, "unknown")]
    line_unknown = [cid for cid, _, _, reason, line in all_cases
                    if not reason and line in (None, "unknown")]
    cases = [(cid, o, p, line) for cid, o, p, reason, line in all_cases if not reason and line == HEALTH]
    cards = approved_cards(store)
    verified = {(c.rule_id, c.version) for c in cards}
    pool = cards + unapproved_cards(store, exclude=verified)  # the resolver also reports non-runnable cards
    family_map = load_family_map()
    reviewed_families = load_reviewed_families(store)
    reviewed = load_reviewed_issues(store)
    quotes_norm = normalise_ws(" ".join(c.quote for c in cards if c.quote))
    stats = {m: dict(agree=0, answered=0, chall=0, fh=0, abst=0, hits=0, total=0, ms=[], cost=0.0,
                     runs=0, stable=[], abst_cases=0, oos_runs=0, oos_cases=[], nu_runs=0, nu_cases=[],
                     skip_runs=0, skip_cases=[],
                     f_agree=0, f_dis=0, f_chall=0, f_fh=0, f_abst=0, f_excl=0, ab_runs=0, ab_safe=0)
             for m in methods}
    case_rows, finding_rows, n_cases, skipped_facts, excluded = [], {}, 0, 0, 0
    buckets = dict(eligible=0, skipped=0, oos=0, nu=0)
    traces, resolver_counts, family_sources = {}, {}, {}
    for case_id, outcome, prevailed, line in cases:
        facts = load_reviewed_facts(case_id, store)
        if not facts:
            skipped_facts += 1
            continue
        n_cases += 1
        excluded += prevailed is None
        issues = reviewed.get(case_id, {})
        # WHAT the dispute is (reviewed families, else the reviewed ground's family) vs WHICH
        # approved cards can decide it; the engine runs only on the applicable ones
        ctx, engine_cards = resolve_case_context(
            list(reviewed_families.get(case_id, {}).values()), facts, pool, line,
            unresolved=load_unresolved_facts(case_id, store), verified=verified,
            family_map=family_map)
        trace = {"families": ctx.families, "family_source": ctx.family_source,
                 "product_line": line, "candidates": [r.model_dump(mode="json") for r in ctx.trace]}
        traces[case_id] = trace
        family_sources[ctx.family_source] = family_sources.get(ctx.family_source, 0) + 1
        for r in ctx.trace:
            resolver_counts[r.status] = resolver_counts.get(r.status, 0) + 1
        # dataset tag comes from the (deterministic) rules verdict, whichever methods are run
        rule_findings = run_rules(facts, engine_cards)
        # a finding that needs a fact nobody has reviewed is skipped, never answered
        skips = ctx.skips()
        tag_cv = SKIPPED if skips else _rules_case_verdict(rule_findings, ctx)
        buckets["skipped" if skips else "oos" if tag_cv == OUT_OF_SCOPE
                else "nu" if tag_cv == NO_USABLE else "eligible"] += 1
        tag = ("skipped" if skips else "abstention" if tag_cv in (OUT_OF_SCOPE, NO_USABLE)
               else "primary" if issues else "untagged")
        per_method, rows = {}, []
        for m in methods:
            st, cvs = stats[m], []
            if skips and m != "rules":  # the same incomplete facts would feed the baseline: no spend
                st["skip_cases"].append(case_id)
                per_method[m] = [SKIPPED] * repeats
                continue
            for rep in range(repeats):
                vs, cv, hits, total, backend, ms, toks, cost = _run_once(
                    m, case_id, facts, cards, quotes_norm, engine_cards, ctx)
                if skips:  # rules method: drop the skipped findings, keep the rest at finding level
                    vs = {k: v for k, v in vs.items() if k not in skips}
                    cv = SKIPPED
                ag = _agrees(cv, prevailed)
                fh = (cv == "CHALLENGEABLE") and prevailed is False
                cvs.append(cv)
                st["runs"] += 1
                st["ms"].append(ms)
                st["cost"] += cost
                st["hits"] += hits
                st["total"] += total
                if cv == SKIPPED:
                    st["skip_runs"] += len(skips)
                    for rid, fields in skips.items():
                        key = (m, case_id, rid, "SKIPPED", "skipped")
                        if key in finding_rows:
                            finding_rows[key].count += 1
                        else:
                            finding_rows[key] = FindingRow(
                                method=m, case_id=case_id, rule_id=rid, verdict="SKIPPED",
                                result="skipped", skip_reason=skip_reason(fields))
                elif cv == NO_USABLE:
                    st["nu_runs"] += 1
                elif cv == OUT_OF_SCOPE:
                    st["oos_runs"] += 1
                elif prevailed is None:
                    pass  # case level: policyholder_prevailed unknown -> excluded and counted
                elif cv == "NEED_INFO":
                    st["abst"] += 1
                else:
                    st["answered"] += 1
                    st["agree"] += bool(ag)
                if cv == "CHALLENGEABLE" and prevailed is not None:
                    st["chall"] += 1
                    st["fh"] += fh
                if tag == "abstention":
                    st["ab_runs"] += 1
                    st["ab_safe"] += cv != "CHALLENGEABLE"
                else:
                    for fr in _finding_results(m, case_id, vs, cards, issues):
                        r = fr.result
                        st["f_abst"] += r == "abstain"
                        st["f_excl"] += r == "excluded"
                        st["f_agree"] += r == "agree"
                        st["f_dis"] += r in ("disagree", "false_hope")
                        if fr.verdict == "CHALLENGEABLE" and r in ("agree", "false_hope"):
                            st["f_chall"] += 1
                            st["f_fh"] += r == "false_hope"
                        key = (m, case_id, fr.rule_id, fr.verdict, r)
                        if key in finding_rows:
                            finding_rows[key].count += 1
                        else:
                            finding_rows[key] = fr
                extra = ({"_skipped": {r: skip_reason(f) for r, f in skips.items()}}
                         if cv == SKIPPED else {})
                if m == "rules":
                    extra["_trace"] = trace
                rows.append(dict(run_id=run_id, case_id=case_id, method=m, repeat=rep,
                                 backend=backend,
                                 verdicts=json.dumps({**vs, "_case": cv, **extra}),
                                 agrees_with_outcome=ag, false_hope=fh,
                                 latency_ms=ms, tokens=toks))
            st["stable"].append(len(set(cvs)) == 1)
            if prevailed is not None:
                st["abst_cases"] += bool(cvs) and all(v == "NEED_INFO" for v in cvs)
            if cvs and all(v == OUT_OF_SCOPE for v in cvs):
                st["oos_cases"].append(case_id)
            if cvs and all(v == NO_USABLE for v in cvs):
                st["nu_cases"].append(case_id)
            if cvs and all(v == SKIPPED for v in cvs):
                st["skip_cases"].append(case_id)
            per_method[m] = cvs
        case_rows.append(CaseRow(case_id=case_id, outcome=outcome, policyholder_prevailed=prevailed,
                                 tag=tag, verdicts=per_method))
        # written per case: paid model results survive a later case failing
        store.upsert("eval_result", rows, key=["run_id", "case_id", "method", "repeat"])
    by_method = {}
    for m, s in stats.items():
        f_n = s["f_agree"] + s["f_dis"]
        by_method[m] = Metrics(
            n_runs=s["runs"], answered_runs=s["answered"], challengeable_runs=s["chall"],
            false_hope_runs=s["fh"], agreeing_runs=s["agree"], abstained_runs=s["abst"],
            abstained_cases=s["abst_cases"], out_of_scope_runs=s["oos_runs"],
            out_of_scope_cases=s["oos_cases"], no_usable_runs=s["nu_runs"],
            no_usable_cases=s["nu_cases"], skipped_unresolved=s["skip_runs"],
            skipped_cases=s["skip_cases"],
            agreement=s["agree"] / s["answered"] if s["answered"] else None,
            false_hope_rate=s["fh"] / s["chall"] if s["chall"] else None,
            abstentions=s["abst"],
            quote_coverage=s["hits"] / s["total"] if s["total"] else None,
            stability=sum(s["stable"]) / len(s["stable"]) if s["stable"] else None,
            mean_latency_ms=sum(s["ms"]) / len(s["ms"]) if s["ms"] else None,
            cost_usd=s["cost"],
            finding_agreeing=s["f_agree"], finding_disagreeing=s["f_dis"], finding_n=f_n,
            finding_challengeable=s["f_chall"], finding_false_hope_runs=s["f_fh"],
            finding_agreement=s["f_agree"] / f_n if f_n else None,
            finding_false_hope_rate=s["f_fh"] / s["f_chall"] if s["f_chall"] else None,
            finding_abstentions=s["f_abst"], finding_excluded=s["f_excl"],
            abstention_set_runs=s["ab_runs"], safe_abstention_runs=s["ab_safe"],
            safe_abstention_rate=s["ab_safe"] / s["ab_runs"] if s["ab_runs"] else None)
    tags = [c.tag for c in case_rows]
    return EvalSummary(n_cases=n_cases, n_skipped_no_facts=skipped_facts,
                       excluded_by_reviewer=by_reviewer,
                       n_case_level_excluded=excluded, n_primary=tags.count("primary"),
                       n_eligible=buckets["eligible"], n_skipped=buckets["skipped"],
                       n_out_of_scope=buckets["oos"], n_no_usable=buckets["nu"],
                       not_health=not_health, product_line_unknown=line_unknown,
                       n_abstention_set=tags.count("abstention"), n_untagged=tags.count("untagged"),
                       repeats=repeats, by_method=by_method, cases=case_rows,
                       finding_rows=list(finding_rows.values()), traces=traces,
                       resolver_counts=resolver_counts, family_sources=family_sources)


def _fmt(x, pct=True):
    if x is None:
        return "n/a"
    return f"{x:.0%}" if pct else f"{x:.1f}"


def _ratio(num: int, den: int, unit: str = "runs") -> str:
    return f"{num}/{den} ({num / den:.0%})" if den else f"n/a (0 {unit})"


def _label(prevailed: bool | None) -> str:
    return {True: "policyholder", False: "insurer", None: "unknown"}[prevailed]


def _cell(verdicts: list[str], prevailed: bool | None) -> str:
    counts: dict[str, int] = {}
    for v in verdicts:
        counts[v] = counts.get(v, 0) + 1
    text = (next(iter(counts)) if len(counts) == 1
            else " / ".join(f"{n}\u00d7{v}" for v, n in counts.items()))
    if all(v == NO_USABLE for v in verdicts):
        return text + " (no usable ground or rule)"
    if all(v == OUT_OF_SCOPE for v in verdicts):
        return text + " (out of scope)"
    if all(v == SKIPPED for v in verdicts):
        return text + " (skipped: unresolved facts)"
    if prevailed is None:
        return text + " (excluded: winner unknown)"
    if all(v == "NEED_INFO" for v in verdicts):
        return text + " (abstain)"
    if any(_agrees(v, prevailed) is False for v in verdicts):
        return text + " \u2717"
    return text


def _count_line(label: str, cases: list[str]) -> str:
    n = len(cases)
    return (f"{label}: {', '.join(cases)} ({n} case{'s' if n != 1 else ''}; "
            "excluded from agreement and false-hope rates).")


def write_summary(summary: EvalSummary, path: Path = Path("docs/eval/summary.json"), *,
                  run_id: str | None = None) -> None:
    """The published numbers as JSON for the app's evidence page. A rate is written only when
    it was computed (a non-zero denominator); otherwise it is null, never 0 and never a guess."""
    import json
    from datetime import date

    def rate(num: int, den: int, r: float | None, key: str):
        return {key: num, "of": den, "rate": r if r is not None else num / den} if den else None

    methods = {}
    for m, x in summary.by_method.items():
        methods[m] = {
            "scorable_findings": x.finding_n,
            "agreement": rate(x.finding_agreeing, x.finding_n, x.finding_agreement, "agree"),
            "false_hope_rate": rate(x.finding_false_hope_runs, x.finding_challengeable,
                                    x.finding_false_hope_rate, "false_hope"),
            "abstained_findings": x.finding_abstentions,
            "excluded_findings": x.finding_excluded,
            "quote_coverage": x.quote_coverage,
            "stability": x.stability,
            "safe_abstention": ({"safe": x.safe_abstention_runs, "of": x.abstention_set_runs}
                                if x.abstention_set_runs else None),
            "cost_usd": round(x.cost_usd, 4),
        }
    out = {
        "run_id": run_id, "generated_on": date.today().isoformat(), "repeats": summary.repeats,
        "n_cases": summary.n_cases, "n_skipped_no_facts": summary.n_skipped_no_facts,
        "n_eligible": summary.n_eligible, "n_skipped_unresolved": summary.n_skipped,
        "n_out_of_scope": summary.n_out_of_scope, "n_no_usable": summary.n_no_usable,
        "methods": methods, "limitation": LIMITATION,
    }
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(out, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def write_report(summary: EvalSummary, path: Path = Path("docs/eval/report.md")) -> None:
    methods = list(summary.by_method)
    L = ["# Evaluation report (Eval v2)", "",
         f"Cases evaluated: {summary.n_cases}. Skipped (no reviewed facts): "
         f"{summary.n_skipped_no_facts}.", "",
         f"Denominators (health cases with reviewed facts, by what the rules method did): "
         f"Eligible: {summary.n_eligible} (an engine verdict). "
         f"Skipped (unresolved facts): {summary.n_skipped} (a fact the rules need is not yet "
         f"reviewed; no verdict, not an abstention). Out of scope: {summary.n_out_of_scope}. "
         f"No usable ground or rule: {summary.n_no_usable}.", "",
         "Dataset tags (from the rules verdict and the reviewed issues): "
         f"primary: {summary.n_primary} (in scope, at least one reviewed issue); "
         f"abstention: {summary.n_abstention_set} (out of scope, or no usable ground or rule); "
         f"in scope without a reviewed issue: {summary.n_untagged}.", "",
         "## Finding-level (primary)", "",
         "Each engine finding is compared with the human-reviewed holding on that rule's issue "
         "(or on a rejection ground in the card's triggers). CHALLENGEABLE against a holding for "
         "the policyholder, or CONSISTENT against a holding for the insurer, agrees. "
         "CHALLENGEABLE against a holding for the insurer is **false hope**. NEED_INFO is an "
         "abstention. A finding with no reviewed issue, or a not-decided holding, is excluded and "
         "counted. Model-only methods give one verdict per case and are compared only when the "
         "case has exactly one decided reviewed issue. The abstention set is reported separately.", "",
         "| Method | Agreement | False-hope rate | Abstentions | Excluded | Quote coverage "
         "| Stability | Mean latency (ms) | Cost (USD) |", "|---|---|---|---|---|---|---|---|---|"]
    for m, x in summary.by_method.items():
        L.append(f"| {m} | Agreement {_ratio(x.finding_agreeing, x.finding_n, 'findings')} "
                 f"| False-hope {_ratio(x.finding_false_hope_runs, x.finding_challengeable, 'findings')} "
                 f"| Abstained {x.finding_abstentions} findings "
                 f"| Excluded {x.finding_excluded} (no reviewed issue / not decided) "
                 f"| {_fmt(x.quote_coverage)} | {_fmt(x.stability)} "
                 f"| {_fmt(x.mean_latency_ms, False)} | {x.cost_usd:.4f} |")
    L += ["", f"Rates are pooled over {summary.repeats} repeats per case; for the rules method "
          "every repeat is identical.", ""]
    dis = [r for r in summary.finding_rows if r.result in ("disagree", "false_hope")]
    L += ["### Disagreements", ""]
    if not dis:
        L.append("None.")
    for r in dis:
        kind = "false hope" if r.result == "false_hope" else "disagrees"
        times = f" x{r.count}" if r.count > 1 else ""
        where = f" (p.{r.page_no})" if r.page_no is not None else ""
        quote = f' "{r.quote}"{where}' if r.quote else " (no quote)"
        L.append(f"- [{r.method}] {r.case_id} {r.rule_id}: engine {r.verdict} vs forum holding "
                 f"{r.holding} on `{r.issue}` ({kind}){times}:{quote}")
    L += ["", f"**Limitation:** {LIMITATION}", "",
          "## Case-level (secondary)", "",
          "The case verdict (CHALLENGEABLE if any finding is) is compared with "
          "`case.policyholder_prevailed`, which is direction-corrected for appeals (an insurer's "
          "dismissed appeal is a policyholder win). The raw court outcome is not used. "
          f"Cases whose policyholder_prevailed is unknown are excluded and counted: "
          f"{summary.n_case_level_excluded}. A court may dismiss for lack of proof or on "
          "procedure, so this does not say the rule's issue was decided that way.", "",
          "| Method | Agreement | False-hope rate | Abstentions |", "|---|---|---|---|"]
    for m, x in summary.by_method.items():
        ac = x.abstained_cases
        L.append(f"| {m} | Agreement {_ratio(x.agreeing_runs, x.answered_runs)} "
                 f"| False-hope {_ratio(x.false_hope_runs, x.challengeable_runs)} "
                 f"| Abstained {x.abstained_runs} runs / {ac} case{'s' if ac != 1 else ''} |")
    L += ["", "### Case-by-case",
          "(\u2717 = a non-abstained verdict disagrees with who prevailed)",
          "", "| case_id | prevailed | tag | " + " | ".join(methods) + " |",
          "|---|---|---|" + "---|" * len(methods)]
    for c in summary.cases:
        cells = [_cell(c.verdicts[m], c.policyholder_prevailed) for m in methods]
        L.append(f"| {c.case_id} | {_label(c.policyholder_prevailed)} | {c.tag} | "
                 + " | ".join(cells) + " |")
    L += ["", "## Abstention set", "",
          "Cases the rules method sends to a human (out of scope, or no usable ground or rule). "
          "Safe abstention = the method produced no CHALLENGEABLE on them. For the rules method "
          "this is 100% by construction; it is informative for the model-only methods.", ""]
    for m, x in summary.by_method.items():
        L.append(f"- {m}: Safe abstention "
                 f"{_ratio(x.safe_abstention_runs, x.abstention_set_runs)}")
    oos = summary.by_method.get("rules")
    if oos and oos.out_of_scope_cases:
        L += ["", _count_line(OUT_OF_SCOPE_LINE, oos.out_of_scope_cases)]
    if oos and oos.no_usable_cases:
        L += ["", _count_line(NO_USABLE_LINE, oos.no_usable_cases)]
    skipped_rows = [r for r in summary.finding_rows if r.result == "skipped"]
    if skipped_rows:
        L += ["", "## Skipped, unresolved facts", "",
              "These findings were not answered: a fact feeding the triggered card is still "
              "extracted or needs_review. They are neither engine verdicts nor abstentions and are "
              "outside every rate. Review the fact, then re-run.", ""]
        for r in skipped_rows:
            times = f" x{r.count}" if r.count > 1 else ""
            L.append(f"- [{r.method}] {r.case_id} {r.rule_id}: {r.skip_reason}{times}")
    if summary.traces:
        L += ["", "## Rule-context resolver", "",
              "What the dispute is (issue family) is kept apart from which approved card can decide "
              "it. The engine ran only on candidates marked `applicable`; every other status is a "
              "reason it did not run, never a verdict. Candidate counts by status "
              f"(over {len(summary.traces)} cases): "
              + (", ".join(f"{k} {v}" for k, v in sorted(summary.resolver_counts.items())) or "none")
              + ". Family source (cases): "
              + (", ".join(f"{k} {v}" for k, v in sorted(summary.family_sources.items())) or "none")
              + " (reviewed = human-reviewed issue family; ground = family of the reviewed "
              "rejection ground; none = neither).", "",
              "Per case: families (source), then each candidate card with its status and reason.", ""]
        for cid, t in summary.traces.items():
            fams = ", ".join(t["families"]) or "no family"
            L.append(f"- {cid}: {fams} ({t['family_source']})")
            for c in t["candidates"]:
                cand = (f"{c['rule_id']} v{c['version']}" if c["rule_id"] and c["version"] is not None
                        else c["rule_id"] or "-")
                warn = f" [warning: {'; '.join(c['warnings'])}]" if c["warnings"] else ""
                L.append(f"  - {cand}: {c['status']}: {c['reason']}{warn}")
    if summary.excluded_by_reviewer:
        L += [""] + [f"Excluded by reviewer: {cid} \u2014 {reason}"
                     for cid, reason in summary.excluded_by_reviewer]
    if summary.not_health:
        L += [""] + [f"Not health: {cid} ({line})" for cid, line in summary.not_health]
    if summary.product_line_unknown:
        n = len(summary.product_line_unknown)
        L += ["", f"Product line unknown: {n} case{'s' if n != 1 else ''} not evaluated "
                  f"({', '.join(summary.product_line_unknown)}); set one with "
                  "`cases set-product-line`."]
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(L) + "\n")
