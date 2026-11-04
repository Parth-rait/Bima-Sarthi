"""The scheme finder: a reviewed catalogue, explainable statuses, and a stateless API."""
import copy
import itertools
import json
import re

import pytest
from fastapi.testclient import TestClient

from sarthi.app import main
from sarthi.app import schemes as S

DEVA = re.compile(r"[\u0900-\u097f]")
SNAKE = re.compile(r"\b[a-z]+_[a-z0-9_]+\b")


def answers(**kw):
    base = {"work": "own_land", "age": "18_50", "bank": "yes", "ration": "yes"}
    base.update(kw)
    return base


def by_id(result):
    return {x["id"]: x for x in result["results"]}


@pytest.fixture
def catalogue():
    return S.load_catalogue()


def bilingual_strings(node, path=""):
    """Every visible {en, hi} pair in the catalogue, with a path for readable failures."""
    if isinstance(node, dict):
        if set(node) >= {"en", "hi"}:
            yield path, node["en"], node["hi"]
            return
        for k, v in node.items():
            yield from bilingual_strings(v, f"{path}.{k}" if path else str(k))
    elif isinstance(node, list):
        for i, v in enumerate(node):
            yield from bilingual_strings(v, f"{path}[{i}]")


# ---------- catalogue ----------

def test_catalogue_has_the_seven_sourced_schemes(catalogue):
    assert [s["id"] for s in catalogue["schemes"]] == [
        "gopinath_munde", "pmsby", "pmjjby", "pmfby", "pmjay", "pmkisan", "mgnrega"]
    for s in catalogue["schemes"]:
        assert s["official_url"].startswith("https://")
        assert s["source"]["url"].startswith("https://")
        assert s["source"]["note"]["en"] and s["source"]["note"]["hi"]
        assert len(s["steps"]) >= 3 and len(s["fails"]) >= 3
        assert s["reasons"]


def test_official_source_urls_are_pinned(catalogue):
    src = {s["id"]: s["source"]["url"] for s in catalogue["schemes"]}
    assert src["pmfby"] == "https://pmfby.gov.in/pdf/Revised_Operational_Guidelines.pdf"
    assert src["pmsby"] == "https://jansuraksha.gov.in/Files/PMSBY/ENGLISH/FAQ.pdf"
    assert src["pmjjby"] == "https://jansuraksha.gov.in/Files/PMJJBY/ENGLISH/FAQ.pdf"
    assert src["pmjay"] == "https://www.pib.gov.in/PressReleasePage.aspx?PRID=1738169"
    assert "mahadbt.maharashtra.gov.in" in src["gopinath_munde"]
    assert src["pmkisan"] == "https://static.pib.gov.in/WriteReadData/specificdocs/documents/2021/nov/doc2021112361.pdf"
    assert src["mgnrega"] == "https://nregaplus.nic.in/Netnrega/Data/Library/Books/1_MGNREGA_Act.pdf"


def test_published_amounts_and_premiums_are_pinned(catalogue):
    text = json.dumps(catalogue, ensure_ascii=False, default=str)
    assert "₹2 lakh" in text and "₹1 lakh" in text
    assert "₹20 per year" in text and "₹436 per year" in text
    assert "2% of the sum insured" in text and "1.5%" in text and "5%" in text
    assert "₹5 lakh" in text
    assert "₹6,000 per year per family" in text and "₹2,000" in text


def test_every_visible_string_is_bilingual_and_has_no_snake_case(catalogue):
    pairs = list(bilingual_strings(catalogue))
    assert len(pairs) > 80
    for path, en, hi in pairs:
        assert en.strip() and hi.strip(), path
        assert not SNAKE.findall(en), f"snake_case in {path}: {en}"
        assert not SNAKE.findall(hi), f"snake_case in {path}: {hi}"
        assert DEVA.search(hi), f"Hindi missing in {path}: {hi}"


def test_questions_are_the_four_the_page_asks(catalogue):
    assert [q["id"] for q in catalogue["questions"]] == ["work", "age", "bank", "ration"]
    values = {q["id"]: [o["value"] for o in q["options"]] for q in catalogue["questions"]}
    assert values["work"] == ["own_land", "both", "farm_labour", "other"]
    assert values["age"] == ["under_18", "18_50", "51_70", "over_70"]
    assert values["bank"] == ["yes", "no", "unsure"]
    assert values["ration"] == ["yes", "no", "unsure"]


# ---------- matching ----------

