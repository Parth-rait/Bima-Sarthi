import json
from datetime import date

import pymupdf
import pytest
from fastapi.testclient import TestClient

from sarthi.app import main
from sarthi.app.explain import Explanation
from sarthi.core.models import FactValue, RuleCard

NOTICE = "This is a rules check, not legal or medical advice."
INDEP = "Bima Sarthi is an independent project, not affiliated with IRDAI, LIC or any insurer."
QUOTE = "No claim shall be contestable after sixty continuous months."
def _gp(v, unit, quote="q", page=1):
    return {"value": v, "unit": unit, "source_id": "s", "page_no": page, "quote": quote}


PARAMS = {"insurer_reply_days": _gp(14, "days"), "ombudsman_wait_months": _gp(1, "months"),
          "ombudsman_limit_months": _gp(12, "months"),
          "ombudsman_claim_limit_inr": _gp(5000000, "inr"),
          "ombudsman_award_cap_inr": _gp(3000000, "inr")}
FLAT = {"insurer_reply_days": 15, "ombudsman_wait_days": 30,
        "ombudsman_limit_months": 12, "ombudsman_cap_inr": 5000000}


def make_pdf(n=1, text="Policy schedule text"):
    doc = pymupdf.open()
    for _ in range(n):
        doc.new_page().insert_text((72, 72), text)
    return doc.tobytes()


def moratorium():
    return RuleCard(
        rule_id="MORATORIUM_60M", version=1, group="rejection", quote=QUOTE,
        source_sha256="a" * 64, page_no=7, in_force_from=date(2024, 4, 1),
        applies_by="policy_start_or_renewal", triggers=["non_disclosure"],
        inputs=["continuous_cover_months", "fraud_alleged"], params={"moratorium_months": 60},
        condition="continuous_cover_months >= 60 and not fraud_alleged",
        if_true="CHALLENGEABLE", if_false="CONSISTENT", question_en="q", action_en="act",
        status="approved")


def grievance():
    return RuleCard(
        rule_id="GRIEVANCE_ROUTE", version=1, quote="Complaint to Ombudsman within one year.",
        source_sha256="b" * 64, page_no=2, in_force_from=date(2024, 4, 1),
        applies_by="claim_date", triggers=["other"], params=PARAMS, status="approved")


def fv(value, status="verified"):
    return FactValue(value=value, quote=f"quote {value}", page_no=1, confidence="high", status=status)


def extracted():
    return {"rejection_ground": fv("non_disclosure"), "fraud_alleged": fv(False),
            "inception_date": fv(date(2019, 1, 10)),
            "policy_renewal_date": fv(date(2024, 6, 1)),
            "claim_date": fv(date(2025, 2, 1), "needs_confirmation")}


@pytest.fixture
def client(tmp_path, monkeypatch):
    monkeypatch.setenv("SARTHI_SESSION_ROOT", str(tmp_path / "sessions"))
    monkeypatch.setenv("SARTHI_GALLERY_DIR", str(tmp_path / "gallery"))
    for v in ("WRITER_MODEL", "READER_MODEL", "SARTHI_DATA_DIR"):
        monkeypatch.delenv(v, raising=False)
    monkeypatch.setattr(main, "load_cards", lambda: [moratorium(), grievance()])
    monkeypatch.setattr(main, "extract_user_facts", lambda s: extracted())
    monkeypatch.setattr(main, "explain",
                        lambda findings, lang, helper: Explanation(f"stub {lang} {helper}", False))
    with TestClient(main.app) as c:
        yield c


def new_session(c):
    r = c.post("/session")
    assert r.status_code == 200
    return r.json()["session_id"]


def upload_extract(c, sid):
    pdf = make_pdf(1, "rejection letter")
    r = c.post(f"/session/{sid}/extract", files={"files": ("a.pdf", pdf, "application/pdf")})
    assert r.status_code == 200, r.text
    return r.json()


