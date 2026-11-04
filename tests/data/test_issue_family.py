"""issue_family / family_status on case_issue: additive schema, validation, CLI, drafted != reviewed."""
import duckdb
import pytest
from pydantic import ValidationError

from sarthi.core.models import ISSUE_FAMILIES, CaseIssue
from sarthi.core.store import Store
from sarthi.data import case_issues


@pytest.fixture
def store(tmp_path):
    s = Store(tmp_path / "t.duckdb")
    s.init()
    return s


def add_issue(store, cid="c1", issue="MORATORIUM_60M", status="rejected", holding="for_policyholder"):
    store.upsert("case_issue", [dict(case_id=cid, issue=issue, holding=holding, holding_quote="q",
                                     page_no=1, status=status, reviewer_note="rejected by Parth")],
                 key=["case_id", "issue"])


def row(store, cid="c1", issue="MORATORIUM_60M"):
    return store.con.execute(
        "SELECT status, holding, holding_quote, reviewer_note, issue_family, family_status "
        "FROM case_issue WHERE case_id=? AND issue=?", [cid, issue]).fetchone()


def test_allowed_families_are_exactly_the_agreed_list():
    assert set(ISSUE_FAMILIES) == {
        "NON_DISCLOSURE", "PED_DEFINITION", "WAITING_PERIOD", "PORTABILITY",
        "POLICY_WORDING_DELIVERY", "EXCLUSION", "CLAIM_SETTLEMENT_DELAY",
        "CLAIM_NOTIFICATION_DELAY", "REJECTION_PROCESS", "DEDUCTION", "CASHLESS_PROCESS",
        "DISCHARGE_PROCESS", "OTHER"}


def test_model_validates_family_and_status():
    CaseIssue(case_id="c", issue="i", holding="not_decided", issue_family="OTHER",
              family_status="drafted")
    with pytest.raises(ValidationError):
        CaseIssue(case_id="c", issue="i", holding="not_decided", issue_family="MORATORIUM_60M")
    with pytest.raises(ValidationError):
        CaseIssue(case_id="c", issue="i", holding="not_decided", family_status="approved")


def test_new_columns_exist_and_default_null(store):
    add_issue(store)
    assert row(store)[4:] == (None, None)


def test_migration_is_idempotent_and_adds_columns_to_an_old_store(tmp_path):
    p = tmp_path / "old.duckdb"
    con = duckdb.connect(str(p))
    con.execute("CREATE TABLE case_issue (case_id VARCHAR, issue VARCHAR, holding VARCHAR, "
                "holding_quote VARCHAR, page_no INTEGER, status VARCHAR, reviewer_note VARCHAR, "
                "PRIMARY KEY (case_id, issue))")
    con.execute("INSERT INTO case_issue VALUES ('c1','MORATORIUM_60M','for_insurer','q',1,"
                "'rejected','n')")
    con.close()
    for _ in range(2):  # init twice: still fine
        s = Store(p)
        s.init()
        s.close()
    s = Store(p)
    cols = [r[0] for r in s.con.execute("DESCRIBE case_issue").fetchall()]
    assert "issue_family" in cols and "family_status" in cols
    assert row(s)[:4] == ("rejected", "for_insurer", "q", "n")  # nothing else touched
    assert row(s)[4:] == (None, None)


def test_set_family_reviewed_keeps_rejected_label_holding_and_quote(store):
    add_issue(store, status="rejected")
    case_issues.set_family(store, "c1", "MORATORIUM_60M", "NON_DISCLOSURE", note="Parth 1 Nov")
    status, holding, quote, note, fam, fstat = row(store)
    assert (status, holding, quote) == ("rejected", "for_policyholder", "q")
    assert (fam, fstat) == ("NON_DISCLOSURE", "reviewed")
    assert note.startswith("rejected by Parth")  # the rejection note survives; family note appended
    assert "family NON_DISCLOSURE" in note and "Parth 1 Nov" in note


def test_set_family_rejects_unknown_family_and_missing_row(store):
    add_issue(store)
    with pytest.raises(ValueError):
        case_issues.set_family(store, "c1", "MORATORIUM_60M", "MORATORIUM_60M")
    with pytest.raises(KeyError):
        case_issues.set_family(store, "c1", "NOPE", "OTHER")
    assert row(store)[4:] == (None, None)


def test_set_family_is_idempotent(store):
    add_issue(store)
    case_issues.set_family(store, "c1", "MORATORIUM_60M", "OTHER", note="x")
    first = row(store)
    case_issues.set_family(store, "c1", "MORATORIUM_60M", "OTHER", note="x")
    assert row(store) == first


def test_drafted_family_is_never_reviewed(store):
    add_issue(store, status="drafted")
    case_issues.set_family(store, "c1", "MORATORIUM_60M", "NON_DISCLOSURE", reviewed=False)
    assert row(store)[4:] == ("NON_DISCLOSURE", "drafted")
    assert case_issues.load_reviewed_families(store) == {}


def test_drafted_family_cannot_overwrite_a_reviewed_family(store):
    add_issue(store)
    case_issues.set_family(store, "c1", "MORATORIUM_60M", "OTHER")
    case_issues.set_family(store, "c1", "MORATORIUM_60M", "NON_DISCLOSURE", reviewed=False)
    assert row(store)[4:] == ("OTHER", "reviewed")


def test_load_reviewed_families_includes_rejected_label_rows_but_not_overall(store):
    add_issue(store, issue="MORATORIUM_60M", status="rejected")
    add_issue(store, issue="PED_WAIT_36M", status="reviewed")
    add_issue(store, issue="_overall", status="reviewed")
    case_issues.set_family(store, "c1", "MORATORIUM_60M", "NON_DISCLOSURE")
    case_issues.set_family(store, "c1", "PED_WAIT_36M", "PED_DEFINITION")
    assert case_issues.load_reviewed_families(store) == {
        "c1": {"MORATORIUM_60M": "NON_DISCLOSURE", "PED_WAIT_36M": "PED_DEFINITION"}}


def test_rejected_label_row_with_family_is_still_never_scored(store):
    add_issue(store, status="rejected")
    case_issues.set_family(store, "c1", "MORATORIUM_60M", "NON_DISCLOSURE")
    assert case_issues.load_reviewed_issues(store) == {}
