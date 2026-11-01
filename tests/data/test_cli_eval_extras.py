import shutil
from pathlib import Path

from sarthi.app import extract
from sarthi.data import cli
from sarthi.data.cli import open_store
from sarthi.data.parse_docs import parse_source
from sarthi.data.policy_index import build_index

FIX = Path(__file__).parent.parent / "fixtures"
SHA_A, SHA_B = "a" * 64, "b" * 64


def test_eval_reading_prints_and_appends_aggregate(tmp_path, monkeypatch, capsys):
    seen = {}

    def fake(docs, truth):
        seen["args"] = (docs, truth)
        return extract.ReadingReport(4, 0.75, 0.5)

    monkeypatch.setattr(extract, "eval_reading", fake)
    out = tmp_path / "report.md"
    out.write_text("# Evaluation report\n")
    rc = cli.main(["eval-reading", "--docs", str(tmp_path), "--truth", str(tmp_path / "t.json"),
                   "--out", str(out)])
    assert rc == 0
    printed = capsys.readouterr().out
    assert "n_docs=4" in printed and "0.75" in printed and "0.5" in printed
    text = out.read_text()
    assert text.startswith("# Evaluation report")  # appended, not overwritten
    assert "Reading accuracy" in text and "n = 4" in text and "75.0%" in text


def _data_dir_with_two_wordings(tmp_path, monkeypatch):
    monkeypatch.setenv("SARTHI_DATA_DIR", str(tmp_path / "data"))
    s = open_store()
    raw = tmp_path / "data" / "raw"
    raw.mkdir(parents=True, exist_ok=True)
    for sha, name in ((SHA_A, "wording_a.pdf"), (SHA_B, "wording_b.pdf")):
        shutil.copyfile(FIX / name, raw / f"{sha}.pdf")
        parse_source(sha, s)
    build_index("acme__arogya_sanjeevani", SHA_A, s)
    build_index("zeta__arogya_sanjeevani", SHA_B, s)
    return s


def test_eval_clauses_reports_hit_rate_with_n(tmp_path, monkeypatch, capsys):
    s = _data_dir_with_two_wordings(tmp_path, monkeypatch)
    ref = [r[0] for r in s.con.execute(
        "SELECT clause_no FROM policy_clause WHERE product_id='acme__arogya_sanjeevani'").fetchall()]
    n_expected = 2 * len(ref)
    out = tmp_path / "report.md"
    rc = cli.main(["eval-clauses", "--out", str(out)])
    assert rc == 0
    text = out.read_text()
    assert "Clause-lookup hit rate" in text
    assert f"n = {n_expected} lookup(s)" in text and "2 wording(s)" in text
    assert "100.0%" in text
    assert "n = " in capsys.readouterr().out


def test_eval_clauses_without_wordings_is_an_error(tmp_path, monkeypatch, capsys):
    monkeypatch.setenv("SARTHI_DATA_DIR", str(tmp_path / "data"))
    assert cli.main(["eval-clauses", "--out", str(tmp_path / "r.md")]) == 2
    assert "no indexed wordings" in capsys.readouterr().err


def test_main_closes_every_store_it_opened(tmp_path, monkeypatch):
    import duckdb
    import pytest

    monkeypatch.setenv("SARTHI_DATA_DIR", str(tmp_path))
    made = []

    class Spy(cli.Store):
        def __init__(self, *a, **k):
            super().__init__(*a, **k)
            made.append(self)

    monkeypatch.setattr(cli, "Store", Spy)
    assert cli.main(["rules", "verify"]) == 0
    assert made
    for s in made:
        with pytest.raises(duckdb.Error):
            s.con.execute("select 1")
