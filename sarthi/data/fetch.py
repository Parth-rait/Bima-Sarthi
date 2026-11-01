"""Fetch sources into the content-addressed raw store (<data>/raw/<sha256>.<ext>)."""
import hashlib
import os
import re
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Callable, Literal
from urllib.parse import urlparse

import httpx
from pydantic import BaseModel

from sarthi.core.models import Source
from sarthi.core.registry import SourceSpec
from sarthi.core.store import Store

USER_AGENT = (
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36"
)
FIRECRAWL_URL = "https://api.firecrawl.dev/v1/scrape"
ATTEMPTS = 3
BACKOFF_S = 1.0
TIMEOUT_S = 60.0


class FetchError(RuntimeError):
    pass


def raw_dir(store: Store) -> Path:
    return store.path.parent / "raw"


def _ext(content_type: str | None, url: str) -> str:
    ct = (content_type or "").split(";")[0].strip().lower()
    if ct == "application/pdf":
        return "pdf"
    if ct in ("text/html", "application/xhtml+xml"):
        return "html"
    suffix = Path(urlparse(url).path).suffix.lower().lstrip(".")
    return suffix if suffix in ("pdf", "html", "htm") else "bin"


def _request(method: str, url: str, sleep: Callable[[float], None], *,
             before_attempt: Callable[[], None] | None = None, **kw) -> httpx.Response:
    """3 attempts, exponential backoff on connect errors/timeouts/5xx only.
    `before_attempt` runs before each HTTP attempt (e.g. to ledger a charge)."""
    last = "no attempt"
    for attempt in range(ATTEMPTS):
        if before_attempt:
            before_attempt()
        try:
            r = httpx.request(method, url, timeout=TIMEOUT_S, follow_redirects=True, **kw)
        except (httpx.ConnectError, httpx.TimeoutException) as e:
            last = f"{type(e).__name__}: {e}"
        else:
            if r.status_code < 500:
                if r.is_success:
                    return r
                raise FetchError(f"{url}: HTTP {r.status_code}")
            last = f"HTTP {r.status_code}"
        if attempt < ATTEMPTS - 1:
            sleep(BACKOFF_S * 2**attempt)
    raise FetchError(f"{url}: failed after {ATTEMPTS} attempts ({last})")


def _firecrawl(page_url: str, formats: list[str], sleep) -> dict:
    key = os.environ.get("FIRECRAWL_API_KEY")
    if not key:
        raise FetchError("FIRECRAWL_API_KEY is not set; export it (see runbook) to use firecrawl mode")
    r = _request("POST", FIRECRAWL_URL, sleep,
                 headers={"Authorization": f"Bearer {key}"},
                 json={"url": page_url, "formats": formats})
    body = r.json()
    if not body.get("success", True):
        raise FetchError(f"{page_url}: Firecrawl reported failure: {body}")
    return body.get("data") or {}


def _store_bytes(store: Store, data: bytes, ext: str) -> str:
    sha = hashlib.sha256(data).hexdigest()
    d = raw_dir(store)
    d.mkdir(parents=True, exist_ok=True)
    path = d / f"{sha}.{ext}"
    if not path.exists():
        path.write_bytes(data)
    return sha


def record_source(spec: SourceSpec, store: Store, sha: str, *,
                  licence_note: str | None = None) -> Source:
    src = Source(source_id=spec.id, url=spec.url, publisher=spec.publisher, title=spec.title,
                 doc_type=spec.doc_type, retrieved_at=datetime.now(timezone.utc).replace(tzinfo=None),
                 sha256=sha, licence_note=licence_note)
    store.upsert("source", [src.model_dump()], key=["source_id"])
    return src


def fetch_source(spec: SourceSpec, store: Store, *,
                 mode: Literal["direct", "firecrawl"] = "direct",
                 sleep: Callable[[float], None] = time.sleep) -> Source:
    # PDFs are always downloaded directly (saves Firecrawl credits)
    if mode == "firecrawl" and not urlparse(spec.url).path.lower().endswith(".pdf"):
        data = _firecrawl(spec.url, ["markdown"], sleep)
        md = data.get("markdown")
        if not md:
            raise FetchError(f"{spec.url}: Firecrawl returned no markdown")
        sha = _store_bytes(store, md.encode("utf-8"), "md")
    else:
        r = _request("GET", spec.url, sleep, headers={"User-Agent": USER_AGENT})
        sha = _store_bytes(store, r.content, _ext(r.headers.get("content-type"), spec.url))
    return record_source(spec, store, sha)


