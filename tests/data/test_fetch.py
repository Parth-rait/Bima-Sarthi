import hashlib
from pathlib import Path

import httpx
import pytest
import respx

from sarthi.core.registry import SourceSpec
from sarthi.core.store import Store
from sarthi.data import cli
from sarthi.data.fetch import FetchError, discover_pdf_links, fetch_source

PDF = b"%PDF-1.4 fake pdf body"
SPEC = SourceSpec(id="doc1", url="https://example.org/a.pdf", doc_type="circular",
                  publisher="Pub", title="Doc One")


@pytest.fixture
def store(tmp_path):
    s = Store(tmp_path / "bima_sarthi.duckdb")
    s.init()
    return s


def raw_files(store):
    return sorted((store.path.parent / "raw").glob("*"))


def nrows(store):
    return store.con.execute("SELECT count(*) FROM source").fetchone()[0]


@respx.mock
def test_direct_pdf_saved_by_hash(store):
    respx.get(SPEC.url).respond(200, content=PDF, headers={"content-type": "application/pdf"})
    src = fetch_source(SPEC, store, sleep=lambda s: None)
    sha = hashlib.sha256(PDF).hexdigest()
    assert src.sha256 == sha
    assert (store.path.parent / "raw" / f"{sha}.pdf").read_bytes() == PDF
    row = store.con.execute(
        "SELECT sha256, doc_type, publisher, title, url FROM source WHERE source_id='doc1'").fetchone()
    assert row == (sha, "circular", "Pub", "Doc One", SPEC.url)


@respx.mock
def test_refetch_same_content_no_duplicate(store):
    respx.get(SPEC.url).respond(200, content=PDF, headers={"content-type": "application/pdf"})
    fetch_source(SPEC, store, sleep=lambda s: None)
    fetch_source(SPEC, store, sleep=lambda s: None)
    assert len(raw_files(store)) == 1
    assert nrows(store) == 1


@respx.mock
def test_changed_content_updates_row_keeps_old_file(store):
    route = respx.get(SPEC.url)
    route.respond(200, content=PDF, headers={"content-type": "application/pdf"})
    fetch_source(SPEC, store, sleep=lambda s: None)
    route.respond(200, content=PDF + b"v2", headers={"content-type": "application/pdf"})
    src = fetch_source(SPEC, store, sleep=lambda s: None)
    assert len(raw_files(store)) == 2
    assert nrows(store) == 1
    assert store.con.execute("SELECT sha256 FROM source").fetchone()[0] == src.sha256


@respx.mock
def test_direct_html_saved_as_html_and_suffix_fallback(store):
    html_spec = SPEC.model_copy(update={"id": "h", "url": "https://example.org/page"})
    respx.get(html_spec.url).respond(200, content=b"<html>x</html>",
                                     headers={"content-type": "text/html; charset=utf-8"})
    fetch_source(html_spec, store, sleep=lambda s: None)
    pdf_spec = SPEC.model_copy(update={"id": "p", "url": "https://example.org/x.pdf"})
    respx.get(pdf_spec.url).respond(200, content=PDF, headers={"content-type": "application/octet-stream"})
    fetch_source(pdf_spec, store, sleep=lambda s: None)
    assert sorted(p.suffix for p in raw_files(store)) == [".html", ".pdf"]


@respx.mock
def test_http_error_raises_and_records_nothing(store):
    respx.get(SPEC.url).respond(403)
    with pytest.raises(FetchError):
        fetch_source(SPEC, store, sleep=lambda s: None)
    assert nrows(store) == 0
    assert raw_files(store) == []


@respx.mock
def test_5xx_is_retried_then_succeeds(store):
    route = respx.get(SPEC.url)
    route.side_effect = [httpx.Response(503), httpx.ConnectError("boom"),
                         httpx.Response(200, content=PDF, headers={"content-type": "application/pdf"})]
    sleeps = []
    fetch_source(SPEC, store, sleep=sleeps.append)
    assert route.call_count == 3
    assert len(sleeps) == 2


@respx.mock
def test_4xx_not_retried(store):
    route = respx.get(SPEC.url).respond(404)
    with pytest.raises(FetchError):
        fetch_source(SPEC, store, sleep=lambda s: None)
    assert route.call_count == 1


