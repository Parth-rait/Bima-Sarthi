import json

import httpx
import pytest
import respx

from sarthi.core.inputs import REJECTION_GROUNDS
from sarthi.core.store import Store
from sarthi.data import cases, cli
from sarthi.data.cases import (QUERIES, SpendCapExceeded, fetch_case, match_insurer,
                               detect_outcome, search_cases)

SEARCH_URL = "https://api.indiankanoon.org/search/"


def doc_url(tid):
    return f"https://api.indiankanoon.org/doc/{tid}/"


def judgment(tail, insurer="Star Health and Allied Insurance Co. Ltd."):
    return (f"<html><body><p>Complainant v. {insurer}</p><p>{'facts ' * 600}</p>"
            f"<p>{tail}</p></body></html>")


def doc_payload(tid, html, publishdate="2023-05-17"):
    return {"tid": tid, "title": "X v. Y", "doc": html,
            "docsource": "State Consumer Disputes Redressal Commission",
            "publishdate": publishdate}


@pytest.fixture
def store(tmp_path):
    s = Store(tmp_path / "bima_sarthi.duckdb")
    s.init()
    return s


@pytest.fixture(autouse=True)
def env(monkeypatch, tmp_path):
    monkeypatch.setenv("SARTHI_DATA_DIR", str(tmp_path))
    monkeypatch.setenv("IKANOON_TOKEN", "tok123")
    monkeypatch.setenv("IK_COST_SEARCH_INR", "0.5")
    monkeypatch.setenv("IK_COST_DOC_INR", "2")
    monkeypatch.delenv("IK_CAP_INR", raising=False)


def ledger(tmp_path):
    p = tmp_path / "ik_spend.jsonl"
    return [json.loads(x) for x in p.read_text().splitlines()] if p.exists() else []


def test_queries_cover_grounds():
    assert set(QUERIES) <= set(REJECTION_GROUNDS) - {"other"}
    assert len(QUERIES) == 12
    assert {"pre_existing_disease", "specific_waiting_period", "room_rent"} <= set(QUERIES)


def test_queries_use_ik_operators_not_bare_or():
    import re
    for ground, q in QUERIES.items():
        bare = re.sub(r'"[^"]*"', '""', q)  # drop phrase contents
        assert not re.search(r"\b(OR|AND|NOT)\b", bare), ground
        for m in re.finditer(r"\w*(?:ANDD|ORR|NOTT)\w*", bare):
            assert m.group(0) in ("ANDD", "ORR", "NOTT"), (ground, m.group(0))
            assert bare[m.start() - 1] == " " and bare[m.end()] == " ", (ground, m.group(0))


def test_every_query_carries_filter_constant_and_balanced_quotes():
    assert cases.QUERY_FILTERS == "doctypes: consumer,supremecourt,highcourts fromdate: 1-10-2020"
    for ground, q in QUERIES.items():
        assert q.endswith(" " + cases.QUERY_FILTERS), ground
        assert q.count('"') % 2 == 0, ground
        assert q.count("(") == q.count(")"), ground
        assert q.count("doctypes:") == 1 and q.count("fromdate:") == 1, ground


def test_queries_restricted_to_health_insurance():
    for ground, q in QUERIES.items():
        assert '"health insurance"' in q and "mediclaim" in q, ground


@respx.mock
def test_search_returns_ids(store, tmp_path):
    route = respx.post(SEARCH_URL).mock(return_value=httpx.Response(200, json={
        "docs": [{"tid": 111, "title": "a"}, {"tid": 222, "title": "b"}, {"tid": 333}]}))
    ids = search_cases("q", max_results=2, store=store)
    assert ids == ["111", "222"]
    req = route.calls[0].request
    assert req.headers["Authorization"] == "Token tok123"
    assert b"formInput=q" in req.content
    assert ledger(tmp_path)[0]["kind"] == "search"


@pytest.mark.parametrize("tail,expected", [
    ("In the result the complaint is allowed with costs.", "allowed"),
    ("The complaint is partly allowed.", "partly_allowed"),
    ("The complaint is partially allowed.", "partly_allowed"),
    ("Hence the complaint stands dismissed.", "dismissed"),
    ("Matter adjourned sine die.", None),
])
@respx.mock
def test_fetch_saves_and_parses_outcome(store, tail, expected):
    respx.post(doc_url(7)).mock(return_value=httpx.Response(200, json=doc_payload(7, judgment(tail))))
    c = fetch_case("7", store)
    assert c.outcome == expected
    assert c.case_id == "ik_7"
    assert c.insurer == "Star Health"
    assert str(c.decided_on) == "2023-05-17"
    assert c.forum == "State Consumer Disputes Redressal Commission"
    row = store.con.execute('SELECT outcome, source_sha256 FROM "case" WHERE case_id=?',
                            ["ik_7"]).fetchone()
    assert row[0] == expected
    assert (store.path.parent / "raw" / f"{row[1]}.html").exists()


