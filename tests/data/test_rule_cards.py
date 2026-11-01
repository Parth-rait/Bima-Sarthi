import json
import logging
import shutil
from datetime import date, datetime
from pathlib import Path

import pytest

from sarthi.core.inputs import KNOWN_INPUTS, REJECTION_GROUNDS
from sarthi.core.models import RuleCard
from sarthi.core.store import Store
from sarthi.data.parse_docs import parse_source
from sarthi.data.rule_cards import (
    NotVerified, UnknownInput, approve, approved_cards, disable, load_seed, verify_quote,
)

FIX = Path(__file__).parent.parent / "fixtures" / "two_page.pdf"
SHA = "b" * 64
SEED = Path(__file__).parents[2] / "rules" / "seed"
QUOTE = "Clause 4.1 Moratorium period applies after 60 months."


def _store(tmp_path):
    s = Store(tmp_path / "t.duckdb")
    s.init()
    raw = tmp_path / "raw"
    raw.mkdir()
    shutil.copyfile(FIX, raw / f"{SHA}.pdf")
    parse_source(SHA, s)
    return s


def _put(store, **kw):
    base = dict(rule_id="R1", version=1, source_sha256=SHA, quote=QUOTE,
                in_force_from=date(2024, 4, 1))
    base.update(kw)
    card = RuleCard(**base)
    row = card.model_dump(mode="json")
    for k in ("triggers", "inputs", "params"):
        row[k] = json.dumps(row[k])
    store.upsert("rule_card", [row], key=["rule_id", "version"])
    return card


def _row(store, rid="R1"):
    return store.con.execute(
        "SELECT status, approved_by, approved_at, page_no, status_note FROM rule_card "
        "WHERE rule_id=?", [rid]).fetchone()


def test_quote_found_exact(tmp_path):
    store = _store(tmp_path)
    qc = verify_quote(_put(store), store)
    assert qc.found is True and qc.page_no == 2 and qc.score == 100.0


def test_quote_whitespace_insensitive(tmp_path):
    store = _store(tmp_path)
    qc = verify_quote(_put(store, quote="Clause 4.1   Moratorium\nperiod applies"), store)
    assert qc.found and qc.page_no == 2


def test_quote_wrong_page_not_found(tmp_path):
    store = _store(tmp_path)
    assert not verify_quote(_put(store, page_no=1), store).found


def test_null_quote_or_source_not_found(tmp_path):
    store = _store(tmp_path)
    for kw in ({"quote": None}, {"source_sha256": None}):
        qc = verify_quote(_put(store, **kw), store)
        assert (qc.found, qc.page_no, qc.score) == (False, None, 0.0)


def test_quote_not_found_blocks_approval(tmp_path):
    store = _store(tmp_path)
    _put(store, quote="Clause 4.1 Moratorium period applies after 48 months.")
    with pytest.raises(NotVerified):
        approve("R1", 1, "parth", store)
    assert _row(store)[0] == "draft"


def test_approve_sets_fields(tmp_path):
    store = _store(tmp_path)
    _put(store)
    approve("R1", 1, "parth", store)
    status, by, at, page, _ = _row(store)
    assert (status, by, page) == ("approved", "parth", 2)
    assert isinstance(at, datetime)


def test_disable_stores_reason(tmp_path):
    store = _store(tmp_path)
    _put(store)
    disable("R1", 1, "quote not found", store)
    row = _row(store)
    assert row[0] == "disabled" and row[4] == "quote not found"


def test_unknown_input_rejected(tmp_path):
    store = _store(tmp_path)
    (tmp_path / "bad.yaml").write_text(
        "rule_id: BAD\nversion: 1\nsource_id: x\ncondition: foo > 1\n")
    with pytest.raises(UnknownInput) as e:
        load_seed(tmp_path, store)
    assert e.value.args[0] == "foo"


def test_approved_cards_respects_dates(tmp_path):
    store = _store(tmp_path)
    _put(store, params={"n": 1}, triggers=["exclusion"])
    approve("R1", 1, "parth", store)
    assert approved_cards(store, date(2023, 12, 31)) == []
    cards = approved_cards(store, date(2024, 6, 1))
    assert [c.rule_id for c in cards] == ["R1"]
    assert cards[0].params == {"n": 1} and cards[0].triggers == ["exclusion"]


