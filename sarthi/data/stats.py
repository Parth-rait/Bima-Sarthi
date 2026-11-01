"""Hand-entered insurer statistics. A value loads only if it appears on its cited page."""
import csv
import re
from pathlib import Path

from sarthi.core.store import Store

DEFAULT_CSV = Path("data_entry/insurer_stats.csv")
_DEVANAGARI = str.maketrans("०१२३४५६७८९", "0123456789")
# grouped numbers: 31,490 / 1,23,456 (Indian) — commas removed only inside a valid group
_GROUPED = re.compile(r"(?<![\d,])\d{1,3}(?:,\d{2,3})+(?![\d,]\d)")


class StatNotOnPage(ValueError):
    def __init__(self, row: dict, reason: str = "value not found on the cited page"):
        self.row = row
        super().__init__(f"{reason}: {row}")


def _norm_page(text: str) -> str:
    return _GROUPED.sub(lambda m: m.group().replace(",", ""), text.translate(_DEVANAGARI))


def _norm_value(v: str) -> str:
    return re.sub(r"[,\s]", "", v.translate(_DEVANAGARI))


def _on_page(value: str, page_text: str) -> bool:
    v = _norm_value(value)
    if not v:
        return False
    pat = r"(?<![\d.,])" + re.escape(v) + r"(?!\d|\.\d|,\d)"
    return re.search(pat, _norm_page(page_text)) is not None


def load_stats_csv(path: Path, store: Store) -> int:
    with open(path, newline="", encoding="utf-8") as f:
        rows = list(csv.DictReader(f))
    out = []
    for r in rows:
        sid = (r.get("source_id") or "").strip()
        found = store.con.execute("SELECT sha256 FROM source WHERE source_id=?", [sid]).fetchone()
        if not found or not found[0]:
            raise ValueError(f"unknown or unstored source '{sid}' in row {r}")
        sha = found[0]
        try:
            page_no = int(r["page_no"])
        except (TypeError, ValueError):
            raise StatNotOnPage(r, "bad page_no") from None
        page = store.con.execute(
            "SELECT text FROM document_page WHERE sha256=? AND page_no=?", [sha, page_no]).fetchone()
        if not page or not _on_page(r["value"], page[0] or ""):
            raise StatNotOnPage(r)
        out.append({"insurer": r["insurer"].strip(), "year": r["year"].strip(),
                    "metric": r["metric"].strip(), "value": float(_norm_value(r["value"])),
                    "unit": r["unit"].strip(), "source_sha256": sha, "page_no": page_no})
    if not out:
        return 0
    return store.upsert("insurer_stat", out, ["insurer", "year", "metric"])
