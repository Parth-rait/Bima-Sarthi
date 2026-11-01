"""Spend-capped candidate discovery on Indian Kanoon.

Searches many query families (health grounds, health-adjacent themes, and adjacent insurance
lines parked for a FUTURE benchmark), pre-screens each hit from search metadata alone (free), logs
candidates to JSONL, and optionally fetches only health-likely documents. Every HTTP call goes
through `cases._call`, so the shared IK ledger (data/ik_spend.jsonl) and IK_CAP_INR still apply;
`RunBudget` adds a per-run cap on top. Nothing here writes to the DuckDB (fetch aside, which uses
the Store the caller passes in).
"""
import json
import math
import os
import re
import time
import uuid
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Callable

from sarthi.data import cases
from sarthi.data.fetch import FetchError

PAGE_SIZE = 10
EPS = 1e-9
DEFAULT_SEARCH_INR = 0.5     # used only to ESTIMATE in --dry-run when prices are not exported
DEFAULT_DOC_INR = 0.2

# ---- query catalogue ------------------------------------------------------------------------
# NB: conjunction is the implicit space (explicit ANDD breaks IK results); ORR / NOTT are fine.
_DOCTYPES = "doctypes: consumer,supremecourt,highcourts"
WINDOW_OLD = f"{_DOCTYPES} fromdate: 1-10-2020 todate: 31-12-2022"
WINDOW_NEW = f"{_DOCTYPES} fromdate: 1-1-2023"
WINDOW_ADJACENT = f"{_DOCTYPES} fromdate: 1-10-2020"
_HEALTH = '("health insurance" ORR mediclaim)'


def _windows(body: str) -> list[str]:
    """Health queries run over two decision-date windows so older decisions about 2020+ claims
    (IK filters the DECISION date) are reachable alongside the newest ones."""
    return [f"{body} {WINDOW_OLD}", f"{body} {WINDOW_NEW}"]


def _health(terms: str) -> list[str]:
    return _windows(f'{_HEALTH} {terms} NOTT "life insurance"')


def _adjacent(*bodies: str) -> list[str]:
    return [f"{b} {WINDOW_ADJACENT}" for b in bodies]


def _reuse(queries: dict[str, str], filters: str) -> list[str]:
    out: list[str] = []
    for q in queries.values():
        out.extend(_windows(q.removesuffix(" " + filters)))
    return out


_HEALTH_THEMES: dict[str, list[str]] = {
    "health_tpa": [
        '(TPA ORR "third party administrator") (repudiated ORR rejected ORR "deficiency in service") claim',
        'TPA cashless ("pre-authorisation" ORR "pre-authorization") denied hospital',
    ],
    "health_mediclaim": [
        'mediclaim repudiated hospitalisation "deficiency in service"',
        '"mediclaim policy" (rejected ORR disallowed ORR "partial settlement") claim',
    ],
    "health_cashless_copay": [
        'cashless (denied ORR refused ORR rejected) hospital "deficiency in service"',
        '("co-payment" ORR copayment) deduction claim settled',
    ],
    "health_deductions": [
        '("non-payable" ORR consumables ORR "not payable") deduction "balance amount" claim',
        '"sum insured" (capping ORR "room rent") "proportionate deduction"',
    ],
    "health_portability": [
        'portability ("waiting period" ORR "continuity benefit") repudiated',
        'portability "previous insurer" claim repudiated "deficiency in service"',
    ],
    "health_ombudsman": [
        '"Insurance Ombudsman" award ("writ petition" ORR challenged ORR "set aside")',
        '"Insurance Ombudsman" mediclaim award dismissed complaint appeal',
    ],
}

# family -> IK query strings
DISCOVERY_QUERIES: dict[str, list[str]] = {
    "health_grounds": _reuse(cases.QUERIES, cases.QUERY_FILTERS),
    "health_expansion": _reuse(cases.EXPANSION_QUERIES, cases.EXPANSION_FILTERS),
    **{fam: [q for body in bodies for q in _health(body)] for fam, bodies in _HEALTH_THEMES.items()},
    # adjacent product lines: parked, labelled, for a FUTURE benchmark (never fed to the health engine)
    "life": _adjacent(
        '"life insurance" repudiated ("death claim" ORR nominee) ("suppression" ORR "material facts" ORR "non-disclosure")',
        '"life insurance policy" "death claim" repudiated "deficiency in service"'),
    "personal_accident": _adjacent(
        '"personal accident" policy (repudiated ORR rejected) claim',
        '"accidental death" insurance claim repudiated nominee'),
    "crop": _adjacent('"crop insurance" claim (rejected ORR repudiated ORR PMFBY ORR "crop loss")'),
    "credit_life": _adjacent(
        '"credit life" insurance (loan ORR borrower) death claim repudiated',
        '"group insurance" loan borrower death repudiated NOTT "housing loan"'),
}

