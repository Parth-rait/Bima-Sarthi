import shutil
from pathlib import Path

from sarthi.core.store import Store
from sarthi.data.parse_docs import parse_source
from sarthi.data.policy_index import build_index, find_clause, uniformity_report

FIX = Path(__file__).parent.parent / "fixtures"
SHA_A, SHA_B = "a" * 64, "b" * 64


def _store(tmp_path):
    s = Store(tmp_path / "t.duckdb")
    s.init()
    raw = tmp_path / "raw"
    raw.mkdir()
    for sha, name in ((SHA_A, "wording_a.pdf"), (SHA_B, "wording_b.pdf")):
        shutil.copyfile(FIX / name, raw / f"{sha}.pdf")
        parse_source(sha, s)
    return s


def _built(tmp_path):
    s = _store(tmp_path)
    build_index("acme__arogya_sanjeevani", SHA_A, s)
    build_index("zeta__arogya_sanjeevani", SHA_B, s)
    return s


def test_refs_resolve_to_same_clause(tmp_path):
    s = _built(tmp_path)
    pid = "acme__arogya_sanjeevani"
    found = [find_clause(pid, r, s) for r in
             ("4.1", "Clause 4.1", "Exclusion 4.1 (Code Excl01)", "Excl01", "excl01")]
    assert all(c is not None and c.clause_no == "4.1" for c in found)
    assert "Pre-existing" in found[0].heading
    assert "start date are excluded until" in found[0].text  # spans the line break


def test_clause_spans_pages_and_stops_at_next_heading(tmp_path):
    s = _built(tmp_path)
    c = find_clause("acme__arogya_sanjeevani", "4.2", s)
    assert c.page_no == 3 and "24 months" in c.text and "Claims" not in c.text


def _nos(s, pid):
    return [r[0] for r in s.con.execute(
        "SELECT clause_no FROM policy_clause WHERE product_id=? ORDER BY clause_no", [pid]).fetchall()]


def test_body_lines_starting_with_numbers_are_not_headings(tmp_path):
    s = _built(tmp_path)
    pid = "acme__arogya_sanjeevani"
    assert _nos(s, pid) == ["1", "1.1", "2", "2.1", "3", "3.1", "4", "4.1", "4.2", "5", "5.1"]
    c = find_clause(pid, "4.1", s)
    assert "24 months has been completed" in c.text and "2 Years of fixture" in c.text
    assert "Inpatient" in find_clause(pid, "2.1", s).heading
    assert find_clause(pid, "2", s).text == ""


def test_page_furniture_is_not_clause_text(tmp_path):
    s = _built(tmp_path)
    c = find_clause("acme__arogya_sanjeevani", "4.1", s)
    assert "declaration has been accepted" in c.text  # spans the page 2/3 break
    for junk in ("ACME FIXTURE", "Acme Tower", "Page 3 of 3", "Page 2 of 3", "- 3 -"):
        assert junk not in c.text
    for r in s.con.execute("SELECT text FROM policy_clause").fetchall():
        assert "FIXTURE INSURANCE" not in r[0] and "FIXTURE GENERAL" not in r[0]


def test_unknown_and_conflicting_refs_give_none(tmp_path):
    s = _built(tmp_path)
    pid = "acme__arogya_sanjeevani"
    assert find_clause(pid, "9.9", s) is None
    assert find_clause(pid, "Excl99", s) is None
    assert find_clause(pid, "Exclusion 4.2 (Code Excl01)", s) is None
    assert find_clause("nope", "4.1", s) is None


def test_build_is_idempotent_and_creates_product(tmp_path):
    s = _store(tmp_path)
    n1 = build_index("acme__arogya_sanjeevani", SHA_A, s)
    n2 = build_index("acme__arogya_sanjeevani", SHA_A, s)
    assert n1 == n2 > 0
    assert s.con.execute("SELECT count(*) FROM policy_clause").fetchone()[0] == n1
    row = s.con.execute("SELECT wording_sha256, is_standard_product FROM policy_product").fetchall()
    assert row == [(SHA_A, True)]


def test_uniformity_flags_exactly_the_differing_clause(tmp_path):
    s = _built(tmp_path)
    rows = uniformity_report(s)
    assert {r.insurer for r in rows} == {"zeta__arogya_sanjeevani"}
    assert [r.clause_no for r in rows if not r.matches_reference] == ["4.2"]
    assert sum(r.matches_reference for r in rows) == len(rows) - 1