def confirm_all(c, sid):
    r = c.put(f"/session/{sid}/facts", json={"facts": {
        "claim_date": {"confirm": True},
        "policyholder_name": {"value": "Asha Rao"},
        "claim_amount_inr": {"value": "₹1,20,000"}}})
    assert r.status_code == 200, r.text
    return r.json()


def test_full_flow_and_delete_removes_folder(client, tmp_path):
    sid = new_session(client)
    ex = upload_extract(client, sid)
    assert ex["facts"]["claim_date"]["status"] == "needs_confirmation"
    assert ex["facts"]["claim_date"]["quote"] == "quote 2025-02-01"
    assert ex["facts"]["claim_date"]["value"] == "01/02/2025"
    assert "claim_date" in ex["needs_confirmation"]
    facts = confirm_all(client, sid)["facts"]
    assert facts["claim_date"]["status"] == "user_confirmed"
    assert facts["claim_amount_inr"]["value"] == 120000
    r = client.post(f"/session/{sid}/check")
    assert r.status_code == 200, r.text
    body = r.json()
    f = body["findings"][0]
    assert f["verdict"] == "CHALLENGEABLE" and f["rule_quote"] == QUOTE and f["page_no"] == 7
    assert f["facts_used"]["inception_date"]["quote"] == "quote 2019-01-10"
    assert body["deadlines"]["insurer_reply_by"]
    dl = body["deadlines"]
    assert dl["rule_quote"] == "Complaint to Ombudsman within one year."
    assert (dl["page_no"], dl["source_sha256"], dl["rule_id"]) == (2, "b" * 64, "GRIEVANCE_ROUTE")
    r = client.post(f"/session/{sid}/explain?lang=hi&helper=1")
    assert r.status_code == 200
    assert r.json()["text"] == "stub hi True" and r.json()["findings"][0]["verdict"] == "CHALLENGEABLE"
    assert r.json()["deadlines"]["rule_quote"] == "Complaint to Ombudsman within one year."
    r = client.get(f"/session/{sid}/letter.pdf?lang=en")
    assert r.status_code == 200 and r.content.startswith(b"%PDF")
    assert client.delete(f"/session/{sid}").status_code == 200
    assert not (tmp_path / "sessions" / sid).exists()
    assert client.post(f"/session/{sid}/check").status_code == 404


def test_check_before_confirmation_is_409(client):
    sid = new_session(client)
    upload_extract(client, sid)
    r = client.post(f"/session/{sid}/check")
    assert r.status_code == 409
    assert "claim_date" in r.json()["detail"]["needs_confirmation"]


def test_letter_needs_grievance_card(client, monkeypatch):
    sid = new_session(client)
    upload_extract(client, sid)
    confirm_all(client, sid)
    assert client.post(f"/session/{sid}/check").status_code == 200
    monkeypatch.setattr(main, "load_cards", lambda: [moratorium()])
    r = client.get(f"/session/{sid}/letter.pdf")
    assert r.status_code == 409
    assert "Deadlines need the grievance-route rule card to be approved" in r.text


def test_letter_without_challengeable_is_409(client, monkeypatch):
    sid = new_session(client)
    upload_extract(client, sid)
    client.put(f"/session/{sid}/facts", json={"facts": {"claim_date": {"confirm": True},
               "fraud_alleged": {"value": True}}})
    assert client.post(f"/session/{sid}/check").status_code == 200
    assert client.get(f"/session/{sid}/letter.pdf").status_code == 409


def test_bad_date_is_422(client):
    sid = new_session(client)
    upload_extract(client, sid)
    r = client.put(f"/session/{sid}/facts", json={"facts": {"claim_date": {"value": "31/02/2025"}}})
    assert r.status_code == 422
    assert "claim_date" in json.dumps(r.json())


def test_unknown_fact_key_and_bad_amount_are_422(client):
    sid = new_session(client)
    upload_extract(client, sid)
    assert client.put(f"/session/{sid}/facts", json={"facts": {"nope": {"value": "x"}}}).status_code == 422
    assert client.put(f"/session/{sid}/facts",
                      json={"facts": {"claim_amount_inr": {"value": "lots"}}}).status_code == 422


