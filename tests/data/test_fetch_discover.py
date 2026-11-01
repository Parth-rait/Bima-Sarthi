"""fetch --discover: Firecrawl finds candidate PDFs, we rank them and download the best directly."""
import hashlib
import json

import httpx
import pytest
import respx

from sarthi.core.registry import SourceSpec
from sarthi.core.store import Store
from sarthi.data import cli, fetch

SEARCH = "https://api.firecrawl.dev/v1/search"
SCRAPE = "https://api.firecrawl.dev/v1/scrape"
PDF = b"%PDF-1.4 master circular body"
GOOD = "https://example.org/files/master-circular-health-insurance-business.pdf"
OTHER_SITE = "https://other.com/unrelated.pdf"
ANNUAL = "https://example.org/files/annual-report.pdf"
LANDING = "https://example.org/circulars"

YAML = """# registry header comment
sources:
  - id: doc1
    # keep this comment
    url: https://example.org/circulars  # url unverified
    doc_type: circular
    publisher: Example Authority
    title: Master Circular on Health Insurance Business (29 May 2024)
  - id: doc2
    url: https://example.org/other
    doc_type: report
    publisher: Example Authority
    title: Something Else Entirely
"""


@pytest.fixture
def env(tmp_path, monkeypatch):
    monkeypatch.setenv("SARTHI_DATA_DIR", str(tmp_path / "data"))
    monkeypatch.setenv("FIRECRAWL_API_KEY", "test-key")
    monkeypatch.setattr(fetch.time, "sleep", lambda s: None)
    reg = tmp_path / "sources.yaml"
    reg.write_text(YAML, encoding="utf-8")
    return reg


def mock_firecrawl(hits, links_by_page):
    search = respx.post(SEARCH).respond(200, json={"success": True, "data": hits})

    def scrape(request):
        page = json.loads(request.content)["url"]
        return httpx.Response(200, json={"success": True, "data": {"links": links_by_page.get(page, [])}})

    return search, respx.post(SCRAPE).mock(side_effect=scrape)


def hits():
    return [{"url": OTHER_SITE, "title": "Unrelated thing", "description": ""},
            {"url": GOOD, "title": "Master Circular on Health Insurance Business", "description": ""}]


def run(env, *extra):
    return cli.main(["--registry", str(env), "fetch", "--discover", "--id", "doc1", *extra])


@respx.mock
def test_discover_downloads_best_pdf_and_prints_table(env, capsys):
    search, scrape = mock_firecrawl(hits(), {LANDING: [ANNUAL]})
    get = respx.get(GOOD).respond(200, content=PDF, headers={"content-type": "application/pdf"})
    assert run(env) == 0
    sha = hashlib.sha256(PDF).hexdigest()
    out = capsys.readouterr().out
    assert "doc1" in out and GOOD in out and sha in out
    assert get.call_count == 1
    body = json.loads(search.calls[0].request.content)
    assert "Master Circular" in body["query"] and "Example Authority" in body["query"]
    assert "example.org" in body["query"]
    assert search.calls[0].request.headers["authorization"] == "Bearer test-key"
    # Firecrawl only ever scraped HTML pages, never the PDF itself
    scraped = [json.loads(c.request.content)["url"] for c in scrape.calls]
    assert LANDING in scraped and not any(u.endswith(".pdf") for u in scraped)
    with Store(cli.data_dir() / "bima_sarthi.duckdb") as s:
        row = s.con.execute("SELECT url, sha256 FROM source WHERE source_id='doc1'").fetchone()
    assert row == (GOOD, sha)
    assert (cli.data_dir() / "raw" / f"{sha}.pdf").read_bytes() == PDF


@respx.mock
def test_yaml_untouched_without_write_urls(env):
    mock_firecrawl(hits(), {})
    respx.get(GOOD).respond(200, content=PDF, headers={"content-type": "application/pdf"})
    run(env)
    assert env.read_text(encoding="utf-8") == YAML


