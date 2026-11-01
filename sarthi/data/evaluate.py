"""Evaluation: deterministic rules vs model-only baselines against real court outcomes.

Headline metric is the false-hope rate: we said CHALLENGEABLE and the court dismissed.
"""
import json
import time
from pathlib import Path
from typing import Literal

from pydantic import BaseModel, ConfigDict

from sarthi.core.engine import run_rules
from sarthi.core.models import RuleCard, Verdict
from sarthi.core.store import Store
from sarthi.data.case_facts import load_reviewed_facts
from sarthi.data.parse_docs import normalise_ws
from sarthi.data.rule_cards import approved_cards
from sarthi.llm.client import chat

Method = Literal["rules", "glimmer_only", "spark_only"]
ROLES = {"glimmer_only": "judge_glimmer", "spark_only": "judge_spark"}
FAVOURABLE = {"allowed", "partly_allowed"}
OUT_OF_SCOPE = "OUT_OF_SCOPE"
NO_USABLE = "NO_USABLE_GROUND_OR_RULE"
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
    agreement: float | None = None
    false_hope_rate: float | None = None
    abstentions: int = 0
    quote_coverage: float | None = None
    stability: float | None = None
    mean_latency_ms: float | None = None
    cost_usd: float = 0.0


class CaseRow(BaseModel):
    case_id: str
    outcome: str
    verdicts: dict[str, list[str]]  # method -> case-level verdict per repeat


class EvalSummary(BaseModel):
    n_cases: int
    n_skipped_no_outcome: int = 0
    n_skipped_no_facts: int = 0
    repeats: int = 1
    by_method: dict[str, Metrics]
    cases: list[CaseRow] = []


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


def _agrees(verdict: str, outcome: str) -> bool | None:
    if verdict in ("NEED_INFO", OUT_OF_SCOPE, NO_USABLE):
        return None
    return (verdict == "CHALLENGEABLE") == (outcome in FAVOURABLE)


def _run_once(method, case_id, facts, cards, quotes_norm):
    """-> (per-finding verdicts, case verdict, quote_hits, quote_total, backend, ms, tokens, cost)"""
    t0 = time.perf_counter()
    if method == "rules":
        findings = run_rules(facts, cards)
        ms = int((time.perf_counter() - t0) * 1000)
        vs = {f.rule_id: f.verdict for f in findings}
        hits = sum(bool(f.rule_quote and f.rule_quote.strip()) for f in findings)
        cv = (NO_USABLE if not findings else OUT_OF_SCOPE if _rules_out_of_scope(findings)
              else case_verdict(list(vs.values())))
        return vs, cv, hits, len(findings), "rules", ms, 0, 0.0
    res = chat(ROLES[method], build_prompt(cards, facts), schema=ModelAnswer, cache=False)
    ms = int((time.perf_counter() - t0) * 1000)
    toks = res.tokens_in + res.tokens_out
    if res.parsed is None or res.needs_review:
        return {"model": "NEED_INFO"}, "NEED_INFO", 0, 1, res.backend, ms, toks, res.cost_usd
    q = normalise_ws(res.parsed.quote)
    hit = int(bool(q) and q in quotes_norm)
    return {"model": res.parsed.verdict}, res.parsed.verdict, hit, 1, res.backend, ms, toks, \
        res.cost_usd


def run_eval(run_id: str, methods: list[Method], repeats: int, store: Store) -> EvalSummary:
    cases = store.con.execute('SELECT case_id, outcome FROM "case" ORDER BY case_id').fetchall()
    skipped_outcome = sum(o is None for _, o in cases)
    cards = approved_cards(store)
    quotes_norm = normalise_ws(" ".join(c.quote for c in cards if c.quote))
    stats = {m: dict(agree=0, answered=0, chall=0, fh=0, abst=0, hits=0, total=0, ms=[], cost=0.0,
                     runs=0, stable=[], abst_cases=0, oos_runs=0, oos_cases=[], nu_runs=0, nu_cases=[]) for m in methods}
    case_rows, n_cases, skipped_facts = [], 0, 0
    for case_id, outcome in cases:
        if outcome is None:
            continue
        facts = load_reviewed_facts(case_id, store)
        if not facts:
            skipped_facts += 1
            continue
        n_cases += 1
        per_method, rows = {}, []
        for m in methods:
            st, cvs = stats[m], []
            for rep in range(repeats):
                vs, cv, hits, total, backend, ms, toks, cost = _run_once(
                    m, case_id, facts, cards, quotes_norm)
                ag = _agrees(cv, outcome)
                fh = (cv == "CHALLENGEABLE") and outcome == "dismissed"
                cvs.append(cv)
                st["runs"] += 1
                st["ms"].append(ms)
                st["cost"] += cost
                st["hits"] += hits
                st["total"] += total
                if cv == NO_USABLE:
                    st["nu_runs"] += 1
                elif cv == OUT_OF_SCOPE:
                    st["oos_runs"] += 1
                elif cv == "NEED_INFO":
                    st["abst"] += 1
                else:
                    st["answered"] += 1
                    st["agree"] += bool(ag)
                if cv == "CHALLENGEABLE":
                    st["chall"] += 1
                    st["fh"] += fh
                rows.append(dict(run_id=run_id, case_id=case_id, method=m, repeat=rep,
                                 backend=backend,
                                 verdicts=json.dumps({**vs, "_case": cv}),
                                 agrees_with_outcome=ag, false_hope=fh,
                                 latency_ms=ms, tokens=toks))
            st["stable"].append(len(set(cvs)) == 1)
            st["abst_cases"] += bool(cvs) and all(v == "NEED_INFO" for v in cvs)
            if cvs and all(v == OUT_OF_SCOPE for v in cvs):
                st["oos_cases"].append(case_id)
            if cvs and all(v == NO_USABLE for v in cvs):
                st["nu_cases"].append(case_id)
            per_method[m] = cvs
        case_rows.append(CaseRow(case_id=case_id, outcome=outcome, verdicts=per_method))
        # written per case: paid model results survive a later case failing
        store.upsert("eval_result", rows, key=["run_id", "case_id", "method", "repeat"])
    by_method = {}
    for m, s in stats.items():
        by_method[m] = Metrics(
            n_runs=s["runs"], answered_runs=s["answered"], challengeable_runs=s["chall"],
            false_hope_runs=s["fh"], agreeing_runs=s["agree"], abstained_runs=s["abst"],
            abstained_cases=s["abst_cases"], out_of_scope_runs=s["oos_runs"],
            out_of_scope_cases=s["oos_cases"], no_usable_runs=s["nu_runs"],
            no_usable_cases=s["nu_cases"],
            agreement=s["agree"] / s["answered"] if s["answered"] else None,
            false_hope_rate=s["fh"] / s["chall"] if s["chall"] else None,
            abstentions=s["abst"],
            quote_coverage=s["hits"] / s["total"] if s["total"] else None,
            stability=sum(s["stable"]) / len(s["stable"]) if s["stable"] else None,
            mean_latency_ms=sum(s["ms"]) / len(s["ms"]) if s["ms"] else None,
            cost_usd=s["cost"])
    return EvalSummary(n_cases=n_cases, n_skipped_no_outcome=skipped_outcome,
                       n_skipped_no_facts=skipped_facts, repeats=repeats, by_method=by_method, cases=case_rows)


