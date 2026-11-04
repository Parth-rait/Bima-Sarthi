"""API flows for the policy key-terms explainer. SYNTHETIC document text only; no network, no model."""
import re
from datetime import date

import pymupdf
import pytest
from fastapi.testclient import TestClient

from sarthi.app import main, policy
from sarthi.app.explain import Explanation
from sarthi.core.models import FactValue, RuleCard
from sarthi.llm.client import ChatResult

L_SUM = "Sum Insured: Rs. 5,00,000 per policy year"          # SYNTHETIC
L_COPAY = "Co-payment of 20% applies to every claim"           # SYNTHETIC
L_PED = "Pre-existing diseases are covered after 36 months of continuous coverage"   # SYNTHETIC
PAGE = "\n".join([L_SUM, L_COPAY, L_PED])
RULE_QUOTE = "No claim shall be contestable after sixty continuous months."


def make_pdf(*texts):
    doc = pymupdf.open()
    for t in texts:
        doc.new_page().insert_text((72, 72), t)
    return doc.tobytes()


def png_bytes():
    pix = pymupdf.Pixmap(pymupdf.csRGB, pymupdf.IRect(0, 0, 800, 600), False)
    pix.clear_with(255)
    return pix.tobytes("png")


def term(value, quote, page_no=1):
    return policy.PolicyTermOut(value=value, quote=quote, page_no=page_no, confidence="high")


def res(parsed=None, text=None):
    return ChatResult(text=text, parsed=parsed, tool_calls=[], tokens_in=1, tokens_out=1, cost_usd=0.0,
                      cache_hit=False, needs_review=False, backend="stub")


class Reader:
    def __init__(self, outs, transcripts=()):
        self.outs, self.transcripts, self.calls = list(outs), list(transcripts), []

    def __call__(self, role, messages, **kw):
        self.calls.append((role, kw))
        if kw.get("schema") is not None:
            return res(self.outs.pop(0))
        return res(text=self.transcripts.pop(0))


def moratorium():
    return RuleCard(
        rule_id="MORATORIUM_60M", version=1, group="rejection", quote=RULE_QUOTE, source_sha256="a" * 64,
        page_no=7, in_force_from=date(2024, 4, 1), applies_by="policy_start_or_renewal",
        triggers=["non_disclosure"], inputs=["continuous_cover_months", "fraud_alleged"],
        params={"moratorium_months": 60}, condition="continuous_cover_months >= 60 and not fraud_alleged",
        if_true="CHALLENGEABLE", if_false="CONSISTENT", question_en="q", action_en="act", status="approved")


def fv(value, status="verified"):
    return FactValue(value=value, quote=f"quote {value}", page_no=1, confidence="high", status=status)


def extracted(ground="non_disclosure"):
    return {"rejection_ground": fv(ground), "fraud_alleged": fv(False), "inception_date": fv(date(2019, 1, 10)),
            "policy_renewal_date": fv(date(2024, 6, 1)), "claim_date": fv(date(2025, 2, 1))}


@pytest.fixture
def env(tmp_path, monkeypatch):
    monkeypatch.setenv("SARTHI_SESSION_ROOT", str(tmp_path / "sessions"))
    monkeypatch.setenv("SARTHI_GALLERY_DIR", str(tmp_path / "gallery"))
    monkeypatch.setenv("SARTHI_DATA_DIR", str(tmp_path / "data"))
    for v in ("WRITER_MODEL", "READER_MODEL"):
        monkeypatch.delenv(v, raising=False)
    monkeypatch.setattr(main, "load_cards", lambda: [moratorium()])
    monkeypatch.setattr(main, "extract_user_facts", lambda s: extracted())
    monkeypatch.setattr(main, "explain", lambda f, lang, helper: Explanation(f"stub {lang}", False))
    with TestClient(main.app) as c:
        yield c, tmp_path


def start(c, ground_facts=None):
    sid = c.post("/session").json()["session_id"]
    r = c.post(f"/session/{sid}/extract", files={"files": ("a.pdf", make_pdf("rejection letter"), "application/pdf")})
    assert r.status_code == 200, r.text
    assert c.put(f"/session/{sid}/facts", json={"facts": {"product_line": {"value": "health"}}}).status_code == 200
    return sid


def upload_policy(c, sid, reader, monkeypatch, pdf=None, name="policy.pdf", mime="application/pdf"):
    monkeypatch.setattr(policy, "chat", reader)
    return c.post(f"/session/{sid}/policy/extract",
                  files={"files": (name, pdf if pdf is not None else make_pdf(PAGE), mime)})


def terms_by_key(body):
    return {t["key"]: t for t in body["policy"]["terms"]}


