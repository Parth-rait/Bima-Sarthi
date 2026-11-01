import json
import shutil
from datetime import date
from pathlib import Path

import pytest

from sarthi.core.models import RuleCard
from sarthi.core.store import Store
from sarthi.data import cli
from sarthi.data.parse_docs import parse_source
from sarthi.data.rule_cards import approve, approved_cards
from sarthi.data.snapshot import SnapshotError, make_snapshot

FIX = Path(__file__).parent.parent / "fixtures" / "two_page.pdf"
SHA, JSHA = "b" * 64, "c" * 64
QUOTE = "Clause 4.1 Moratorium period applies after 60 months."


def _src(sid, sha, doc_type):
    return {"source_id": sid, "url": "u", "publisher": "p", "title": "t", "doc_type": doc_type,
            "published_on": None, "retrieved_at": None, "sha256": sha, "licence_note": None}


def _full_store(tmp_path):
    s = Store(tmp_path / "full.duckdb")
    s.init()
    raw = tmp_path / "raw"
    raw.mkdir()
    shutil.copyfile(FIX, raw / f"{SHA}.pdf")
    parse_source(SHA, s)
    s.upsert("source", [_src("circ", SHA, "circular"), _src("ik_1", JSHA, "judgment")], key=["source_id"])
    s.upsert("document_page", [{"sha256": JSHA, "page_no": 1, "text": "JUDGMENT TEXT", "char_count": 13,
                                "has_text_layer": True, "image_path": None}], key=["sha256", "page_no"])
    for rid, ver in (("R1", 1), ("R2", 1)):
        card = RuleCard(rule_id=rid, version=ver, source_sha256=SHA, quote=QUOTE,
                        in_force_from=date(2024, 4, 1))
        row = card.model_dump(mode="json")
        for k in ("triggers", "inputs", "params"):
            row[k] = json.dumps(row[k])
        s.upsert("rule_card", [row], key=["rule_id", "version"])
    approve("R1", 1, "parth", s)  # R2 stays a draft
    s.upsert("case", [{"case_id": "ik_1", "source_sha256": JSHA, "forum": "f", "case_number": None,
                       "decided_on": None, "insurer": None, "product_id": None, "outcome": None,
                       "relief_amount": None}], key=["case_id"])
    s.upsert("case_fact", [{"case_id": "ik_1", "field": "x", "value": "1", "quote": "q", "page_no": 1,
                            "confidence": 1.0, "status": "extracted", "reviewer_note": None}],
             key=["case_id", "field"])
    s.upsert("policy_product", [{"product_id": "p", "insurer": "i", "product_name": None, "uin": None,
                                 "wording_sha256": SHA, "cis_sha256": None, "is_standard_product": True}],
             key=["product_id"])
    s.upsert("policy_clause", [{"product_id": "p", "clause_no": "1", "heading": "H", "text": "T",
                                "page_no": 1, "normalised_hash": "h"}], key=["product_id", "clause_no"])
    s.upsert("insurer_stat", [{"insurer": "i", "year": "2023-24", "metric": "m", "value": 1.0,
                               "unit": "pct", "source_sha256": SHA, "page_no": 1}],
             key=["insurer", "year", "metric"])
    s.upsert("eval_result", [{"run_id": "r", "case_id": "ik_1", "method": "m", "repeat": 1, "backend": "b",
                              "verdicts": "[]", "agrees_with_outcome": True, "false_hope": False,
                              "latency_ms": 1, "tokens": 1}], key=["run_id", "case_id", "method", "repeat"])
    return s


def _count(s, t):
    return s.con.execute(f'SELECT count(*) FROM "{t}"').fetchone()[0]


def test_snapshot_has_no_judgment_case_or_eval_rows(tmp_path):
    full = _full_store(tmp_path)
    counts = make_snapshot(full, tmp_path / "snap.duckdb")
    snap = Store(tmp_path / "snap.duckdb")
    assert _count(snap, "case") == _count(snap, "case_fact") == _count(snap, "eval_result") == 0
    assert snap.con.execute("SELECT count(*) FROM source WHERE doc_type='judgment'").fetchone()[0] == 0
    assert snap.con.execute("SELECT count(*) FROM document_page WHERE sha256=?", [JSHA]).fetchone()[0] == 0
    assert "JUDGMENT TEXT" not in (tmp_path / "snap.duckdb").read_bytes().decode("latin-1")
    assert counts["source"] == 1 and counts["rule_card"] == 1 and counts["case"] == 0


def test_snapshot_keeps_approved_cards_with_verifying_quotes(tmp_path):
    make_snapshot(_full_store(tmp_path), tmp_path / "snap.duckdb")
    snap = Store(tmp_path / "snap.duckdb")
    cards = approved_cards(snap)
    assert [(c.rule_id, c.quote) for c in cards] == [("R1", QUOTE)]
    assert _count(snap, "rule_card") == 1  # the draft is not copied
    assert (_count(snap, "policy_product"), _count(snap, "policy_clause"), _count(snap, "insurer_stat")) == (1, 1, 1)


def test_snapshot_refuses_to_overwrite(tmp_path):
    full = _full_store(tmp_path)
    (tmp_path / "snap.duckdb").write_bytes(b"x")
    with pytest.raises(SnapshotError):
        make_snapshot(full, tmp_path / "snap.duckdb")


def test_cli_snapshot_prints_row_counts(tmp_path, monkeypatch, capsys):
    full = _full_store(tmp_path)
    monkeypatch.setattr(cli, "open_store", lambda: full)
    assert cli.main(["snapshot", "--out", str(tmp_path / "s.duckdb")]) == 0
    out = capsys.readouterr().out
    assert "case_fact" in out and "rule_card" in out
    assert cli.main(["snapshot", "--out", str(tmp_path / "s.duckdb")]) == 2  # exists