@pytest.mark.parametrize(
    "case, expected",
    [
        ({}, {"gopinath_munde": "likely", "pmsby": "likely", "pmjjby": "likely",
              "pmfby": "check", "pmjay": "check", "pmkisan": "likely", "mgnrega": "check"}),
        ({"work": "farm_labour"}, {"gopinath_munde": "not_eligible", "pmfby": "check",
                                   "pmsby": "likely", "pmjjby": "likely", "pmkisan": "check",
                                   "mgnrega": "check"}),
        ({"work": "both"}, {"gopinath_munde": "check", "pmfby": "check", "pmkisan": "likely",
                            "mgnrega": "check"}),
        ({"work": "other"}, {"gopinath_munde": "not_eligible", "pmfby": "not_eligible",
                             "pmjay": "check", "pmkisan": "check", "mgnrega": "check"}),
        ({"age": "51_70"}, {"gopinath_munde": "likely", "pmsby": "likely",
                            "pmjjby": "not_eligible", "pmkisan": "likely", "mgnrega": "check"}),
        ({"age": "over_70"}, {"gopinath_munde": "check", "pmsby": "not_eligible",
                              "pmjjby": "not_eligible", "pmkisan": "likely", "mgnrega": "check"}),
        ({"age": "under_18"}, {"gopinath_munde": "check", "pmsby": "not_eligible",
                               "pmjjby": "not_eligible", "pmkisan": "check", "mgnrega": "check"}),
        ({"bank": "no"}, {"pmsby": "not_eligible", "pmjjby": "not_eligible",
                          "pmjay": "check", "pmkisan": "check", "mgnrega": "check"}),
        ({"bank": "unsure"}, {"pmsby": "check", "pmjjby": "check", "pmkisan": "check",
                              "mgnrega": "check"}),
    ],
)
def test_statuses_follow_the_published_conditions(catalogue, case, expected):
    got = by_id(S.match_schemes(answers(**case), catalogue))
    for scheme_id, status in expected.items():
        assert got[scheme_id]["status"] == status, scheme_id


def test_not_eligible_reasons_name_the_actual_barrier(catalogue):
    got = by_id(S.match_schemes(answers(work="farm_labour"), catalogue))
    assert "7/12" in got["gopinath_munde"]["why"]["en"]
    got = by_id(S.match_schemes(answers(bank="no"), catalogue))
    assert "bank or post office account" in got["pmsby"]["why"]["en"]
    got = by_id(S.match_schemes(answers(age="51_70"), catalogue))
    assert "age 50" in got["pmjjby"]["why"]["en"]


@pytest.mark.parametrize("age", ["under_18", "over_70"])
def test_pmsby_age_barrier_beats_an_unsure_account(catalogue, age):
    got = by_id(S.match_schemes(answers(age=age, bank="unsure"), catalogue))
    assert got["pmsby"]["status"] == "not_eligible"


@pytest.mark.parametrize("age", ["under_18", "51_70", "over_70"])
def test_pmjjby_age_barrier_beats_an_unsure_account(catalogue, age):
    got = by_id(S.match_schemes(answers(age=age, bank="unsure"), catalogue))
    assert got["pmjjby"]["status"] == "not_eligible"


def test_every_answer_combination_keeps_the_published_barriers(catalogue):
    before = copy.deepcopy(catalogue)
    values = {q["id"]: [o["value"] for o in q["options"]] for q in catalogue["questions"]}
    for combo in itertools.product(*(values[k] for k in S.REQUIRED)):
        a = dict(zip(S.REQUIRED, combo))
        got = by_id(S.match_schemes(a, catalogue))
        assert len(got) == 7
        if a["age"] == "under_18":
            assert got["pmsby"]["status"] == "not_eligible"
            assert got["pmjjby"]["status"] == "not_eligible"
        if a["age"] == "over_70":
            assert got["pmsby"]["status"] == "not_eligible"
        if a["age"] in {"51_70", "over_70"}:
            assert got["pmjjby"]["status"] == "not_eligible"
        if a["work"] == "farm_labour":
            assert got["gopinath_munde"]["status"] == "not_eligible"
        if a["work"] == "other":
            assert got["pmfby"]["status"] == "not_eligible"
        if a["bank"] == "no":
            assert got["pmsby"]["status"] != "likely"
            assert got["pmjjby"]["status"] != "likely"
    assert catalogue == before


def test_a_missing_ration_card_changes_the_health_reason_not_the_status(catalogue):
    got = by_id(S.match_schemes(answers(ration="no"), catalogue))
    assert got["pmjay"]["status"] == "check"
    assert "ration card" in got["pmjay"]["why"]["en"]


def test_results_are_grouped_and_ordered_likely_check_then_not_eligible(catalogue):
    result = S.match_schemes(answers(), catalogue)
    order = [r["status"] for r in result["results"]]
    expected = sorted(order, key=S.STATUS_ORDER.get)
    assert order == expected
    for r in result["results"]:
        assert r["group"] == S.STATUS_GROUP[r["status"]]
    empty = S.match_schemes(answers(work="other", bank="no"), catalogue)
    groups = {r["group"] for r in result["results"]} | {r["group"] for r in empty["results"]}
    assert groups == {"start", "ask", "not_now"}
    assert "start" not in {r["group"] for r in empty["results"]}


def test_each_result_carries_its_source_and_a_checked_date(catalogue):
    results = S.match_schemes(answers(), catalogue)["results"]
    for r in results:
        assert r["official_url"].startswith("https://")
        assert r["source"]["url"].startswith("https://")
        assert r["steps"] and r["fails"]
    dates = {r["id"]: r["verified_on"] for r in results}
    assert dates["pmkisan"] == "2026-11-03"
    assert dates["mgnrega"] == "2026-11-03"
    assert all(v == "2026-11-02" for k, v in dates.items() if k not in {"pmkisan", "mgnrega"})


