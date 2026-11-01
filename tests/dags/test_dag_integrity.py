from pathlib import Path

import pytest

pytest.importorskip("airflow", reason="install the airflow dependency group: uv run --group airflow pytest tests/dags")

DAGS = Path(__file__).resolve().parents[2] / "dags"
EXPECTED = {"ingest_sources", "rule_cards", "policy_index", "cases", "evaluation", "freshness"}


@pytest.fixture(scope="module")
def bag():
    try:
        from airflow.dag_processing.dagbag import DagBag
    except ImportError:  # Airflow < 3.1
        from airflow.models import DagBag
    return DagBag(dag_folder=str(DAGS), include_examples=False)


def test_dags_import_cleanly(bag):
    assert bag.import_errors == {}
    assert set(bag.dag_ids) == EXPECTED


def test_rule_cards_has_approval_gate(bag):
    ops = {t.task_type for t in bag.dags["rule_cards"].tasks}
    assert "ApprovalOperator" in ops


def test_cases_has_entry_form(bag):
    ops = {t.task_type for t in bag.dags["cases"].tasks}
    assert "HITLEntryOperator" in ops


def _store_tasks(bag):
    import inspect

    for dag in bag.dags.values():
        for t in dag.tasks:
            fn = getattr(t, "python_callable", None) or getattr(t, "partial_kwargs", {}).get("python_callable")
            if fn is not None and "open_store" in inspect.getsource(fn):
                yield dag.dag_id, t


def test_every_store_task_uses_the_duckdb_pool(bag):
    found = list(_store_tasks(bag))
    assert len(found) >= 10
    assert [(d, t.task_id) for d, t in found if t.pool != "duckdb"] == []


def test_store_tasks_close_the_store_via_with():
    import ast

    for path in DAGS.glob("*.py"):
        tree = ast.parse(path.read_text(encoding="utf-8"))
        withed = {id(i.context_expr) for n in ast.walk(tree) if isinstance(n, ast.With) for i in n.items}
        bare = [n.lineno for n in ast.walk(tree)
                if isinstance(n, ast.Call) and getattr(n.func, "id", "") == "open_store" and id(n) not in withed]
        assert bare == [], f"{path.name}: open_store() outside `with` at lines {bare}"