def test_unknown_session_is_404(client):
    for method, path in [("post", "/session/nope/extract"), ("put", "/session/nope/facts"),
                         ("post", "/session/nope/check"), ("post", "/session/nope/explain"),
                         ("get", "/session/nope/letter.pdf"), ("delete", "/session/nope")]:
        kw = {"json": {"facts": {}}} if method == "put" else {}
        if path.endswith("extract"):
            kw = {"files": {"files": ("a.pdf", make_pdf(), "application/pdf")}}
        assert getattr(client, method)(path, **kw).status_code == 404, path


def test_expired_session_is_404(client, tmp_path):
    import os
    sid = new_session(client)
    d = tmp_path / "sessions" / sid
    os.utime(d, (1, 1))
    assert client.post(f"/session/{sid}/check").status_code == 404
    assert not d.exists()


def test_upload_too_large_is_413(client, monkeypatch):
    from sarthi.app import session
    monkeypatch.setattr(session, "MAX_BYTES", 10)
    sid = new_session(client)
    r = client.post(f"/session/{sid}/extract", files={"files": ("a.pdf", make_pdf(), "application/pdf")})
    assert r.status_code == 413


def test_health(client):
    assert client.get("/health").json() == {"status": "ok"}


def test_every_html_response_has_notices(client):
    for path in ["/", "/nope"]:
        r = client.get(path, headers={"accept": "text/html"})
        assert "text/html" in r.headers["content-type"], path
        assert NOTICE in r.text and INDEP in r.text, path
    assert client.get("/nope", headers={"accept": "application/json"}).headers["content-type"].startswith("application/json")


def test_index_is_self_contained_and_toggles(client):
    t = client.get("/").text
    assert "https://" not in t.replace("https://www.w3.org", "")
    assert 'name="viewport"' in t and "lang" in t and "gallery" in t.lower()


def test_spark_footer_only_when_spark_used(client, monkeypatch):
    assert "Built with Muse Spark Open" not in client.get("/").text
    monkeypatch.setenv("WRITER_MODEL", "meta-models/muse-spark-open")
    assert "Built with Muse Spark Open" in client.get("/").text


# ---------- fix round 1 ----------

def put_extracted(c, monkeypatch, facts, put):
    monkeypatch.setattr(main, "extract_user_facts", lambda s: facts)
    sid = new_session(c)
    upload_extract(c, sid)
    return sid, c.put(f"/session/{sid}/facts", json={"facts": put})


def raw(value, key=None):
    return FactValue(value=value, quote="q", page_no=1, confidence="low", status="needs_confirmation")


OK = lambda: {"rejection_ground": fv("non_disclosure"), "inception_date": fv(date(2019, 1, 10)),
              "policy_renewal_date": fv(date(2024, 6, 1)), "claim_date": fv(date(2025, 2, 1))}


def test_confirming_unparsed_ground_is_422(client, monkeypatch):
    _, r = put_extracted(client, monkeypatch, {"rejection_ground": raw("illness existed before policy")},
                         {"rejection_ground": {"confirm": True}})
    assert r.status_code == 422 and "rejection_ground" in json.dumps(r.json())


def test_confirming_unparsed_date_is_422(client, monkeypatch):
    _, r = put_extracted(client, monkeypatch, {**OK(), "inception_date": raw("10th Jan nineteen")},
                         {"inception_date": {"confirm": True}})
    assert r.status_code == 422


def test_confirming_string_boolean_is_parsed_not_stored_raw(client, monkeypatch):
    sid, r = put_extracted(client, monkeypatch, {**OK(), "fraud_alleged": raw("no")},
                           {"fraud_alleged": {"confirm": True}})
    assert r.status_code == 200 and r.json()["facts"]["fraud_alleged"]["value"] is False
    assert client.post(f"/session/{sid}/check").status_code == 200


@pytest.mark.parametrize("text,expected", [("yes", True), ("हाँ", True), ("हां", True), ("true", True),
                                           ("no", False), ("नहीं", False), ("False", False)])
