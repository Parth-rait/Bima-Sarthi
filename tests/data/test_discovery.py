import json
import re

import httpx
import pytest
import respx

from sarthi.core.store import Store
from sarthi.data import cases, cli, discovery
from sarthi.data.discovery import (DISCOVERY_QUERIES, FAMILY_LINE, CandidateLog, RunBudget,
                                   RunCapReached, parse_found, prescreen, search_pages)

SEARCH_URL = "https://api.indiankanoon.org/search/"


def doc_url(tid):
    return f"https://api.indiankanoon.org/doc/{tid}/"


def hit(tid, title="A v. Star Health", headline="mediclaim repudiated", docsource="NCDRC",
        publishdate="2023-05-17", fragment=""):
    return {"tid": tid, "title": title, "headline": headline, "docsource": docsource,
            "publishdate": publishdate, "fragment": fragment}


def page(tids, found, **kw):
    return httpx.Response(200, json={"docs": [hit(t, **kw) for t in tids], "found": found})


@pytest.fixture(autouse=True)
def env(monkeypatch, tmp_path):
    monkeypatch.setenv("SARTHI_DATA_DIR", str(tmp_path))
    monkeypatch.setenv("IKANOON_TOKEN", "tok123")
    monkeypatch.setenv("IK_COST_SEARCH_INR", "0.5")
    monkeypatch.setenv("IK_COST_DOC_INR", "0.2")
    monkeypatch.delenv("IK_CAP_INR", raising=False)


def ledger(tmp_path):
    p = tmp_path / "ik_spend.jsonl"
    return [json.loads(x) for x in p.read_text().splitlines()] if p.exists() else []


def lines(p):
    return [json.loads(x) for x in p.read_text().splitlines() if x.strip()]


# ---- query catalogue ---------------------------------------------------------

def test_every_family_has_a_product_line_and_valid_ik_syntax():
    assert set(DISCOVERY_QUERIES) == set(FAMILY_LINE)
    assert {"life", "personal_accident", "crop", "credit_life"} <= set(FAMILY_LINE.values())
    assert "health" in FAMILY_LINE.values()
    for fam, qs in DISCOVERY_QUERIES.items():
        assert qs, fam
        for q in qs:
            bare = re.sub(r'"[^"]*"', '""', q)
            assert not re.search(r"\b(OR|AND|NOT)\b", bare), (fam, q)
            assert "ANDD" not in bare, (fam, q)   # explicit ANDD breaks IK results
            for m in re.finditer(r"\w*(?:ORR|NOTT)\w*", bare):
                assert m.group(0) in ("ORR", "NOTT"), (fam, m.group(0))
                assert bare[m.start() - 1] == " " and bare[m.end()] == " ", (fam, q)
            assert q.count('"') % 2 == 0 and q.count("(") == q.count(")"), (fam, q)
            assert q.count("doctypes:") == 1 and q.count("fromdate:") == 1, (fam, q)


def test_health_families_use_two_date_windows():
    for fam, line in FAMILY_LINE.items():
        if line != "health":
            continue
        qs = DISCOVERY_QUERIES[fam]
        old = [q for q in qs if "todate: 31-12-2022" in q]
        new = [q for q in qs if "fromdate: 1-1-2023" in q]
        assert old and new and len(old) == len(new) and len(qs) == len(old) + len(new), fam
        assert all("fromdate: 1-10-2020" in q for q in old), fam


def test_existing_grounds_and_expansion_are_reused():
    assert len(DISCOVERY_QUERIES["health_grounds"]) == 2 * len(cases.QUERIES)
    assert len(DISCOVERY_QUERIES["health_expansion"]) == 2 * len(cases.EXPANSION_QUERIES)
    assert any('"pre-existing disease"' in q for q in DISCOVERY_QUERIES["health_grounds"])


# ---- pagination ---------------------------------------------------------------

def test_parse_found():
    assert parse_found("1 - 10 of 23") == 23
    assert parse_found("11 - 20 of 1,234") == 1234
    assert parse_found("1 - 3 of 3") == 3
    assert parse_found(None) is None
    assert parse_found("nonsense") is None


@respx.mock
def test_search_pages_stops_when_total_exhausted_without_extra_page(tmp_path):
    route = respx.post(SEARCH_URL).mock(side_effect=[
        page(range(1, 11), "1 - 10 of 14"),
        page(range(11, 15), "11 - 14 of 14"),
        page([], "0"),   # must never be requested
    ])
    res = search_pages("q", 60)
    assert [d["tid"] for d in res.docs] == list(range(1, 15))
    assert res.total == 14 and res.pages == 2 and res.stopped == "exhausted"
    assert route.call_count == 2
    assert len(ledger(tmp_path)) == 2


