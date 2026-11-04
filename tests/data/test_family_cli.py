"""CLI: cases issues set-family / families / apply-families, cases accept-exact-facts; the
reproducible relabel file of the 1 Nov review."""
import json
from pathlib import Path

import pytest
import yaml

from sarthi.core.models import ISSUE_FAMILIES
from sarthi.core.store import Store
from sarthi.data import case_issues, cli

RELABEL = Path(cli.__file__).with_name("family_relabel_1nov.yaml")
SHA = "d" * 64


@pytest.fixture
def datadir(tmp_path, monkeypatch):
    monkeypatch.setenv("SARTHI_DATA_DIR", str(tmp_path))
    s = Store(tmp_path / "bima_sarthi.duckdb")
    s.init()
    s.upsert("case", [dict(case_id="c1", source_sha256=SHA, product_line="health")], key=["case_id"])
    s.upsert("case_issue", [dict(case_id="c1", issue="MORATORIUM_60M", holding="for_policyholder",
                                 holding_quote="q", page_no=1, status="rejected", reviewer_note="n")],
             key=["case_id", "issue"])
    s.upsert("document_page", [dict(sha256=SHA, page_no=1, text="waiting period exclusion", char_count=1,
                                    has_text_layer=True, image_path=None)], key=["sha256", "page_no"])
    s.close()
    return tmp_path


def open_(datadir):
    return Store(datadir / "bima_sarthi.duckdb")


def test_set_family_command(datadir, capsys):
    assert cli.main(["cases", "issues", "set-family", "c1", "MORATORIUM_60M", "NON_DISCLOSURE",
                     "--note", "real issue"]) == 0
    assert "NON_DISCLOSURE" in capsys.readouterr().out
    with open_(datadir) as s:
        assert s.con.execute("SELECT status, issue_family, family_status FROM case_issue").fetchone() == \
            ("rejected", "NON_DISCLOSURE", "reviewed")


def test_set_family_rejects_unknown_family(datadir, capsys):
    with pytest.raises(SystemExit):
        cli.main(["cases", "issues", "set-family", "c1", "MORATORIUM_60M", "MORATORIUM_60M"])


def test_set_family_unknown_row_is_a_clean_error(datadir, capsys):
    assert cli.main(["cases", "issues", "set-family", "c1", "NOPE", "OTHER"]) == 2
    assert "error:" in capsys.readouterr().err


def test_families_command_writes_the_coverage_report(datadir, tmp_path, capsys):
    out = tmp_path / "review" / "coverage.md"
    assert cli.main(["cases", "issues", "families", "--out", str(out)]) == 0
    assert "Coverage is not accuracy" in out.read_text()


def test_accept_exact_facts_command(datadir, capsys):
    with open_(datadir) as s:
        s.upsert("case_fact", [dict(case_id="c1", field="cited_clause", value=json.dumps("Excl 2"),
                                    quote="waiting period", page_no=1, confidence=1.0,
                                    status="extracted", reviewer_note=None)], key=["case_id", "field"])
    assert cli.main(["cases", "accept-exact-facts", "c1"]) == 0
    out = capsys.readouterr().out
    assert "c1" in out and "accepted 1" in out
    with open_(datadir) as s:
        assert s.con.execute("SELECT status FROM case_fact").fetchone()[0] == "reviewed"


def test_accept_exact_facts_requires_explicit_case_ids(datadir):
    with pytest.raises(SystemExit):
        cli.main(["cases", "accept-exact-facts"])


# ---------- the 1 Nov relabel file ----------

def test_relabel_file_is_valid_and_covers_the_14_cases():
    rows = yaml.safe_load(RELABEL.read_text())["relabel"]
    assert {r["case_id"] for r in rows} == {
        "ik_79121837", "ik_31366034", "ik_55284993", "ik_98838150", "ik_61348487", "ik_93195318",
        "ik_62769190", "ik_54612895", "ik_185595546", "ik_149919666", "ik_140785688", "ik_75424763",
        "ik_191559903", "ik_133560673"}
    assert all(r["family"] in ISSUE_FAMILIES and r["issue"] for r in rows)
    got = {(r["case_id"], r["issue"]): r["family"] for r in rows}
    assert got[("ik_93195318", "EXCLUSION_LISTED")] == got[("ik_93195318", "MORATORIUM_60M")] == \
        got[("ik_93195318", "PED_WAIT_36M")] == "NON_DISCLOSURE"
    assert got[("ik_185595546", "MORATORIUM_60M")] == "OTHER"
    assert got[("ik_191559903", "MORATORIUM_60M")] == "CLAIM_NOTIFICATION_DELAY"
    assert got[("ik_140785688", "SPECIFIC_WAIT")] == "OTHER"
    assert ("ik_79121837", "PORTABILITY_CREDIT") not in got   # stays as it is


def test_apply_family_relabels_is_all_or_nothing_and_idempotent(datadir, tmp_path):
    f = tmp_path / "r.yaml"
    f.write_text(yaml.safe_dump({"relabel": [
        {"case_id": "c1", "issue": "MORATORIUM_60M", "family": "NON_DISCLOSURE", "note": "n"},
        {"case_id": "c1", "issue": "MISSING", "family": "OTHER", "note": "n"}]}))
    with open_(datadir) as s:
        with pytest.raises(KeyError):
            case_issues.apply_family_relabels(s, f)
        assert s.con.execute("SELECT issue_family FROM case_issue").fetchone()[0] is None  # nothing written
        f.write_text(yaml.safe_dump({"relabel": [
            {"case_id": "c1", "issue": "MORATORIUM_60M", "family": "NON_DISCLOSURE", "note": "n"}]}))
        assert case_issues.apply_family_relabels(s, f) == 1
        first = s.con.execute("SELECT * FROM case_issue").fetchall()
        case_issues.apply_family_relabels(s, f)
        assert s.con.execute("SELECT * FROM case_issue").fetchall() == first


def test_apply_families_command(datadir, tmp_path, capsys):
    f = tmp_path / "r.yaml"
    f.write_text(yaml.safe_dump({"relabel": [
        {"case_id": "c1", "issue": "MORATORIUM_60M", "family": "OTHER", "note": "n"}]}))
    assert cli.main(["cases", "issues", "apply-families", str(f)]) == 0
    with open_(datadir) as s:
        assert s.con.execute("SELECT issue_family, family_status FROM case_issue").fetchone() == \
            ("OTHER", "reviewed")
