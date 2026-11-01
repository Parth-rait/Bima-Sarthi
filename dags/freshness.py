"""Weekly search for new IRDAI circulars that may affect approved rules."""
from datetime import datetime, timedelta

from airflow.sdk import dag, task


@dag(
    dag_id="freshness",
    schedule="@weekly",
    start_date=datetime(2026, 10, 1),
    catchup=False,
    tags=["sarthi", "data"],
)
def freshness():
    @task(pool="duckdb")
    def check(data_interval_start=None) -> int:
        from sarthi.data.cli import open_store
        from sarthi.data.freshness import check_freshness

        since = (data_interval_start or datetime.now() - timedelta(days=7)).date()
        with open_store() as store:
            return len(check_freshness(store, since))

    check()


freshness()