@respx.mock
def test_search_pages_exact_multiple_of_ten_does_not_bill_an_empty_page(tmp_path):
    route = respx.post(SEARCH_URL).mock(side_effect=[
        page(range(1, 11), "1 - 10 of 20"), page(range(11, 21), "11 - 20 of 20"), page([], "0")])
    res = search_pages("q", 60)
    assert len(res.docs) == 20 and route.call_count == 2 and res.stopped == "exhausted"


@respx.mock
def test_search_pages_stops_at_max_results_and_truncates():
    route = respx.post(SEARCH_URL).mock(side_effect=[
        page(range(1, 11), "1 - 10 of 500"), page(range(11, 21), "11 - 20 of 500")])
    res = search_pages("q", 15)
    assert [d["tid"] for d in res.docs] == list(range(1, 16))
    assert res.pages == 2 and res.stopped == "max_results" and route.call_count == 2


@respx.mock
def test_search_pages_without_found_falls_back_to_empty_page():
    route = respx.post(SEARCH_URL).mock(side_effect=[
        httpx.Response(200, json={"docs": [hit(1), hit(2)]}),
        httpx.Response(200, json={"docs": []})])
    res = search_pages("q", 60)
    assert len(res.docs) == 2 and res.total is None and route.call_count == 2


@respx.mock
def test_search_pages_zero_results_one_page():
    route = respx.post(SEARCH_URL).mock(return_value=httpx.Response(200, json={"docs": [], "found": "0 - 0 of 0"}))
    res = search_pages("q", 60)
    assert res.docs == [] and res.pages == 1 and route.call_count == 1


@respx.mock
def test_search_pages_sends_zero_based_pagenum():
    route = respx.post(SEARCH_URL).mock(side_effect=[
        page(range(1, 11), "1 - 10 of 12"), page([11, 12], "11 - 12 of 12")])
    search_pages("qq", 60)
    assert b"pagenum=0" in route.calls[0].request.content
    assert b"pagenum=1" in route.calls[1].request.content


# ---- run cap --------------------------------------------------------------------

@respx.mock
def test_run_budget_stops_before_exceeding_and_keeps_partial_docs(tmp_path):
    route = respx.post(SEARCH_URL).mock(side_effect=[
        page(range(1, 11), "1 - 10 of 500"), page(range(11, 21), "11 - 20 of 500")])
    budget = RunBudget(max_inr=0.9)       # one 0.5 page fits, a second would hit 1.0
    res = search_pages("q", 60, budget=budget)
    assert route.call_count == 1 and len(res.docs) == 10 and res.stopped == "run_cap"
    assert total_spend(tmp_path) == pytest.approx(0.5)


def total_spend(tmp_path):
    return sum(r["cost_inr"] for r in ledger(tmp_path))


def test_run_budget_counts_only_this_runs_spend(tmp_path):
    (tmp_path / "ik_spend.jsonl").write_text(json.dumps({"kind": "search", "ref": "x", "cost_inr": 40.0}) + "\n")
    b = RunBudget(max_inr=1.0)
    b.check(0.5)
    assert b.spent == 0.0
    (tmp_path / "ik_spend.jsonl").write_text(
        (tmp_path / "ik_spend.jsonl").read_text() + json.dumps({"kind": "search", "ref": "y", "cost_inr": 0.8}) + "\n")
    assert b.spent == pytest.approx(0.8)
    with pytest.raises(RunCapReached):
        b.check(0.5)


@respx.mock
def test_global_cap_stops_cleanly_too(tmp_path, monkeypatch):
    monkeypatch.setenv("IK_CAP_INR", "0.6")
    route = respx.post(SEARCH_URL).mock(side_effect=[
        page(range(1, 11), "1 - 10 of 500"), page(range(11, 21), "11 - 20 of 500")])
    res = search_pages("q", 60, budget=RunBudget(max_inr=100))
    assert route.call_count == 1 and len(res.docs) == 10 and res.stopped == "global_cap"


# ---- pre-screen --------------------------------------------------------------------

def screen(title="", headline="", fragment="", docsource="", prior="health"):
    return prescreen({"title": title, "headline": headline, "fragment": fragment,
                      "docsource": docsource}, prior)