def test_mgnrega_always_asks_for_the_job_card(catalogue):
    for case in ({}, {"work": "farm_labour"}, {"work": "other"}, {"bank": "no"}, {"age": "under_18"}):
        got = by_id(S.match_schemes(answers(**case), catalogue))
        assert got["mgnrega"]["status"] == "check"
        assert "job card" in got["mgnrega"]["why"]["en"].lower()


def test_pm_kisan_names_its_land_bank_and_family_conditions(catalogue):
    got = by_id(S.match_schemes(answers(work="farm_labour"), catalogue))
    assert "land in your family's name" in got["pmkisan"]["why"]["en"]
    got = by_id(S.match_schemes(answers(bank="no"), catalogue))
    assert "bank account" in got["pmkisan"]["why"]["en"]
    got = by_id(S.match_schemes(answers(age="under_18"), catalogue))
    assert "family" in got["pmkisan"]["why"]["en"]


def test_matching_is_deterministic(catalogue):
    a = S.match_schemes(answers(), catalogue)
    b = S.match_schemes(answers(), catalogue)
    assert a == b


@pytest.mark.parametrize("bad", [
    {"work": "teacher"},
    {"age": "35"},
    {"bank": "maybe"},
    {"ration": "<script>alert(1)</script>"},
])
def test_unknown_answers_are_rejected(catalogue, bad):
    with pytest.raises(ValueError):
        S.match_schemes(answers(**bad), catalogue)


def test_missing_answers_are_rejected(catalogue):
    with pytest.raises(ValueError):
        S.match_schemes({"work": "own_land"}, catalogue)


# ---------- API ----------

@pytest.fixture
def scheme_client():
    with TestClient(main.app) as c:
        yield c


def test_catalogue_endpoint_serves_questions_but_not_reasons(scheme_client):
    r = scheme_client.get("/api/schemes")
    assert r.status_code == 200
    assert r.headers["x-content-type-options"] == "nosniff"
    assert r.headers["referrer-policy"] == "strict-origin-when-cross-origin"
    body = r.json()
    assert body["state"] == "Maharashtra"
    assert body["scheme_count"] == 7
    assert body["checked_on"] == "2026-11-02"
    assert [q["id"] for q in body["questions"]] == ["work", "age", "bank", "ration"]
    assert "reasons" not in json.dumps(body)
    assert "results" not in body


def test_match_endpoint_returns_a_ranked_list(scheme_client):
    r = scheme_client.post("/api/schemes/match", json=answers())
    assert r.status_code == 200, r.text
    body = r.json()
    assert [x["id"] for x in body["results"]][:3] == ["gopinath_munde", "pmsby", "pmjjby"]
    assert all(x["status"] in {"likely", "check", "not_eligible"} for x in body["results"])
    assert "This is information, not an eligibility decision." in body["disclaimer"]["en"]


def test_match_endpoint_rejects_an_unknown_answer(scheme_client):
    r = scheme_client.post("/api/schemes/match", json=answers(work="teacher"))
    assert r.status_code == 422


def test_match_endpoint_rejects_a_missing_required_answer(scheme_client):
    r = scheme_client.post("/api/schemes/match", json={"age": "18_50"})
    assert r.status_code == 422


@pytest.mark.parametrize("value", [b"NaN", b"Infinity", b"-Infinity"])
def test_non_finite_numbers_are_rejected_without_a_server_error(scheme_client, value):
    raw = b'{"work":"own_land","age":' + value + b',"bank":"yes","ration":"yes"}'
    r = scheme_client.post("/api/schemes/match", content=raw, headers={"content-type": "application/json"})
    assert r.status_code == 422
    assert r.json()["detail"]


def test_defaults_cover_a_skipped_bank_and_ration_answer(scheme_client):
    r = scheme_client.post("/api/schemes/match", json={"work": "farm_labour", "age": "18_50"})
    assert r.status_code == 200
    got = {x["id"]: x["status"] for x in r.json()["results"]}
    assert got["pmsby"] == "check" and got["pmjjby"] == "check"


CLAIM_LINES = {"health", "life", "motor", "accident", "crop", "credit_life", "other"}


def test_insurance_schemes_name_the_claim_type_the_claim_check_uses(catalogue):
    # The bridge from the finder to "check my claim": only schemes that are an insurance policy
    # carry the claim check's type of insurance; benefit schemes (PM-KISAN, MGNREGA) never do.
    out = S.match_schemes(answers(), catalogue)
    lines = {r["id"]: r.get("claim_product_line") for r in out["results"]}
    assert lines["pmsby"] == "accident" and lines["pmjjby"] == "life" and lines["pmfby"] == "crop"
    assert lines["pmkisan"] is None and lines["mgnrega"] is None
    assert {v for v in lines.values() if v} <= CLAIM_LINES