@respx.mock
def test_outcome_only_from_last_2000_chars(store):
    html = judgment("Complaint is allowed.") .replace("facts", "dismissed", 5)
    respx.post(doc_url(8)).mock(return_value=httpx.Response(200, json=doc_payload(8, html)))
    assert fetch_case("8", store).outcome == "allowed"


@respx.mock
def test_attribution_field_set(store):
    respx.post(doc_url(9)).mock(return_value=httpx.Response(200, json=doc_payload(9, judgment("allowed."))))
    fetch_case("9", store)
    row = store.con.execute("SELECT licence_note, doc_type, source_id FROM source").fetchone()
    assert "powered by IKanoon" in row[0]
    assert row[1] == "judgment" and row[2] == "ik_9"


@respx.mock
def test_spend_cap_stops(store, monkeypatch, tmp_path):
    monkeypatch.setenv("IK_CAP_INR", "2.5")
    route = respx.post(doc_url(1)).mock(return_value=httpx.Response(200, json=doc_payload(1, judgment("allowed."))))
    fetch_case("1", store)  # 2.0 spent
    with pytest.raises(SpendCapExceeded):
        fetch_case("1", store)  # 2.0 + 2.0 > 2.5
    assert route.call_count == 1
    assert len(ledger(tmp_path)) == 1


@respx.mock
def test_refuses_without_prices(store, monkeypatch):
    monkeypatch.delenv("IK_COST_DOC_INR")
    route = respx.post(doc_url(1)).mock(return_value=httpx.Response(200, json={}))
    with pytest.raises(cases.IKConfigError, match="IK_COST_DOC_INR"):
        fetch_case("1", store)
    monkeypatch.delenv("IK_COST_SEARCH_INR")
    with pytest.raises(cases.IKConfigError, match="IK_COST_SEARCH_INR"):
        search_cases("q", max_results=1, store=store)
    assert route.call_count == 0


def test_refuses_without_token(store, monkeypatch):
    monkeypatch.delenv("IKANOON_TOKEN")
    with pytest.raises(cases.IKConfigError, match="IKANOON_TOKEN"):
        search_cases("q", max_results=1, store=store)


def test_match_insurer_aliases():
    assert match_insurer("claim vs Religare Health Insurance") == "Care Health"
    assert match_insurer("The New India Assurance Co.") == "New India Assurance"
    assert match_insurer("no insurer here") is None
    assert detect_outcome("x" * 5000 + " partly allowed") == "partly_allowed"


def test_cases_add_local(tmp_path, monkeypatch, capsys):
    f = tmp_path / "order.html"
    f.write_text(judgment("The complaint is partly allowed.", "HDFC ERGO General Insurance"))
    assert cli.main(["cases", "add-local", str(f), "--case-id", "ej_1", "--forum", "NCDRC",
                     "--decided-on", "2024-01-09"]) == 0
    s = Store(tmp_path / "bima_sarthi.duckdb")
    row = s.con.execute('SELECT forum, decided_on, insurer, outcome, source_sha256 FROM "case"').fetchone()
    assert row[0] == "NCDRC" and str(row[1]) == "2024-01-09"
    assert row[2] == "HDFC ERGO" and row[3] == "partly_allowed"
    src = s.con.execute("SELECT doc_type, source_id FROM source WHERE sha256=?", [row[4]]).fetchone()
    assert src == ("judgment", "local_ej_1")


@respx.mock
def test_cli_search_and_fetch(tmp_path, capsys):
    respx.post(SEARCH_URL).mock(return_value=httpx.Response(200, json={"docs": [{"tid": 5}]}))
    respx.post(doc_url(5)).mock(return_value=httpx.Response(200, json=doc_payload(5, judgment("dismissed."))))
    assert cli.main(["cases", "search", "--ground", "room_rent", "--max", "3"]) == 0
    assert "5" in capsys.readouterr().out
    assert cli.main(["cases", "fetch", "5"]) == 0
    assert "ik_5" in capsys.readouterr().out


