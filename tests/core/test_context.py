"""Family -> candidate cards map and the per-case rule-context resolver."""
from datetime import date, datetime
from pathlib import Path

import pytest
import yaml

from sarthi.app.extract import ready_for_rules
from sarthi.core.engine import run_rules
from sarthi.core.inputs import REJECTION_GROUNDS
from sarthi.core.models import ISSUE_FAMILIES, FactValue, RuleCard
from sarthi.core import context
from sarthi.core.context import (FamilyMapError, applicable_cards, load_family_map,
                                 resolve_rule_context)

SEED = Path(__file__).parents[2] / "rules" / "seed"


def seed_card(name, status="approved", **over):
    data = yaml.safe_load((SEED / f"{name}.yaml").read_text(encoding="utf-8"))
    data.pop("source_id", None)
    data.update(status=status, source_sha256="a" * 64, quote="q " + name)
    data.update(over)
    return RuleCard(**data)


def deck(status="approved"):
    return [seed_card(n, status) for n in (
        "MORATORIUM_60M", "MORATORIUM_60M.v0", "PED_WAIT_36M", "PED_WAIT_36M.v0", "SPECIFIC_WAIT",
        "SPECIFIC_WAIT.v0", "INITIAL_30D.v0", "PORTABILITY_CREDIT", "CASHLESS_1H", "DISCHARGE_3H",
        "REJECTION_PROCESS")] + [seed_card("EXCLUSION_LISTED", "draft")]


def fv(value, status="verified"):
    return FactValue(value=value, quote="q", page_no=1, status=status)


def facts(**kw):
    return {k: (v if isinstance(v, FactValue) else fv(v)) for k, v in kw.items()}


ND = dict(rejection_ground="non_disclosure", fraud_alleged=False, inception_date=date(2019, 1, 10),
          claim_date=date(2025, 4, 15), policy_renewal_date=date(2024, 6, 1))


def by_rule(results):
    return {r.rule_id: r for r in results}


# ---------- the family map ----------

def test_map_has_every_family_and_the_agreed_cards():
    m = load_family_map()
    assert set(m.families) == set(ISSUE_FAMILIES)
    assert m.cards("NON_DISCLOSURE") == ["MORATORIUM_60M"]
    assert m.cards("PED_DEFINITION") == ["PED_WAIT_36M"]
    assert m.cards("WAITING_PERIOD") == ["INITIAL_30D", "PED_WAIT_36M", "SPECIFIC_WAIT"]
    assert m.cards("PORTABILITY") == ["PORTABILITY_CREDIT"]
    assert m.cards("CASHLESS_PROCESS") == ["CASHLESS_1H"]
    assert m.cards("DISCHARGE_PROCESS") == ["DISCHARGE_3H"]
    assert m.cards("REJECTION_PROCESS") == ["REJECTION_PROCESS"]
    for f in ("EXCLUSION", "POLICY_WORDING_DELIVERY", "CLAIM_SETTLEMENT_DELAY",
              "CLAIM_NOTIFICATION_DELAY", "DEDUCTION", "OTHER"):
        assert m.cards(f) == []
    assert m.research_needed("EXCLUSION") and m.research_needed("CLAIM_SETTLEMENT_DELAY")
    assert not m.research_needed("NON_DISCLOSURE")


def test_exclusion_listed_is_never_a_candidate_of_any_family():
    m = load_family_map()
    assert all("EXCLUSION_LISTED" not in m.cards(f) for f in m.families)


def test_every_ground_maps_to_a_family():
    m = load_family_map()
    assert set(m.grounds) == set(REJECTION_GROUNDS)
    assert all(g in ISSUE_FAMILIES for g in m.grounds.values())


def _write(tmp_path, doc):
    p = tmp_path / "f.yaml"
    p.write_text(yaml.safe_dump(doc))
    return p


def _good():
    return yaml.safe_load((Path(context.__file__).parents[1] / "data" / "rule_families.yaml").read_text())


def test_loader_rejects_a_rule_id_that_is_not_in_rules_seed(tmp_path):
    d = _good()
    d["families"]["NON_DISCLOSURE"]["cards"] = ["NO_SUCH_CARD"]
    with pytest.raises(FamilyMapError, match="NO_SUCH_CARD"):
        load_family_map(_write(tmp_path, d))


def test_loader_rejects_unknown_family_and_missing_family_and_bad_ground(tmp_path):
    d = _good()
    d["families"]["MADE_UP"] = {"cards": []}
    with pytest.raises(FamilyMapError, match="MADE_UP"):
        load_family_map(_write(tmp_path, d))
    d = _good()
    del d["families"]["OTHER"]
    with pytest.raises(FamilyMapError, match="OTHER"):
        load_family_map(_write(tmp_path, d))
    d = _good()
    d["grounds"]["non_disclosure"] = "MORATORIUM_60M"
    with pytest.raises(FamilyMapError):
        load_family_map(_write(tmp_path, d))


# ---------- one family -> several candidate cards ----------

