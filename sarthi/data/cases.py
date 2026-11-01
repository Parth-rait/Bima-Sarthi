"""Real case ingestion from Indian Kanoon judgments (and hand-saved e-Jagriti orders).

API shapes follow the public Indian Kanoon API documentation and are unverified against a
live call. Per-call prices are not hard-coded: set IK_COST_SEARCH_INR / IK_COST_DOC_INR.
"""
import json
import os
import re
import time
from datetime import date, datetime
from html.parser import HTMLParser
from pathlib import Path
from typing import Callable

from sarthi.core.models import Case
from sarthi.core.registry import SourceSpec
from sarthi.core.store import Store
from sarthi.data.fetch import USER_AGENT, _request, _store_bytes, record_source

IK_BASE = "https://api.indiankanoon.org"
LICENCE_NOTE = "Judgment text via Indian Kanoon API; display attribution: powered by IKanoon"
DEFAULT_CAP_INR = 500.0
OUTCOME_WINDOW = 2000

# Indian Kanoon operators are ANDD / ORR / NOTT (case-sensitive, spaces both sides); ANDD is
# implicit between words and phrases go in double quotes. Filters ride inside formInput.
QUERY_FILTERS = "doctypes: consumer,supremecourt,highcourts fromdate: 1-10-2020"
_HEALTH = '("health insurance" ORR mediclaim)'
_NOT_LIFE = 'NOTT ("life insurance" ORR "life insurance corporation")'


def build_query(terms: str) -> str:
    """Health-insurance-only IK query for a ground's `terms`, with the shared filters appended."""
    return f"{_HEALTH} {terms} {_NOT_LIFE} {QUERY_FILTERS}"


# One query per covered rejection ground (deduction-type grounds share one).
QUERIES: dict[str, str] = {k: build_query(v) for k, v in {
    "non_disclosure": 'repudiated "non-disclosure" ("eight years" ORR moratorium ORR "60 months")',
    "pre_existing_disease": 'repudiated "pre-existing disease" ("48 months" ORR "36 months" ORR moratorium)',
    "specific_waiting_period": 'repudiated "specific waiting period" ("waiting period" ORR "24 months")',
    "initial_waiting_period": 'repudiated "initial waiting period" ("30 days" ORR "waiting period")',
    "portability": 'portability ("continuity benefit" ORR "waiting period" ORR "portability credit")',
    "exclusion": 'repudiated ("policy exclusion" ORR "excluded") "medical expenses"',
    "deduction": '("non-payable" ORR consumables ORR "proportionate deduction" ORR "co-payment")',
    "room_rent": '"insurance company" "room rent" ("proportionate deduction" ORR "room rent capping" ORR eligibility)',
    "sub_limit": '("sub-limit" ORR sublimit ORR "sub limit") claim reduced',
    "cashless_delay": 'cashless ("pre-authorisation" ORR "cashless facility" ORR denied) deficiency',
    "discharge_delay": '"insurance company" "discharge" ("delay in settlement" ORR "delay" ORR "claim review committee") deficiency',
    "process_defect": '"insurance company" repudiated ("delay in intimation" ORR condonation ORR "documents not submitted" ORR "claim review committee")',
}.items()}

INSURER_ALIASES: dict[str, list[str]] = {
    "Star Health": ["Star Health"],
    "New India Assurance": ["New India Assurance"],
    "United India": ["United India Insurance"],
    "Oriental Insurance": ["Oriental Insurance"],
    "National Insurance": ["National Insurance Co"],
    "HDFC ERGO": ["HDFC ERGO", "HDFC Ergo", "Apollo Munich"],
    "ICICI Lombard": ["ICICI Lombard"],
    "Bajaj Allianz": ["Bajaj Allianz"],
    "Care Health": ["Care Health", "Religare Health"],
    "Niva Bupa": ["Niva Bupa", "Max Bupa"],
    "Aditya Birla": ["Aditya Birla Health", "Aditya Birla"],
    "Tata AIG": ["Tata AIG"],
    "SBI General": ["SBI General"],
    "Reliance General": ["Reliance General"],
    "ManipalCigna": ["ManipalCigna", "Manipal Cigna"],
}

