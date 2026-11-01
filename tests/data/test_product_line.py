"""product_line: which kind of insurance a case is about. Only 'health' feeds the health rules."""
import pytest
from pydantic import ValidationError

from sarthi.core.models import Case, PRODUCT_LINES
from sarthi.core.store import Store
from sarthi.data import case_issues, cases, cli


@pytest.fixture(autouse=True)
def env(monkeypatch, tmp_path):
    monkeypatch.setenv("SARTHI_DATA_DIR", str(tmp_path))


@pytest.fixture
def store(tmp_path):
    s = Store(tmp_path / "bima_sarthi.duckdb")
    s.init()
    return s


def _case(store, cid, excluded=None, product_line=None):
    store.upsert("case", [dict(case_id=cid, source_sha256=None, forum="X", outcome=None,
                               excluded_reason=excluded, product_line=product_line)],
                 key=["case_id"])


def _issue(store, cid, issue, status):
    store.upsert("case_issue", [dict(case_id=cid, issue=issue, holding="for_insurer",
                                     holding_quote="q", page_no=1, status=status,
                                     reviewer_note=None)], key=["case_id", "issue"])


def test_allowed_values():
    assert set(PRODUCT_LINES) == {"health", "life", "credit_life", "crop", "accident", "motor",
                                  "other", "unknown"}


def test_case_model_accepts_and_rejects_product_line():
    assert Case(case_id="c").product_line is None
    assert Case(case_id="c", product_line="life").product_line == "life"
    with pytest.raises(ValidationError):
        Case(case_id="c", product_line="pet")


def test_column_exists_and_migration_is_additive(store):
    store.init()  # second init must not fail or drop anything
    _case(store, "c1", product_line="health")
    store.init()
    assert store.con.execute('SELECT product_line FROM "case"').fetchone() == ("health",)


def test_refetch_does_not_wipe_curated_columns(store):
    _case(store, "ik_1", excluded="motor", product_line="motor")
    case, row = cases._upsert_case("ik_1", "a" * 64, "text", "Forum", None, None)
    store.upsert("case", [row], key=["case_id"])
    assert store.con.execute(
        'SELECT product_line, excluded_reason FROM "case"').fetchone() == ("motor", "motor")


def test_cli_set_product_line(store, capsys):
    _case(store, "c1")
    assert cli.main(["cases", "set-product-line", "c1", "life"]) == 0
    s2 = Store(store.path)
    assert s2.con.execute('SELECT product_line FROM "case"').fetchone() == ("life",)
    s2.close()
    with pytest.raises(SystemExit):
        cli.main(["cases", "set-product-line", "c1", "pet"])
    assert cli.main(["cases", "set-product-line", "nope", "health"]) != 0


def test_backfill_health_only_with_reviewed_real_issue(store):
    _case(store, "reviewed_real")
    _issue(store, "reviewed_real", "MORATORIUM_60M", "reviewed")
    _case(store, "corrected_real")
    _issue(store, "corrected_real", "non_disclosure", "corrected")
    _case(store, "only_overall")
    _issue(store, "only_overall", "_overall", "reviewed")
    _case(store, "drafted_only")
    _issue(store, "drafted_only", "MORATORIUM_60M", "drafted")
    _case(store, "excluded", excluded="motor")
    _issue(store, "excluded", "MORATORIUM_60M", "reviewed")
    _case(store, "already_life", product_line="life")
    _issue(store, "already_life", "MORATORIUM_60M", "reviewed")
    _case(store, "no_issue")
    counts = case_issues.backfill_product_line(store)
    got = dict(store.con.execute('SELECT case_id, product_line FROM "case"').fetchall())
    assert got == {"reviewed_real": "health", "corrected_real": "health", "only_overall": None,
                   "drafted_only": None, "excluded": None, "already_life": "life",
                   "no_issue": None}
    assert counts["health"] == 2
    assert case_issues.backfill_product_line(store)["health"] == 0  # idempotent


def test_review_sheet_shows_product_line(store, tmp_path):
    _case(store, "c_h", product_line="health")
    _issue(store, "c_h", "MORATORIUM_60M", "drafted")
    _case(store, "c_u")
    _issue(store, "c_u", "MORATORIUM_60M", "drafted")
    out = tmp_path / "sheet.md"
    case_issues.write_review_sheet(store, out)
    t = out.read_text()
    assert "Product line: health" in t
    assert "Product line: unknown" in t