def test_prescreen_health_claim_is_likely_health():
    s = screen("Ramesh v. Star Health and Allied Insurance", "mediclaim claim repudiated, hospitalisation")
    assert (s.label, s.line) == ("likely_health", "health")


def test_prescreen_life_insurer_with_health_policy_is_unsure_not_excluded():
    s = screen("Seema v. HDFC Life Insurance Co Ltd", "the health policy cashless hospitalisation claim")
    assert s.label == "unsure" and s.line == "health"


def test_prescreen_pure_life_claim_is_other_line_life():
    s = screen("Kaur v. Life Insurance Corporation of India", "death claim repudiated, nominee, suppression of age", prior="health")
    assert (s.label, s.line) == ("likely_other_line", "life")


@pytest.mark.parametrize("title", [
    "State of Kerala v. Commissioner of Treasuries",
    "Retired Teacher v. District Level Empowered Committee",
    "Singh v. Union of India (CGHS reimbursement)",
    "Employees State Insurance Corporation v. Rao (ESI medical benefit)",
])
def test_prescreen_government_schemes_excluded(title):
    s = screen(title, "mediclaim health insurance reimbursement")
    assert s.label == "exclude" and "scheme" in s.reason


@pytest.mark.parametrize("title,headline", [
    ("Das v. New India Assurance", "motor vehicle accident, third party claim, own damage"),
    ("Shah v. United India Insurance", "Motor Accident Claims Tribunal compensation"),
    ("Roy v. ICICI Lombard", "truck accident vehicle insurance claim repudiated"),
])
def test_prescreen_motor_excluded(title, headline):
    assert screen(title, headline).label == "exclude"


def test_prescreen_housing_loan_death_claim_excluded():
    s = screen("Bank v. Gupta", "housing loan, borrower died, insurance claim for loan outstanding")
    assert s.label == "exclude"


def test_prescreen_credit_life_non_housing_is_other_line():
    s = screen("Rao v. Bajaj Allianz", "credit life cover on personal loan, borrower died, claim repudiated", prior="credit_life")
    assert (s.label, s.line) == ("likely_other_line", "credit_life")


def test_prescreen_crop_and_accident_lines():
    assert screen("Farmer v. Oriental Insurance", "crop insurance PMFBY claim rejected").line == "crop"
    s = screen("Heir v. National Insurance", "personal accident policy, accidental death, claim repudiated")
    assert (s.label, s.line) == ("likely_other_line", "personal_accident")


def test_prescreen_accident_policy_plus_mediclaim_is_unsure():
    s = screen("X v. National Insurance", "mediclaim and personal accident cover, hospitalisation")
    assert s.label == "unsure"


def test_prescreen_no_signal_is_unsure_with_family_prior():
    s = screen("A v. B", "insurance company deficiency in service", prior="health")
    assert (s.label, s.line) == ("unsure", "health")
    s2 = screen("A v. B", "insurance company deficiency in service", prior="crop")
    assert (s2.label, s2.line) == ("unsure", "crop")


def test_snippet_is_html_stripped_and_truncated():
    assert discovery.make_snippet({"headline": "a <b>b</b>  c", "fragment": ""}) == "a b c"
    assert len(discovery.make_snippet({"headline": "x" * 900})) <= 400


def test_prescreen_strips_html_and_is_case_insensitive():
    s = screen("A v. <b>STAR HEALTH</b>", "<b>Mediclaim</b> HOSPITALISATION")
    assert s.label == "likely_health"


def test_prescreen_tolerates_missing_fields():
    assert prescreen({"tid": 1}, "health").label == "unsure"


# ---- candidate log ----------------------------------------------------------------------

def test_candidate_log_dedupes_by_tid_and_survives_reload(tmp_path):
    p = tmp_path / "discovery" / "candidates.jsonl"
    log = CandidateLog(p)
    rec = {"tid": "7", "query_family": "f", "query": "q", "run_id": "r1", "title": "t", "forum": "NCDRC",
           "publishdate": "2023-01-01", "prescreen": "likely_health", "product_line_guess": "health"}
    assert log.add(rec) is True
    assert log.add({**rec, "run_id": "r2"}) is False
    assert "7" in log
    log2 = CandidateLog(p)
    assert "7" in log2 and log2.add({**rec, "tid": "8"}) is True
    rows = lines(p)
    assert [r["tid"] for r in rows] == ["7", "8"] and rows[0]["fetched"] is False