def _fmt(x, pct=True):
    if x is None:
        return "n/a"
    return f"{x:.0%}" if pct else f"{x:.1f}"


def _ratio(num: int, den: int) -> str:
    return f"{num}/{den} ({num / den:.0%})" if den else "n/a (0 runs)"


def _cell(verdicts: list[str], outcome: str) -> str:
    counts: dict[str, int] = {}
    for v in verdicts:
        counts[v] = counts.get(v, 0) + 1
    text = (next(iter(counts)) if len(counts) == 1
            else " / ".join(f"{n}\u00d7{v}" for v, n in counts.items()))
    if all(v == NO_USABLE for v in verdicts):
        return text + " (no usable ground or rule)"
    if all(v == OUT_OF_SCOPE for v in verdicts):
        return text + " (out of scope)"
    if all(v == "NEED_INFO" for v in verdicts):
        return text + " (abstain)"
    if any(_agrees(v, outcome) is False for v in verdicts):
        return text + " \u2717"
    return text


def write_report(summary: EvalSummary, path: Path = Path("docs/eval/report.md")) -> None:
    L = ["# Evaluation report", "",
         f"Cases evaluated: {summary.n_cases}. Skipped (no outcome): "
         f"{summary.n_skipped_no_outcome}. Skipped (no reviewed facts): "
         f"{summary.n_skipped_no_facts}.", "",
         "| Method | Agreement | False-hope rate | Abstentions | Quote coverage | Stability "
         "| Mean latency (ms) | Cost (USD) |", "|---|---|---|---|---|---|---|---|"]
    for m, x in summary.by_method.items():
        ac = x.abstained_cases
        L.append(f"| {m} | Agreement {_ratio(x.agreeing_runs, x.answered_runs)} "
                 f"| False-hope {_ratio(x.false_hope_runs, x.challengeable_runs)} "
                 f"| Abstained {x.abstained_runs} runs / {ac} case{'s' if ac != 1 else ''} "
                 f"| {_fmt(x.quote_coverage)} | {_fmt(x.stability)} "
                 f"| {_fmt(x.mean_latency_ms, False)} | {x.cost_usd:.4f} |")
    methods = list(summary.by_method)
    oos = summary.by_method.get("rules")
    if oos and oos.out_of_scope_cases:
        L += ["", f"{OUT_OF_SCOPE_LINE}: {', '.join(oos.out_of_scope_cases)} "
              f"({len(oos.out_of_scope_cases)} case{'s' if len(oos.out_of_scope_cases) != 1 else ''}; "
              "excluded from agreement and false-hope rates)."]
    if oos and oos.no_usable_cases:
        L += ["", f"{NO_USABLE_LINE}: {', '.join(oos.no_usable_cases)} "
              f"({len(oos.no_usable_cases)} case{'s' if len(oos.no_usable_cases) != 1 else ''}; "
              "excluded from agreement and false-hope rates)."]
    L += ["", f"Rates are pooled over {summary.repeats} repeats per case; for the rules method "
          "every repeat is identical.", "",
          f"**Limitation:** {LIMITATION}", "", "## Case-by-case",
          "(\u2717 = a non-abstained verdict disagrees with the court outcome)",
          "", "| case_id | outcome | " + " | ".join(methods) + " |",
          "|---|---|" + "---|" * len(methods)]
    for c in summary.cases:
        cells = [_cell(c.verdicts[m], c.outcome) for m in methods]
        L.append(f"| {c.case_id} | {c.outcome} | " + " | ".join(cells) + " |")
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(L) + "\n")
