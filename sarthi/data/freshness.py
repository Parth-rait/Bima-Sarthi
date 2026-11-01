"""Weekly freshness check: search IRDAI for new circulars that may affect approved rule cards.

Raises alerts for a human to review. Never changes a rule card.
"""
import hashlib
import os
from datetime import date, datetime

import httpx

from sarthi.core.models import FreshnessAlert
from sarthi.core.store import Store
from sarthi.data import rule_cards

TAVILY_URL = "https://api.tavily.com/search"
DOMAIN = "irdai.gov.in"
MAX_RESULTS = 5
TIMEOUT_S = 60.0
TITLE_TERMS = ("circular", "master circular", "regulation")
DATE_FORMATS = ("%d %B %Y", "%d %b %Y", "%B %d, %Y", "%b %d, %Y", "%d-%m-%Y", "%d/%m/%Y")


class FreshnessError(RuntimeError):
    pass


def alert_id(found_url: str, rule_id: str) -> str:
    return hashlib.sha256(f"{rule_id}\x1f{found_url}".encode("utf-8")).hexdigest()


def _parse_date(raw) -> date | None:
    if not isinstance(raw, str) or not raw.strip():
        return None
    text = raw.strip()
    try:
        return datetime.fromisoformat(text).date()
    except ValueError:
        pass
    for fmt in DATE_FORMATS:
        try:
            return datetime.strptime(text, fmt).date()
        except ValueError:
            continue
    return None


def _search(query: str, api_key: str) -> list[dict]:
    try:
        r = httpx.post(
            TAVILY_URL,
            headers={"Authorization": f"Bearer {api_key}"},
            timeout=TIMEOUT_S,
            json={"query": query, "search_depth": "basic",
                  "include_domains": [DOMAIN], "max_results": MAX_RESULTS},
        )
    except httpx.HTTPError as e:
        raise FreshnessError(f"Tavily search failed: {type(e).__name__}: {e}") from e
    if not r.is_success:
        raise FreshnessError(f"Tavily search failed: HTTP {r.status_code}")
    return r.json().get("results") or []


def check_freshness(store: Store, since: date) -> list[FreshnessAlert]:
    """Return the alerts newly created by this run. Existing alerts are never touched,
    so a human's dismissed/actioned status survives reruns."""
    api_key = os.environ.get("TAVILY_API_KEY")
    if not api_key:
        raise FreshnessError("TAVILY_API_KEY is not set; export it to run the freshness check")
    created: list[FreshnessAlert] = []
    for card in rule_cards.approved_cards(store):
        if not card.title_en:
            continue
        for res in _search(f"IRDAI circular {card.title_en}", api_key):
            url = res.get("url") or ""
            title = res.get("title") or ""
            found_on = _parse_date(res.get("published_date"))
            if not url or found_on is None or found_on <= since:
                continue
            if not any(term in title.lower() for term in TITLE_TERMS):
                continue
            aid = alert_id(url, card.rule_id)
            if store.con.execute(
                    "SELECT 1 FROM freshness_alert WHERE alert_id=?", [aid]).fetchone():
                continue
            alert = FreshnessAlert(alert_id=aid, rule_id=card.rule_id, found_url=url,
                                   found_title=title, found_on=found_on, status="open")
            store.upsert("freshness_alert", [alert.model_dump()], key=["alert_id"])
            created.append(alert)
    return created