@respx.mock
def test_persistent_5xx_raises_after_three_attempts(store):
    route = respx.get(SPEC.url).respond(500)
    with pytest.raises(FetchError):
        fetch_source(SPEC, store, sleep=lambda s: None)
    assert route.call_count == 3
    assert nrows(store) == 0


@respx.mock
def test_html_page_via_firecrawl_saved_as_md(store, monkeypatch):
    monkeypatch.setenv("FIRECRAWL_API_KEY", "fc-test")
    spec = SPEC.model_copy(update={"url": "https://example.org/page", "doc_type": "regulation"})
    route = respx.post("https://api.firecrawl.dev/v1/scrape").respond(
        200, json={"success": True, "data": {"markdown": "# Hello\nbody"}})
    src = fetch_source(spec, store, mode="firecrawl", sleep=lambda s: None)
    assert src.doc_type == "regulation"
    sha = hashlib.sha256(b"# Hello\nbody").hexdigest()
    assert (store.path.parent / "raw" / f"{sha}.md").read_text() == "# Hello\nbody"
    assert route.calls[0].request.headers["authorization"] == "Bearer fc-test"
    assert store.con.execute("SELECT doc_type FROM source").fetchone()[0] == "regulation"


def test_firecrawl_without_key_is_clear_error(store, monkeypatch):
    monkeypatch.delenv("FIRECRAWL_API_KEY", raising=False)
    with pytest.raises(FetchError, match="FIRECRAWL_API_KEY"):
        fetch_source(SPEC.model_copy(update={"url": "https://example.org/page"}), store, mode="firecrawl")
    with pytest.raises(FetchError, match="FIRECRAWL_API_KEY"):
        discover_pdf_links("https://example.org")


@respx.mock
def test_discover_pdf_links_filters_pdfs(monkeypatch):
    monkeypatch.setenv("FIRECRAWL_API_KEY", "fc-test")
    respx.post("https://api.firecrawl.dev/v1/scrape").respond(200, json={"success": True, "data": {
        "markdown": "x", "links": ["https://a.org/x.pdf", "https://a.org/page", "https://a.org/Y.PDF?dl=1"]}})
    assert discover_pdf_links("https://a.org") == ["https://a.org/x.pdf", "https://a.org/Y.PDF?dl=1"]


def test_register_local_file(tmp_path, monkeypatch, capsys):
    monkeypatch.setenv("SARTHI_DATA_DIR", str(tmp_path / "d"))
    f = tmp_path / "my.pdf"
    f.write_bytes(PDF)
    reg = tmp_path / "sources.yaml"
    reg.write_text("sources:\n  - {id: doc1, url: 'https://e.org', doc_type: circular, publisher: P, title: T}\n")
    assert cli.main(["--registry", str(reg), "register-local", str(f), "--id", "doc1"]) == 0
    sha = hashlib.sha256(PDF).hexdigest()
    assert (tmp_path / "d" / "raw" / f"{sha}.pdf").read_bytes() == PDF
    s = Store(tmp_path / "d" / "bima_sarthi.duckdb")
    assert s.con.execute("SELECT sha256, publisher, doc_type FROM source WHERE source_id='doc1'").fetchone() == (sha, "P", "circular")
    # unknown id -> clear error, nothing registered
    assert cli.main(["--registry", str(reg), "register-local", str(f), "--id", "nope"]) != 0
    assert "nope" in capsys.readouterr().err


@respx.mock
def test_firecrawl_mode_downloads_pdf_urls_directly(store, monkeypatch):
    monkeypatch.setenv("FIRECRAWL_API_KEY", "fc-test")
    fc = respx.post("https://api.firecrawl.dev/v1/scrape")
    respx.get(SPEC.url).respond(200, content=PDF, headers={"content-type": "application/pdf"})
    fetch_source(SPEC, store, mode="firecrawl", sleep=lambda s: None)
    assert fc.call_count == 0
    sha = hashlib.sha256(PDF).hexdigest()
    assert (store.path.parent / "raw" / f"{sha}.pdf").exists()
