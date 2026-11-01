"""Product-line choice, the general plan (non-health) and "Your plan" (health).

Fixed templates only; no model calls, no network. The quote catalogue is checked
word for word against the stored official texts when the database is readable.
"""
import re
from datetime import date

import pytest

from sarthi.app import labels, plan
from sarthi.app.verify import verify
from sarthi.core.models import FactValue, Finding

SNAKE = re.compile(r"\b[a-z0-9]+(?:_[a-z0-9]+)+\b")
VERDICT_WORDS = re.compile(r"CHALLENGEABLE|CONSISTENT|NEED_INFO|challengeable", re.I)


def _p(value, unit, quote, page, source="ombudsman_rules_2017"):
    return {"value": value, "unit": unit, "source_id": source, "page_no": page, "quote": quote}


PARAMS = {
    "insurer_reply_days": _p(14, "days", "Insurers should provide resolution to the complaint within 14 days",
                             111, "irdai_ppi_master_2024"),
    "ombudsman_wait_months": _p(1, "months", "the complainant had not received any reply within a period of one month", 10),
    "ombudsman_limit_months": _p(12, "months", "The complaint is made within one year", 10),
    "ombudsman_claim_limit_inr": _p(5000000, "inr", "claim amount is up to Rs. 50 lakhs", 135, "irdai_ppi_master_2024"),
    "ombudsman_award_cap_inr": _p(3000000, "inr", "not award compensation exceeding rupees thirty lakhs", 12),
}

Q = "No claim shall be contestable after sixty continuous months."


def finding(verdict="CHALLENGEABLE", rule_id="MORATORIUM_60M", action="Ask for the policy wording.",
            question=None):
    return Finding(rule_id=rule_id, rule_version=1, verdict=verdict, reason=None, rule_quote=Q,
                   source_sha256="a" * 64, page_no=7,
                   facts_used={"inception_date": {"value": "2019-01-10", "quote": "Start 10/01/2019", "page_no": 1}},
                   question_en=question, action_en=action)


# ---------- product line ----------

def test_seven_choices_with_en_hi_labels_and_no_unknown():
    assert plan.PRODUCT_LINE_KEYS == ("health", "life", "accident", "motor", "crop", "credit_life", "other")
    for k in plan.PRODUCT_LINE_KEYS:
        en, hi = plan.product_label(k, "en"), plan.product_label(k, "hi")
        assert "_" not in en and re.search(r"[ऀ-ॿ]", hi) and not re.search(r"[ऀ-ॿ]", en)
    assert plan.product_label("crop", "en") == "Crop (agriculture)"
    assert plan.FIELD_LABEL["en"] == "Type of insurance"


def fvs(**kw):
    return {k: FactValue(value=v, quote="q", page_no=1) for k, v in kw.items()}


def test_hint_is_health_only_for_hospital_facts_plus_a_health_ground():
    assert plan.product_line_hint(fvs(rejection_ground="room_rent", admission_date=date(2025, 1, 1))) == "health"
    assert plan.product_line_hint(fvs(rejection_ground="cashless_delay",
                                      cashless_request_at="2025-01-01T10:00")) == "health"


@pytest.mark.parametrize("facts", [
    fvs(rejection_ground="room_rent"),                                         # no hospital fact
    fvs(admission_date=date(2025, 1, 1)),                                      # no ground
    fvs(rejection_ground="non_disclosure", admission_date=date(2025, 1, 1)),   # generic ground
    fvs(rejection_ground="pre_existing_disease", admission_date=date(2025, 1, 1)),
    fvs(rejection_ground="other", admission_date=date(2025, 1, 1)),
    {},
])
def test_hint_is_none_when_not_clear(facts):
    assert plan.product_line_hint(facts) is None


# ---------- general plan ----------

SUPPORTED = ("life", "motor", "accident")
UNSUPPORTED = ("crop", "credit_life", "other")


def routes(p):
    return [i for s in p["steps"] for i in s["items"] if i.get("quote")]


def test_general_title_is_the_fixed_sentence():
    p, _ = plan.general_plan("life", params=None, complaint_date=None, reply_date=None)
    assert p["supported"] is False and p["kind"] == "general"
    assert p["title"]["en"] == ("We don't have a checked rules engine for this type of insurance yet. "
                                "This does not mean the decision is correct. "
                                "Here is a general way to take your case forward.")
    assert "सही है" in p["title"]["hi"] and "_" not in p["title"]["hi"]