def test_one_family_resolves_to_several_candidate_cards():
    f = facts(rejection_ground="specific_waiting_period", inception_date=date(2024, 6, 1),
              claim_date=date(2025, 4, 15))
    res = resolve_rule_context("WAITING_PERIOD", f, deck(), "health")
    assert {r.rule_id for r in res} == {"INITIAL_30D", "PED_WAIT_36M", "SPECIFIC_WAIT"}
    assert all(r.family == "WAITING_PERIOD" for r in res)
    r = by_rule(res)
    # only the card the stated ground triggers can decide; the other candidates are not applicable
    assert r["SPECIFIC_WAIT"].status == "applicable" and r["SPECIFIC_WAIT"].version == 1
    assert r["PED_WAIT_36M"].status == "no_candidate_rule"
    assert "pre_existing_disease" not in r["PED_WAIT_36M"].reason or "specific_waiting_period" in r["PED_WAIT_36M"].reason
    assert r["INITIAL_30D"].status in ("no_candidate_rule", "not_in_force")


# ---------- a family without a card ----------

@pytest.mark.parametrize("family", ["EXCLUSION", "POLICY_WORDING_DELIVERY", "CLAIM_SETTLEMENT_DELAY",
                                    "CLAIM_NOTIFICATION_DELAY", "DEDUCTION", "OTHER"])
def test_family_with_no_card_is_no_candidate_rule_never_exclusion_listed(family):
    f = facts(rejection_ground="exclusion", claim_date=date(2025, 4, 15), cited_clause_found=True)
    res = resolve_rule_context(family, f, deck(), "health")
    assert [r.status for r in res] == ["no_candidate_rule"]
    assert res[0].rule_id is None
    assert applicable_cards(res, deck()) == []
    assert "EXCLUSION_LISTED" not in res[0].reason


def test_exclusion_family_reports_research_needed():
    res = resolve_rule_context("EXCLUSION", facts(rejection_ground="exclusion"), deck(), "health")
    assert "research_needed" in res[0].reason


# ---------- a draft / unverified card is never applicable ----------

def test_draft_card_is_not_approved_and_never_applicable():
    cards = [c for c in deck() if c.rule_id != "MORATORIUM_60M"] + [
        seed_card("MORATORIUM_60M", "draft"), seed_card("MORATORIUM_60M.v0", "draft")]
    res = resolve_rule_context("NON_DISCLOSURE", facts(**ND), cards, "health")
    assert [r.status for r in res] == ["not_approved"]
    assert res[0].approved is False
    assert applicable_cards(res, cards) == []


def test_approved_but_quote_not_verified_is_not_applicable():
    cards = deck()
    verified = {(c.rule_id, c.version) for c in cards if c.rule_id != "MORATORIUM_60M"}
    res = resolve_rule_context("NON_DISCLOSURE", facts(**ND), cards, "health", verified=verified)
    assert [r.status for r in res] == ["quote_unverified"]
    assert res[0].approved is True and res[0].quote_verified is False
    assert applicable_cards(res, cards) == []


def test_run_rules_never_receives_a_draft_or_unverified_card():
    cards = deck()
    res = resolve_rule_context("EXCLUSION", facts(rejection_ground="exclusion"), cards, "health")
    for c in applicable_cards(res, cards):
        assert c.status == "approved"
    # and the engine itself still refuses one (unchanged guard)
    with pytest.raises(ValueError):
        run_rules(facts(rejection_ground="exclusion"), [seed_card("EXCLUSION_LISTED", "draft")])


# ---------- dates / versions ----------

def test_card_not_yet_in_force_is_not_in_force():
    f = facts(**{**ND, "claim_date": date(2024, 1, 1), "inception_date": date(2019, 1, 10),
                 "policy_renewal_date": date(2023, 6, 1)})
    cards = [c for c in deck() if c.rule_id != "MORATORIUM_60M"] + [seed_card("MORATORIUM_60M")]
    res = resolve_rule_context("NON_DISCLOSURE", f, cards, "health")  # only v1 (from 2024-05-29)
    assert res[0].status == "not_in_force"
    assert res[0].applicability_date == date(2023, 6, 1)
    assert "2024-05-29" in res[0].reason
    assert applicable_cards(res, cards) == []


def test_old_claim_picks_the_historical_v0_card():
    f = facts(**{**ND, "claim_date": date(2022, 3, 1), "inception_date": date(2021, 1, 10),
                 "policy_renewal_date": date(2022, 1, 10)})
    res = resolve_rule_context("NON_DISCLOSURE", f, deck(), "health")
    assert res[0].status == "applicable" and res[0].version == 0
    assert res[0].applicability_date == date(2022, 1, 10)
    assert res[0].applies_by == "policy_start_or_renewal"
    picked = applicable_cards(res, deck())
    assert {(c.rule_id, c.version) for c in picked} >= {("MORATORIUM_60M", 0)}
    out = run_rules(f, picked)
    assert [x.rule_version for x in out] == [0]  # the engine selects the same version


