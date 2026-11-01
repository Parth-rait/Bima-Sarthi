"""Parse raw sources into per-page text rows (document_page).

normalise_ws is the shared whitespace/quote normaliser used by every quote check.
"""
import logging
import re
from html.parser import HTMLParser
from pathlib import Path

import pymupdf

from sarthi.core.models import DocumentPage
from sarthi.core.store import Store
from sarthi.data.fetch import raw_dir

log = logging.getLogger(__name__)

MIN_TEXT_CHARS = 20  # pages with fewer normalised chars are treated as having no text layer
_MAP = str.maketrans({
    "‐": "-", "–": "-", "—": "-",
    "‘": "'", "’": "'", "“": '"', "”": '"',
})
_WS = re.compile(r"\s+")  # \s matches NBSP (U+00A0) on str patterns


def normalise_ws(text: str) -> str:
    return _WS.sub(" ", text.translate(_MAP)).strip()


class _TextExtractor(HTMLParser):
    def __init__(self):
        super().__init__()
        self.parts: list[str] = []
        self._skip = 0

    def handle_starttag(self, tag, attrs):
        if tag in ("script", "style"):
            self._skip += 1
        else:
            self.parts.append(" ")

    def handle_endtag(self, tag):
        if tag in ("script", "style"):
            self._skip = max(0, self._skip - 1)
        else:
            self.parts.append(" ")

    def handle_data(self, data):
        if not self._skip:
            self.parts.append(data)


def _html_text(raw: str) -> str:
    p = _TextExtractor()
    p.feed(raw)
    p.close()
    return re.sub(r"[ \t]+", " ", "".join(p.parts)).strip()


def _find_raw(store: Store, sha256: str) -> Path | None:
    return next(iter(sorted(raw_dir(store).glob(f"{sha256}.*"))), None)


def _page(sha256: str, n: int, text: str) -> dict:
    return DocumentPage(sha256=sha256, page_no=n, text=text, char_count=len(text),
                        has_text_layer=len(normalise_ws(text)) >= MIN_TEXT_CHARS).model_dump()


def parse_source(sha256: str, store: Store) -> int:
    """Write one document_page row per page; idempotent. Returns pages written."""
    path = _find_raw(store, sha256)
    if path is None:
        raise FileNotFoundError(f"no raw file for {sha256} in {raw_dir(store)}")
    ext = path.suffix.lower().lstrip(".")
    if ext == "pdf":
        with pymupdf.open(path) as doc:
            rows = [_page(sha256, i, pg.get_text()) for i, pg in enumerate(doc, start=1)]
    elif ext in ("html", "htm"):
        rows = [_page(sha256, 1, _html_text(path.read_text(encoding="utf-8", errors="replace")))]
        rows[0]["has_text_layer"] = True
    elif ext == "md":
        rows = [_page(sha256, 1, path.read_text(encoding="utf-8"))]
        rows[0]["has_text_layer"] = True
    else:
        log.warning("skipping %s: unsupported extension '.%s'", path.name, ext)
        return 0
    store.upsert("document_page", rows, key=["sha256", "page_no"])
    return len(rows)


def render_page(sha256: str, page_no: int, dpi: int = 150, *, store: Store | None = None) -> Path:
    """Render a PDF page to <data>/pages/<sha256>/<n>.png and return the path.

    Does not update document_page.image_path. `store` locates the data root;
    when omitted the data root comes from SARTHI_DATA_DIR (default 'data').
    """
    if store is None:
        from sarthi.data.cli import open_store  # lazy: cli imports this module
        store = open_store()
    path = _find_raw(store, sha256)
    if path is None or path.suffix.lower() != ".pdf":
        raise FileNotFoundError(f"no PDF raw file for {sha256}")
    out = store.path.parent / "pages" / sha256 / f"{page_no}.png"
    out.parent.mkdir(parents=True, exist_ok=True)
    with pymupdf.open(path) as doc:
        doc[page_no - 1].get_pixmap(dpi=dpi).save(out)
    return out
