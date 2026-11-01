"""Disk cache and spend ledger for model calls. Paths derive from SARTHI_DATA_DIR."""

import hashlib
import json
import os
from pathlib import Path


def data_dir() -> Path:
    return Path(os.environ.get("SARTHI_DATA_DIR", "data"))


def cache_key(model: str, messages: list, tools: list | None, schema_name: str | None,
              max_tokens: int) -> str:
    canon = json.dumps([model, messages, tools, schema_name, max_tokens],
                       sort_keys=True, separators=(",", ":"), ensure_ascii=False)
    return hashlib.sha256(canon.encode()).hexdigest()


def _cache_path(key: str) -> Path:
    return data_dir() / "llm_cache" / f"{key}.json"


def cache_get(key: str) -> dict | None:
    p = _cache_path(key)
    if not p.exists():
        return None
    try:
        return json.loads(p.read_text())
    except (OSError, ValueError):
        return None


def cache_put(key: str, value: dict) -> None:
    p = _cache_path(key)
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(json.dumps(value))


def _ledger() -> Path:
    return data_dir() / "llm_spend.jsonl"


def total_spend() -> float:
    p = _ledger()
    if not p.exists():
        return 0.0
    total = 0.0
    for line in p.read_text().splitlines():
        if line.strip():
            total += float(json.loads(line).get("cost_usd", 0.0))
    return total


def record_spend(entry: dict) -> None:
    p = _ledger()
    p.parent.mkdir(parents=True, exist_ok=True)
    with open(p, "a") as f:
        f.write(json.dumps(entry) + "\n")
