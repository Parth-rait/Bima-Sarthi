"""The page script for "What your policy says" and the documents-to-request checklist."""
import json
import re
import shutil
import subprocess
import tempfile
from pathlib import Path

import pytest

from sarthi.app import main


def _html() -> str:
    return (Path(main.__file__).parent / "static" / "index.html").read_text(encoding="utf-8")


def _js() -> str:
    return re.search(r"<script>(.*)</script>", _html(), re.S).group(1)


def test_page_script_passes_node_check():
    node = shutil.which("node")
    if not node:
        pytest.skip("node not available")
    with tempfile.NamedTemporaryFile("w", suffix=".js", delete=False, encoding="utf-8") as f:
        f.write(_js())
    r = subprocess.run([node, "--check", f.name], capture_output=True, text=True)
    assert r.returncode == 0, r.stderr


def test_no_innerhtml_anywhere():
    h = _html()
    assert "innerHTML" not in h and "insertAdjacentHTML" not in h and "outerHTML" not in h
    assert "document.write" not in h


def test_policy_upload_is_a_labelled_optional_file_input_posting_to_the_policy_route():
    js = _js()
    assert 'el("label",{for:"policy-files"},t("pol_l"))' in js and 'id:"policy-files"' in js
    assert "/policy/extract" in js and '"PUT",`/session/${sid}/policy`' in js and '"DELETE",`/session/${sid}/policy`' in js
    assert "(optional)" in re.search(r'en:\{.*?pol_up_h:"([^"]*)"', js, re.S).group(1)


def test_check_does_not_depend_on_the_policy():
    js = _js()
    run = js[js.index('const run=el("button"'):js.index("/* ---- step 3 ---- */")]
    assert "policy" not in run.replace("product_line", "")
    assert "/policy" not in run


def test_new_strings_exist_in_both_languages():
    js = _js()
    en = re.search(r"\ben:\{(.*?)\},\nhi:\{", js, re.S).group(1)
    hi = re.search(r"\nhi:\{(.*?)\}\n\};", js, re.S).group(1)
    keys = lambda blob: set(re.findall(r"(?:^|[,\s])(pol_[a-z_]+):", blob))
    assert keys(en) and keys(en) == keys(hi)
    for k in keys(hi):
        m = re.search(rf'{k}:"([^"]*)"', hi)
        assert m and re.search(r"[ऀ-ॿ]", m.group(1)), k
        assert "_" not in m.group(1)


def test_section_shows_label_value_quote_page_and_the_server_disclaimer():
    js = _js()
    assert "function renderPolicyTerms(" in js and "function renderPolicySection(" in js
    for needle in ("x.label[lang]", "x.display[lang]", "x.message[lang]", "x.quote", "x.page_no",
                   "p.disclaimer[lang]", "p.heading[lang]"):
        assert needle in js, needle


def test_result_screen_renders_policy_and_checklist_and_resets_on_delete():
    js = _js()
    assert "renderPolicySection(policy)" in js and "renderChecklist(result.request_checklist)" in js
    assert "request_checklist:c.request_checklist" in js
    assert "result.request_checklist=ex.request_checklist" in js
    assert "sid=null;facts={};result=null;policy=null;productChoice=null" in js


def test_policy_controls_are_labelled_and_get_the_44px_rule():
    js, h = _js(), _html()
    assert 'type:"file",id:"policy-files"' in js
    assert 'el("label",{for:"pt-"+x.key}' in js and 'el("label",{for:"pc-"+x.key' in js
    assert re.search(r"button,\.btn\{[^}]*min-height:44px", h)
    assert "input[type=text],input[type=file]" in h and "min-height:44px" in h.split("input[type=text]")[1].split("}")[0]
