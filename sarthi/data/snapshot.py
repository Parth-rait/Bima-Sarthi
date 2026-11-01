"""Public-data snapshot for the Space: only what the app serves, no judgments, cases or evals."""
from pathlib import Path

from sarthi.core.store import Store

# table -> (primary key, WHERE clause on the source store). The where clauses are the privacy
# boundary: judgment text, cases, case facts and eval results are never selected.
_NON_JUDGMENT_SHAS = ("(SELECT sha256 FROM source "
                      "WHERE sha256 IS NOT NULL AND COALESCE(doc_type, '') <> 'judgment')")
TABLES: dict[str, tuple[list[str], str]] = {
    "source": (["source_id"], "COALESCE(doc_type, '') <> 'judgment'"),
    "document_page": (["sha256", "page_no"], f"sha256 IN {_NON_JUDGMENT_SHAS}"),
    "rule_card": (["rule_id", "version"], "status = 'approved'"),
    "policy_product": (["product_id"], "TRUE"),
    "policy_clause": (["product_id", "clause_no"], "TRUE"),
    "insurer_stat": (["insurer", "year", "metric"], "TRUE"),
}
# Tables that must exist but stay empty in a snapshot (reported so the privacy check is visible).
EMPTY_TABLES = ["case", "case_fact", "eval_result", "freshness_alert"]


class SnapshotError(Exception):
    pass


def make_snapshot(src: Store, out: Path) -> dict[str, int]:
    """Write a fresh store at `out` holding the public tables only. Returns row counts per table
    (including the always-empty ones)."""
    out = Path(out)
    if out.exists():
        raise SnapshotError(f"{out} already exists; refusing to overwrite")
    with Store(out) as dst:
        dst.init()
        counts: dict[str, int] = {}
        for table, (key, where) in TABLES.items():
            cur = src.con.execute(f'SELECT * FROM "{table}" WHERE {where}')
            cols = [c[0] for c in cur.description]
            rows = [dict(zip(cols, r)) for r in cur.fetchall()]
            counts[table] = dst.upsert(table, rows, key=key)
        for table in EMPTY_TABLES:
            counts[table] = dst.con.execute(f'SELECT count(*) FROM "{table}"').fetchone()[0]
        dst.con.execute("CHECKPOINT")
    return counts