FAMILY_LINE: dict[str, str] = {
    **{fam: "health" for fam in DISCOVERY_QUERIES if fam.startswith("health_")},
    "life": "life", "personal_accident": "personal_accident", "crop": "crop", "credit_life": "credit_life",
}


# ---- pagination --------------------------------------------------------------------------------

class RunCapReached(RuntimeError):
    pass


@dataclass
class RunBudget:
    """Per-run INR cap measured against the shared ledger (so retries billed by `_call` count)."""
    max_inr: float
    start: float = field(default_factory=cases.total_spend_inr)

    @property
    def spent(self) -> float:
        return cases.total_spend_inr() - self.start

    def check(self, cost: float) -> None:
        if self.spent + cost > self.max_inr + EPS:
            raise RunCapReached(f"run cap {self.max_inr:.2f} INR reached "
                                f"(spent {self.spent:.2f}, next call {cost:.2f})")


def parse_found(found) -> int | None:
    """IK's `found` looks like '1 - 10 of 1,234': the total is the number after 'of'."""
    m = re.search(r"\bof\s+([\d,]+)", str(found or ""))
    if m:
        return int(m.group(1).replace(",", ""))
    if re.fullmatch(r"\s*0\s*", str(found or "")):
        return 0
    return None


@dataclass
class SearchResult:
    docs: list[dict]
    total: int | None
    pages: int
    stopped: str     # exhausted | max_results | empty_page | run_cap | global_cap


def search_pages(query: str, max_results: int, *, budget: RunBudget | None = None,
                 sleep: Callable[[float], None] = time.sleep) -> SearchResult:
    """Page through one query. Stops as soon as the reported total is exhausted, so the extra,
    billed, empty page past the last one is never requested."""
    docs: list[dict] = []
    total: int | None = None
    pages = 0
    stopped = "empty_page"
    while len(docs) < max_results:
        try:
            if budget:
                budget.check(cases._price("IK_COST_SEARCH_INR"))
            body = cases._call("/search/", "search", "IK_COST_SEARCH_INR", sleep, query,
                               data={"formInput": query, "pagenum": pages})
        except RunCapReached:
            stopped = "run_cap"
            break
        except cases.SpendCapExceeded:
            stopped = "global_cap"
            break
        pages += 1
        got = body.get("docs") or []
        found = parse_found(body.get("found"))
        if found is not None:
            total = found
        docs.extend(got)
        if not got:
            stopped = "empty_page"
            break
        if total is not None and len(docs) >= total:
            stopped = "exhausted"
            break
        if len(docs) >= max_results:
            stopped = "max_results"
            break
    return SearchResult(docs[:max_results], total, pages, stopped)


# ---- pre-screen (free: search metadata only) ----------------------------------------------------

@dataclass
class Screen:
    label: str      # likely_health | likely_other_line | exclude | unsure
    line: str       # product_line_guess
    reason: str = ""


def _rx(*alts: str) -> re.Pattern:
    return re.compile("|".join(alts), re.I)


_SCHEME = _rx(r"Commissioner of Treasur", r"Empowered Committee", r"\bCGHS\b", r"Central Government Health Scheme",
              r"\bESI\b", r"\bESIC\b", r"Employees'?\s+State Insurance", r"Ayushman", r"A+rogya\s?sri",
              r"\bPM-?JAY\b", r"Rashtriya Swasthya", r"Medical Attendance Rules", r"Jan Arogya", r"\bTreasur(?:y|ies)\b")
_MOTOR = _rx(r"motor vehicle", r"\bvehicles?\b", r"Motor Accident", r"\bMACT\b", r"own damage", r"\btruck\b",
             r"\bgoods carriage\b")