@pytest.mark.parametrize("line", SUPPORTED)
def test_supported_lines_show_insurer_and_ombudsman_steps_with_quote_and_page(line):
    p, _ = plan.general_plan(line, params=None, complaint_date=None, reply_date=None)
    qs = routes(p)
    assert qs and all(i["page_no"] and i["source_id"] and i["quote"] for i in qs)
    sources = {(i["source_id"], i["page_no"]) for i in qs}
    assert ("ombudsman_rules_2017", 10) in sources and ("ombudsman_rules_2017", 12) in sources
    assert ("irdai_ppi_master_2024", 111 if line == "life" else 135) in sources
    assert p["unverified"] is None


@pytest.mark.parametrize("line", UNSUPPORTED)
def test_unsupported_lines_make_no_route_claim_and_say_so(line):
    p, _ = plan.general_plan(line, params=PARAMS, complaint_date=date(2026, 9, 1), reply_date=None)
    assert routes(p) == []
    t = plan.plan_text(p, "en").lower()
    assert "we have not verified the complaint route for this type of insurance" in t
    assert "ombudsman" not in t and "14" not in t and "grievance officer" not in t
    assert not any(i.get("date") for s in p["steps"] for i in s["items"])


def test_crop_says_government_schemes_may_have_their_own_process():
    p, _ = plan.general_plan("crop", params=None, complaint_date=None, reply_date=None)
    t = plan.plan_text(p, "en")
    assert "government crop schemes can have their own complaint process that this tool has not verified" in t.lower()
    assert "local agriculture office" in t and "bank branch" in t and "in writing" in t


@pytest.mark.parametrize("line", plan.PRODUCT_LINE_KEYS[1:])
@pytest.mark.parametrize("lang", ["en", "hi"])
def test_general_plan_text_has_no_verdict_snake_case_or_promise(line, lang):
    p, extras = plan.general_plan(line, params=PARAMS, complaint_date=date(2026, 9, 1), reply_date=None)
    t = plan.plan_text(p, lang)
    assert not VERDICT_WORDS.search(t) and not SNAKE.findall(t)
    r = verify(t, [], **extras)
    assert r.ok, r.problems


def test_general_deadlines_only_from_user_dates_and_params_and_only_where_sources_apply():
    p, _ = plan.general_plan("life", params=PARAMS, complaint_date=date(2026, 9, 1), reply_date=None)
    dates = {i["date"]["iso"] for s in p["steps"] for i in s["items"] if i.get("date")}
    assert {"2026-09-15", "2026-10-01", "2027-10-01"} <= dates       # 14 days; 1 month; 1 year after the wait ends
    # no complaint date -> a message, no date at all
    p, _ = plan.general_plan("life", params=PARAMS, complaint_date=None, reply_date=None)
    assert not any(i.get("date") for s in p["steps"] for i in s["items"])
    assert "Add the date you sent your complaint" in plan.plan_text(p, "en")
    # no approved card -> no dates
    p, _ = plan.general_plan("motor", params=None, complaint_date=date(2026, 9, 1), reply_date=None)
    assert not any(i.get("date") for s in p["steps"] for i in s["items"])


def test_general_reply_date_moves_the_ombudsman_window_with_its_own_source_label():
    p, _ = plan.general_plan("motor", params=PARAMS, complaint_date=date(2026, 9, 1),
                             reply_date=date(2026, 9, 10))
    items = {i["key"]: i for s in p["steps"] for i in s["items"] if i.get("key")}
    assert items["ombudsman_earliest"]["date"]["iso"] == "2026-09-10"
    assert items["ombudsman_earliest"]["source_label"]["en"] == "your insurer's reply date (entered by you)"
    assert items["ombudsman_latest"]["date"]["iso"] == "2027-09-10"


# ---------- catalogue quotes are verbatim ----------

def _norm(s):
    return re.sub(r"\s+", " ", s)


def _pages():
    import duckdb
    from pathlib import Path
    path = Path(__file__).resolve().parents[2] / "data" / "bima_sarthi.duckdb"
    if not path.is_file():
        pytest.skip("database not present")
    try:
        con = duckdb.connect(str(path), read_only=True)
    except duckdb.IOException:
        pytest.skip("database is locked by a writer")
    try:
        rows = con.execute(
            "SELECT s.source_id, d.page_no, d.text FROM document_page d JOIN source s USING (sha256) "
            "WHERE s.source_id IN ('irdai_ppi_master_2024','ombudsman_rules_2017')").fetchall()
    finally:
        con.close()
    return {(sid, pg): _norm(t or "") for sid, pg, t in rows}