def test_boolean_words_parse(client, monkeypatch, text, expected):
    _, r = put_extracted(client, monkeypatch, {**OK(), "fraud_alleged": raw(None)},
                         {"fraud_alleged": {"value": text}})
    assert r.status_code == 200 and r.json()["facts"]["fraud_alleged"]["value"] is expected


@pytest.mark.parametrize("text", ["not sure", "pata nahi", "maybe", ""])
def test_unrecognised_boolean_is_422_never_false(client, monkeypatch, text):
    _, r = put_extracted(client, monkeypatch, {**OK(), "fraud_alleged": raw(None)},
                         {"fraud_alleged": {"value": text}})
    assert r.status_code == 422


def test_session_folder_gone_after_check_but_results_still_work(client, tmp_path):
    sid = new_session(client)
    upload_extract(client, sid)
    confirm_all(client, sid)
    assert (tmp_path / "sessions" / sid).exists()
    assert client.post(f"/session/{sid}/check").status_code == 200
    assert not (tmp_path / "sessions" / sid).exists()
    assert client.post(f"/session/{sid}/explain").status_code == 200
    assert client.get(f"/session/{sid}/letter.pdf").status_code == 200
    assert client.delete(f"/session/{sid}").status_code == 200
    assert client.post(f"/session/{sid}/explain").status_code == 404


def test_background_sweep_drops_expired_entries(client, tmp_path):
    import os
    sid = new_session(client)
    os.utime(tmp_path / "sessions" / sid, (1, 1))
    main.sweep_sessions()
    assert sid not in main._SESSIONS


def test_expired_entry_after_check_is_dropped(client, tmp_path, monkeypatch):
    sid = new_session(client)
    upload_extract(client, sid)
    confirm_all(client, sid)
    client.post(f"/session/{sid}/check")
    main._SESSIONS[sid]["created"] -= 4000
    main.sweep_sessions()
    assert sid not in main._SESSIONS
    assert client.post(f"/session/{sid}/explain").status_code == 404


def test_no_approved_cards_is_503(client, monkeypatch):
    monkeypatch.setattr(main, "load_cards", lambda: [])
    sid = new_session(client)
    upload_extract(client, sid)
    client.put(f"/session/{sid}/facts", json={"facts": {"claim_date": {"confirm": True}}})
    r = client.post(f"/session/{sid}/check")
    assert r.status_code == 503 and "The rules are not available right now" in r.text


def test_cards_exist_but_none_triggered_is_200_empty(client, monkeypatch):
    sid, _ = put_extracted(client, monkeypatch, {"rejection_ground": fv("exclusion")}, {})
    r = client.post(f"/session/{sid}/check")
    assert r.status_code == 200 and r.json()["findings"] == []


def test_oversized_upload_rejected_by_running_cap(client, monkeypatch):
    monkeypatch.setattr(main, "MAX_UPLOAD_BYTES", 100)
    sid = new_session(client)
    r = client.post(f"/session/{sid}/extract", files={"files": ("a.pdf", b"x" * 1000, "application/pdf")})
    assert r.status_code == 413 and "25 MB" in r.text


def test_oversized_content_length_rejected_early(client):
    sid = new_session(client)
    r = client.post(f"/session/{sid}/extract", content=b"x",
                    headers={"content-length": str(60 * 1024 * 1024), "content-type": "multipart/form-data; boundary=b"})
    assert r.status_code == 413


def test_extraction_failure_logs_type_not_message(client, monkeypatch, caplog):
    def boom(s):
        raise RuntimeError("SECRET-FRAGMENT-123")
    monkeypatch.setattr(main, "extract_user_facts", boom)
    sid = new_session(client)
    with caplog.at_level("DEBUG"):
        r = client.post(f"/session/{sid}/extract",
                        files={"files": ("a.pdf", make_pdf(), "application/pdf")})
    assert r.status_code == 502
    assert "SECRET-FRAGMENT-123" not in caplog.text and "RuntimeError" in caplog.text
    assert "Traceback" not in caplog.text