# Alternation order matters: at the same start, longer/more specific phrases win; "not allowed"
# and "disallowed" start earlier than / are not word-bounded to a bare "allowed".
_OUTCOME_RE = re.compile(
    r"(?P<partly>\bpart(?:ly|ially)\s+allowed\b|\ballowed\s+(?:in\s+part|part(?:ly|ially))\b)"
    r"|(?P<dismissed>\bnot\s+allowed\b|\bdisallowed\b|\bnot\s+maintainable\b|\bdismissed\b)"
    r"|(?P<allowed>\ballowed\b)", re.I)
AMBIGUITY_WINDOW = 500


class SpendCapExceeded(RuntimeError):
    pass


class IKConfigError(RuntimeError):
    pass


class _Text(HTMLParser):
    def __init__(self):
        super().__init__()
        self.parts: list[str] = []
        self._skip = 0

    def handle_starttag(self, tag, attrs):
        if tag in ("script", "style"):
            self._skip += 1

    def handle_endtag(self, tag):
        if tag in ("script", "style") and self._skip:
            self._skip -= 1

    def handle_data(self, data):
        if not self._skip:
            self.parts.append(data)


def html_to_text(html: str) -> str:
    p = _Text()
    p.feed(html)
    p.close()
    return re.sub(r"\s+", " ", " ".join(p.parts)).strip()


def detect_outcome(text: str) -> str | None:
    """Operative label = matching phrase nearest the end of the text. If both an allowed-family
    and a dismissed-family phrase fall in the final 500 chars the order is ambiguous -> None."""
    tail = text[-OUTCOME_WINDOW:]
    found = [(m.start(), m.lastgroup) for m in _OUTCOME_RE.finditer(tail)]
    if not found:
        return None
    cutoff = len(tail) - AMBIGUITY_WINDOW
    near = {g == "dismissed" for pos, g in found if pos >= cutoff}
    if len(near) == 2:
        return None
    return found[-1][1] if found[-1][1] != "partly" else "partly_allowed"


def match_insurer(text: str) -> str | None:
    """Insurer whose alias appears earliest in the text (the respondent is named first)."""
    best: tuple[int, str] | None = None
    for name, aliases in INSURER_ALIASES.items():
        for a in aliases:
            m = re.search(re.escape(a), text, re.I)
            if m and (best is None or m.start() < best[0]):
                best = (m.start(), name)
    return best[1] if best else None


def _parse_date(s: str | None) -> date | None:
    for fmt in ("%Y-%m-%d", "%d %B, %Y", "%d-%m-%Y", "%d %B %Y"):
        try:
            return datetime.strptime((s or "").strip(), fmt).date()
        except ValueError:
            continue
    return None


# ---- spend ledger ----------------------------------------------------------

def _data_dir() -> Path:
    return Path(os.environ.get("SARTHI_DATA_DIR", "data"))


def _ledger() -> Path:
    return _data_dir() / "ik_spend.jsonl"


def total_spend_inr() -> float:
    p = _ledger()
    if not p.exists():
        return 0.0
    return sum(float(json.loads(x).get("cost_inr", 0.0)) for x in p.read_text().splitlines() if x.strip())


def _price(var: str) -> float:
    v = os.environ.get(var)
    if v is None or v == "":
        raise IKConfigError(f"{var} is not set; confirm the price on the Indian Kanoon pricing "
                            "page and export it (see docs/runbooks/09-ikanoon-credit.md)")
    return float(v)


def _token() -> str:
    t = os.environ.get("IKANOON_TOKEN")
    if not t:
        raise IKConfigError("IKANOON_TOKEN is not set; add it to .env (see runbook 09)")
    return t


