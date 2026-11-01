"""Build the clause index for every wording source in the store."""
from datetime import datetime

from airflow.sdk import Asset, dag, task

PAGES = Asset("pages")
POLICY_INDEX = Asset("policy_index")


@dag(
    dag_id="policy_index",
    schedule=[PAGES],
    start_date=datetime(2026, 10, 1),
    catchup=False,
    tags=["sarthi", "data"],
)
def policy_index():
    @task(pool="duckdb")
    def list_wordings() -> list[dict]:
        from sarthi.data.cli import open_store

        with open_store() as store:
            rows = store.con.execute(
                "SELECT source_id, sha256 FROM source "
                "WHERE doc_type='wording' AND sha256 IS NOT NULL ORDER BY 1").fetchall()
        return [{"product_id": r[0], "wording_sha256": r[1]} for r in rows]

    @task(outlets=[POLICY_INDEX], pool="duckdb")
    def build(product_id: str, wording_sha256: str) -> int:
        from sarthi.data.cli import open_store
        from sarthi.data.policy_index import build_index

        with open_store() as store:
            return build_index(product_id, wording_sha256, store)

    build.expand_kwargs(list_wordings())


policy_index()