# ---------- (a) all verified ----------

def test_policy_upload_returns_verified_terms_with_quotes_and_pages(env, monkeypatch):
    c, _ = env
    sid = start(c)
    reader = Reader([policy.PolicyTermsOut(sum_insured=term("Rs. 5,00,000", L_SUM), co_payment=term("20%", L_COPAY),
                                           ped_waiting_months=term(36, L_PED))])
    r = upload_policy(c, sid, reader, monkeypatch)
    assert r.status_code == 200, r.text
    body = r.json()
    t = terms_by_key(body)
    assert [t[k]["state"] for k in ("sum_insured", "co_payment", "ped_waiting_months")] == ["found"] * 3
    assert t["sum_insured"]["quote"] == L_SUM and t["sum_insured"]["page_no"] == 1
    assert t["sum_insured"]["display"]["en"] == "₹5,00,000" and t["co_payment"]["display"]["en"] == "20%"
    assert t["room_rent_limit"]["state"] == "absent"
    assert body["policy"]["disclaimer"]["en"].startswith("This shows what the uploaded document says.")
    assert body["pages"] == 1 and body["reader_backend"] == "stub"
    assert c.get(f"/session/{sid}/policy").json()["policy"]["terms"] == body["policy"]["terms"]


# ---------- (b) hallucinated ----------

def test_hallucinated_term_is_unverified_and_never_shown_as_fact(env, monkeypatch):
    c, _ = env
    sid = start(c)
    reader = Reader([policy.PolicyTermsOut(co_payment=term("50%", "Co-payment of 50% applies to every claim"),
                                           sum_insured=term(500000, L_SUM))])
    r = upload_policy(c, sid, reader, monkeypatch)
    t = terms_by_key(r.json())
    assert t["co_payment"]["state"] == "unverified" and t["co_payment"]["display"] is None
    assert t["co_payment"]["message"]["en"] == "We could not find this in your document."
    assert "50%" not in r.text and "Co-payment of 50" not in r.text
    assert t["sum_insured"]["state"] == "found"


# ---------- (c) no policy: app unchanged ----------

def test_without_a_policy_the_app_works_as_before(env):
    c, _ = env
    sid = start(c)
    assert c.get(f"/session/{sid}/policy").json() == {"policy": None}
    r = c.post(f"/session/{sid}/check")
    assert r.status_code == 200, r.text
    body = r.json()
    assert "policy" not in body and body["findings"][0]["verdict"] == "CHALLENGEABLE"
    assert c.post(f"/session/{sid}/explain?lang=en").status_code == 200


def test_policy_routes_404_for_unknown_session(env):
    c, _ = env
    assert c.get("/session/nope/policy").status_code == 404
    assert c.put("/session/nope/policy", json={"terms": {}}).status_code == 404
    assert c.delete("/session/nope/policy").status_code == 404
    assert c.post("/session/nope/policy/extract", files={"files": ("a.pdf", make_pdf("x"), "application/pdf")}).status_code == 404


# ---------- (d) scanned pages ----------

def test_scanned_policy_pages_go_through_transcription(env, monkeypatch):
    c, _ = env
    sid = start(c)
    reader = Reader([policy.PolicyTermsOut(sum_insured=term(500000, L_SUM))], transcripts=[PAGE])
    r = upload_policy(c, sid, reader, monkeypatch, pdf=png_bytes(), name="scan.png", mime="image/png")
    assert r.status_code == 200, r.text
    assert terms_by_key(r.json())["sum_insured"]["state"] == "found"
    assert [kw.get("schema") is not None for _, kw in reader.calls] == [True, False]


# ---------- upload limits and errors ----------

def test_policy_upload_reuses_the_upload_limits(env, monkeypatch):
    c, _ = env
    sid = start(c)
    r = upload_policy(c, sid, Reader([]), monkeypatch, pdf=b"hello", name="policy.txt", mime="text/plain")
    assert r.status_code == 415
    r = upload_policy(c, sid, Reader([]), monkeypatch, pdf=make_pdf(*["p"] * 21))
    assert r.status_code == 413 and "20 pages" in r.json()["detail"]
    r = c.post(f"/session/{sid}/policy/extract", content=b"x",
               headers={"content-length": str(60 * 1024 * 1024), "content-type": "multipart/form-data; boundary=b"})
    assert r.status_code == 413
    monkeypatch.setattr(main, "MAX_UPLOAD_BYTES", 100)
    r = upload_policy(c, sid, Reader([]), monkeypatch, pdf=b"x" * 1000)
    assert r.status_code == 413 and "25 MB" in r.text


