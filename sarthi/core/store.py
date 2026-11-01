from pathlib import Path

import duckdb

SCHEMA_PATH = Path(__file__).with_name("schema.sql")


def _q(ident: str) -> str:
    return '"' + ident.replace('"', '""') + '"'


class Store:
    def __init__(self, path: Path):
        self.path = Path(path)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self.con = duckdb.connect(str(self.path))

    def close(self) -> None:
        """Release the DuckDB file lock (idempotent)."""
        self.con.close()

    def __enter__(self) -> "Store":
        return self

    def __exit__(self, *exc) -> None:
        self.close()

    def init(self) -> None:
        self.con.execute(SCHEMA_PATH.read_text(encoding="utf-8"))

    def upsert(self, table: str, rows: list[dict], key: list[str]) -> int:
        """Insert or replace rows on the primary key `key`. Returns rows written."""
        if not rows:
            return 0
        cols = list(rows[0].keys())
        if not set(key) <= set(cols):
            raise ValueError(f"key {key} not in row columns {cols}")
        col_sql = ", ".join(_q(c) for c in cols)
        marks = ", ".join("?" for _ in cols)
        key_sql = ", ".join(_q(k) for k in key)
        updates = [c for c in cols if c not in key]
        action = (
            "DO UPDATE SET " + ", ".join(f"{_q(c)} = EXCLUDED.{_q(c)}" for c in updates)
            if updates else "DO NOTHING"
        )
        sql = (
            f"INSERT INTO {_q(table)} ({col_sql}) VALUES ({marks}) "
            f"ON CONFLICT ({key_sql}) {action}"
        )
        self.con.executemany(sql, [[r[c] for c in cols] for r in rows])
        return len(rows)
