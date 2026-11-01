"""Golden app flows: upload -> confirm -> check -> plan, with hand-written synthetic fixtures.

Models are stubbed (extraction, explanation); rule cards are built in memory with the real
GRIEVANCE_ROUTE parameter shape. No network, no model call.
"""
import json
import re
from datetime import date, timedelta

import pytest
from fastapi.testclient import TestClient

from sarthi.app import main
from sarthi.app.explain import Explanation
from sarthi.app.letter import deadlines
from sarthi.core.models import RuleCard
from tests.app.test_api import (confirm_all, extracted, fv, grievance, moratorium, new_session,
                                upload_extract)

SNAKE = re.compile(r"\b[a-z0-9]+(?:_[a-z0-9]+)+\b")
DMY = re.compile(r"\b\d{2}/\d{2}/\d{4}\b")
VERDICT_WORDS = re.compile(r"CHALLENGEABLE|CONSISTENT|NEED_INFO|verdict", re.I)
DEVANAGARI = re.compile(r"[ऀ-ॿ]")


def gp(value, unit, source_id, page, quote):
    return {"value": value, "unit": unit, "source_id": source_id, "page_no": page, "quote": quote}


# The shape and values of the approved GRIEVANCE_ROUTE card (quotes shortened, same pages).
REAL_PARAMS = {
    "insurer_reply_days": gp(14, "days", "irdai_ppi_master_2024", 111,
                             "Insurers should provide resolution to the complaint within 14 days"),
    "ombudsman_wait_months": gp(1, "months", "ombudsman_rules_2017", 10,
                                "the complainant had not received any reply within a period of one month"),
    "ombudsman_limit_months": gp(12, "months", "ombudsman_rules_2017", 10,
                                 "The complaint is made within one year"),
    "ombudsman_claim_limit_inr": gp(5000000, "inr", "irdai_ppi_master_2024", 135,
                                    "claim amount is up to Rs. 50 lakhs"),
    "ombudsman_award_cap_inr": gp(3000000, "inr", "ombudsman_rules_2017", 12,
                                  "not award compensation exceeding rupees thirty lakhs"),
}
LINES = ["life", "accident", "motor", "crop", "credit_life", "other"]


@pytest.fixture
def client(tmp_path, monkeypatch):
    monkeypatch.setenv("SARTHI_SESSION_ROOT", str(tmp_path / "sessions"))
    monkeypatch.setenv("SARTHI_GALLERY_DIR", str(tmp_path / "gallery"))
    for v in ("WRITER_MODEL", "READER_MODEL", "SARTHI_DATA_DIR", "SARTHI_REPHRASE"):
        monkeypatch.delenv(v, raising=False)
    card = grievance().model_copy(update={"params": REAL_PARAMS})
    monkeypatch.setattr(main, "load_cards", lambda: [moratorium(), card])
    monkeypatch.setattr(main, "extract_user_facts", lambda s: extracted())
    monkeypatch.setattr(main, "explain", lambda f, lang, helper: Explanation("stub", False))
    with TestClient(main.app) as c:
        yield c


def put(client, sid, **facts):
    r = client.put(f"/session/{sid}/facts", json={"facts": {k: {"value": v} for k, v in facts.items()}})
    assert r.status_code == 200, r.text
    return r.json()


def items(plan):
    return [i for s in plan["steps"] for i in s["items"]]


def by_key(plan):
    return {i["key"]: i for i in items(plan) if i["key"]}


# (a) health happy path ----------------------------------------------------------------

