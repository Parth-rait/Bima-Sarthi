"""Fetch every registered source, then parse the raw files into pages."""
import os
from datetime import datetime
from pathlib import Path

from airflow.sdk import Asset, Param, dag, task

REGISTRY = Path(os.environ.get("SARTHI_REGISTRY", Path(__file__).resolve().parents[1] / "sources.yaml"))
RAW_SOURCES = Asset("raw_sources")
PAGES = Asset("pages")


@dag(
    dag_id="ingest_sources",
    schedule=None,  # manual; switch to "@weekly" to refresh on a cadence
    start_date=datetime(2026, 10, 1),
    catchup=False,
    params={"mode": Param("direct", enum=["direct", "firecrawl"])},
    tags=["sarthi", "data"],
)
def ingest_sources():
    @task
    def list_sources() -> list[dict]:
        from sarthi.core.registry import load_registry

        return [s.model_dump() for s in load_registry(REGISTRY)]

    @task(outlets=[RAW_SOURCES], pool="duckdb")
    def fetch(spec: dict, params=None) -> str:
        from sarthi.core.registry import SourceSpec
        from sarthi.data.cli import open_store
        from sarthi.data.fetch import fetch_source

        with open_store() as store:
            return fetch_source(SourceSpec(**spec), store, mode=params["mode"]).sha256

    @task(outlets=[PAGES], trigger_rule="all_done", pool="duckdb")
    def parse() -> int:
        from sarthi.data.cli import open_store
        from sarthi.data.parse_docs import parse_source

        with open_store() as store:
            shas = [r[0] for r in store.con.execute(
                "SELECT DISTINCT sha256 FROM source WHERE sha256 IS NOT NULL ORDER BY 1").fetchall()]
            return sum(parse_source(sha, store) for sha in shas)

    fetched = fetch.expand(spec=list_sources())
    fetched >> parse()


ingest_sources()
