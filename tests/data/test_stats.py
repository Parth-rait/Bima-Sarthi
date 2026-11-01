import httpx
import pytest
import respx

from sarthi.core.store import Store
from sarthi.data import cli, literature, stats
from sarthi.data.literature import search_literature
from sarthi.data.stats import StatNotOnPage, load_stats_csv

HEADER = "insurer,year,metric,value,unit,source_id,page_no\n"
SHA = "a" * 64


@pytest.fixture
def store(tmp_path):
    s = Store(tmp_path / "bima_sarthi.duckdb")
    s.init()
    s.con.execute("INSERT INTO source (source_id, sha256) VALUES ('cio_2023_24', ?)", [SHA])
    s.con.execute("INSERT INTO document_page (sha256, page_no, text) VALUES (?, 7, ?)",
                  [SHA, "Health complaints received: 31,490 in 2023-24; later 131,490 and १०,१४०."])
    return s


def write(tmp_path, *rows):
    p = tmp_path / "s.csv"
    p.write_text(HEADER + "".join(r + "\n" for r in rows))
    return p


def row(value="31,490", source="cio_2023_24", page=7, metric="health_complaints"):
    return f"All,2023-24,{metric},\"{value}\",count,{source},{page}"


def test_value_on_page_loads(store, tmp_path):
    n = load_stats_csv(write(tmp_path, row(), row("10140", metric="mediated")), store)
    assert n == 2
    got = store.con.execute(
        "SELECT value, source_sha256, page_no FROM insurer_stat WHERE metric='health_complaints'"
    ).fetchone()
    assert got == (31490.0, SHA, 7)


def test_value_not_on_page_raises(store, tmp_path):
    with pytest.raises(StatNotOnPage):
        load_stats_csv(write(tmp_path, row("31,491")), store)


def test_substring_of_larger_number_rejected(store, tmp_path):
    store.con.execute("UPDATE document_page SET text='only 131,490 here'")
    with pytest.raises(StatNotOnPage):
        load_stats_csv(write(tmp_path, row("31490")), store)


def test_all_or_nothing(store, tmp_path):
    with pytest.raises(StatNotOnPage):
        load_stats_csv(write(tmp_path, row(), row("99999", metric="bad")), store)
    assert store.con.execute("SELECT count(*) FROM insurer_stat").fetchone()[0] == 0


def test_unknown_source_raises(store, tmp_path):
    with pytest.raises(ValueError, match="nope"):
        load_stats_csv(write(tmp_path, row(source="nope")), store)


def test_header_only_loads_zero(store, tmp_path):
    assert load_stats_csv(write(tmp_path), store) == 0


OA = "https://api.openalex.org/works"


@respx.mock
def test_openalex_parses(tmp_path, monkeypatch):
    monkeypatch.setenv("OPENALEX_KEY", "k")
    route = respx.get(OA).mock(return_value=httpx.Response(200, json={"results": [
        {"title": "Claim denial in Indian health insurance", "publication_year": 2021,
         "doi": "https://doi.org/10.1/abc",
         "authorships": [{"author": {"display_name": "A B"}}],
         "primary_location": {"source": {"display_name": "J Ins"}}}]}))
    out = tmp_path / "lit.md"
    res = search_literature("health insurance india", n=5, out_path=out)
    assert res[0]["title"].startswith("Claim denial") and res[0]["year"] == 2021
    assert res[0]["doi"] == "https://doi.org/10.1/abc"
    req = route.calls[0].request
    assert req.url.params["search"] == "health insurance india"
    assert req.url.params["per-page"] == "5" and req.url.params["api_key"] == "k"
    assert "https://doi.org/10.1/abc" in out.read_text()


def test_openalex_missing_key(tmp_path, monkeypatch):
    monkeypatch.delenv("OPENALEX_KEY", raising=False)
    with pytest.raises(literature.LiteratureError, match="OPENALEX_KEY"):
        search_literature("x", out_path=tmp_path / "l.md")


def test_cli_stats_load(store, tmp_path, monkeypatch, capsys):
    monkeypatch.setenv("SARTHI_DATA_DIR", str(tmp_path))
    p = write(tmp_path, row())
    assert cli.main(["stats", "load", "--csv", str(p)]) == 0
    assert "loaded 1" in capsys.readouterr().out