def test_every_catalogue_quote_and_scope_quote_is_verbatim_on_its_page():
    pages = _pages()
    assert plan.CATALOGUE
    for sid, entries in plan.CATALOGUE.items():
        for e in entries:
            for key in ("quote", "scope_quote"):
                if e.get(key):
                    assert _norm(e[key]) in pages[(e["source_id"], e["page_no"])], (sid, e[key][:50])


# ---------- "Your plan" for health ----------

MISSING_COMPLAINT = "Add the date you sent your complaint to see your Ombudsman dates"


def fs():
    return [finding("CHALLENGEABLE"),
            finding("NEED_INFO", rule_id="WAIT_SPECIFIC", action="Ask for the waiting-period clause.",
                    question="When did the cover start?")]


def health(findings=None, *, params=PARAMS, complaint=date(2026, 9, 1), reply=None, amount=None):
    return plan.health_plan(findings or fs(), params=params, complaint_date=complaint,
                            reply_date=reply, claim_amount=amount)


def by_id(p):
    return {s["id"]: s for s in p["steps"]}


def test_health_plan_steps_are_ordered_and_use_the_existing_pieces():
    p, _ = health(amount=6_000_000)
    assert [s["id"] for s in p["steps"]] == ["findings", "ask", "letter", "ombudsman", "commission"]
    assert p["supported"] is True and p["kind"] == "health"
    s1 = by_id(p)["findings"]["items"]
    assert [i["rule_id"] for i in s1] == ["MORATORIUM_60M", "WAIT_SPECIFIC"]      # challengeable first
    assert s1[0]["quote"] == Q and s1[0]["page_no"] == 7
    asks = " ".join(i["text"]["en"] for i in by_id(p)["ask"]["items"])
    assert "Ask for the policy wording." in asks and "When did the cover start?" in asks
    assert any(i.get("link") == "letter" for i in by_id(p)["letter"]["items"])


def test_health_plan_dates_come_from_the_complaint_date_and_card_params_only():
    p, _ = health()
    items = {i["key"]: i for s in p["steps"] for i in s["items"] if i.get("key")}
    assert items["insurer_reply_by"]["date"]["iso"] == "2026-09-15"
    assert items["insurer_reply_by"]["page_no"] == 111 and items["insurer_reply_by"]["quote"]
    assert items["ombudsman_earliest"]["date"]["iso"] == "2026-10-01"
    assert items["ombudsman_latest"]["date"]["iso"] == "2027-10-01"
    assert items["ombudsman_latest"]["page_no"] == 10


def test_health_plan_missing_complaint_date_shows_the_add_the_date_message_not_a_date():
    p, _ = health(complaint=None)
    assert not any(i.get("date") for s in p["steps"] for i in s["items"])
    assert MISSING_COMPLAINT in plan.plan_text(p, "en")
    p, _ = health(complaint=None, reply=date(2026, 9, 10))
    assert not any(i.get("date") for s in p["steps"] for i in s["items"])


def test_health_plan_without_a_challengeable_finding_offers_no_letter_or_dates():
    p, _ = health([finding("CONSISTENT")])
    assert not any(i.get("link") for s in p["steps"] for i in s["items"])
    assert not any(i.get("date") for s in p["steps"] for i in s["items"])
    assert "Deadlines apply when a finding is challengeable." in plan.plan_text(p, "en")


def test_health_plan_without_the_approved_grievance_card_says_so():
    p, _ = health(params=None)
    assert "Deadlines need the grievance-route rule card to be approved" in plan.plan_text(p, "en")
    assert not any(i.get("date") or i.get("link") for s in p["steps"] for i in s["items"])


def test_commission_step_only_when_the_claim_is_above_a_limit():
    assert "commission" not in by_id(health(amount=100_000)[0])
    big = by_id(health(amount=6_000_000)[0])["commission"]["items"][0]["text"]["en"]
    assert "consumer commission" in big
    mid = by_id(health(amount=4_000_000)[0])["commission"]["items"][0]["text"]["en"]
    assert "at most" in mid


