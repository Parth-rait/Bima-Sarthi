from pathlib import Path

from sarthi.core.hashing import sha256_file
from sarthi.core.registry import load_registry
from sarthi.core.store import Store

ROOT = Path(__file__).resolve().parents[2]

TABLES = {
    "source", "document_page", "rule_card", "policy_product", "policy_clause",
    "case", "case_fact", "insurer_stat", "eval_result", "freshness_alert",
    "case_issue",
}


def _source_row(**over):
    row = {
        "source_id": "s1", "url": "https://example.org/a.pdf", "publisher": "IRDAI",
        "title": "T", "doc_type": "regulation", "sha256": "abc",
    }
    row.update(over)
    return row


def test_init_creates_all_tables(tmp_path):
    store = Store(tmp_path / "t.duckdb")
    store.init()
    names = {r[0] for r in store.con.execute("SHOW TABLES").fetchall()}
    assert names == TABLES


def test_upsert_is_idempotent(tmp_path):
    store = Store(tmp_path / "t.duckdb")
    store.init()
    assert store.upsert("source", [_source_row()], ["source_id"]) == 1
    store.upsert("source", [_source_row()], ["source_id"])
    assert store.con.execute("SELECT count(*) FROM source").fetchone()[0] == 1


def test_upsert_replaces_existing_row(tmp_path):
    store = Store(tmp_path / "t.duckdb")
    store.init()
    store.upsert("source", [_source_row()], ["source_id"])
    store.upsert("source", [_source_row(title="New")], ["source_id"])
    assert store.con.execute("SELECT title FROM source").fetchone()[0] == "New"


def test_upsert_handles_reserved_words_and_json(tmp_path):
    store = Store(tmp_path / "t.duckdb")
    store.init()
    card = {"rule_id": "R", "version": 1, "group": "rejections", "params": '{"months": 60}'}
    assert store.upsert("rule_card", [card], ["rule_id", "version"]) == 1
    assert store.upsert("case", [{"case_id": "c1", "forum": "OMB"}], ["case_id"]) == 1
    assert store.con.execute('SELECT "group" FROM rule_card').fetchone()[0] == "rejections"


def test_upsert_composite_key_eval_result(tmp_path):
    store = Store(tmp_path / "t.duckdb")
    store.init()
    base = {"run_id": "r", "case_id": "c", "method": "rules", "backend": "none"}
    store.upsert("eval_result", [{**base, "repeat": 0}, {**base, "repeat": 1}],
                 ["run_id", "case_id", "method", "repeat"])
    store.upsert("eval_result", [{**base, "repeat": 1}],
                 ["run_id", "case_id", "method", "repeat"])
    assert store.con.execute("SELECT count(*) FROM eval_result").fetchone()[0] == 2


def test_upsert_empty_rows_returns_zero(tmp_path):
    store = Store(tmp_path / "t.duckdb")
    store.init()
    assert store.upsert("source", [], ["source_id"]) == 0


def test_sha256_file(tmp_path):
    p = tmp_path / "f.txt"
    p.write_bytes(b"abc")
    assert sha256_file(p) == "ba7816bf8f01cfea414140de5dae2223b00361a396177a9cb410ff61f20015ad"


def test_registry_loads():
    specs = load_registry(ROOT / "sources.yaml")
    assert len(specs) >= 6
    ids = {s.id for s in specs}
    assert {"irdai_health_master_2024", "irdai_products_regs_2024",
            "ombudsman_rules_2017", "cio_annual_2023_24"} <= ids
    assert all(s.url.startswith("https://") for s in specs)


def test_upsert_serialises_dict_and_list_values_as_json(tmp_path):
    store = Store(tmp_path / "t.duckdb")
    store.init()
    card = {"rule_id": "R", "version": 1, "params": {"months": 60}, "triggers": ["a"]}
    store.upsert("rule_card", [card], ["rule_id", "version"])
    got = store.con.execute("SELECT params->>'$.months', triggers::VARCHAR FROM rule_card").fetchone()
    assert got == ("60", '["a"]')


def test_close_is_idempotent_and_ends_use(tmp_path):
    import duckdb
    import pytest

    store = Store(tmp_path / "t.duckdb")
    store.init()
    store.close()
    store.close()
    with pytest.raises(duckdb.Error):
        store.con.execute("select 1")


def test_context_manager_closes(tmp_path):
    import duckdb

    with Store(tmp_path / "t.duckdb") as store:
        store.init()
        assert store.con.execute("select 1").fetchone() == (1,)
    try:
        store.con.execute("select 1")
        raised = False
    except duckdb.Error:
        raised = True
    assert raised
