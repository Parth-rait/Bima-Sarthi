import shutil
from pathlib import Path

import pymupdf

from sarthi.core.store import Store
from sarthi.data.parse_docs import normalise_ws, parse_source, render_page

FIX = Path(__file__).parent.parent / "fixtures" / "two_page.pdf"


def _store(tmp_path):
    s = Store(tmp_path / "t.duckdb")
    s.init()
    return s


def _put(tmp_path, src: Path, sha: str, ext="pdf"):
    raw = tmp_path / "raw"
    raw.mkdir(exist_ok=True)
    shutil.copyfile(src, raw / f"{sha}.{ext}")


def _rows(store, sha):
    return store.con.execute(
        "SELECT page_no, text, has_text_layer, char_count FROM document_page "
        "WHERE sha256=? ORDER BY page_no", [sha]).fetchall()


def test_pages_and_text(tmp_path):
    store = _store(tmp_path)
    _put(tmp_path, FIX, "a" * 64)
    assert parse_source("a" * 64, store) == 2
    rows = _rows(store, "a" * 64)
    assert [r[0] for r in rows] == [1, 2]
    assert "Clause 4.1" in rows[1][1]
    assert rows[1][2] is True
    assert parse_source("a" * 64, store) == 2  # idempotent
    assert len(_rows(store, "a" * 64)) == 2


def test_no_text_layer_flagged(tmp_path):
    img = pymupdf.open()
    p = img.new_page()
    pix = pymupdf.Pixmap(pymupdf.csRGB, pymupdf.IRect(0, 0, 50, 50), False)
    pix.clear_with(200)
    p.insert_image(pymupdf.Rect(10, 10, 200, 200), pixmap=pix)
    f = tmp_path / "img.pdf"
    img.save(f)
    store = _store(tmp_path)
    _put(tmp_path, f, "b" * 64)
    assert parse_source("b" * 64, store) == 1
    rows = _rows(store, "b" * 64)
    assert rows[0][2] is False


def test_html_and_md_single_page(tmp_path):
    store = _store(tmp_path)
    h = tmp_path / "x.html"
    h.write_text("<html><head><style>p{}</style><script>var x=1;</script></head>"
                 "<body><p>Hello   <b>world</b></p><p>Second</p></body></html>")
    _put(tmp_path, h, "c" * 64, "html")
    assert parse_source("c" * 64, store) == 1
    r = _rows(store, "c" * 64)[0]
    assert "Hello" in r[1] and "world" in r[1] and "var x" not in r[1] and "p{}" not in r[1]
    assert r[2] is True
    m = tmp_path / "x.md"
    m.write_text("# Title\n\nbody text that is long enough to count")
    _put(tmp_path, m, "d" * 64, "md")
    assert parse_source("d" * 64, store) == 1
    assert _rows(store, "d" * 64)[0][1].startswith("# Title")


def test_unknown_extension_skipped(tmp_path):
    store = _store(tmp_path)
    b = tmp_path / "x.bin"
    b.write_bytes(b"zz")
    _put(tmp_path, b, "e" * 64, "bin")
    assert parse_source("e" * 64, store) == 0


def test_render_page_writes_png(tmp_path):
    store = _store(tmp_path)
    _put(tmp_path, FIX, "a" * 64)
    out = render_page("a" * 64, 2, store=store)
    assert out == tmp_path / "pages" / ("a" * 64) / "2.png"
    assert out.read_bytes()[:4] == b"\x89PNG"


def test_normalise_ws():
    assert normalise_ws("a\n  b – c") == "a b - c"
    assert normalise_ws("  x y ‐ z — w ") == "x y - z - w"
    assert normalise_ws("‘a’ “b”") == "'a' \"b\""