def test_approved_cards_excludes_ended_and_unapproved(tmp_path):
    store = _store(tmp_path)
    _put(store, in_force_to=date(2025, 1, 1))
    _put(store, rule_id="R2")  # draft
    approve("R1", 1, "parth", store)
    assert approved_cards(store, date(2025, 1, 1)) == []
    assert len(approved_cards(store, date(2024, 12, 31))) == 1


def _valid_condition(cond):
    from sarthi.core.expr import names
    names(cond)  # raises on an unparsable or disallowed expression
    return True


def test_seed_loads_18_draft_rows_for_14_rule_ids(tmp_path):
    store = _store(tmp_path)
    assert load_seed(SEED, store) == 18  # 14 cards at version 1 + 4 pre-2024 cards at version 0
    rows = store.con.execute(
        "SELECT rule_id, version, status, approved_by, approved_at, condition FROM rule_card"
    ).fetchall()
    assert len(rows) == 18
    assert len({r[0] for r in rows}) == 14
    assert sorted(r[1] for r in rows).count(1) == 14
    assert sorted(r[1] for r in rows).count(0) == 4
    assert all(r[2] == "draft" and r[3] is None and r[4] is None for r in rows)
    assert all(r[5] is None or (r[5].strip() and _valid_condition(r[5])) for r in rows)
    assert load_seed(SEED, store) == 0  # unchanged seed: nothing rewritten
    assert store.con.execute("SELECT count(*) FROM rule_card").fetchone()[0] == 18


def test_seed_triggers_and_inputs_in_vocabulary(tmp_path):
    store = _store(tmp_path)
    load_seed(SEED, store)
    for t, i in store.con.execute("SELECT triggers, inputs FROM rule_card").fetchall():
        assert set(json.loads(t)) <= set(REJECTION_GROUNDS)
        assert set(json.loads(i)) <= KNOWN_INPUTS


def test_cli_rules_load_verify_disable(tmp_path, monkeypatch, capsys):
    from sarthi.data import cli
    monkeypatch.setenv("SARTHI_DATA_DIR", str(tmp_path / "d"))
    monkeypatch.chdir(Path(__file__).parents[2])
    assert cli.main(["rules", "load"]) == 0
    assert cli.main(["rules", "verify"]) == 0
    out = capsys.readouterr().out
    assert "MORATORIUM_60M" in out and "draft" in out and "False" in out
    assert cli.main(["rules", "approve", "MORATORIUM_60M", "--version", "1", "--by", "p"]) == 2
    assert cli.main(["rules", "disable", "MORATORIUM_60M", "--version", "1",
                     "--reason", "no source"]) == 0
    s = cli.open_store()
    assert s.con.execute("SELECT status FROM rule_card WHERE rule_id='MORATORIUM_60M' "
                         "AND version=1").fetchone()[0] == "disabled"


def test_approved_cards_no_date_returns_every_approved_version(tmp_path):
    store = _store(tmp_path)
    _put(store, in_force_to=date(2025, 1, 1))
    _put(store, version=2, in_force_from=date(2025, 1, 1))
    approve("R1", 1, "parth", store)
    approve("R1", 2, "parth", store)
    assert [c.version for c in approved_cards(store)] == [1, 2]


def test_approved_cards_drops_card_whose_quote_no_longer_verifies(tmp_path, caplog):
    store = _store(tmp_path)
    _put(store)
    approve("R1", 1, "parth", store)
    store.con.execute("UPDATE rule_card SET quote='Totally different text' WHERE rule_id='R1'")
    with caplog.at_level(logging.WARNING):
        assert approved_cards(store) == []
    assert "R1" in caplog.text


def _seed_one(tmp_path, quote=QUOTE):
    d = tmp_path / "seed"
    d.mkdir(exist_ok=True)
    (d / "R1.yaml").write_text(
        f"rule_id: R1\nversion: 1\nsource_id: src\nquote: \"{quote}\"\ntriggers: [exclusion]\n")
    return d


def _store_with_source(tmp_path):
    store = _store(tmp_path)
    store.con.execute("INSERT INTO source (source_id, sha256) VALUES ('src', ?)", [SHA])
    return store


def test_reload_unchanged_seed_keeps_approval(tmp_path):
    store = _store_with_source(tmp_path)
    d = _seed_one(tmp_path)
    assert load_seed(d, store) == 1
    approve("R1", 1, "parth", store)
    assert load_seed(d, store) == 0
    status, by, at, page, _ = _row(store)
    assert (status, by, page) == ("approved", "parth", 2) and at is not None