def discover_pdf_links(page_url: str, *, sleep: Callable[[float], None] = time.sleep) -> list[str]:
    data = _firecrawl(page_url, ["markdown", "links"], sleep)
    return [u for u in data.get("links", []) if urlparse(u).path.lower().endswith(".pdf")]


# ---------- Firecrawl discovery (fetch --discover) ----------
# Search endpoint: POST https://api.firecrawl.dev/v1/search {"query", "limit"}; each hit has url,
# title, description. v1 returns "data" as a list, v2 as {"web": [...]}; both are accepted.
FIRECRAWL_SEARCH_URL = "https://api.firecrawl.dev/v1/search"
MIN_SCORE = 0.4
DOMAIN_BONUS = 0.25
SEARCH_LIMIT = 5
PAGES_TO_SCAN = 3  # landing page plus the top search hits
_STOP = {"the", "and", "for", "of", "on", "in", "to", "act", "pdf", "with", "from"}


# Publisher sites we trust for the PDFs this project cites (one place; a source's own registry
# host is always official too).
OFFICIAL_DOMAINS = ("irdai.gov.in", "cioins.co.in", "financialservices.gov.in", "policyholder.gov.in")


class Discovery(BaseModel):
    source_id: str
    url: str | None = None
    score: float = 0.0
    sha256: str | None = None
    note: str = ""
    domain: str = ""
    official: bool = False
    kept: bool = False  # the PDF already stored was kept, not re-downloaded


def firecrawl_search(query: str, *, limit: int = SEARCH_LIMIT,
                     sleep: Callable[[float], None] = time.sleep) -> list[dict]:
    key = os.environ.get("FIRECRAWL_API_KEY")
    if not key:
        raise FetchError("FIRECRAWL_API_KEY is not set (see runbook 01)")
    r = _request("POST", FIRECRAWL_SEARCH_URL, sleep, headers={"Authorization": f"Bearer {key}"},
                 json={"query": query, "limit": limit})
    body = r.json()
    if not body.get("success", True):
        raise FetchError(f"Firecrawl search reported failure: {body}")
    data = body.get("data") or []
    if isinstance(data, dict):
        data = data.get("web") or []
    return [h for h in data if isinstance(h, dict) and h.get("url")]


def _words(text: str) -> set[str]:
    return {w for w in re.split(r"[^a-z0-9]+", text.lower()) if len(w) >= 3 and w not in _STOP}


def _site(url: str) -> str:
    host = (urlparse(url).hostname or "").lower()
    return host[4:] if host.startswith("www.") else host


def _same_site(host: str, site: str) -> bool:
    return bool(site and host and (host == site or host.endswith("." + site)))


def is_official(spec: SourceSpec, url: str) -> bool:
    """The candidate is on the registry URL's site or a known publisher domain."""
    host = _site(url)
    return any(_same_site(host, d) for d in (_site(spec.url), *OFFICIAL_DOMAINS))


def rank_candidates(spec: SourceSpec, candidates: dict[str, str]) -> list[tuple[str, float]]:
    """candidates: pdf url -> hit title/description ('' when unknown). Score = share of the source
    title's words found in the candidate's text and URL, plus a bonus for the registered site."""
    want = _words(spec.title)
    site = _site(spec.url)
    ranked = []
    for url, text in candidates.items():
        have = _words(text) | _words(urlparse(url).path)
        overlap = len(want & have) / len(want) if want else 0.0
        host = _site(url)
        bonus = DOMAIN_BONUS if site and (host == site or host.endswith("." + site) or site.endswith("." + host)) else 0.0
        ranked.append((url, round(overlap + bonus, 3)))
    # official sites always rank above off-site ones, whatever the score
    return sorted(ranked, key=lambda x: (not is_official(spec, x[0]), -x[1], x[0]))


def _is_pdf_url(u: str) -> bool:
    return urlparse(u).path.lower().endswith(".pdf")


