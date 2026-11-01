import json
from datetime import date

import pytest
import respx

from sarthi.core.store import Store
from sarthi.data import cli
from sarthi.data.freshness import check_freshness

TAVILY = "https://api.tavily.com/search"
QUOTE = "Unit linked insurance products shall levy charges as disclosed in the policy."
SINCE = date(2026, 10, 24)


@pytest.fixture
def store(tmp_path):
    s = Store(tmp_path / "bima_sarthi.duckdb")
    s.init()
    return s


@pytest.fixture
def key(monkeypatch):
    monkeypatch.setenv("TAVILY_API_KEY", "tvly-test")


def seed_approved_card(store, rule_id="R1", title="Ulip charges"):
    """One approved card whose quote is verbatim on its stored source page."""
    store.upsert("document_page", [{
        "sha256": "abc", "page_no": 1, "text": QUOTE, "char_count": len(QUOTE),
        "has_text_layer": True, "image_path": None}], key=["sha256", "page_no"])
    store.upsert("rule_card", [{
        "rule_id": rule_id, "version": 1, "group": None, "title_en": title, "title_hi": None,
        "source_sha256": "abc", "page_no": 1, "quote": QUOTE, "in_force_from": None,
        "in_force_to": None, "applies_by": None, "triggers": "[]", "inputs": "[]", "params": "{}",
        "condition": None, "if_true": None, "if_false": None, "question_en": None,
        "question_hi": None, "action_en": None, "action_hi": None, "status": "approved",
        "approved_by": "tester", "approved_at": None, "status_note": None}],
        key=["rule_id", "version"])


def tavily_result(title, url, published_date):
    return {"title": title, "url": url, "published_date": published_date}


def nalerts(store):
    return store.con.execute("SELECT count(*) FROM freshness_alert").fetchone()[0]


@respx.mock
def test_new_dated_circular_creates_one_alert(store, key):
    seed_approved_card(store)
    route = respx.post(TAVILY).respond(200, json={"results": [tavily_result(
        "Master Circular on Unit Linked Insurance Products", "https://irdai.gov.in/circ-1",
        "2026-10-28")]})
    alerts = check_freshness(store, SINCE)
    assert len(alerts) == 1
    a = alerts[0]
    assert (a.rule_id, a.found_url, a.found_on, a.status) == (
        "R1", "https://irdai.gov.in/circ-1", date(2026, 10, 28), "open")
    assert nalerts(store) == 1
    sent = json.loads(route.calls[0].request.content)
    assert sent["query"] == "IRDAI circular Ulip charges"
    assert sent["include_domains"] == ["irdai.gov.in"]
    assert route.calls[0].request.headers["authorization"] == "Bearer tvly-test"


@respx.mock
def test_older_result_creates_no_alert(store, key):
    seed_approved_card(store)
    respx.post(TAVILY).respond(200, json={"results": [tavily_result(
        "Circular on Unit Linked Insurance Products", "https://irdai.gov.in/old",
        "2026-01-05")]})
    assert check_freshness(store, SINCE) == []
    assert nalerts(store) == 0


@respx.mock
def test_rerun_does_not_duplicate_and_keeps_human_status(store, key):
    seed_approved_card(store)
    respx.post(TAVILY).respond(200, json={"results": [tavily_result(
        "Regulation on Unit Linked Insurance Products", "https://irdai.gov.in/reg-1",
        "2026-10-29")]})
    assert len(check_freshness(store, SINCE)) == 1
    store.con.execute("UPDATE freshness_alert SET status='dismissed'")
    assert check_freshness(store, SINCE) == []
    assert nalerts(store) == 1
    assert store.con.execute("SELECT status FROM freshness_alert").fetchone()[0] == "dismissed"


@respx.mock
def test_run_never_changes_rule_card_rows(store, key):
    seed_approved_card(store)
    before = store.con.execute("SELECT * FROM rule_card ORDER BY rule_id, version").fetchall()
    respx.post(TAVILY).respond(200, json={"results": [tavily_result(
        "Circular on Unit Linked Insurance Products", "https://irdai.gov.in/circ-2",
        "2026-10-30")]})
    assert len(check_freshness(store, SINCE)) == 1
    after = store.con.execute("SELECT * FROM rule_card ORDER BY rule_id, version").fetchall()
    assert after == before


def test_cli_without_tavily_key_is_clear_error(tmp_path, monkeypatch, capsys):
    monkeypatch.delenv("TAVILY_API_KEY", raising=False)
    monkeypatch.setenv("SARTHI_DATA_DIR", str(tmp_path / "d"))
    assert cli.main(["freshness", "check", "--since", "2026-10-24"]) == 2
    assert "TAVILY_API_KEY" in capsys.readouterr().err