def test_uniformity_missing_clause_does_not_match(tmp_path):
    s = _built(tmp_path)
    s.con.execute("DELETE FROM policy_clause WHERE product_id='zeta__arogya_sanjeevani' "
                  "AND clause_no='5.1'")
    bad = sorted(r.clause_no for r in uniformity_report(s) if not r.matches_reference)
    assert bad == ["4.2", "5.1"]
    # explicit reference flips the direction
    rows = uniformity_report(s, reference_product_id="zeta__arogya_sanjeevani")
    assert {r.insurer for r in rows} == {"acme__arogya_sanjeevani"}
    assert "5.1" not in [r.clause_no for r in rows]


def test_cli_policy_build_and_report(tmp_path, monkeypatch, capsys):
    from sarthi.data import cli
    monkeypatch.setenv("SARTHI_DATA_DIR", str(tmp_path / "d"))
    raw = tmp_path / "d" / "raw"
    raw.mkdir(parents=True)
    for sha, name in ((SHA_A, "wording_a.pdf"), (SHA_B, "wording_b.pdf")):
        shutil.copyfile(FIX / name, raw / f"{sha}.pdf")
        assert cli.main(["parse", "--sha", sha]) == 0
    assert cli.main(["policy", "build", "--product-id", "acme__arogya_sanjeevani",
                     "--sha", SHA_A, "--insurer", "Acme"]) == 0
    assert cli.main(["policy", "build", "--product-id", "zeta__arogya_sanjeevani",
                     "--sha", SHA_B, "--insurer", "Zeta"]) == 0
    capsys.readouterr()
    assert cli.main(["policy", "report"]) == 0
    out = capsys.readouterr().out
    assert "Zeta" in out and "4.2" in out and "DIFFERS" in out


def _pages_store(tmp_path, pages):
    s = Store(tmp_path / "p.duckdb")
    s.init()
    s.upsert("document_page", [
        {"sha256": "c" * 64, "page_no": i, "text": t, "char_count": len(t),
         "has_text_layer": True, "image_path": None}
        for i, t in enumerate(pages, start=1)], key=["sha256", "page_no"])
    build_index("p", "c" * 64, s)
    return s


def _by_no(s):
    return {r[0]: r[1] for r in s.con.execute(
        "SELECT clause_no, text FROM policy_clause WHERE product_id='p'").fetchall()}


def test_contents_list_is_replaced_by_body(tmp_path):
    toc = "Contents\n1 Definitions\n2 Coverage\n3 Exclusions\n12 Grievance"
    body = "1 Definitions\nHospital means a fixture place.\n2 Coverage\nCovered things.\n3 Exclusions\nNot covered."
    got = _by_no(_pages_store(tmp_path, [toc, body]))
    assert got["1"] == "Hospital means a fixture place."
    assert got["2"] == "Covered things." and got["3"] == "Not covered."


def test_extract_may_start_at_any_number(tmp_path):
    got = _by_no(_pages_store(tmp_path, ["4 Exclusions\nIntro text.\n4.1 Pre-existing (Code Excl01)\nBody."]))
    assert set(got) == {"4", "4.1"}


def test_small_gap_is_tolerated_large_gap_is_not(tmp_path):
    text = ("4.1 First clause\nA.\n4.2 Second clause\nB.\n4.4 Fourth clause\nC.\n"
            "4.9 Ninth Looking Like A Heading\nD.")
    got = _by_no(_pages_store(tmp_path, [text]))
    assert set(got) == {"4.1", "4.2", "4.4"}
    assert "4.9 Ninth Looking Like A Heading" in got["4.4"]


def test_rejected_candidates_are_logged(tmp_path, caplog):
    import logging
    with caplog.at_level(logging.WARNING, logger="sarthi.data.policy_index"):
        _pages_store(tmp_path, ["1 Definitions\nText\n24 months of cover\n"])
    assert "1 numbered line(s) rejected" in caplog.text


# ---- R88: heading forms and the Excl-code primary uniformity key ----

def test_dotted_and_bracket_heading_forms(tmp_path):
    text = ("1. Definitions\nSome words.\n2) Coverage\nCovered.\n2.1. Inpatient care\nBeds.\n"
            "3. Exclusions\nNot covered.\n3.1) Waiting Periods\nWait.\nx 4. lower case line\n")
    got = _by_no(_pages_store(tmp_path, [text]))
    assert set(got) == {"1", "2", "2.1", "3", "3.1"}
    assert got["2.1"] == "Beds."