def test_reload_edited_seed_resets_to_draft(tmp_path):
    store = _store_with_source(tmp_path)
    approve_dir = _seed_one(tmp_path)
    load_seed(approve_dir, store)
    approve("R1", 1, "parth", store)
    d = _seed_one(tmp_path, quote="Clause 4.1 Moratorium period applies after 48 months.")
    assert load_seed(d, store) == 1
    assert _row(store)[:3] == ("draft", None, None)


def test_reload_adds_new_card_as_draft_and_keeps_others(tmp_path):
    store = _store_with_source(tmp_path)
    d = _seed_one(tmp_path)
    load_seed(d, store)
    approve("R1", 1, "parth", store)
    (d / "R2.yaml").write_text("rule_id: R2\nversion: 1\nsource_id: src\n")
    assert load_seed(d, store) == 1
    rows = dict(store.con.execute("SELECT rule_id, status FROM rule_card").fetchall())
    assert rows == {"R1": "approved", "R2": "draft"}


def test_approval_body_shows_everything_the_reviewer_decides_on():
    from sarthi.data.rule_cards import approval_body
    card = RuleCard(rule_id="R9", version=2, title_en="Nine", quote="Quote text here.", page_no=3,
                    in_force_from=date(2024, 4, 1), in_force_to=date(2026, 1, 1),
                    applies_by="claim_date", triggers=["non_disclosure"], inputs=["x"],
                    params={"moratorium_months": 60}, condition="x >= 60",
                    if_true="CHALLENGEABLE", if_false="CONSISTENT")
    body = approval_body(card, page_no=4)
    for needle in ("Nine", "> Quote text here.", "page 4", "x >= 60", "CHALLENGEABLE", "CONSISTENT",
                   "2024-04-01", "2026-01-01", "claim_date", "non_disclosure", "moratorium_months", "60"):
        assert needle in body, needle
    open_ended = approval_body(card.model_copy(update={"in_force_to": None}), page_no=4)
    assert "no end date" in open_ended


# ---------- per-parameter sources (Parth's 1 Nov 2026 GRIEVANCE_ROUTE decision) ----------

def _np(value, quote, page, source_id="src"):
    return {"value": value, "unit": "months", "source_id": source_id,
            "page_no": page, "quote": quote}


def _param_store(tmp_path):
    store = _store(tmp_path)
    store.con.execute("INSERT INTO source (source_id, sha256) VALUES ('src', ?)", [SHA])
    return store


def test_nested_params_round_trip_through_store(tmp_path):
    from sarthi.data.rule_cards import _get
    store = _param_store(tmp_path)
    params = {"a": _np(1, "Page one. General conditions", 1), "flat": 3}
    _put(store, params=params)
    assert _get(store, "R1", 1).params == params


def test_nested_param_missing_key_is_invalid():
    with pytest.raises(ValueError):
        RuleCard(rule_id="R", version=1, params={"a": {"value": 1, "unit": "months"}})


def test_approve_checks_param_quotes_ok(tmp_path):
    store = _param_store(tmp_path)
    _put(store, params={"a": _np(1, "Page one.   General conditions", 1)})
    approve("R1", 1, "parth", store)
    assert _row(store)[0] == "approved"


def test_approve_refuses_param_quote_not_found(tmp_path):
    store = _param_store(tmp_path)
    _put(store, params={"a": _np(1, "text that is nowhere", 1)})
    with pytest.raises(NotVerified, match="a"):
        approve("R1", 1, "parth", store)
    assert _row(store)[0] == "draft"


def test_approve_refuses_param_quote_on_wrong_page(tmp_path):
    store = _param_store(tmp_path)
    _put(store, params={"a": _np(1, "Page one. General conditions", 2)})
    with pytest.raises(NotVerified):
        approve("R1", 1, "parth", store)


def test_approve_refuses_param_with_unknown_source(tmp_path):
    store = _param_store(tmp_path)
    _put(store, params={"a": _np(1, "Page one.", 1, source_id="nope")})
    with pytest.raises(NotVerified):
        approve("R1", 1, "parth", store)