def test_candidate_log_mark_fetched_appends_and_merges(tmp_path):
    p = tmp_path / "candidates.jsonl"
    log = CandidateLog(p)
    log.add({"tid": "7", "prescreen": "unsure", "product_line_guess": "health"})
    log.mark_fetched("7", "r2")
    assert len(lines(p)) == 2     # append-only
    assert CandidateLog(p).get("7")["fetched"] is True
    assert CandidateLog(p).get("7")["prescreen"] == "unsure"


def test_stored_case_ids_reads_case_table_read_only(tmp_path):
    s = Store(tmp_path / "bima_sarthi.duckdb")
    s.init()
    s.upsert("case", [{"case_id": "ik_555", "source_sha256": "a"}], key=["case_id"])
    s.close()
    assert discovery.stored_case_tids(tmp_path / "bima_sarthi.duckdb") == {"555"}
    assert discovery.stored_case_tids(tmp_path / "missing.duckdb") == set()


# ---- end-to-end runner ---------------------------------------------------------------------

def two_query_catalogue(monkeypatch):
    monkeypatch.setattr(discovery, "DISCOVERY_QUERIES", {"fam_h": ["qh1", "qh2"], "fam_c": ["qc1"]})
    monkeypatch.setattr(discovery, "FAMILY_LINE", {"fam_h": "health", "fam_c": "crop"})


@respx.mock
def test_run_discovery_dedupes_logs_and_reports(tmp_path, monkeypatch):
    two_query_catalogue(monkeypatch)
    respx.post(SEARCH_URL).mock(side_effect=[
        page([1, 2, 3], "1 - 3 of 3"),                       # qh1
        page([3, 4], "1 - 2 of 2"),                          # qh2 (3 is dup inside the run)
        page([5], "1 - 1 of 1", title="Farmer v. Oriental", headline="crop insurance claim"),  # qc1
    ])
    out = discovery.run_discovery(["all"], max_results=60, max_inr=50, run_id="r1",
                                  stored_tids={"2"}, discovery_dir=tmp_path / "discovery")
    cand = lines(tmp_path / "discovery" / "candidates.jsonl")
    assert [c["tid"] for c in cand] == ["1", "3", "4", "5"]    # "2" is stored
    assert {"tid", "query_family", "query", "run_id", "title", "forum", "publishdate", "prescreen",
            "product_line_guess", "fetched"} <= set(cand[0])
    assert cand[0]["query_family"] == "fam_h" and cand[-1]["product_line_guess"] == "crop"
    assert cand[0]["snippet"] == "mediclaim repudiated"      # headline kept so humans can judge the pre-screen
    assert cand[0]["numcites"] is None
    run = lines(tmp_path / "discovery" / "runs.jsonl")[0]
    assert run["run_id"] == "r1" and run["pages_billed"] == 3
    assert run["ik_spend_after"] - run["ik_spend_before"] == pytest.approx(1.5)
    q = run["queries"]
    assert [x["returned"] for x in q] == [3, 2, 1]
    assert q[0]["new"] == 2 and q[0]["stored_duplicates"] == 1
    assert q[1]["new"] == 1 and q[1]["run_duplicates"] == 1
    assert run["unique_new"] == 4
    assert run["prescreen_counts"]["by_line"]["crop"] >= 1
    assert sum(run["prescreen_counts"]["by_label"].values()) == 4
    assert out["stopped"] is None


@respx.mock
def test_run_discovery_skips_candidates_from_previous_runs(tmp_path, monkeypatch):
    two_query_catalogue(monkeypatch)
    d = tmp_path / "discovery"
    respx.post(SEARCH_URL).mock(side_effect=[page([1], "1 - 1 of 1"), page([], "0"),
                                             page([1, 9], "1 - 2 of 2"), page([], "0")])
    discovery.run_discovery(["fam_h"], max_results=10, max_inr=50, run_id="r1", stored_tids=set(), discovery_dir=d)
    discovery.run_discovery(["fam_h"], max_results=10, max_inr=50, run_id="r2", stored_tids=set(), discovery_dir=d)
    assert [c["tid"] for c in lines(d / "candidates.jsonl")] == ["1", "9"]
    r2 = lines(d / "runs.jsonl")[1]
    assert r2["queries"][0]["previous_duplicates"] == 1 and r2["queries"][0]["new"] == 1