def test_dotted_form_still_under_capital_and_sequence_guards(tmp_path):
    text = "1. Definitions\nText\n24. months of cover\n2. coverage in lower case\n9. Far Away Heading\n"
    got = _by_no(_pages_store(tmp_path, [text]))
    assert set(got) == {"1"}


def _wording(sick="Pre-existing disease means a condition for 36 months.", maternity="Maternity is excluded."):
    return [
        "Intro\n1. Definitions\nWords.\n2. Exclusions\n"
        f"2.1. Pre-Existing Diseases (Code- Excl01)\n{sick}\n"
        "2.2 Specific Waiting Period: (Code-Excl02)\nSpecific illness waits two years.\n",
        "2.3 Maternity Expenses (Code - Excl 03):\n" + maternity + "\n3. Claims\nHow to claim.\n",
    ]


def _two_codes_store(tmp_path, other_pages):
    from sarthi.data.policy_index import build_index as bi
    s = Store(tmp_path / "x.duckdb")
    s.init()
    for sha, pages in (("a" * 64, _wording()), ("b" * 64, other_pages)):
        s.upsert("document_page", [
            {"sha256": sha, "page_no": i, "text": t, "char_count": len(t),
             "has_text_layer": True, "image_path": None}
            for i, t in enumerate(pages, start=1)], key=["sha256", "page_no"])
    bi("a_prod", "a" * 64, s)
    bi("b_prod", "b" * 64, s)
    return s


def test_code_uniformity_reports_per_code_and_insurer(tmp_path):
    from sarthi.data.policy_index import code_uniformity_report
    s = _two_codes_store(tmp_path, _wording(sick="Pre-existing means something else, 48 months."))
    rows = {(r.code, r.product_id): r.status for r in code_uniformity_report(s)}
    assert rows[("Excl01", "a_prod")] == "match"  # reference itself
    assert rows[("Excl01", "b_prod")] == "differs"
    assert rows[("Excl02", "b_prod")] == "match"
    assert rows[("Excl03", "b_prod")] == "match"  # spans the page break, stops at "3. Claims"


def test_code_text_ignores_spacing_and_case_and_code_spelling(tmp_path):
    from sarthi.data.policy_index import code_uniformity_report
    other = [p.replace("Excl01", "Excl 01").replace("Code-Excl02", "Code - Excl02")
             .replace("Specific illness", "SPECIFIC   illness") for p in _wording()]
    s = _two_codes_store(tmp_path, other)
    assert {r.status for r in code_uniformity_report(s) if r.product_id == "b_prod"} == {"match"}


def test_code_missing_in_one_wording(tmp_path):
    from sarthi.data.policy_index import code_uniformity_report
    other = [p.replace("(Code-Excl02)", "") for p in _wording()]
    s = _two_codes_store(tmp_path, other)
    rows = {(r.code, r.product_id): r.status for r in code_uniformity_report(s)}
    assert rows[("Excl02", "b_prod")] == "missing"


def test_cli_report_shows_codes_first_then_clause_numbers(tmp_path, monkeypatch, capsys):
    from sarthi.data import cli
    s = _two_codes_store(tmp_path, _wording(sick="Different."))
    monkeypatch.setattr(cli, "open_store", lambda: s)
    assert cli.main(["policy", "report"]) == 0
    out = capsys.readouterr().out
    assert out.index("Excl01") < out.index("clause")
    assert "differs" in out and "match" in out and "Excl03" in out


def test_list_markers_and_page_footers_are_layout_not_content(tmp_path):
    from sarthi.data.policy_index import code_uniformity_report
    a = ["2.1 Pre-Existing (Code- Excl01)\na. First limb.\nb. Second limb.\n2.2 Next (Code- Excl02)\ni. Alpha.\nii. Beta.\n"]
    b = ["2.1 Pre-Existing (Code- Excl01)\n(a) First limb.\n11 | Page\nb) Second limb.\n2.2 Next (Code- Excl02)\n(i) Alpha.\n(ii) Beta.\n"]
    s = Store(tmp_path / "y.duckdb")
    s.init()
    from sarthi.data.policy_index import build_index as bi
    for sha, pages in (("a" * 64, a), ("b" * 64, b)):
        s.upsert("document_page", [{"sha256": sha, "page_no": 1, "text": pages[0], "char_count": 1,
                                    "has_text_layer": True, "image_path": None}], key=["sha256", "page_no"])
    bi("a_prod", "a" * 64, s)
    bi("b_prod", "b" * 64, s)
    assert {r.status for r in code_uniformity_report(s)} == {"match"}