@pytest.mark.parametrize("lang", ["en", "hi"])
@pytest.mark.parametrize("amount", [None, 100_000, 4_000_000, 6_000_000])
@pytest.mark.parametrize("complaint,reply", [(date(2026, 9, 1), None), (date(2026, 9, 1), date(2026, 9, 10)),
                                             (None, None)])
def test_health_plan_text_passes_the_existing_verify(lang, amount, complaint, reply):
    fl = fs()
    p, extras = health(fl, amount=amount, complaint=complaint, reply=reply)
    t = plan.plan_text(p, lang)
    r = verify(t, fl, **extras)
    assert r.ok, (r.problems, t)
    assert not SNAKE.findall(t.replace("MORATORIUM_60M", "").replace("WAIT_SPECIFIC", ""))


def test_verify_extras_do_not_open_the_door_to_other_dates_or_promises():
    fl = fs()
    p, extras = health(fl)
    t = plan.plan_text(p, "en")
    assert not verify(t + " Send it by 05/05/2030.", fl, **extras).ok
    assert not verify(t + " You will win.", fl, **extras).ok
    assert not verify(t + " Wait 99 days.", fl, **extras).ok


def test_verify_without_extras_is_unchanged():
    assert verify("Plain text.", []).ok
    assert not verify("Send it by 05/05/2030.", []).ok


def test_finalize_drops_a_plan_whose_text_fails_verify():
    fl = fs()
    p, extras = health(fl)
    assert plan.finalize(p, extras, fl) is p and p["verified"] is True
    p2, extras2 = health(fl)
    p2["steps"][0]["items"][0]["text"]["en"] = "You will win this claim."
    assert plan.finalize(p2, extras2, fl) is None


# ---------- the page (no browser here: assert on the shipped source) ----------

def _html():
    from pathlib import Path
    return (Path(plan.__file__).parent / "static" / "index.html").read_text(encoding="utf-8")


def test_ui_product_labels_come_from_the_single_source():
    import json
    m = re.search(r"const PRODUCT_LABEL=(\{.*?\});\n", _html(), re.S)
    ui = json.loads(re.sub(r"(\w+):", r'"\1":', m.group(1)))
    assert ui == {"en": {k: plan.product_label(k, "en") for k in plan.PRODUCT_LINE_KEYS},
                  "hi": {k: plan.product_label(k, "hi") for k in plan.PRODUCT_LINE_KEYS}}
    assert 'const PRODUCT_KEYS=["health","life","accident","motor","crop","credit_life","other"]' in _html()
    assert f'pl_label:"{plan.FIELD_LABEL["en"]}"' in _html() and f'pl_label:"{plan.FIELD_LABEL["hi"]}"' in _html()


def test_ui_select_is_labelled_required_before_checking_and_uses_no_innerhtml():
    h = _html()
    assert 'el("label",{for:"product_line"},t("pl_label"))' in h and '{id:"product_line"' in h
    assert "if(!pl.value)" in h and "payload={product_line:{value:pl.value}}" in h
    assert "k!==\"product_line\"" in h                       # not shown as an editable fact card
    assert "innerHTML" not in h and "insertAdjacentHTML" not in h
    assert "renderPlan(result.plan)" in h and "result.supported!==false" in h


def test_ui_hint_is_a_preselection_only_and_marked_as_a_suggestion():
    h = _html()
    assert "const start=productChoice||stored||plHint||\"\"" in h and 't("pl_hint")' in h


def test_ui_script_parses():
    import shutil
    import subprocess
    import tempfile
    node = shutil.which("node")
    if not node:
        pytest.skip("node not available")
    js = re.search(r"<script>(.*)</script>", _html(), re.S).group(1)
    with tempfile.NamedTemporaryFile("w", suffix=".js", delete=False, encoding="utf-8") as f:
        f.write(js)
    r = subprocess.run([node, "--check", f.name], capture_output=True, text=True)
    assert r.returncode == 0, r.stderr


def test_building_a_plan_never_shares_mutable_text_between_plans():
    a, _ = health()
    a["steps"][0]["items"][0]["text"]["en"] = "changed"
    b, _ = health()
    assert b["steps"][0]["items"][0]["text"]["en"] != "changed"
    g1, _ = plan.general_plan("life", params=None, complaint_date=None, reply_date=None)
    g1["steps"][0]["items"][0]["text"]["en"] = "changed"
    g2, _ = plan.general_plan("life", params=None, complaint_date=None, reply_date=None)
    assert g2["steps"][0]["items"][0]["text"]["en"] != "changed"