_HOUSING = _rx(r"housing loan", r"home loan")
_BORROWER_DEATH = _rx(r"\bborrower", r"\bdeath\b", r"\bdied\b", r"\bdeceased\b")
_STRONG_HEALTH = _rx(r"mediclaim", r"hospitali[sz]ation", r"\bcashless\b", r"\bTPA\b", r"third party administrator",
                     r"pre-?existing", r"room rent", r"co-?payment", r"Star Health", r"Care Health",
                     r"Niva Bupa", r"Max Bupa", r"Religare Health", r"Aditya Birla Health", r"Manipal ?Cigna",
                     r"Apollo Munich", r"health plus", r"Jeevan Arogya", r"medical expenses")
_WEAK_HEALTH = _rx(r"health insurance", r"health polic", r"health plan", r"health cover")
_LIFE = _rx(r"Life Insurance Corporation", r"\bLIC\b", r"life insurance", r"\b(?:SBI|HDFC|ICICI Prudential|Max|"
            r"Bajaj Allianz|Tata AIA|Kotak|Aditya Birla Sun|PNB Met|Reliance Nippon|Exide|Aviva|Canara HSBC) Life\b",
            r"death claim", r"\bnominee\b", r"term plan", r"\bendowment\b")
_ACCIDENT = _rx(r"personal accident", r"accidental death", r"accident insurance", r"\bPA polic")
_CROP = _rx(r"crop insurance", r"\bPMFBY\b", r"Fasal Bima", r"crop loss", r"\bkharif\b", r"\brabi\b")
_CREDIT_LIFE = _rx(r"credit[- ]life", r"loan protection", r"group insurance")
_LOAN = _rx(r"\bloan\b")
_TAGS = re.compile(r"<[^>]+>")


def _text(meta: dict) -> str:
    parts = (meta.get(k) or "" for k in ("title", "headline", "fragment", "docsource"))
    return re.sub(r"\s+", " ", _TAGS.sub("", " ".join(str(p) for p in parts)))


def make_snippet(meta: dict, limit: int = 400) -> str:
    """Headline (else fragment) with HTML stripped, kept in the candidate log for human review."""
    raw = meta.get("headline") or meta.get("fragment") or ""
    return re.sub(r"\s+", " ", _TAGS.sub("", str(raw))).strip()[:limit]


def prescreen(meta: dict, prior: str = "health") -> Screen:
    """Deterministic label from title/headline/fragment/docsource. `prior` is the query family's
    product line; borderline cases stay `unsure` rather than being discarded."""
    t = _text(meta)
    if m := _SCHEME.search(t):
        return Screen("exclude", prior, f"government scheme / non-insurer matter: {m.group(0)}")
    strong = bool(_STRONG_HEALTH.search(t))
    weak = bool(_WEAK_HEALTH.search(t))
    if (m := _HOUSING.search(t)) and _BORROWER_DEATH.search(t):
        return Screen("exclude", prior, f"housing-loan death claim: {m.group(0)}")
    if (m := _MOTOR.search(t)) and not strong:
        return Screen("exclude", prior, f"motor / vehicle matter: {m.group(0)}")

    other: list[str] = []
    if _LIFE.search(t):
        other.append("life")
    if _ACCIDENT.search(t):
        other.append("personal_accident")
    if _CROP.search(t):
        other.append("crop")
    if _CREDIT_LIFE.search(t) or (_LOAN.search(t) and _BORROWER_DEATH.search(t)):
        other.append("credit_life")

    if other and (strong or weak):
        # e.g. a life insurer selling a health policy, or an accident rider on a mediclaim cover
        return Screen("unsure", "health" if strong else other[0], f"mixed signals: health + {','.join(other)}")
    if other:
        # credit-life wins over bare life when a loan is involved; accident/crop over life keywords
        line = next((x for x in ("credit_life", "crop", "personal_accident", "life") if x in other), other[0])
        return Screen("likely_other_line", line, f"{line} signals")
    if strong:
        return Screen("likely_health", "health", "health-claim signals")
    if weak:
        return Screen("unsure", "health", "generic health-insurance mention only")
    return Screen("unsure", prior, "no distinguishing signal")


# ---- candidate / run logs -------------------------------------------------------------------------