def test_last_code_stops_at_a_bare_heading_number_line(tmp_path):
    from sarthi.data.policy_index import exclusion_texts
    s = Store(tmp_path / "z.duckdb")
    s.init()
    t = "6.1 Maternity (Code- Excl18)\nChildbirth is excluded.\n6.2.\nWaiting periods\nlater text"
    s.upsert("document_page", [{"sha256": "c" * 64, "page_no": 1, "text": t, "char_count": 1,
                                "has_text_layer": True, "image_path": None}], key=["sha256", "page_no"])
    assert exclusion_texts(s, "c" * 64)["Excl18"].text == "Maternity Childbirth is excluded."


def test_code_printed_at_end_of_a_one_line_exclusion(tmp_path):
    from sarthi.data.policy_index import exclusion_texts
    s = Store(tmp_path / "w.duckdb")
    s.init()
    t = ("7.9 Treatment for alcoholism and\nconsequences thereof.(Code- Excl12)\n"
         "7.10\nNature cure clinics. (Code- Excl13)\n7.11 Dietary supplements.\n")
    s.upsert("document_page", [{"sha256": "d" * 64, "page_no": 1, "text": t, "char_count": 1,
                                "has_text_layer": True, "image_path": None}], key=["sha256", "page_no"])
    got = exclusion_texts(s, "d" * 64)
    assert got["Excl12"].text == "Treatment for alcoholism and consequences thereof."
    assert got["Excl13"].text == "Nature cure clinics."


def test_genuinely_different_numbers_still_differ(tmp_path):
    from sarthi.data.policy_index import code_uniformity_report
    s = _two_codes_store(tmp_path, _wording(sick="Pre-existing disease means a condition for 48 months."))
    assert {(r.code, r.status) for r in code_uniformity_report(s) if r.product_id == "b_prod"} >= {("Excl01", "differs")}


# ---- R88 round 2 ----

def _status(tmp_path, a_text, b_text, code="Excl01"):
    from sarthi.data.policy_index import code_uniformity_report
    mk = lambda body: [f"2.1 Thing (Code- {code})\n{body}\n2.2 Next heading\nx\n"]
    s = _store_from(tmp_path, mk(a_text), mk(b_text))
    return {r.product_id: r.status for r in code_uniformity_report(s) if r.code == code}


def _store_from(tmp_path, a, b):
    from sarthi.data.policy_index import build_index as bi
    s = Store(tmp_path / "r2.duckdb")
    s.init()
    for sha, pages in (("a" * 64, a), ("b" * 64, b)):
        s.upsert("document_page", [
            {"sha256": sha, "page_no": i, "text": t, "char_count": len(t),
             "has_text_layer": True, "image_path": None}
            for i, t in enumerate(pages, start=1)], key=["sha256", "page_no"])
    bi("a_prod", "a" * 64, s)
    bi("b_prod", "b" * 64, s)
    return s


def test_parenthetical_numbers_in_a_sentence_are_content(tmp_path):
    assert _status(tmp_path, "Notify within thirty (30) days of loss.",
                   "Notify within thirty (45) days of loss.")["b_prod"] == "differs"


def test_number_before_a_full_stop_in_a_sentence_is_content(tmp_path):
    assert _status(tmp_path, "The limit is 30. Then it resets.",
                   "The limit is 45. Then it resets.")["b_prod"] == "differs"


def test_line_start_enumerators_are_layout_but_item_text_is_not(tmp_path):
    same = _status(tmp_path, "a) alpha cover.\nb) beta cover.", "i. alpha cover.\nii. beta cover.")
    assert same["b_prod"] == "match"
    other = _status(tmp_path, "a) alpha cover.\nb) beta cover.", "a) alpha cover.\nb) gamma cover.")
    assert other["b_prod"] == "differs"


def test_code_spellings_en_dash_bare_and_single_digit(tmp_path):
    from sarthi.data.policy_index import exclusion_texts
    s = Store(tmp_path / "sp.duckdb")
    s.init()
    t = ("2.1 One (Code \u2013 Excl01)\nA.\n2.2 Two (Code-Excl 2)\nB.\nEXCL03 Three\nC.\n"
         "2.4 Four (Code: Excl 04)\nD.\n2.5 Five (Code\u2014 Excl05)\nE.\n2.6 End\nz\n")
    s.upsert("document_page", [{"sha256": "e" * 64, "page_no": 1, "text": t, "char_count": 1,
                                "has_text_layer": True, "image_path": None}], key=["sha256", "page_no"])
    got = exclusion_texts(s, "e" * 64)
    assert sorted(got) == ["Excl01", "Excl02", "Excl03", "Excl04", "Excl05"]
    assert got["Excl02"].text == "Two B." and got["Excl03"].text == "Three C."