def test_index_page_has_safe_link_and_radio_logic(client):
    t = client.get("/").text
    assert r"^https:\/\/" in t and 'type:"radio"' in t
    assert "REJECTION_GROUNDS" in t and "select" in t


_real_load_cards = main.load_cards


def test_locked_database_is_503_not_500(client, monkeypatch, tmp_path):
    import duckdb

    (tmp_path / "bima_sarthi.duckdb").write_bytes(b"x")
    monkeypatch.setenv("SARTHI_DATA_DIR", str(tmp_path))

    def locked(*a, **k):
        raise duckdb.IOException("Could not set lock on file")

    monkeypatch.setattr(main.duckdb, "connect", locked)
    monkeypatch.setattr(main, "load_cards", _real_load_cards)
    sid = new_session(client)
    upload_extract(client, sid)
    client.put(f"/session/{sid}/facts", json={"facts": {"claim_date": {"confirm": True}}})
    r = client.post(f"/session/{sid}/check")
    assert r.status_code == 503 and "The rules are not available right now" in r.text


# ---------- fix C ----------

from sarthi.app.extract import ExtractedFacts  # noqa: E402


def test_extract_merges_under_user_confirmed_facts(client, monkeypatch):
    sid = new_session(client)
    upload_extract(client, sid)
    r = client.put(f"/session/{sid}/facts", json={"facts": {"claim_date": {"value": "05/03/2025"},
                                                          "admission_date": {"value": "01/03/2025"}}})
    assert r.status_code == 200
    again = extracted()
    again["claim_date"] = fv(date(2020, 1, 1))          # would overwrite the user's answer
    again["inception_date"] = fv(date(2018, 5, 5))      # not user-confirmed: replaced
    monkeypatch.setattr(main, "extract_user_facts", lambda s: again)
    body = upload_extract(client, sid)
    assert body["facts"]["claim_date"]["value"] == "05/03/2025"
    assert body["facts"]["claim_date"]["status"] == "user_confirmed"
    assert body["facts"]["admission_date"]["value"] == "01/03/2025"
    assert body["facts"]["inception_date"]["value"] == "05/05/2018"


@pytest.mark.parametrize("key", ["claim_date", "admission_date", "inception_date", "policy_renewal_date"])
def test_missing_date_fact_can_be_added_and_is_parsed_server_side(client, monkeypatch, key):
    sid, r = put_extracted(client, monkeypatch, {"rejection_ground": fv("non_disclosure")},
                           {key: {"value": "7/3/2024"}})
    assert r.status_code == 200, r.text
    f = r.json()["facts"][key]
    assert f["value"] == "07/03/2024" and f["status"] == "user_confirmed"
    bad = client.put(f"/session/{sid}/facts", json={"facts": {key: {"value": "not a date"}}})
    assert bad.status_code == 422 and key in bad.json()["detail"]["errors"]


def test_ground_can_be_chosen_when_extraction_missed_it(client, monkeypatch):
    sid, r = put_extracted(client, monkeypatch, {"claim_date": fv(date(2025, 2, 1))},
                           {"rejection_ground": {"value": "non_disclosure"}})
    assert r.status_code == 200 and r.json()["facts"]["rejection_ground"]["status"] == "user_confirmed"


def test_reader_backend_is_stored_and_returned_with_extract_and_check(client, monkeypatch):
    def with_backend(s):
        f = ExtractedFacts(extracted())
        f.backend = "stub-backend"
        return f
    monkeypatch.setattr(main, "extract_user_facts", with_backend)
    sid = new_session(client)
    assert upload_extract(client, sid)["reader_backend"] == "stub-backend"
    confirm_all(client, sid)
    body = client.post(f"/session/{sid}/check").json()
    assert body["reader_backend"] == "stub-backend"
    assert client.post(f"/session/{sid}/explain").json()["reader_backend"] == "stub-backend"