@respx.mock
def test_run_discovery_stops_cleanly_at_run_cap(tmp_path, monkeypatch):
    two_query_catalogue(monkeypatch)
    route = respx.post(SEARCH_URL).mock(side_effect=[
        page(range(1, 11), "1 - 10 of 500"), page(range(11, 21), "11 - 20 of 500"),
        page(range(21, 31), "21 - 30 of 500")])
    out = discovery.run_discovery(["all"], max_results=60, max_inr=1.2, run_id="r1", stored_tids=set(),
                                  discovery_dir=tmp_path / "discovery")
    assert route.call_count == 2                       # 1.0 spent; a third page (1.5) is refused
    assert out["stopped"] == "run_cap"
    assert total_spend(tmp_path) <= 1.2
    run = lines(tmp_path / "discovery" / "runs.jsonl")[0]
    assert run["stopped"] == "run_cap" and run["unique_new"] == 20
    assert len(run["queries"]) == 1                    # remaining queries not started


@respx.mock
def test_run_discovery_reports_cap_headroom(tmp_path, monkeypatch):
    two_query_catalogue(monkeypatch)
    monkeypatch.setenv("IK_CAP_INR", "10")
    respx.post(SEARCH_URL).mock(return_value=page([1], "1 - 1 of 1"))
    out = discovery.run_discovery(["fam_c"], max_results=10, max_inr=5, run_id="r1", stored_tids=set(),
                                  discovery_dir=tmp_path / "discovery")
    assert out["headroom_inr"] == pytest.approx(9.5)


@respx.mock
def test_run_discovery_fetch_only_health_likely_or_unsure_within_cap(tmp_path, monkeypatch):
    two_query_catalogue(monkeypatch)
    s = Store(tmp_path / "bima_sarthi.duckdb")
    s.init()
    respx.post(SEARCH_URL).mock(side_effect=[
        httpx.Response(200, json={"docs": [
            hit(1),                                                           # likely_health
            hit(2, title="A v. B", headline="insurance deficiency"),          # unsure/health
            hit(3, title="Seth v. LIC", headline="death claim nominee life insurance"),  # other line
            hit(4, title="State v. Commissioner of Treasuries", headline="mediclaim"),   # exclude
        ], "found": "1 - 4 of 4"}),
        page([], "0")])
    fetch_route = respx.post(url__regex=r"https://api\.indiankanoon\.org/doc/\d+/").mock(
        return_value=httpx.Response(200, json={"doc": "<p>Star Health. Complaint allowed.</p>",
                                               "title": "t", "docsource": "NCDRC", "publishdate": "2023-05-17"}))
    discovery.run_discovery(["fam_h"], max_results=10, max_inr=50, run_id="r1", stored_tids=set(),
                            discovery_dir=tmp_path / "discovery", fetch=True, store=s)
    fetched = sorted(c["tid"] for c in CandidateLog(tmp_path / "discovery" / "candidates.jsonl").all() if c["fetched"])
    assert fetched == ["1", "2"] and fetch_route.call_count == 2
    run = lines(tmp_path / "discovery" / "runs.jsonl")[0]
    assert run["fetched"] == 2
    kinds = [r["kind"] for r in ledger(tmp_path)]
    assert kinds.count("doc") == 2
    assert s.con.execute('select count(*) from "case"').fetchone()[0] == 2


@respx.mock
def test_run_discovery_fetch_stops_at_run_cap(tmp_path, monkeypatch):
    two_query_catalogue(monkeypatch)
    s = Store(tmp_path / "bima_sarthi.duckdb")
    s.init()
    respx.post(SEARCH_URL).mock(side_effect=[page([1, 2, 3, 4, 5], "1 - 5 of 5")] * 2)
    fetch_route = respx.post(url__regex=r"https://api\.indiankanoon\.org/doc/\d+/").mock(
        return_value=httpx.Response(200, json={"doc": "<p>Star Health. allowed.</p>", "title": "t",
                                               "docsource": "NCDRC", "publishdate": "2023-05-17"}))
    out = discovery.run_discovery(["fam_h"], max_results=10, max_inr=0.9, run_id="r1", stored_tids=set(),
                                  discovery_dir=tmp_path / "discovery", fetch=True, store=s)
    # 2 searches (queries qh1, qh2 -> 1.0)? cap 0.9 -> only 1 search (0.5) then 2 docs (0.4)
    assert fetch_route.call_count == 2 and out["stopped"] == "run_cap"
    assert total_spend(tmp_path) <= 0.9 + 1e-9


