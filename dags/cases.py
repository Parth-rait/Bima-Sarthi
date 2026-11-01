"""Search -> fetch -> extract judgments, then a human reviews flagged facts."""
from datetime import datetime

from airflow.providers.standard.operators.hitl import HITLEntryOperator
from airflow.sdk import Asset, Param, dag, get_current_context, task

from sarthi.data.cases import QUERIES

REVIEWED = Asset("reviewed_case_facts")


@dag(
    dag_id="cases",
    schedule=None,  # manual
    start_date=datetime(2026, 10, 1),
    catchup=False,
    params={"max_results": Param(5, type="integer", minimum=1, description="Results per query")},
    tags=["sarthi", "data", "hitl"],
)
def cases():
    @task(pool="duckdb")
    def search(query_key: str, params=None) -> list[str]:
        from sarthi.data.cases import search_cases
        from sarthi.data.cli import open_store

        with open_store() as store:
            return search_cases(QUERIES[query_key], max_results=params["max_results"], store=store)

    @task
    def dedupe(per_query: list[list[str]]) -> list[str]:
        return sorted({doc_id for ids in per_query for doc_id in ids})

    @task(pool="duckdb")
    def fetch(doc_id: str) -> str:
        from sarthi.data.cases import fetch_case
        from sarthi.data.cli import open_store

        with open_store() as store:
            return fetch_case(doc_id, store).case_id

    @task(pool="duckdb")
    def extract(case_id: str) -> dict:
        from sarthi.data.case_facts import extract_case
        from sarthi.data.cli import open_store

        with open_store() as store:
            rows = extract_case(case_id, store)
        return {"case_id": case_id,
                "needs_review": [r.field for r in rows if r.status == "needs_review"]}

    @task(pool="duckdb")
    def build_forms(extracted: list[dict]) -> list[dict]:
        """One entry form per case with at least one extracted fact (all fields listed)."""
        from sarthi.data.case_facts import build_review_form
        from sarthi.data.cli import open_store

        with open_store() as store:
            forms = [build_review_form(e["case_id"], store) for e in extracted]
        return [{k: f[k] for k in ("case_id", "subject", "body")} for f in forms if f]

    @task(outlets=[REVIEWED], trigger_rule="none_failed", pool="duckdb")
    def apply_review(forms: list[dict]) -> int:
        from sarthi.data.case_facts import apply_review_forms
        from sarthi.data.cli import open_store

        ti = get_current_context()["ti"]
        responses = ti.xcom_pull(task_ids="review_form", map_indexes=list(range(len(forms)))) or []
        with open_store() as store:
            return apply_review_forms(forms, responses, store)

    ids = dedupe(search.expand(query_key=list(QUERIES)))
    extracted = extract.expand(case_id=fetch.expand(doc_id=ids))
    forms = build_forms(extracted)

    form = HITLEntryOperator.partial(
        task_id="review_form",
        params={"decisions": Param("{}", type="string", description="JSON: field -> {action, value, note}")},
        map_index_template="{{ task.subject }}",
    ).expand_kwargs(forms.map(lambda f: {"subject": f["subject"], "body": f["body"]}))

    form >> apply_review(forms)


cases()