def test_applicability_date_is_not_always_claim_date():
    f = facts(**ND)
    res = resolve_rule_context("NON_DISCLOSURE", f, deck(), "health")
    assert res[0].applicability_date == date(2024, 6, 1)  # the renewal, not the claim date
    assert res[0].date_basis == ["claim_date", "inception_date", "policy_renewal_date"]
    res2 = resolve_rule_context("CASHLESS_PROCESS",
                                facts(rejection_ground="cashless_delay", claim_date=date(2025, 4, 15),
                                      cashless_request_at=datetime(2025, 4, 15, 9),
                                      decision_at=datetime(2025, 4, 15, 12)), deck(), "health")
    assert res2[0].applicability_date == date(2025, 4, 15) and res2[0].applies_by == "claim_date"


def test_missing_applicability_date_is_reported_explicitly():
    f = facts(**{k: v for k, v in ND.items() if k != "inception_date"})
    res = resolve_rule_context("NON_DISCLOSURE", f, deck(), "health")
    assert res[0].status == "missing_applicability_date"
    assert res[0].reason == "missing_inception_date"
    assert applicable_cards(res, deck()) == []


def test_unsupported_applies_by_is_an_ambiguous_applicability_date():
    cards = [seed_card("MORATORIUM_60M", applies_by="somewhere_else")]
    res = resolve_rule_context("NON_DISCLOSURE", facts(**ND), cards, "health")
    assert res[0].status == "missing_applicability_date"
    assert res[0].reason == "unsupported_applies_by"


# ---------- facts ----------

PORT = dict(rejection_ground="non_disclosure", fraud_alleged=False, inception_date=date(2024, 12, 1),
            claim_date=date(2025, 4, 15))


def test_unreviewed_porting_fact_blocks_the_card():
    res = resolve_rule_context("NON_DISCLOSURE", facts(**PORT), deck(), "health",
                               unresolved={"ported_from_date": fv("2014", "needs_confirmation")})
    assert res[0].status == "missing_required_fact"
    assert res[0].missing_facts == ["ported_from_date"]
    assert applicable_cards(res, deck()) == []


def test_flagged_fact_inside_the_facts_dict_also_blocks():
    f = facts(**PORT)
    f["ported_from_date"] = fv(date(2014, 1, 1), "needs_confirmation")
    res = resolve_rule_context("NON_DISCLOSURE", f, deck(), "health")
    assert res[0].status == "missing_required_fact"


def test_unrelated_flagged_fact_does_not_block_a_complete_finding():
    f = facts(**ND)
    res = resolve_rule_context("NON_DISCLOSURE", f, deck(), "health", unresolved={
        "cashless_request_at": fv(datetime(2025, 4, 15, 10), "needs_confirmation"),
        "deductions": fv([], "needs_confirmation")})
    assert res[0].status == "applicable" and res[0].missing_facts == []


def test_unreviewed_ground_blocks_everything_and_absent_ground_is_missing_not_unreviewed():
    f = facts(**{k: v for k, v in ND.items() if k != "rejection_ground"})
    res = resolve_rule_context("NON_DISCLOSURE", f, deck(), "health",
                               unresolved={"rejection_ground": fv("non_disclosure", "needs_confirmation")})
    assert res[0].status == "missing_required_fact" and res[0].missing_facts == ["rejection_ground"]
    res = resolve_rule_context("NON_DISCLOSURE", f, deck(), "health")
    assert res[0].status == "missing_required_fact"
    assert res[0].missing_facts == [] and res[0].absent_facts == ["rejection_ground"]


def test_blocking_matches_the_apps_ready_for_rules_gate():
    cases = [
        (facts(**PORT), {"ported_from_date": fv("2014", "needs_confirmation")}),
        (facts(**ND), {"cashless_request_at": fv(datetime(2025, 4, 15), "needs_confirmation")}),
        (facts(**ND), {"fraud_alleged": fv(False, "needs_confirmation")}),
        (facts(**ND), {"inception_date": fv(date(2019, 1, 1), "needs_confirmation")}),
    ]
    for f, unresolved in cases:
        app_view = {**f, **unresolved}
        card = [c for c in deck() if (c.rule_id, c.version) == ("MORATORIUM_60M", 1)]
        ready = ready_for_rules(app_view, card)
        res = resolve_rule_context("NON_DISCLOSURE", f, deck(), "health", unresolved=unresolved)
        assert (res[0].status != "missing_required_fact") == ready


# ---------- product line ----------

@pytest.mark.parametrize("line", ["life", "credit_life", "crop", "accident", "motor", "other", "unknown", None])
def test_other_product_lines_never_invoke_health_rules(line):
    res = resolve_rule_context("NON_DISCLOSURE", facts(**ND), deck(), line)
    assert [r.status for r in res] == ["unsupported_product"]
    assert applicable_cards(res, deck()) == []


def test_health_product_is_supported():
    assert resolve_rule_context("NON_DISCLOSURE", facts(**ND), deck(), "health")[0].status == "applicable"


def test_resolver_trace_is_json_serialisable():
    res = resolve_rule_context("NON_DISCLOSURE", facts(**ND), deck(), "health")
    import json
    json.dumps([r.model_dump(mode="json") for r in res])