def find_candidates(spec: SourceSpec, sleep: Callable[[float], None] = time.sleep) -> dict[str, str]:
    query = f"{spec.title} {spec.publisher} site:{_site(spec.url)} filetype:pdf"
    hits = firecrawl_search(query, sleep=sleep)
    cands: dict[str, str] = {}
    pages = [spec.url]
    for h in hits:
        text = f"{h.get('title') or ''} {h.get('description') or ''}"
        if _is_pdf_url(h["url"]):
            cands.setdefault(h["url"], text)
        elif len(pages) < PAGES_TO_SCAN + 1 and h["url"] not in pages:
            pages.append(h["url"])
    for page in pages:
        try:
            for link in discover_pdf_links(page, sleep=sleep):
                cands.setdefault(link, "")
        except FetchError:
            continue  # a page that will not scrape is not fatal while others may work
    return cands


def _has_pdf(store: Store, source_id: str) -> bool:
    row = store.con.execute("SELECT sha256 FROM source WHERE source_id=?", [source_id]).fetchone()
    return bool(row and row[0] and (raw_dir(store) / f"{row[0]}.pdf").exists())


def discover_source(spec: SourceSpec, store: Store, *, replace: bool = False, allow_offsite: bool = False,
                    sleep: Callable[[float], None] = time.sleep) -> Discovery:
    """Find, rank and download the best PDF for one source. Never raises for 'nothing found'."""

    def found(url, score, **kw):
        return Discovery(source_id=spec.id, url=url, score=score, domain=_site(url),
                         official=is_official(spec, url), **kw)

    if _has_pdf(store, spec.id) and not replace:  # no search needed: the stored bytes have a known origin
        url, sha = store.con.execute("SELECT url, sha256 FROM source WHERE source_id=?", [spec.id]).fetchone()
        if not _is_pdf_url(url or ""):
            return Discovery(source_id=spec.id, note="stored bytes have no PDF URL; run with --replace "
                                                     "to download the best official candidate")
        score = rank_candidates(spec, {url: ""})[0][1]
        return found(url, score, sha256=sha, kept=True,
                     note="kept the PDF already stored, not downloaded again; pass --replace to overwrite it")
    try:
        cands = find_candidates(spec, sleep)
    except FetchError as e:
        return Discovery(source_id=spec.id, note=f"Firecrawl unavailable ({e})")
    ranked = [(u, sc) for u, sc in rank_candidates(spec, cands) if sc >= MIN_SCORE]
    if not ranked:
        return Discovery(source_id=spec.id, note="no confident PDF found")
    if not is_official(spec, ranked[0][0]) and not allow_offsite:
        # official candidates rank first, so the best one being off-site means there is no official one
        return found(ranked[0][0], ranked[0][1],
                     note=f"best candidate is off-site ({_site(ranked[0][0])} is not a publisher domain), "
                          "not downloaded; open it, and if it is right rerun with --allow-offsite")
    for url, score in ranked:
        if not is_official(spec, url) and not allow_offsite:
            break
        try:  # PDFs are downloaded directly, no Firecrawl credits
            r = _request("GET", url, sleep, headers={"User-Agent": USER_AGENT})
        except FetchError:
            continue
        if not r.content.startswith(b"%PDF"):
            continue
        sha = _store_bytes(store, r.content, "pdf")
        record_source(spec.model_copy(update={"url": url}), store, sha)
        return found(url, score, sha256=sha, note="downloaded")
    return Discovery(source_id=spec.id, note="no confident PDF found (candidates did not download as PDFs)")


def write_back_url(registry: Path, source_id: str, url: str, today: str) -> bool:
    """Replace the `url:` line of one source, keeping every other line and comment."""
    lines = Path(registry).read_text(encoding="utf-8").splitlines(keepends=True)
    inside = False
    for i, line in enumerate(lines):
        m = re.match(r"^(\s*)- id:\s*(\S+)", line)
        if m:
            inside = m.group(2) == source_id
        elif inside and re.match(r"^\s+url:", line):
            indent = re.match(r"^(\s*)", line).group(1)
            lines[i] = f"{indent}url: {url}  # discovered {today} via Firecrawl\n"
            Path(registry).write_text("".join(lines), encoding="utf-8")
            return True
    return False
