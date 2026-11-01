"""Seed rule cards -> verify quotes -> human approval per card -> approve or disable."""
import os
from datetime import datetime
from pathlib import Path

from airflow.providers.standard.operators.empty import EmptyOperator
from airflow.providers.standard.operators.hitl import ApprovalOperator
from airflow.sdk import Asset, Param, dag, get_current_context, task

SEED_DIR = Path(os.environ.get("SARTHI_RULES_DIR", Path(__file__).resolve().parents[1] / "rules" / "seed"))
PAGES = Asset("pages")
APPROVED = Asset("approved_rule_cards")


@dag(
    dag_id="rule_cards",
    schedule=[PAGES],
    start_date=datetime(2026, 10, 1),
    catchup=False,
    tags=["sarthi", "data", "hitl"],
)
def rule_cards():
    @task(pool="duckdb")
    def load_seed() -> int:
        from sarthi.data.cli import open_store
        from sarthi.data.rule_cards import load_seed as _load

        with open_store() as store:
            return _load(SEED_DIR, store)

    @task(pool="duckdb")
    def verify_quotes(_loaded: int) -> list[dict]:
        """One approval form per card whose quote is found verbatim on its source page."""
        from sarthi.data.cli import open_store
        from sarthi.data.rule_cards import approval_body, verify_all

        with open_store() as store:
            verified = verify_all(store)
        return [
            {
                "subject": f"Approve rule card {c.rule_id} v{c.version}?",
                "body": approval_body(c, qc.page_no),
                "rule_id": c.rule_id,
                "version": c.version,
            }
            for c, qc in verified if qc.found and c.status == "draft"
        ]

    forms = verify_quotes(load_seed())

    approval = ApprovalOperator.partial(
        task_id="approve_card",
        params={"reason": Param("", type="string", description="Required when rejecting")},
        map_index_template="{{ task.subject }}",
    ).expand_kwargs(forms.map(lambda f: {"subject": f["subject"], "body": f["body"]}))

    # ApprovalOperator skips its direct downstream on Reject; this barrier absorbs the skip so
    # approve_or_disable (trigger_rule all_done) still runs and can disable the rejected cards.
    barrier = EmptyOperator(task_id="after_approvals", trigger_rule="all_done")
    approval >> barrier

    @task(outlets=[APPROVED], trigger_rule="all_done", pool="duckdb")
    def approve_or_disable(cards: list[dict]) -> dict:
        from sarthi.data.cli import open_store
        from sarthi.data.rule_cards import approve, disable

        ti = get_current_context()["ti"]
        decisions = ti.xcom_pull(task_ids="approve_card", map_indexes=list(range(len(cards)))) or []
        done = {"approved": 0, "disabled": 0, "undecided": 0}
        with open_store() as store:
            for card, d in zip(cards, decisions):
                if not d:  # failed or timed out: leave as draft (fail closed)
                    done["undecided"] += 1
                    continue
                user = (d.get("responded_by_user") or {}).get("name") or "unknown"
                if d["chosen_options"] == ["Approve"]:
                    approve(card["rule_id"], card["version"], user, store)
                    done["approved"] += 1
                else:
                    reason = (d.get("params_input") or {}).get("reason") or "rejected by reviewer"
                    disable(card["rule_id"], card["version"], f"{reason} (by {user})", store)
                    done["disabled"] += 1
        return done

    barrier >> approve_or_disable(forms)


rule_cards()