@pytest.mark.parametrize("text,expected", [
    ("the complaint is not allowed", "dismissed"),
    ("the complaint is disallowed", "dismissed"),
    ("the claim was disallowed by insurer. " + "x" * 600 + " complaint is dismissed", "dismissed"),
    ("the complaint stands allowed in part", "partly_allowed"),
    ("complaint allowed partly with costs", "partly_allowed"),
    ("the complaint is not maintainable", "dismissed"),
    ("appeal dismissed. " + "x" * 600 + " complaint allowed", "allowed"),
    ("appeal dismissed. " + "x" * 100 + " complaint allowed", None),
    ("complaint allowed. " + "x" * 100 + " appeal dismissed", None),
    ("nothing operative here", None),
])
def test_detect_outcome_negation_and_nearest_end(text, expected):
    assert detect_outcome(text) == expected


@respx.mock
def test_503_then_200_ledgers_two_charges(store, tmp_path):
    respx.post(doc_url(3)).mock(side_effect=[
        httpx.Response(503), httpx.Response(200, json=doc_payload(3, judgment("allowed.")))])
    fetch_case("3", store, sleep=lambda s: None)
    assert len(ledger(tmp_path)) == 2


@respx.mock
def test_persistent_503_ledgers_three_and_raises(store, tmp_path):
    from sarthi.data.fetch import FetchError
    respx.post(doc_url(3)).mock(return_value=httpx.Response(503))
    with pytest.raises(FetchError):
        fetch_case("3", store, sleep=lambda s: None)
    assert len(ledger(tmp_path)) == 3


@respx.mock
def test_cap_stops_before_second_attempt(store, tmp_path, monkeypatch):
    monkeypatch.setenv("IK_CAP_INR", "3")
    route = respx.post(doc_url(3)).mock(return_value=httpx.Response(503))
    with pytest.raises(SpendCapExceeded):
        fetch_case("3", store, sleep=lambda s: None)
    assert route.call_count == 1
    assert len(ledger(tmp_path)) == 1


@respx.mock
def test_4xx_is_still_charged(store, tmp_path):
    from sarthi.data.fetch import FetchError
    respx.post(doc_url(3)).mock(return_value=httpx.Response(403))
    with pytest.raises(FetchError):
        fetch_case("3", store, sleep=lambda s: None)
    assert len(ledger(tmp_path)) == 1


def _pdf(path, text):
    import pymupdf
    doc = pymupdf.open()
    page = doc.new_page()
    page.insert_text((72, 72), text)
    doc.save(path)
    doc.close()


def test_add_local_pdf_uses_parsed_text(tmp_path):
    f = tmp_path / "order.pdf"
    _pdf(f, "Complainant versus HDFC ERGO General Insurance. The complaint is partly allowed.")
    assert cli.main(["cases", "add-local", str(f), "--case-id", "ej_pdf"]) == 0
    s = Store(tmp_path / "bima_sarthi.duckdb")
    assert s.con.execute('SELECT insurer, outcome FROM "case"').fetchone() == ("HDFC ERGO", "partly_allowed")


def test_add_local_outcome_flag_overrides_detection(tmp_path):
    f = tmp_path / "order.html"
    f.write_text(judgment("The complaint is partly allowed."))
    assert cli.main(["cases", "add-local", str(f), "--case-id", "ej_2", "--outcome", "dismissed"]) == 0
    s = Store(tmp_path / "bima_sarthi.duckdb")
    assert s.con.execute('SELECT outcome FROM "case"').fetchone() == ("dismissed",)


def test_cases_set_outcome(tmp_path, capsys):
    f = tmp_path / "order.html"
    f.write_text(judgment("Nothing decisive here."))
    cli.main(["cases", "add-local", str(f), "--case-id", "ej_3"])
    assert cli.main(["cases", "set-outcome", "ej_3", "allowed"]) == 0
    s = Store(tmp_path / "bima_sarthi.duckdb")
    assert s.con.execute('SELECT outcome FROM "case"').fetchone() == ("allowed",)
    with pytest.raises(SystemExit):
        cli.main(["cases", "set-outcome", "ej_3", "won"])
    assert cli.main(["cases", "set-outcome", "nope", "allowed"]) != 0