def test_reader_failure_is_a_502_and_leaves_no_files(env, monkeypatch):
    c, tmp = env
    sid = start(c)
    def boom(*a, **k):
        raise RuntimeError("secret document text 5,00,000")
    monkeypatch.setattr(policy, "chat", boom)
    r = c.post(f"/session/{sid}/policy/extract", files={"files": ("a.pdf", make_pdf(PAGE), "application/pdf")})
    assert r.status_code == 502 and "secret" not in r.text
    assert [p.name for p in (tmp / "sessions").iterdir()] == [sid]
    assert c.get(f"/session/{sid}/policy").json() == {"policy": None}


# ---------- confirm / edit / clear ----------

def test_confirm_edit_clear_and_errors(env, monkeypatch):
    c, _ = env
    sid = start(c)
    upload_policy(c, sid, Reader([policy.PolicyTermsOut(
        sum_insured=term(500000, L_SUM), co_payment=term("50%", "Co-payment of 50% applies to every claim"))]), monkeypatch)
    put = lambda terms: c.put(f"/session/{sid}/policy", json={"terms": terms})
    r = put({"sum_insured": {"confirm": True}})
    t = terms_by_key(r.json())["sum_insured"]
    assert r.status_code == 200 and t["state"] == "confirmed" and t["quote"] == L_SUM
    r = put({"co_payment": {"value": "10%"}})
    t = terms_by_key(r.json())["co_payment"]
    assert t["state"] == "entered" and t["display"]["en"] == "10%" and t["quote"] is None
    r = put({"room_rent_limit": {"value": "1% of the Sum Insured"}})
    assert terms_by_key(r.json())["room_rent_limit"]["state"] == "entered"
    r = put({"sum_insured": {"value": "1000000"}})
    assert terms_by_key(r.json())["sum_insured"]["quote"] is None            # a changed value loses the old quote
    r = put({"sum_insured": {"value": "500000"}, "claim_intimation_days": {"clear": True}})
    assert terms_by_key(r.json())["claim_intimation_days"]["state"] == "absent"
    r = put({"sum_insured": {"clear": True}})
    assert terms_by_key(r.json())["sum_insured"]["state"] == "absent"
    for bad in ({"nope": {"value": "x"}}, {"sum_insured": {"value": "lots"}}, {"policy_period": {"confirm": True}},
                {"ped_waiting_months": {}}):
        r = put(bad)
        assert r.status_code == 422 and r.json()["detail"]["errors"], bad
    assert put({}).status_code == 200
    # nothing was applied from a rejected request
    assert terms_by_key(c.get(f"/session/{sid}/policy").json())["co_payment"]["display"]["en"] == "10%"


def test_policy_edit_before_any_upload_creates_the_policy_from_user_entries(env):
    c, _ = env
    sid = start(c)
    r = c.put(f"/session/{sid}/policy", json={"terms": {"co_payment": {"value": "20"}}})
    assert r.status_code == 200 and terms_by_key(r.json())["co_payment"]["state"] == "entered"


def test_reupload_keeps_what_the_user_confirmed(env, monkeypatch):
    c, _ = env
    sid = start(c)
    upload_policy(c, sid, Reader([policy.PolicyTermsOut(sum_insured=term(500000, L_SUM))]), monkeypatch)
    c.put(f"/session/{sid}/policy", json={"terms": {"sum_insured": {"value": "750000"}}})
    r = upload_policy(c, sid, Reader([policy.PolicyTermsOut(sum_insured=term(500000, L_SUM),
                                                            co_payment=term("20%", L_COPAY))]), monkeypatch)
    t = terms_by_key(r.json())
    assert t["sum_insured"]["display"]["en"] == "₹7,50,000" and t["co_payment"]["state"] == "found"


def test_delete_policy_removes_it(env, monkeypatch):
    c, _ = env
    sid = start(c)
    upload_policy(c, sid, Reader([policy.PolicyTermsOut(sum_insured=term(500000, L_SUM))]), monkeypatch)
    assert c.delete(f"/session/{sid}/policy").json() == {"deleted": True}
    assert c.get(f"/session/{sid}/policy").json() == {"policy": None}


# ---------- (f) privacy ----------

def test_privacy_cache_off_nothing_under_data_and_page_images_deleted(env, monkeypatch):
    c, tmp = env
    sid = start(c)
    reader = Reader([policy.PolicyTermsOut(sum_insured=term(500000, L_SUM))])
    r = upload_policy(c, sid, reader, monkeypatch)
    assert r.status_code == 200
    assert reader.calls and all(role == "reader" and kw["cache"] is False for role, kw in reader.calls)
    assert not (tmp / "data").exists()                                        # nothing written to the data dir
    assert [p.name for p in (tmp / "sessions").iterdir()] == [sid]            # policy page images already gone
    assert not [f for f in (tmp / "sessions").rglob("*") if f.is_file() and b"Sum Insured" in f.read_bytes()]
    c.put(f"/session/{sid}/policy", json={"terms": {"co_payment": {"value": "20"}}})
    assert not (tmp / "data").exists()