@respx.mock
def test_write_urls_updates_only_that_url_and_adds_comment(env):
    mock_firecrawl(hits(), {})
    respx.get(GOOD).respond(200, content=PDF, headers={"content-type": "application/pdf"})
    assert run(env, "--write-urls") == 0
    text = env.read_text(encoding="utf-8")
    assert f"    url: {GOOD}  # discovered " in text and " via Firecrawl" in text
    assert "# registry header comment" in text and "# keep this comment" in text
    assert "url: https://example.org/other" in text
    assert "# url unverified" not in text.split("id: doc2")[0]


@respx.mock
def test_low_scoring_candidates_are_not_downloaded(env, capsys):
    mock_firecrawl([{"url": OTHER_SITE, "title": "Unrelated thing", "description": ""}], {})
    get = respx.get(OTHER_SITE).respond(200, content=PDF)
    assert run(env) == 1
    out = capsys.readouterr().out
    assert get.call_count == 0
    assert "no confident PDF" in out and "03-manual-downloads" in out


def test_missing_key_points_to_manual_runbook(env, monkeypatch, capsys):
    monkeypatch.delenv("FIRECRAWL_API_KEY")
    assert run(env) == 1
    out = capsys.readouterr().out
    assert "FIRECRAWL_API_KEY" in out and "03-manual-downloads" in out


def store_old_pdf(url="https://example.org/old.pdf"):
    with Store(cli.data_dir() / "bima_sarthi.duckdb") as s:
        s.init()
        fetch.record_source(SourceSpec(id="doc1", url=url, doc_type="circular",
                                       publisher="P", title="T"), s, "a" * 64)
        (cli.data_dir() / "raw").mkdir(parents=True, exist_ok=True)
        (cli.data_dir() / "raw" / f"{'a' * 64}.pdf").write_bytes(b"%PDF-old")


@respx.mock
def test_existing_pdf_is_not_redownloaded_but_its_url_is_written_back(env, capsys):
    mock_firecrawl(hits(), {})
    get = respx.get(GOOD).respond(200, content=PDF, headers={"content-type": "application/pdf"})
    store_old_pdf()
    assert run(env, "--write-urls") == 0
    out = capsys.readouterr().out
    assert get.call_count == 0 and "a" * 64 in out
    assert f"    url: https://example.org/old.pdf  # discovered " in env.read_text(encoding="utf-8")
    with Store(cli.data_dir() / "bima_sarthi.duckdb") as s:
        assert s.con.execute("SELECT sha256 FROM source WHERE source_id='doc1'").fetchone() == ("a" * 64,)
    assert run(env, "--replace") == 0
    assert get.call_count == 1


@respx.mock
def test_existing_pdf_without_write_urls_leaves_yaml_alone(env):
    mock_firecrawl(hits(), {})
    store_old_pdf()
    assert run(env) == 0
    assert env.read_text(encoding="utf-8") == YAML


MIRROR = "https://mirror.example.net/master-circular-health-insurance-business-2024.pdf"
OFFICIAL_LOWER = "https://example.org/files/circular-2024.pdf"


@respx.mock
def test_official_outranks_a_higher_scoring_mirror(env, capsys):
    mock_firecrawl([{"url": MIRROR, "title": "Master Circular on Health Insurance Business", "description": ""},
                    {"url": OFFICIAL_LOWER, "title": "Circular health", "description": ""}], {})
    get = respx.get(OFFICIAL_LOWER).respond(200, content=PDF, headers={"content-type": "application/pdf"})
    mirror = respx.get(MIRROR).respond(200, content=PDF + b"m")
    assert run(env) == 0
    out = capsys.readouterr().out
    assert get.call_count == 1 and mirror.call_count == 0
    assert "example.org" in out and "official" in out and "yes" in out


