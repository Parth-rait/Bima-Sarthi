import json
from datetime import date

import pytest
from fastapi.testclient import TestClient

from sarthi.app import main
from sarthi.app.gallery import build_gallery
from sarthi.core.models import Case, CaseFact, RuleCard, Source
from sarthi.core.store import Store


def moratorium():
    return RuleCard(
        rule_id="MORATORIUM_60M", version=1, quote="No claim shall be contestable after sixty continuous months.",
        source_sha256="a" * 64, page_no=7, in_force_from=date(2024, 4, 1),
        applies_by="policy_start_or_renewal", triggers=["non_disclosure"],
        inputs=["continuous_cover_months", "fraud_alleged"], params={"moratorium_months": 60},
        condition="continuous_cover_months >= 60 and not fraud_alleged",
        if_true="CHALLENGEABLE", if_false="CONSISTENT", status="approved")


@pytest.fixture
def store(tmp_path):
    s = Store(tmp_path / "t.duckdb")
    s.init()
    s.upsert("source", [Source(source_id="j1", url="https://indiankanoon.org/doc/1/",
                               sha256="j" * 64, licence_note="public judgment").model_dump()], ["source_id"])
    for cid, outcome in [("c1", "allowed"), ("c2", None), ("c3", "dismissed")]:
        s.upsert("case", [Case(case_id=cid, source_sha256="j" * 64, forum="State Commission",
                               case_number=f"CC/{cid}", decided_on=date(2025, 3, 1), insurer="X",
                               outcome=outcome).model_dump()], ["case_id"])
    def facts(cid, status):
        return [CaseFact(case_id=cid, field=f, value=json.dumps(v), quote=f"q {f}", page_no=2,
                         status=status).model_dump() for f, v in [
            ("rejection_ground", "non_disclosure"), ("fraud_alleged", False),
            ("inception_date", "2019-01-10"), ("policy_renewal_date", "2024-06-01"),
            ("claim_date", "2025-02-01")]]
    s.upsert("case_fact", facts("c1", "reviewed") + facts("c2", "reviewed") + facts("c3", "extracted"),
             ["case_id", "field"])
    return s


def test_build_gallery_uses_only_reviewed_cases_with_outcome(store, tmp_path):
    out = tmp_path / "gal"
    cases = build_gallery(store, n=6, out_dir=out, cards=[moratorium()])
    assert [c.case_id for c in cases] == ["c1"]
    d = json.loads((out / "c1.json").read_text())
    assert d["citation"] == {"forum": "State Commission", "case_number": "CC/c1",
                             "decided_on": "2025-03-01", "source_url": "https://indiankanoon.org/doc/1/"}
    assert d["outcome"] == "allowed" and d["attribution"] == "powered by IKanoon"
    assert d["findings"][0]["verdict"] == "CHALLENGEABLE"


def test_gallery_routes_read_json_only(tmp_path, monkeypatch, store):
    out = tmp_path / "gal"
    build_gallery(store, out_dir=out, cards=[moratorium()])
    monkeypatch.setenv("SARTHI_GALLERY_DIR", str(out))
    monkeypatch.setenv("SARTHI_DATA_DIR", str(tmp_path / "nodb"))
    for v in ("WRITER_MODEL", "READER_MODEL"):
        monkeypatch.delenv(v, raising=False)
    c = TestClient(main.app)
    lst = c.get("/gallery").json()
    assert lst["attribution"] == "powered by IKanoon" and lst["cases"][0]["case_id"] == "c1"
    one = c.get("/gallery/c1").json()
    assert one["findings"][0]["rule_quote"]
    assert c.get("/gallery/zzz").status_code == 404
    assert c.get("/gallery/..%2Fsecret").status_code == 404


def test_gallery_empty_dir_is_empty_list(tmp_path, monkeypatch):
    monkeypatch.setenv("SARTHI_GALLERY_DIR", str(tmp_path / "none"))
    assert TestClient(main.app).get("/gallery").json()["cases"] == []