def test_policy_terms_are_dropped_when_the_session_is_deleted(env, monkeypatch):
    c, _ = env
    sid = start(c)
    upload_policy(c, sid, Reader([policy.PolicyTermsOut(sum_insured=term(500000, L_SUM))]), monkeypatch)
    assert c.delete(f"/session/{sid}").status_code == 200
    assert sid not in main._SESSIONS
    assert c.get(f"/session/{sid}/policy").status_code == 404


def test_policy_log_lines_carry_no_document_content(env, monkeypatch, caplog):
    import logging
    c, _ = env
    sid = start(c)
    with caplog.at_level(logging.DEBUG):
        upload_policy(c, sid, Reader([policy.PolicyTermsOut(sum_insured=term(500000, L_SUM))]), monkeypatch)
        c.put(f"/session/{sid}/policy", json={"terms": {"co_payment": {"value": "20"}}})
    logged = " ".join(r.getMessage() for r in caplog.records)
    assert "5,00,000" not in logged and "Sum Insured" not in logged and "500000" not in logged


# ---------- (g) display never alters findings ----------

def test_policy_never_changes_findings_verdicts_or_facts(env, monkeypatch):
    c, _ = env
    sid_a = start(c)
    sid_b = start(c)
    base = c.post(f"/session/{sid_a}/check").json()
    upload_policy(c, sid_b, Reader([policy.PolicyTermsOut(
        sum_insured=term(500000, L_SUM), co_payment=term("20%", L_COPAY), ped_waiting_months=term(36, L_PED))]), monkeypatch)
    c.put(f"/session/{sid_b}/policy", json={"terms": {"co_payment": {"value": "35"}, "sum_insured": {"confirm": True}}})
    facts_before = c.put(f"/session/{sid_b}/facts", json={"facts": {}}).json()["facts"]
    with_policy = c.post(f"/session/{sid_b}/check").json()
    assert with_policy["findings"] == base["findings"]
    assert [f["verdict"] for f in with_policy["findings"]] == ["CHALLENGEABLE"]
    assert set(facts_before) == {"rejection_ground", "fraud_alleged", "inception_date", "policy_renewal_date",
                                 "claim_date", "product_line"}
    assert not any(k in facts_before for k in policy.TERM_KEYS)
    # editing the policy after the check leaves the check result and the explanation in place
    c.put(f"/session/{sid_b}/policy", json={"terms": {"co_payment": {"value": "5"}}})
    ex = c.post(f"/session/{sid_b}/explain?lang=en")
    assert ex.status_code == 200 and ex.json()["findings"] == base["findings"]


def test_policy_feature_adds_no_verdict_type():
    from typing import get_args
    from sarthi.core.models import Verdict
    assert set(get_args(Verdict)) == {"CHALLENGEABLE", "CONSISTENT", "NEED_INFO"}


def test_policy_module_does_not_import_the_rule_engine():
    import inspect
    src = inspect.getsource(policy) + inspect.getsource(__import__("sarthi.app.checklist", fromlist=["x"]))
    assert not re.search(r"^\s*(from|import)\s+sarthi\.core\.(engine|derive|expr)\b", src, re.M)
    assert "run_rules" not in src


# ---------- documents-to-request helper in /check and /explain ----------

def test_need_info_check_returns_the_request_checklist(env, monkeypatch):
    c, _ = env
    monkeypatch.setattr(main, "extract_user_facts",
                        lambda s: {k: v for k, v in extracted().items() if k != "inception_date"})
    sid = start(c)
    body = c.post(f"/session/{sid}/check").json()
    assert body["findings"][0]["verdict"] == "NEED_INFO"
    ck = body["request_checklist"]
    assert ck["verified"] is True and len(ck["items"]) == 5
    assert c.post(f"/session/{sid}/explain?lang=hi").json()["request_checklist"] == ck


def test_deduction_reason_returns_the_checklist_and_a_clean_challengeable_case_does_not(env, monkeypatch):
    c, _ = env
    sid = start(c)
    assert c.post(f"/session/{sid}/check").json()["request_checklist"] is None
    monkeypatch.setattr(main, "extract_user_facts", lambda s: extracted("room_rent"))
    sid2 = start(c)
    body = c.post(f"/session/{sid2}/check").json()
    assert body["request_checklist"]["title"]["en"] == "What to ask the insurer for, in writing"
