import json

from fastapi.testclient import TestClient

from sarthi.app import main
from sarthi.data.evaluate import EvalSummary, Metrics, write_summary


def _summary(**m) -> EvalSummary:
    return EvalSummary(n_cases=13, n_skipped_no_facts=6, n_eligible=5, n_skipped=2, n_out_of_scope=1,
                       n_no_usable=5, repeats=3, by_method={"rules": Metrics(**m)})


def test_summary_marks_rates_unmeasurable_when_no_finding_is_scorable(tmp_path):
    p = tmp_path / "summary.json"
    write_summary(_summary(finding_abstentions=15, quote_coverage=1.0, stability=1.0,
                           abstention_set_runs=18, safe_abstention_runs=18), p, run_id="r1")
    d = json.loads(p.read_text())
    r = d["methods"]["rules"]
    assert d["run_id"] == "r1" and d["n_cases"] == 13 and d["n_eligible"] == 5
    assert r["scorable_findings"] == 0 and r["agreement"] is None and r["false_hope_rate"] is None
    assert r["abstained_findings"] == 15 and r["quote_coverage"] == 1.0
    assert r["safe_abstention"] == {"safe": 18, "of": 18}
    assert d["limitation"]


def test_summary_reports_computed_rates_only(tmp_path):
    p = tmp_path / "summary.json"
    write_summary(_summary(finding_n=4, finding_agreeing=3, finding_challengeable=2, finding_false_hope_runs=1,
                           finding_agreement=0.75, finding_false_hope_rate=0.5), p, run_id="r2")
    r = json.loads(p.read_text())["methods"]["rules"]
    assert r["agreement"] == {"agree": 3, "of": 4, "rate": 0.75}
    assert r["false_hope_rate"] == {"false_hope": 1, "of": 2, "rate": 0.5}


def test_evidence_route_serves_the_summary_and_404s_without_one(tmp_path, monkeypatch):
    c = TestClient(main.app)
    monkeypatch.setenv("SARTHI_EVIDENCE_FILE", str(tmp_path / "missing.json"))
    assert c.get("/api/evidence").status_code == 404
    p = tmp_path / "summary.json"
    write_summary(_summary(), p, run_id="r3")
    monkeypatch.setenv("SARTHI_EVIDENCE_FILE", str(p))
    body = c.get("/api/evidence").json()
    assert body["run_id"] == "r3" and "rules" in body["methods"]


def test_evidence_page_is_a_client_route(monkeypatch, tmp_path):
    # The page lives at /evidence; the JSON at /api/evidence, so a refresh never lands on raw JSON.
    assert "evidence" in main.CLIENT_ROUTES