@respx.mock
def test_offsite_best_candidate_is_not_downloaded_without_allow_offsite(env, capsys):
    mock_firecrawl([{"url": MIRROR, "title": "Master Circular on Health Insurance Business", "description": ""}], {})
    mirror = respx.get(MIRROR).respond(200, content=PDF, headers={"content-type": "application/pdf"})
    assert run(env, "--write-urls") == 1
    out = capsys.readouterr().out
    assert mirror.call_count == 0
    assert "mirror.example.net" in out and "off-site" in out and "--allow-offsite" in out
    assert env.read_text(encoding="utf-8") == YAML
    with Store(cli.data_dir() / "bima_sarthi.duckdb") as s:
        assert s.con.execute("SELECT count(*) FROM source").fetchone() == (0,)
    assert run(env, "--write-urls", "--allow-offsite") == 0
    assert mirror.call_count == 1
    assert f"url: {MIRROR}  # discovered " in env.read_text(encoding="utf-8")


@respx.mock
def test_stored_pdf_url_is_written_back_without_any_search(env, monkeypatch, capsys):
    monkeypatch.delenv("FIRECRAWL_API_KEY")  # Firecrawl unavailable; any HTTP call would fail the test
    store_old_pdf()
    assert run(env, "--write-urls") == 0
    out = capsys.readouterr().out
    assert "https://example.org/old.pdf" in out and "a" * 64 in out
    assert "url: https://example.org/old.pdf  # discovered " in env.read_text(encoding="utf-8")


@respx.mock
def test_stored_bytes_without_a_pdf_url_write_nothing(env, capsys):
    mock_firecrawl(hits(), {})
    store_old_pdf(url="https://example.org/landing-page")
    assert run(env, "--write-urls") == 1
    out = capsys.readouterr().out
    assert "stored bytes have no PDF URL; run with --replace to download the best official candidate" in out
    assert env.read_text(encoding="utf-8") == YAML


@respx.mock
def test_stored_offsite_url_is_not_written_without_allow_offsite(env, capsys):
    store_old_pdf(url="https://mirror.example.net/old.pdf")
    assert run(env, "--write-urls") == 1
    assert "off-site" in capsys.readouterr().out
    assert env.read_text(encoding="utf-8") == YAML


@respx.mock
def test_stored_url_shows_its_real_score_not_zero(env, capsys):
    store_old_pdf(url=GOOD)
    assert run(env) == 0
    row = [l for l in capsys.readouterr().out.splitlines() if l.startswith("doc1")][0]
    assert " 0.00 " not in row


def test_lookalike_domains_are_not_official():
    spec = SourceSpec(id="d", url="https://example.org/x", doc_type="circular", publisher="P", title="T")
    for bad in ("https://irdai.gov.in.evil.com/a.pdf", "https://evilirdai.gov.in/a.pdf",
                "https://irdai.gov.in@evil.com/a.pdf", "https://notexample.org/a.pdf"):
        assert not fetch.is_official(spec, bad), bad


def test_known_publisher_domains_are_official():
    spec = SourceSpec(id="d", url="https://irdai.gov.in/regulations", doc_type="circular", publisher="P", title="T")
    assert fetch.is_official(spec, "https://www.irdai.gov.in/x.pdf")
    other = SourceSpec(id="d", url="https://example.org/x", doc_type="circular", publisher="P", title="T")
    assert fetch.is_official(other, "https://cioins.co.in/a.pdf")
    assert not fetch.is_official(other, "https://mirror.example.net/a.pdf")


def test_rank_prefers_title_overlap_then_domain():
    spec = SourceSpec(id="d", url=LANDING, doc_type="circular", publisher="P",
                      title="Master Circular on Health Insurance Business")
    ranked = fetch.rank_candidates(spec, {GOOD: "", OTHER_SITE: "Master Circular", ANNUAL: ""})
    scores = dict(ranked)
    assert ranked[0][0] == GOOD
    assert scores[GOOD] > scores[OTHER_SITE] > 0          # overlap counts
    assert scores[ANNUAL] > 0                              # same domain alone still scores a little
    same = fetch.rank_candidates(spec, {"https://example.org/a.pdf": "Circular", "https://x.com/a.pdf": "Circular"})
    assert same[0][0].startswith("https://example.org")    # domain breaks ties