def test_approved_cards_drops_card_with_unverifiable_param_quote(tmp_path):
    store = _param_store(tmp_path)
    _put(store, params={"a": _np(1, "Page one.", 1)})
    approve("R1", 1, "parth", store)
    p = json.dumps({"a": _np(1, "gone", 1)})
    store.con.execute("UPDATE rule_card SET params=? WHERE rule_id='R1'", [p])
    assert approved_cards(store) == []


def test_verify_params_lists_each_param(tmp_path):
    from sarthi.data.rule_cards import verify_params
    store = _param_store(tmp_path)
    card = _put(store, params={"a": _np(1, "Page one.", 1), "b": _np(2, "nope", 2), "flat": 3})
    got = {n: qc.found for n, qc in verify_params(card, store)}
    assert got == {"a": True, "b": False}


def test_cli_verify_shows_param_checks(tmp_path, monkeypatch, capsys):
    from sarthi.data import cli
    monkeypatch.setenv("SARTHI_DATA_DIR", str(tmp_path / "d"))
    s = cli.open_store()
    s.init()
    shutil.copyfile(FIX, tmp_path / "x.pdf")
    _put(s, params={"a": _np(1, "nope", 1)})
    assert cli.main(["rules", "verify"]) == 0
    out = capsys.readouterr().out
    assert "param a" in out and "False" in out


def test_seed_grievance_route_params_are_sourced():
    import yaml
    d = yaml.safe_load((SEED / "GRIEVANCE_ROUTE.yaml").read_text(encoding="utf-8"))
    d.pop("source_id")
    card = RuleCard(**d)
    assert set(card.params) == {"insurer_reply_days", "ombudsman_wait_months",
                                "ombudsman_limit_months", "ombudsman_claim_limit_inr",
                                "ombudsman_award_cap_inr"}
    assert card.params["insurer_reply_days"]["value"] == 14
    assert card.params["ombudsman_wait_months"]["value"] == 1
    assert card.params["ombudsman_claim_limit_inr"]["value"] == 5000000
    assert card.params["ombudsman_award_cap_inr"]["value"] == 3000000


# ---------- round 2 (R98b): GRIEVANCE_ROUTE needs all five sourced params to be approved ----------

G_KEYS = ("insurer_reply_days", "ombudsman_wait_months", "ombudsman_limit_months",
          "ombudsman_claim_limit_inr", "ombudsman_award_cap_inr")


def _g_params(**over):
    p = {k: _np(1, "Page one.", 1) for k in G_KEYS}
    p.update(over)
    return p


def test_approve_grievance_with_all_five_sourced_params(tmp_path):
    store = _param_store(tmp_path)
    _put(store, rule_id="GRIEVANCE_ROUTE", params=_g_params())
    approve("GRIEVANCE_ROUTE", 1, "parth", store)
    assert _row(store, "GRIEVANCE_ROUTE")[0] == "approved"


def test_approve_grievance_refuses_flat_params(tmp_path):
    store = _param_store(tmp_path)
    flat = {"insurer_reply_days": 15, "ombudsman_wait_days": 30,
            "ombudsman_limit_months": 12, "ombudsman_cap_inr": 5000000}
    _put(store, rule_id="GRIEVANCE_ROUTE", params=flat)
    with pytest.raises(NotVerified, match="insurer_reply_days"):
        approve("GRIEVANCE_ROUTE", 1, "parth", store)
    assert _row(store, "GRIEVANCE_ROUTE")[0] == "draft"


@pytest.mark.parametrize("missing", G_KEYS)
def test_approve_grievance_refuses_when_a_param_is_missing(tmp_path, missing):
    store = _param_store(tmp_path)
    p = _g_params()
    del p[missing]
    _put(store, rule_id="GRIEVANCE_ROUTE", params=p)
    with pytest.raises(NotVerified, match=missing):
        approve("GRIEVANCE_ROUTE", 1, "parth", store)


def test_approve_grievance_refuses_one_flat_param_among_nested(tmp_path):
    store = _param_store(tmp_path)
    _put(store, rule_id="GRIEVANCE_ROUTE", params=_g_params(ombudsman_award_cap_inr=3000000))
    with pytest.raises(NotVerified, match="ombudsman_award_cap_inr"):
        approve("GRIEVANCE_ROUTE", 1, "parth", store)


def test_other_cards_may_still_have_flat_params(tmp_path):
    store = _param_store(tmp_path)
    _put(store, params={"months": 60})
    approve("R1", 1, "parth", store)
    assert _row(store)[0] == "approved"