def test_results_carry_plain_labels_for_every_fact(client):
    sid = new_session(client)
    ex = upload_extract(client, sid)
    assert ex["facts"]["inception_date"]["label"] == {"en": "policy start date",
                                                      "hi": main.label("inception_date", "hi")}
    confirm_all(client, sid)
    body = client.post(f"/session/{sid}/check").json()
    assert body["labels"]["inception_date"]["en"] == "policy start date"


def test_oversized_image_is_413_with_a_clear_message(client):
    from tests.app.test_session import _png_header_only
    sid = new_session(client)
    r = client.post(f"/session/{sid}/extract", files={"files": ("bomb.png", _png_header_only(30000, 30000), "image/png")})
    assert r.status_code == 413 and "megapixels" in r.text


# ---------- fix C: the page itself (no browser here, so assert on the shipped source) ----------

def page(client):
    return client.get("/").text


def test_ui_never_dead_ends_on_a_missed_rejection_ground(client):
    t = page(client)
    assert "view_facts.rejection_ground" in t          # a ground card is always rendered
    for k in ("claim_date", "admission_date", "inception_date", "policy_renewal_date"):
        assert f'"{k}"' in t
    assert "Add a missing fact" in t


def test_ui_continuity_is_tri_state_with_no_default(client):
    t = page(client)
    assert "notsure" in t and 'id:"cont"' not in t     # the old single checkbox is gone
    assert 'name:"cont"' in t


def test_ui_uses_labels_and_stays_safe(client):
    t = page(client)
    assert "innerHTML" not in t and "insertAdjacentHTML" not in t
    assert "min-height:44px" in t
    assert "labelOf(" in t and "factLabel(k){return k.replaceAll" not in t
    assert "nonpayable_listed" in t                    # per-item answer for deductions


def test_deadlines_json_shows_quote_and_page_of_each_setting_param(client, monkeypatch):
    def p(v, unit, quote, page):
        return {"value": v, "unit": unit, "source_id": "s", "page_no": page, "quote": quote}
    nested = {**PARAMS, "insurer_reply_days": p(14, "days", "reply q", 111),
              "ombudsman_wait_months": p(1, "months", "wait q", 10),
              "ombudsman_limit_months": p(12, "months", "limit q", 10)}
    g = grievance().model_copy(update={"params": nested})
    monkeypatch.setattr(main, "load_cards", lambda: [moratorium(), g])
    sid = new_session(client)
    upload_extract(client, sid)
    confirm_all(client, sid)
    dl = client.post(f"/session/{sid}/check").json()["deadlines"]
    assert dl["sources"]["insurer_reply_by"] == {
        "quote": "reply q", "page_no": 111, "source_id": "s", "value": 14, "unit": "days"}
    assert dl["sources"]["ombudsman_earliest"]["quote"] == "wait q"
    assert dl["sources"]["ombudsman_latest"]["page_no"] == 10
    assert client.get(f"/session/{sid}/letter.pdf?lang=en").status_code == 200


def test_approved_card_with_flat_params_is_never_served(client, monkeypatch):
    g = grievance().model_copy(update={"params": FLAT})
    monkeypatch.setattr(main, "load_cards", lambda: [moratorium(), g])
    sid = new_session(client)
    upload_extract(client, sid)
    confirm_all(client, sid)
    dl = client.post(f"/session/{sid}/check").json()["deadlines"]
    assert dl["available"] is False
    assert client.get(f"/session/{sid}/letter.pdf?lang=en").status_code == 409


def test_card_missing_a_param_is_never_served(client, monkeypatch):
    params = {k: v for k, v in PARAMS.items() if k != "ombudsman_award_cap_inr"}
    g = grievance().model_copy(update={"params": params})
    monkeypatch.setattr(main, "load_cards", lambda: [moratorium(), g])
    sid = new_session(client)
    upload_extract(client, sid)
    confirm_all(client, sid)
    assert client.post(f"/session/{sid}/check").json()["deadlines"]["available"] is False