def test_health_happy_path_upload_confirm_check_plan(client):
    sid = new_session(client)
    upload_extract(client, sid)                                  # also answers "Type of insurance": health
    confirm_all(client, sid)
    put(client, sid, complaint_sent_date="01/09/2026", claim_amount_inr="60,00,000")
    body = client.post(f"/session/{sid}/check").json()
    assert body["supported"] is True
    plan = body["plan"]
    assert plan["verified"] is True and plan["title"]["en"] == "Your plan"
    assert [s["id"] for s in plan["steps"]] == ["findings", "ask", "letter", "ombudsman", "commission"]
    first = plan["steps"][0]["items"][0]                         # (1) the finding with its card quote
    assert first["rule_id"] == "MORATORIUM_60M" and first["page_no"] == 7 and first["quote"]
    ask = " ".join(i["text"]["en"] for i in plan["steps"][1]["items"])
    assert "act" in ask.split()                                  # (2) the card's action text (stub: "act")
    d = by_key(plan)                                             # (3)-(4) dates and their sources
    assert any(i["link"] == "letter" for i in items(plan))
    assert d["insurer_reply_by"]["date"]["iso"] == "2026-09-15" and d["insurer_reply_by"]["page_no"] == 111
    assert d["ombudsman_earliest"]["date"]["iso"] == "2026-10-01"
    assert d["ombudsman_latest"]["date"]["iso"] == "2027-10-01" and d["ombudsman_latest"]["page_no"] == 10
    assert "consumer commission" in d["commission"]["text"]["en"]           # (5) 60 lakh > 50 lakh limit
    assert client.get(f"/session/{sid}/letter.pdf?lang=hi").status_code == 200
    again = client.post(f"/session/{sid}/explain?lang=hi").json()
    assert again["plan"]["steps"] == plan["steps"]


def test_health_plan_without_a_complaint_date_shows_the_add_the_date_message(client):
    sid = new_session(client)
    upload_extract(client, sid)
    confirm_all(client, sid)
    plan = client.post(f"/session/{sid}/check").json()["plan"]
    assert not any(i["date"] for i in items(plan))
    assert "Add the date you sent your complaint to see your Ombudsman dates" in plan["text"]["en"]
    assert DEVANAGARI.search(plan["text"]["hi"]) and not DMY.findall(plan["text"]["hi"])


# (b) product_line missing -------------------------------------------------------------

def test_product_line_missing_is_409(client):
    sid = new_session(client)
    upload_extract(client, sid, product_line=None)
    confirm_all(client, sid)
    r = client.post(f"/session/{sid}/check")
    assert r.status_code == 409 and r.json()["detail"]["needs_product_line"] is True


# (c) life -----------------------------------------------------------------------------

def test_life_is_supported_false_with_no_findings_no_verdict_and_a_general_plan(client):
    sid = new_session(client)
    upload_extract(client, sid, product_line="life")
    r = client.post(f"/session/{sid}/check")
    assert r.status_code == 200
    body = r.json()
    assert body["supported"] is False and body["findings"] == []
    assert not VERDICT_WORDS.search(json.dumps({k: v for k, v in body.items() if k != "labels"}))
    plan = body["plan"]
    assert plan["title"]["en"].startswith("We don't have a checked rules engine for this type of insurance yet.")
    assert "This does not mean the decision is correct." in plan["title"]["en"]
    quoted = [i for i in items(plan) if i["quote"]]
    assert quoted and all(i["page_no"] for i in quoted)
    assert {(i["source_id"], i["page_no"]) for i in quoted} >= {
        ("irdai_ppi_master_2024", 111), ("ombudsman_rules_2017", 10), ("ombudsman_rules_2017", 12)}
    t = plan["text"]["en"]
    assert "Keep copies of your policy" in t and "Write down the date of every call" in t
    assert "It does not promise any result" in t


# (d) crop -----------------------------------------------------------------------------

