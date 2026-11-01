import os
import time
from pathlib import Path

import pymupdf
import pytest

from sarthi.app.session import Session, UnsupportedUpload, UploadTooLarge, session_root, sweep


@pytest.fixture(autouse=True)
def root(tmp_path, monkeypatch):
    monkeypatch.setenv("SARTHI_SESSION_ROOT", str(tmp_path / "sessions"))
    return tmp_path / "sessions"


def make_pdf(n_pages=1, text="Policy schedule text"):
    doc = pymupdf.open()
    for i in range(n_pages):
        page = doc.new_page()
        if text:
            page.insert_text((72, 72), f"{text} {i}")
    data = doc.tobytes()
    doc.close()
    return data


def make_png(w=3000, h=2000):
    pix = pymupdf.Pixmap(pymupdf.csRGB, pymupdf.IRect(0, 0, w, h), False)
    pix.clear_with(255)
    return pix.tobytes("png")


def test_create_under_root_and_delete(root):
    s = Session.create()
    assert s.path.parent == root and s.path.is_dir()
    s.delete()
    assert not s.path.exists()


def test_pdf_split_into_pages_with_text_layer():
    s = Session.create()
    pages = s.add_upload(("letter.pdf", make_pdf(2)))
    assert len(pages) == 2 and all(p.suffix == ".png" and p.exists() for p in pages)
    assert "Policy schedule text 0" in s.page_text(pages[0])
    assert s.page_text(pages[1]) is not None


def test_image_has_no_text_layer_and_is_resized():
    s = Session.create()
    (p,) = s.add_upload(("photo.png", make_png()))
    assert s.page_text(p) is None
    pix = pymupdf.Pixmap(str(p))
    assert max(pix.width, pix.height) == 1600


def test_add_upload_accepts_path(tmp_path):
    f = tmp_path / "x.pdf"
    f.write_bytes(make_pdf(1))
    s = Session.create()
    assert len(s.add_upload(f)) == 1


def test_unsupported_type_rejected():
    s = Session.create()
    with pytest.raises(UnsupportedUpload):
        s.add_upload(("notes.docx", b"x"))


def test_upload_limits_pages():
    s = Session.create()
    s.add_upload(("a.pdf", make_pdf(20)))
    with pytest.raises(UploadTooLarge):
        s.add_upload(("b.pdf", make_pdf(1)))
    assert len(list(s.path.glob("*.png"))) == 20


def test_upload_limits_21_pages_keeps_nothing():
    s = Session.create()
    with pytest.raises(UploadTooLarge):
        s.add_upload(("a.pdf", make_pdf(21)))
    assert list(s.path.iterdir()) == []


def test_upload_limits_bytes(monkeypatch):
    s = Session.create()
    with pytest.raises(UploadTooLarge):
        s.add_upload(("big.png", b"\x89PNG" + b"0" * (25 * 1024 * 1024)))
    assert list(s.path.iterdir()) == []


def test_session_deleted_after_sweep(root):
    old, new = Session.create(), Session.create()
    past = time.time() - 7200
    os.utime(old.path, (past, past))
    assert sweep() == 1
    assert not old.path.exists() and new.path.exists()


@pytest.mark.parametrize("val", ["", "   "])
def test_empty_root_env_falls_back_to_default(monkeypatch, val):
    monkeypatch.setenv("SARTHI_SESSION_ROOT", val)
    assert session_root() == Path("/tmp/sarthi")


def test_sweep_only_deletes_uuid_directories(root):
    import uuid
    root.mkdir(parents=True)
    past = time.time() - 7200
    stray = root / "not-a-session"
    stray.mkdir()
    target = root.parent / "outside"
    target.mkdir()
    link = root / str(uuid.uuid4())
    link.symlink_to(target, target_is_directory=True)
    stray_file = root / str(uuid.uuid4())
    stray_file.write_text("x")
    real = Session.create()
    for p in (stray, real.path):
        os.utime(p, (past, past))
    os.utime(link, (past, past), follow_symlinks=False)
    assert sweep() == 1
    assert stray.exists() and target.exists() and link.is_symlink() and stray_file.exists()
    assert not real.path.exists()


# ---------- fix C: decompression-bomb guard ----------

def _png_header_only(w, h):
    """A tiny, valid-looking PNG header that claims w x h pixels (decoding it would be huge)."""
    import struct, zlib
    def chunk(t, d):
        c = struct.pack(">I", len(d)) + t + d
        return c + struct.pack(">I", zlib.crc32(t + d) & 0xFFFFFFFF)
    ihdr = struct.pack(">IIBBBBB", w, h, 8, 2, 0, 0, 0)
    return b"\x89PNG\r\n\x1a\n" + chunk(b"IHDR", ihdr) + chunk(b"IDAT", zlib.compress(b"\0")) + chunk(b"IEND", b"")


def test_image_over_the_pixel_cap_is_refused_before_decoding(monkeypatch):
    from sarthi.app.session import ImageTooLarge
    s = Session.create()
    decoded = []
    real = pymupdf.Pixmap
    monkeypatch.setattr(pymupdf, "Pixmap", lambda *a, **k: decoded.append(1) or real(*a, **k))
    with pytest.raises(ImageTooLarge) as e:
        s.add_upload(("bomb.png", _png_header_only(30000, 30000)))
    assert "megapixels" in str(e.value) and not decoded and s.pages() == []
    assert isinstance(e.value, UploadTooLarge)


def test_jpeg_over_the_pixel_cap_is_refused():
    import struct
    from sarthi.app.session import ImageTooLarge
    sof = b"\xff\xc0" + struct.pack(">HBHHB", 11, 8, 20000, 20000, 1) + b"\x01\x11\x00"
    jpeg = b"\xff\xd8" + sof + b"\xff\xd9"
    with pytest.raises(ImageTooLarge):
        Session.create().add_upload(("bomb.jpg", jpeg))


def test_normal_photo_is_still_accepted():
    (p,) = Session.create().add_upload(("photo.png", make_png(4000, 3000)))
    assert p.exists()