def _put(c, sid, complaint=None, reply=None, extra=None):
    facts = {"claim_date": {"confirm": True}, "claim_amount_inr": {"value": "120000"}}
    if complaint:
        facts["complaint_sent_date"] = {"value": complaint}
    body = {"facts": {**facts, **(extra or {})}}
    if reply:
        body["insurer_reply_date"] = reply
    return c.put(f"/session/{sid}/facts", json=body)


def _ready(client):
    sid = new_session(client)
    upload_extract(client, sid)
    return sid


def _days(n):
    from datetime import timedelta
    return (date.today() + timedelta(days=n)).strftime("%d/%m/%Y")


def test_first_time_flow_counts_from_today(client):
    sid = _ready(client)
    assert _put(client, sid).status_code == 200
    dl = client.post(f"/session/{sid}/check").json()["deadlines"]
    assert dl["available"] and dl["letter_date"]["display"] == _days(0)
    assert dl["ombudsman_latest"]["iso"] == (
        main.deadlines(date.today(), None, params=PARAMS).ombudsman_latest.isoformat())


def test_past_complaint_and_past_reply_count_from_the_reply(client):
    sid = _ready(client)
    r = _put(client, sid, complaint="01/09/2026", reply="10/09/2026")
    assert r.status_code == 200, r.text
    dl = client.post(f"/session/{sid}/check").json()["deadlines"]
    assert dl["letter_date"]["iso"] == "2026-09-01"
    assert dl["insurer_reply_by"]["iso"] == "2026-09-15"
    assert dl["ombudsman_earliest"]["iso"] == "2026-09-10"
    assert dl["ombudsman_latest"]["iso"] == "2027-09-10"
    assert dl["sources"]["ombudsman_earliest"]["label"] == "your insurer's reply date (entered by you)"


def test_reply_equal_to_complaint_date_is_valid(client):
    sid = _ready(client)
    assert _put(client, sid, complaint="01/09/2026", reply="01/09/2026").status_code == 200


def test_reply_without_complaint_date_leaves_ombudsman_dates_unavailable(client):
    sid = _ready(client)
    assert _put(client, sid, reply="10/09/2026").status_code == 200
    dl = client.post(f"/session/{sid}/check").json()["deadlines"]
    assert dl["available"] is True
    assert dl["ombudsman_earliest"] is None and dl["ombudsman_latest"] is None
    assert dl["insurer_reply_by"] is None
    assert dl["ombudsman_note"] == "Add the date you sent your complaint to see your Ombudsman dates"
    assert client.get(f"/session/{sid}/letter.pdf?lang=en").status_code == 409


def test_future_complaint_date_is_rejected(client):
    sid = _ready(client)
    r = _put(client, sid, complaint=_days(2))
    assert r.status_code == 422
    msg = r.json()["detail"]["errors"]["complaint_sent_date"]
    assert "future" in msg and "भविष्य" in msg


def test_future_reply_date_is_rejected(client):
    sid = _ready(client)
    r = _put(client, sid, complaint="01/09/2026", reply=_days(2))
    assert r.status_code == 422
    msg = r.json()["detail"]["errors"]["insurer_reply_date"]
    assert "future" in msg and "भविष्य" in msg


def test_reply_before_complaint_date_is_rejected(client):
    sid = _ready(client)
    r = _put(client, sid, complaint="10/09/2026", reply="01/09/2026")
    assert r.status_code == 422
    msg = r.json()["detail"]["errors"]["insurer_reply_date"]
    assert "before" in msg and "पहले" in msg


def test_reply_checked_against_complaint_date_stored_earlier(client):
    sid = _ready(client)
    assert _put(client, sid, complaint="10/09/2026").status_code == 200
    r = client.put(f"/session/{sid}/facts", json={"facts": {}, "insurer_reply_date": "01/09/2026"})
    assert r.status_code == 422


def test_session_kept_past_midnight_still_works(client, monkeypatch):
    sid = _ready(client)
    assert _put(client, sid, complaint="01/09/2026", reply="10/09/2026").status_code == 200
    client.post(f"/session/{sid}/check")
    assert client.get(f"/session/{sid}/letter.pdf?lang=en").status_code == 200
