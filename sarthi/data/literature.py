"""OpenAlex literature search, written to docs/evidence/literature.md."""
import os
from pathlib import Path

import httpx

from sarthi.data.fetch import USER_AGENT

OPENALEX_URL = "https://api.openalex.org/works"
DEFAULT_OUT = Path("docs/evidence/literature.md")


class LiteratureError(RuntimeError):
    pass


def search_literature(query: str, n: int = 20, out_path: Path = DEFAULT_OUT) -> list[dict]:
    key = os.environ.get("OPENALEX_KEY")
    if not key:
        raise LiteratureError("OPENALEX_KEY is not set (put it in .env)")
    try:
        r = httpx.get(OPENALEX_URL, params={"search": query, "per-page": n, "api_key": key},
                      headers={"User-Agent": USER_AGENT}, timeout=30.0)
        r.raise_for_status()
    except httpx.HTTPError as e:
        raise LiteratureError(f"OpenAlex request failed: {e}") from e
    works = []
    for w in r.json().get("results", []):
        loc = (w.get("primary_location") or {}).get("source") or {}
        works.append({
            "title": w.get("title") or w.get("display_name") or "(untitled)",
            "year": w.get("publication_year"),
            "doi": w.get("doi"),
            "authors": [a["author"]["display_name"] for a in w.get("authorships", [])
                        if a.get("author", {}).get("display_name")],
            "venue": loc.get("display_name"),
        })
    lines = [f"# Literature: {query}", ""]
    for w in works:
        doi = f" [{w['doi']}]({w['doi']})" if w["doi"] else " (no DOI)"
        lines.append(f"- {w['title']} ({w['year']}).{doi}")
    out_path = Path(out_path)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    return works
