"""Run the rules-vs-baselines evaluation when reviewed facts or approved cards change."""
from datetime import datetime
from pathlib import Path

from airflow.sdk import Asset, Param, dag, task

EVAL_REPORT = Asset("eval_report")


@dag(
    dag_id="evaluation",
    schedule=(Asset("reviewed_case_facts") | Asset("approved_rule_cards")),
    start_date=datetime(2026, 10, 1),
    catchup=False,
    params={"repeats": Param(3, type="integer", minimum=1)},
    tags=["sarthi", "data"],
)
def evaluation():
    @task(outlets=[EVAL_REPORT], pool="duckdb")
    def run(params=None, run_id=None) -> str:
        from sarthi.data import evaluate
        from sarthi.data.cli import open_store

        with open_store() as store:
            summary = evaluate.run_eval(f"airflow-{run_id}", ["rules", "glimmer_only", "spark_only"],
                                        params["repeats"], store)
        out = Path("docs/eval/report.md")
        evaluate.write_report(summary, out)
        return str(out)

    run()


evaluation()