def test_cases_review_cli(tmp_path, capsys):
    s = Store(tmp_path / "bima_sarthi.duckdb")
    s.init()
    s.con.execute('INSERT INTO "case" (case_id, outcome) VALUES (?, ?)', ["c9", "allowed"])
    s.upsert("case_fact", [dict(case_id="c9", field=f, value='"x"', quote="q", page_no=1, confidence=1.0,
                                status=st, reviewer_note=None)
                           for f, st in (("cited_clause", "extracted"), ("rejection_ground", "needs_review"))],
             key=["case_id", "field"])
    assert cli.main(["cases", "review", "c9"]) == 0
    shown = json.loads(capsys.readouterr().out)
    assert {f["field"] for f in shown["fields"]} == {"cited_clause", "rejection_ground"}
    d = tmp_path / "decisions.json"
    d.write_text(json.dumps({"rejection_ground": {"action": "correct", "value": "exclusion"}}))
    assert cli.main(["cases", "review", "c9", "--json", str(d)]) == 0
    s2 = Store(tmp_path / "bima_sarthi.duckdb")
    st = dict(s2.con.execute("SELECT field, status FROM case_fact").fetchall())
    assert st == {"cited_clause": "reviewed", "rejection_ground": "corrected"}
    assert cli.main(["cases", "review", "missing"]) != 0


def test_cases_exclude_sets_reason_and_validates(tmp_path, capsys):
    s = Store(tmp_path / "bima_sarthi.duckdb")
    s.init()
    s.con.execute('INSERT INTO "case" (case_id, outcome) VALUES (?, ?)', ["cx", "allowed"])
    assert cli.main(["cases", "exclude", "cx", "--reason", "motor insurance"]) == 0
    s2 = Store(tmp_path / "bima_sarthi.duckdb")
    assert s2.con.execute('SELECT excluded_reason FROM "case" WHERE case_id=?',
                          ["cx"]).fetchone() == ("motor insurance",)
    assert cli.main(["cases", "exclude", "nope", "--reason", "x"]) != 0
    assert cli.main(["cases", "exclude", "cx", "--reason", "   "]) != 0
    with pytest.raises(SystemExit):
        cli.main(["cases", "exclude", "cx"])  # --reason is required


# ---------- EXPANSION_QUERIES (R105) ----------

def test_expansion_queries_one_per_family_and_existing_queries_untouched():
    assert set(cases.EXPANSION_QUERIES) == {"moratorium", "ped_waiting", "cashless", "discharge", "committee"}
    assert len(QUERIES) == 12 and cases.QUERIES is QUERIES


def test_expansion_queries_use_valid_ik_syntax():
    import re
    for fam, q in cases.EXPANSION_QUERIES.items():
        bare = re.sub(r'"[^"]*"', '""', q)
        assert not re.search(r"\b(OR|AND|NOT)\b", bare), fam
        for m in re.finditer(r"\w*(?:ANDD|ORR|NOTT)\w*", bare):
            assert m.group(0) in ("ANDD", "ORR", "NOTT"), (fam, m.group(0))
            assert bare[m.start() - 1] == " " and bare[m.end()] == " ", (fam, m.group(0))
        assert q.count('"') % 2 == 0 and q.count("(") == q.count(")"), fam
        assert q.count("doctypes:") == 1 and q.count("fromdate:") == 1, fam


def test_expansion_queries_filter_decisions_from_2023_and_exclude_life():
    assert cases.EXPANSION_FILTERS == "doctypes: consumer,supremecourt,highcourts fromdate: 1-1-2023"
    for fam, q in cases.EXPANSION_QUERIES.items():
        assert q.endswith(" " + cases.EXPANSION_FILTERS), fam
        assert q.startswith('("health insurance" ORR mediclaim) '), fam
        assert ' NOTT "life insurance" ' in q, fam


def test_expansion_queries_family_terms():
    q = cases.EXPANSION_QUERIES
    assert '"non-disclosure" (moratorium ORR "eight years" ORR "60 months" ORR "sixty months")' in q["moratorium"]
    assert '"pre-existing" "waiting period" (36 ORR 48 ORR "thirty-six" ORR "forty-eight")' in q["ped_waiting"]
    assert 'cashless ("one hour" ORR "within an hour" ORR authorisation) delay' in q["cashless"]
    assert 'discharge ("three hours" ORR "final authorisation")' in q["discharge"]
    assert '"claims review committee" ORR "claim review committee"' in q["committee"]


def test_expansion_queries_never_use_explicit_andd():
    # Live probe (2026-11-01): an explicit ANDD makes Indian Kanoon drop the whole boolean clause and
    # return every 2023+ decision (10M hits). Conjunction must be the implicit space.
    for fam, q in cases.EXPANSION_QUERIES.items():
        assert "ANDD" not in q, fam