@pytest.mark.parametrize("line", ["crop", "credit_life", "other"])
def test_unverified_lines_make_no_route_claim(client, line):
    sid = new_session(client)
    upload_extract(client, sid, product_line=line)
    put(client, sid, complaint_sent_date="01/09/2026")
    client.put(f"/session/{sid}/facts", json={"facts": {}, "insurer_reply_date": "10/09/2026"})
    plan = client.post(f"/session/{sid}/check").json()["plan"]
    t = plan["text"]["en"]
    assert "We have not verified the complaint route for this type of insurance." in t
    assert not [i for i in items(plan) if i["quote"] or i["date"] or i["link"]]
    assert not re.search(r"ombudsman|grievance officer|14|within \d", t, re.I)
    assert "लोकपाल" not in plan["text"]["hi"]
    if line == "crop":
        assert "Government crop schemes can have their own complaint process that this tool has not verified" in t
        assert "local agriculture office" in t and "bank branch" in t


# (e) Hindi ----------------------------------------------------------------------------

@pytest.mark.parametrize("line", ["health"] + LINES)
def test_hindi_plan_has_no_snake_case_and_is_hindi(client, line):
    sid = new_session(client)
    upload_extract(client, sid, product_line=line)
    if line == "health":
        confirm_all(client, sid)
    put(client, sid, complaint_sent_date="01/09/2026")
    plan = client.post(f"/session/{sid}/check").json()["plan"]
    hi = plan["text"]["hi"]
    assert DEVANAGARI.search(hi) and not SNAKE.findall(hi.replace("MORATORIUM_60M", ""))
    for it in items(plan):
        for k in ("text", "date_label", "source_label"):
            if it[k]:
                assert it[k]["hi"] and not SNAKE.findall(it[k]["hi"])
    for s in plan["steps"]:
        assert DEVANAGARI.search(s["title"]["hi"]) and "_" not in s["title"]["hi"]


# (f) dates only from user input or params ---------------------------------------------

@pytest.mark.parametrize("line", ["health", "life", "motor", "accident"] + ["crop", "other", "credit_life"])
@pytest.mark.parametrize("complaint,reply", [(None, None), ("01/09/2026", None), ("01/09/2026", "10/09/2026"),
                                             ("29/01/2026", None)])
def test_plan_dates_are_only_computed_from_user_input_and_params(client, line, complaint, reply):
    sid = new_session(client)
    upload_extract(client, sid, product_line=line)
    if line == "health":
        confirm_all(client, sid)
    if complaint:
        put(client, sid, complaint_sent_date=complaint)
    if reply:
        client.put(f"/session/{sid}/facts", json={"facts": {}, "insurer_reply_date": reply})
    plan = client.post(f"/session/{sid}/check").json()["plan"]
    shown = set(DMY.findall(plan["text"]["en"]) + DMY.findall(plan["text"]["hi"]))
    allowed = set()
    if complaint and line in ("health", "life", "motor", "accident"):
        c = date(*map(int, complaint.split("/")[::-1]))
        r = date(*map(int, reply.split("/")[::-1])) if reply else None
        d = deadlines(c, r, params=REAL_PARAMS)
        allowed = {x.strftime("%d/%m/%Y") for x in (c, d.insurer_reply_by, d.ombudsman_earliest, d.ombudsman_latest)}
        if r and line != "health":
            allowed.add(r.strftime("%d/%m/%Y"))
    # official texts carry dates in their titles (e.g. "as amended till 18.05.2021") but not as dd/mm/yyyy
    assert shown <= allowed, (shown, allowed)
    if complaint is None or line in ("crop", "other", "credit_life"):
        assert not shown                                          # nothing entered, or sources do not apply
    for it in items(plan):
        if it["date"]:
            assert it["date"]["display"] in allowed


def test_no_plan_date_is_today_or_in_the_future_unless_computed_from_a_user_date(client):
    sid = new_session(client)
    upload_extract(client, sid, product_line="life")
    plan = client.post(f"/session/{sid}/check").json()["plan"]
    assert not DMY.findall(plan["text"]["en"]) and date.today().strftime("%d/%m/%Y") not in plan["text"]["en"]
    assert (date.today() + timedelta(days=14)).strftime("%d/%m/%Y") not in plan["text"]["en"]
