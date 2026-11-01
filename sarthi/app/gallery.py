"""Gallery of real, reviewed judgment cases (never users' documents).

`build_gallery` runs the rule engine on the reviewed facts of real cases and writes one
JSON file per case. The web app serves those files only, so it needs no database or model.
Builder: `python -m sarthi.app.gallery build`.
"""
import json
import os
import re
import sys
from pathlib import Path

from pydantic import BaseModel

from sarthi.core.engine import run_rules
from sarthi.core.models import RuleCard
from sarthi.core.store import Store
from sarthi.data.case_facts import load_reviewed_facts
from sarthi.data.rule_cards import approved_cards

ATTRIBUTION = "powered by IKanoon"
_ID = re.compile(r"^[A-Za-z0-9_.-]{1,128}$")


class GalleryCase(BaseModel):
    case_id: str
    citation: dict
    insurer: str | None = None
    outcome: str | None = None
    relief_amount: float | None = None
    licence_note: str | None = None
    findings: list[dict]
    attribution: str = ATTRIBUTION


def gallery_dir() -> Path:
    return Path(os.environ.get("SARTHI_GALLERY_DIR", Path(__file__).resolve().parents[2] / "gallery"))


def build_gallery(store: Store, n: int = 6, *, out_dir: Path | None = None,
                  cards: list[RuleCard] | None = None) -> list[GalleryCase]:
    out_dir = Path(out_dir) if out_dir else gallery_dir()
    cards = approved_cards(store) if cards is None else cards
    rows = store.con.execute(
        'SELECT c.case_id, c.forum, c.case_number, c.decided_on, c.insurer, c.outcome, '
        'c.relief_amount, s.url, s.licence_note FROM "case" c '
        'LEFT JOIN source s ON s.sha256 = c.source_sha256 '
        "WHERE c.outcome IS NOT NULL AND EXISTS (SELECT 1 FROM case_fact f WHERE f.case_id = c.case_id "
        "AND f.status IN ('reviewed','corrected')) ORDER BY c.decided_on DESC NULLS LAST, c.case_id"
    ).fetchall()
    out: list[GalleryCase] = []
    for cid, forum, number, decided, insurer, outcome, relief, url, licence in rows:
        if len(out) >= n:
            break
        findings = run_rules(load_reviewed_facts(cid, store), cards)
        if not findings:
            continue
        out.append(GalleryCase(
            case_id=cid, insurer=insurer, outcome=outcome, relief_amount=relief,
            licence_note=licence,
            citation={"forum": forum, "case_number": number,
                      "decided_on": decided.isoformat() if decided else None, "source_url": url},
            findings=[f.model_dump(mode="json") for f in findings]))
    out_dir.mkdir(parents=True, exist_ok=True)
    for old in out_dir.glob("*.json"):
        old.unlink()
    for c in out:
        (out_dir / f"{c.case_id}.json").write_text(
            json.dumps(c.model_dump(mode="json"), ensure_ascii=False, indent=2), encoding="utf-8")
    return out


def list_cases(directory: Path | None = None) -> list[dict]:
    d = Path(directory) if directory else gallery_dir()
    cases = []
    for p in sorted(d.glob("*.json")) if d.is_dir() else []:
        data = json.loads(p.read_text(encoding="utf-8"))
        cases.append({"case_id": data["case_id"], "citation": data["citation"],
                      "outcome": data.get("outcome"),
                      "verdicts": [f["verdict"] for f in data["findings"]]})
    return cases


def load_case(case_id: str, directory: Path | None = None) -> dict | None:
    if not _ID.match(case_id):
        return None
    p = (Path(directory) if directory else gallery_dir()) / f"{case_id}.json"
    return json.loads(p.read_text(encoding="utf-8")) if p.is_file() else None


def main(argv: list[str]) -> int:
    if argv[:1] != ["build"]:
        print("usage: python -m sarthi.app.gallery build", file=sys.stderr)
        return 2
    data_dir = Path(os.environ.get("SARTHI_DATA_DIR", Path(__file__).resolve().parents[2] / "data"))
    store = Store(data_dir / "bima_sarthi.duckdb")
    cases = build_gallery(store)
    print(f"wrote {len(cases)} gallery case(s) to {gallery_dir()}")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