@respx.mock
def test_run_discovery_default_does_not_fetch(tmp_path, monkeypatch):
    two_query_catalogue(monkeypatch)
    respx.post(SEARCH_URL).mock(return_value=page([1], "1 - 1 of 1"))
    discovery.run_discovery(["fam_h"], max_results=10, max_inr=50, run_id="r1", stored_tids=set(),
                            discovery_dir=tmp_path / "discovery")
    assert all(r["kind"] == "search" for r in ledger(tmp_path))


# ---- planning / dry run / CLI -----------------------------------------------------------------

def test_plan_estimates_cost_upper_bound(monkeypatch):
    two_query_catalogue(monkeypatch)
    plan = discovery.plan(["all"], max_results=25, search_price=0.5, doc_price=0.2)
    assert plan["n_queries"] == 3 and plan["pages_per_query_max"] == 3
    assert plan["est_search_inr_max"] == pytest.approx(4.5)
    assert [q["family"] for q in plan["queries"]] == ["fam_h", "fam_h", "fam_c"]


def test_plan_rejects_unknown_family(monkeypatch):
    two_query_catalogue(monkeypatch)
    with pytest.raises(ValueError, match="unknown famil"):
        discovery.plan(["nope"], max_results=10, search_price=0.5, doc_price=0.2)


@respx.mock
def test_cli_dry_run_makes_no_http_calls_and_writes_nothing(tmp_path, capsys, monkeypatch):
    monkeypatch.delenv("IKANOON_TOKEN")
    monkeypatch.delenv("IK_COST_SEARCH_INR")
    monkeypatch.delenv("IK_COST_DOC_INR")
    route = respx.post(SEARCH_URL).mock(return_value=page([1], "1 - 1 of 1"))
    assert cli.main(["cases", "discover", "--families", "crop,health_tpa", "--dry-run",
                     "--max-results-per-query", "20"]) == 0
    out = capsys.readouterr().out
    assert route.call_count == 0 and ledger(tmp_path) == []
    assert "DRY RUN" in out and "estimated" in out.lower() and "crop" in out
    assert not (tmp_path / "discovery").exists()
    assert not (tmp_path / "bima_sarthi.duckdb").exists()


@respx.mock
def test_cli_discover_runs_and_reports(tmp_path, capsys, monkeypatch):
    monkeypatch.setenv("IK_CAP_INR", "100")
    monkeypatch.setattr(discovery, "DISCOVERY_QUERIES", {"fam_c": ["qc1"]})
    monkeypatch.setattr(discovery, "FAMILY_LINE", {"fam_c": "crop"})
    respx.post(SEARCH_URL).mock(return_value=page([1, 2], "1 - 2 of 2", title="F v. Oriental",
                                                  headline="crop insurance"))
    assert cli.main(["cases", "discover", "--families", "fam_c", "--max-results-per-query", "10",
                     "--max-inr", "5", "--run-id", "rid"]) == 0
    out = capsys.readouterr().out
    assert "rid" in out and "IK_CAP_INR headroom" in out and "crop" in out
    assert (tmp_path / "discovery" / "runs.jsonl").exists()
    assert not (tmp_path / "bima_sarthi.duckdb").exists()    # no fetch -> DB untouched


def test_cli_discover_unknown_family_errors(capsys):
    assert cli.main(["cases", "discover", "--families", "bogus", "--dry-run"]) == 2
    assert "unknown famil" in capsys.readouterr().err


@respx.mock
def test_families_none_skips_search_and_fetches_from_the_existing_log(tmp_path, monkeypatch):
    two_query_catalogue(monkeypatch)
    d = tmp_path / "discovery"
    CandidateLog(d / "candidates.jsonl").add({"tid": "42", "prescreen": "likely_health",
                                              "product_line_guess": "health"})
    s = Store(tmp_path / "bima_sarthi.duckdb")
    s.init()
    search = respx.post(SEARCH_URL).mock(return_value=page([1], "1 - 1 of 1"))
    respx.post(url__regex=r"https://api\.indiankanoon\.org/doc/\d+/").mock(
        return_value=httpx.Response(200, json={"doc": "<p>Star Health allowed.</p>", "title": "t",
                                               "docsource": "NCDRC", "publishdate": "2023-05-17"}))
    out = discovery.run_discovery(["none"], max_results=10, max_inr=5, run_id="r9", stored_tids=set(),
                                  discovery_dir=d, fetch=True, store=s)
    assert search.call_count == 0 and out["run"]["fetched"] == 1 and out["run"]["pages_billed"] == 0
    assert CandidateLog(d / "candidates.jsonl").get("42")["fetched"] is True