def _call(path: str, kind: str, cost_var: str, sleep, ref: str, **kw) -> dict:
    token = _token()
    cost = _price(cost_var)
    cap = float(os.environ.get("IK_CAP_INR", DEFAULT_CAP_INR))

    def charge() -> None:  # pessimistic: ledger every HTTP attempt before it is sent
        spent = total_spend_inr()
        if spent + cost > cap:
            raise SpendCapExceeded(f"Indian Kanoon spend {spent:.2f} + {cost:.2f} INR would exceed "
                                   f"cap {cap:.2f} INR (IK_CAP_INR)")
        p = _ledger()
        p.parent.mkdir(parents=True, exist_ok=True)
        with open(p, "a") as f:
            f.write(json.dumps({"ts": datetime.now().isoformat(timespec="seconds"), "kind": kind,
                                "ref": ref, "cost_inr": cost}) + "\n")

    r = _request("POST", IK_BASE + path, sleep, before_attempt=charge,
                 headers={"Authorization": f"Token {token}", "User-Agent": USER_AGENT}, **kw)
    return r.json()


# ---- public API ------------------------------------------------------------

def search_cases(query: str, *, max_results: int, store: Store,
                 sleep: Callable[[float], None] = time.sleep) -> list[str]:
    ids: list[str] = []
    page = 0
    while len(ids) < max_results:
        body = _call("/search/", "search", "IK_COST_SEARCH_INR", sleep, query,
                     data={"formInput": query, "pagenum": page})
        docs = body.get("docs") or []
        if not docs:
            break
        ids.extend(str(d["tid"]) for d in docs)
        page += 1
    return ids[:max_results]


def _upsert_case(case_id: str, sha: str, text: str, forum: str | None, decided_on: date | None,
                 outcome: str | None = None) -> tuple[Case, dict]:
    case = Case(case_id=case_id, source_sha256=sha, forum=forum, decided_on=decided_on,
                insurer=match_insurer(text), outcome=outcome or detect_outcome(text))
    # appellant / policyholder_prevailed are curated later; a re-fetch must not wipe them
    return case, case.model_dump(exclude={"appellant", "policyholder_prevailed"})


def fetch_case(doc_id: str, store: Store, *, sleep: Callable[[float], None] = time.sleep) -> Case:
    body = _call(f"/doc/{doc_id}/", "doc", "IK_COST_DOC_INR", sleep, doc_id)
    html = body.get("doc") or ""
    sha = _store_bytes(store, html.encode("utf-8"), "html")
    spec = SourceSpec(id=f"ik_{doc_id}", url=f"https://indiankanoon.org/doc/{doc_id}/",
                      doc_type="judgment", publisher=body.get("docsource") or "Indian Kanoon",
                      title=body.get("title") or f"Indian Kanoon doc {doc_id}")
    record_source(spec, store, sha, licence_note=LICENCE_NOTE)
    case, row = _upsert_case(f"ik_{doc_id}", sha, html_to_text(html), body.get("docsource"),
                             _parse_date(body.get("publishdate")))
    store.upsert("case", [row], key=["case_id"])
    return case


def add_local(path: Path, case_id: str, store: Store, *, forum: str | None = None,
              decided_on: date | None = None, outcome: str | None = None) -> Case:
    """Register a hand-saved judgment (e-Jagriti fallback) and create its case row."""
    data = Path(path).read_bytes()
    ext = Path(path).suffix.lower().lstrip(".") or "bin"
    sha = _store_bytes(store, data, ext)
    spec = SourceSpec(id=f"local_{case_id}", url=f"file://{Path(path).name}", doc_type="judgment",
                      publisher=forum or "hand-saved", title=Path(path).name)
    record_source(spec, store, sha, licence_note="Hand-saved public judgment (e-Jagriti)")
    # parse_source handles PDFs (text layer) and html; only unsupported types fall back to raw decode
    from sarthi.data.parse_docs import parse_source
    if parse_source(sha, store):
        text = " ".join(r[0] or "" for r in store.con.execute(
            "SELECT text FROM document_page WHERE sha256=? ORDER BY page_no", [sha]).fetchall())
    else:
        text = data.decode("utf-8", errors="replace")
    case, row = _upsert_case(case_id, sha, text, forum, decided_on, outcome)
    store.upsert("case", [row], key=["case_id"])
    return case