def test_two_empty_texts_report_empty_not_match(tmp_path):
    from sarthi.data.policy_index import code_uniformity_report
    s = _store_from(tmp_path, ["(Code- Excl01)\n2. Next\n"], ["(Code- Excl01)\n2. Next\n"])
    assert {r.status for r in code_uniformity_report(s)} == {"empty"}


def test_enumerator_right_after_the_printed_code_is_layout(tmp_path):
    from sarthi.data.policy_index import code_uniformity_report
    s = _store_from(tmp_path, ["2.1 Thing (Code- Excl01) a) alpha cover.\n2.2 Next\nx\n"],
                    ["2.1 Thing (Code- Excl01)\nalpha cover.\n2.2 Next\nx\n"])
    assert {r.status for r in code_uniformity_report(s) if r.code == "Excl01"} == {"match"}


# ---- R88 round 3 / R91 ----

def test_digit_only_markers_are_never_stripped(tmp_path):
    # a wrapped line that starts with a number is content, not an enumerator
    assert _status(tmp_path, "Notify within thirty\n(30) days of loss.",
                   "Notify within thirty\n(45) days of loss.")["b_prod"] == "differs"
    assert _status(tmp_path, "1) alpha cover.", "2) alpha cover.")["b_prod"] == "differs"


def test_number_right_after_the_code_is_kept(tmp_path):
    from sarthi.data.policy_index import exclusion_texts
    s = _store_from(tmp_path, ["2.1 Thing (Code- Excl01) 30. Then pay\n2.2 Next\nx\n"],
                    ["2.1 Thing (Code- Excl01) (30) days notice\n2.2 Next\nx\n"])
    assert exclusion_texts(s, "a" * 64)["Excl01"].text == "Thing 30. Then pay"
    assert exclusion_texts(s, "b" * 64)["Excl01"].text == "Thing (30) days notice"


def test_mid_sentence_references_do_not_start_a_segment(tmp_path):
    from sarthi.data.policy_index import exclusion_texts
    s = Store(tmp_path / "ref.duckdb")
    s.init()
    t = ("2.1 One (Code- Excl01)\nCovered unless see Excl 2 above and as in Code-Excl02 note, or\n"
         "excl 5 years apply.\nExcl 5 years of cover.\n2.2 Two (Code- Excl02)\nB.\n2.3 End\nz\n")
    s.upsert("document_page", [{"sha256": "f" * 64, "page_no": 1, "text": t, "char_count": 1,
                                "has_text_layer": True, "image_path": None}], key=["sha256", "page_no"])
    got = exclusion_texts(s, "f" * 64)
    assert sorted(got) == ["Excl01", "Excl02"]
    assert "see Excl 2 above" in got["Excl01"].text and "as in Code-Excl02 note" in got["Excl01"].text
    assert "excl 5 years apply." in got["Excl01"].text and "Excl 5 years of cover." in got["Excl01"].text
    assert got["Excl02"].text == "Two B."


def test_heading_position_rule_for_codes(tmp_path):
    from sarthi.data.policy_index import code_hits
    # accepted: line start (after a marker), parenthesised, or at the end of the line
    assert [c for _, _, c in code_hits("Code- Excl01 Pre-existing")] == ["Excl01"]
    assert [c for _, _, c in code_hits("2.1 Pre-existing Diseases(Code- Excl01)")] == ["Excl01"]
    assert [c for _, _, c in code_hits("Breach of law: Code- (Excl10)")] == ["Excl10"]
    assert [c for _, _, c in code_hits("(Code \u2013 Excl01) Expenses related")] == ["Excl01"]
    assert [c for _, _, c in code_hits("Care (Code: Excl 1):")] == ["Excl01"]
    assert [c for _, _, c in code_hits("a) EXCL01 Pre-existing")] == ["Excl01"]
    assert [c for _, _, c in code_hits("Excl 01")] == ["Excl01"]
    # rejected: mid-sentence references
    for line in ("as in Code-Excl02 note", "see Excl 2 above", "excl 5 years", "Excl 5 years",
                 "the Excl01 rule applies"):
        assert code_hits(line) == [], line