def stored_tids_from(case_ids) -> set[str]:
    return {c[3:] if str(c).startswith("ik_") else str(c) for c in case_ids}


def stored_case_tids(db_path: Path) -> set[str]:
    """tids already in the `case` table, read with a READ-ONLY connection (never writes the DB)."""
    import duckdb
    db_path = Path(db_path)
    if not db_path.exists():
        return set()
    con = duckdb.connect(str(db_path), read_only=True)
    try:
        rows = con.execute('SELECT case_id FROM "case" WHERE case_id LIKE \'ik_%\'').fetchall()
    except duckdb.CatalogException:
        return set()
    finally:
        con.close()
    return stored_tids_from(r[0] for r in rows)


class CandidateLog:
    """Append-only JSONL keyed by tid. A later line for the same tid (e.g. a fetched marker)
    merges over the earlier one on load; new candidates are written only if the tid is unseen."""

    def __init__(self, path: Path):
        self.path = Path(path)
        self._rows: dict[str, dict] = {}
        if self.path.exists():
            for line in self.path.read_text().splitlines():
                if line.strip():
                    r = json.loads(line)
                    self._rows.setdefault(str(r["tid"]), {}).update(r)

    def __contains__(self, tid) -> bool:
        return str(tid) in self._rows

    def get(self, tid) -> dict | None:
        return self._rows.get(str(tid))

    def all(self) -> list[dict]:
        return list(self._rows.values())

    def _append(self, rec: dict) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        with open(self.path, "a") as f:
            f.write(json.dumps(rec) + "\n")

    def add(self, rec: dict) -> bool:
        tid = str(rec["tid"])
        if tid in self._rows:
            return False
        rec = {**rec, "tid": tid, "fetched": bool(rec.get("fetched", False))}
        self._rows[tid] = dict(rec)
        self._append(rec)
        return True

    def mark_fetched(self, tid, run_id: str) -> None:
        upd = {"tid": str(tid), "fetched": True, "fetched_run_id": run_id,
               "fetched_ts": datetime.now().isoformat(timespec="seconds")}
        self._rows.setdefault(str(tid), {}).update(upd)
        self._append(upd)


def _append_jsonl(path: Path, rec: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "a") as f:
        f.write(json.dumps(rec) + "\n")


# ---- planning -----------------------------------------------------------------------------------------

def resolve_families(families: list[str]) -> list[str]:
    """'all' = every family; 'none' = no searching (use with fetch to spend only on documents)."""
    if families == ["none"]:
        return []
    if any(f == "all" for f in families):
        return list(DISCOVERY_QUERIES)
    unknown = [f for f in families if f not in DISCOVERY_QUERIES]
    if unknown:
        raise ValueError(f"unknown family/families: {', '.join(unknown)}. "
                         f"Known: {', '.join(DISCOVERY_QUERIES)}")
    return list(dict.fromkeys(families))


def plan(families: list[str], *, max_results: int, search_price: float, doc_price: float) -> dict:
    fams = resolve_families(families)
    queries = [{"family": f, "line": FAMILY_LINE[f], "query": q} for f in fams for q in DISCOVERY_QUERIES[f]]
    pages = max(1, math.ceil(max_results / PAGE_SIZE))
    return {"families": fams, "n_queries": len(queries), "pages_per_query_max": pages,
            "max_results": max_results, "queries": queries,
            "search_price": search_price, "doc_price": doc_price,
            "est_search_inr_max": len(queries) * pages * search_price,
            "est_fetch_inr_per_candidate": doc_price}


# ---- the run ---------------------------------------------------------------------------------------------

def new_run_id() -> str:
    return datetime.now().strftime("%Y%m%d-%H%M%S-") + uuid.uuid4().hex[:4]


def _fetchable(c: dict) -> bool:
    return (not c.get("fetched") and c.get("product_line_guess") == "health"
            and c.get("prescreen") in ("likely_health", "unsure"))


def run_discovery(families: list[str], *, max_results: int, max_inr: float, run_id: str | None = None,
                  stored_tids: set[str], discovery_dir: Path | None = None, fetch: bool = False,
                  store=None, sleep: Callable[[float], None] = time.sleep) -> dict:
    fams = resolve_families(families)
    run_id = run_id or new_run_id()
    ddir = Path(discovery_dir) if discovery_dir else cases._data_dir() / "discovery"
    log = CandidateLog(ddir / "candidates.jsonl")
    budget = RunBudget(max_inr)
    spend_before = cases.total_spend_inr()
    started = datetime.now().isoformat(timespec="seconds")
    seen_this_run: set[str] = set()
    qrows: list[dict] = []
    by_label: dict[str, int] = {}
    by_line: dict[str, int] = {}
    by_line_label: dict[str, int] = {}
    pages_billed = 0
    stopped: str | None = None

    for fam in fams:
        if stopped:
            break
        for q in DISCOVERY_QUERIES[fam]:
            res = search_pages(q, max_results, budget=budget, sleep=sleep)
            pages_billed += res.pages
            row = {"family": fam, "query": q, "requested": max_results, "returned": len(res.docs),
                   "total_found": res.total, "pages": res.pages, "stopped": res.stopped,
                   "new": 0, "stored_duplicates": 0, "previous_duplicates": 0, "run_duplicates": 0}
            for d in res.docs:
                tid = str(d.get("tid"))
                if tid in stored_tids:
                    row["stored_duplicates"] += 1
                elif tid in seen_this_run:
                    row["run_duplicates"] += 1
                elif tid in log:
                    row["previous_duplicates"] += 1
                    seen_this_run.add(tid)
                else:
                    seen_this_run.add(tid)
                    s = prescreen(d, FAMILY_LINE[fam])
                    log.add({"tid": tid, "query_family": fam, "query": q, "run_id": run_id,
                             "title": d.get("title"), "forum": d.get("docsource"),
                             "publishdate": d.get("publishdate"), "prescreen": s.label,
                             "product_line_guess": s.line, "prescreen_reason": s.reason,
                             "snippet": make_snippet(d), "numcites": d.get("numcites"), "fetched": False})
                    row["new"] += 1
                    by_label[s.label] = by_label.get(s.label, 0) + 1
                    by_line[s.line] = by_line.get(s.line, 0) + 1
                    k = f"{s.line}/{s.label}"
                    by_line_label[k] = by_line_label.get(k, 0) + 1
            qrows.append(row)
            if res.stopped in ("run_cap", "global_cap"):
                stopped = res.stopped
                break

    fetched = 0
    fetch_errors: list[str] = []
    if fetch:
        if store is None:
            raise ValueError("fetch=True needs a store")
        order = {"likely_health": 0, "unsure": 1}
        todo = sorted((c for c in log.all() if _fetchable(c) and c["tid"] not in stored_tids),
                      key=lambda c: order[c["prescreen"]])
        for c in todo:
            try:
                budget.check(cases._price("IK_COST_DOC_INR"))
                cases.fetch_case(c["tid"], store, sleep=sleep)
            except RunCapReached:
                stopped = stopped or "run_cap"
                break
            except cases.SpendCapExceeded:
                stopped = stopped or "global_cap"
                break
            except FetchError as e:
                fetch_errors.append(f"{c['tid']}: {e}")
                continue
            log.mark_fetched(c["tid"], run_id)
            fetched += 1

    spend_after = cases.total_spend_inr()
    cap = float(os.environ.get("IK_CAP_INR", cases.DEFAULT_CAP_INR))
    headroom = cap - spend_after
    run = {"run_id": run_id, "ts": started, "families": fams, "max_results_per_query": max_results,
           "max_inr": max_inr, "queries": qrows, "pages_billed": pages_billed,
           "unique_new": sum(r["new"] for r in qrows),
           "duplicates": {"stored": sum(r["stored_duplicates"] for r in qrows),
                          "previous": sum(r["previous_duplicates"] for r in qrows),
                          "within_run": sum(r["run_duplicates"] for r in qrows)},
           "ik_spend_before": spend_before, "ik_spend_after": spend_after,
           "ik_cap_inr": cap, "ik_headroom_inr": headroom,
           "prescreen_counts": {"by_label": by_label, "by_line": by_line, "by_line_label": by_line_label},
           "fetch": fetch, "fetched": fetched, "fetch_errors": fetch_errors, "stopped": stopped}
    _append_jsonl(ddir / "runs.jsonl", run)
    return {"run": run, "run_id": run_id, "stopped": stopped, "headroom_inr": headroom,
            "spent_this_run": spend_after - spend_before}
