"""Private per-user session folders for uploaded documents.

Uploads live only under the session root (default /tmp/sarthi, override with the env var
SARTHI_SESSION_ROOT), never under data/. The folder is deleted after the result, or by
`sweep()` once it is older than an hour.
"""
import os
import shutil
import struct
import time
import uuid
from pathlib import Path

import pymupdf

MAX_PAGES = 20
MAX_BYTES = 25 * 1024 * 1024
MAX_SIDE_PX = 1600
MAX_IMAGE_PIXELS = 40_000_000  # decompression-bomb guard for photos (about 40 megapixels)
IMAGE_EXTS = {".jpg", ".jpeg", ".png"}
ALLOWED_EXTS = IMAGE_EXTS | {".pdf"}


class UploadTooLarge(ValueError):
    pass


class ImageTooLarge(UploadTooLarge):
    pass


class UnsupportedUpload(ValueError):
    pass


def image_pixels(data: bytes) -> int | None:
    """Pixel count read from a PNG or JPEG header without decoding; None if unreadable."""
    if data[:8] == b"\x89PNG\r\n\x1a\n" and data[12:16] == b"IHDR" and len(data) >= 24:
        w, h = struct.unpack(">II", data[16:24])
        return w * h
    if data[:2] == b"\xff\xd8":
        i = 2
        while i + 9 < len(data):
            if data[i] != 0xFF:
                i += 1
                continue
            m = data[i + 1]
            if m == 0xFF:
                i += 1
            elif m in (0x01, 0xD8) or 0xD0 <= m <= 0xD7:
                i += 2
            elif m in (0xC0, 0xC1, 0xC2, 0xC3, 0xC5, 0xC6, 0xC7, 0xC9, 0xCA, 0xCB, 0xCD, 0xCE, 0xCF):
                h, w = struct.unpack(">HH", data[i + 5:i + 9])
                return w * h
            else:
                i += 2 + struct.unpack(">H", data[i + 2:i + 4])[0]
    return None


def session_root() -> Path:
    raw = os.environ.get("SARTHI_SESSION_ROOT", "").strip()
    return Path(raw) if raw else Path("/tmp/sarthi")


def _render(page: "pymupdf.Page", max_side: int) -> "pymupdf.Pixmap":
    r = page.rect
    scale = max_side / max(r.width, r.height)
    return page.get_pixmap(matrix=pymupdf.Matrix(scale, scale), alpha=False)


class Session:
    def __init__(self, path: Path):
        self.path = path
        self._bytes = 0

    @classmethod
    def create(cls) -> "Session":
        path = session_root() / str(uuid.uuid4())
        path.mkdir(parents=True, mode=0o700)
        return cls(path)

    def pages(self) -> list[Path]:
        return sorted(self.path.glob("page_*.png"))

    def page_text(self, page: Path) -> str | None:
        """Text layer of a page (PDFs only); None for photographed pages."""
        t = page.with_suffix(".txt")
        return t.read_text(encoding="utf-8") if t.exists() else None

    def add_upload(self, file: "Path | str | tuple[str, bytes]") -> list[Path]:
        """Add a document: a path, or a (filename, bytes) pair as received from a web form.
        Returns the page PNG paths. On any error nothing from this upload is kept."""
        if isinstance(file, tuple):
            name, data = file
        else:
            name, data = Path(file).name, Path(file).read_bytes()
        ext = Path(name).suffix.lower()
        if ext not in ALLOWED_EXTS:
            raise UnsupportedUpload("Only JPG, PNG and PDF files are accepted.")
        if self._bytes + len(data) > MAX_BYTES:
            raise UploadTooLarge("Uploads are limited to 25 MB in total.")
        existing = len(self.pages())
        if ext in IMAGE_EXTS:
            px = image_pixels(data)
            if px is None:
                raise UnsupportedUpload("This file could not be opened.")
            if px > MAX_IMAGE_PIXELS:
                raise ImageTooLarge(
                    f"This image is too large (over {MAX_IMAGE_PIXELS // 1_000_000} megapixels). "
                    "Please upload a smaller photo or a PDF.")

        try:
            doc = pymupdf.open(stream=data, filetype="pdf" if ext == ".pdf" else ext[1:])
        except Exception as e:
            raise UnsupportedUpload("This file could not be opened.") from e
        with doc:
            if existing + len(doc) > MAX_PAGES:
                raise UploadTooLarge("Uploads are limited to 20 pages in total.")
            rendered: list[tuple[bytes, str | None]] = []
            for page in doc:
                if ext == ".pdf":
                    side = MAX_SIDE_PX
                else:
                    px = pymupdf.Pixmap(data)
                    side = min(MAX_SIDE_PX, max(px.width, px.height))
                text = page.get_text().strip() if ext == ".pdf" else ""
                rendered.append((_render(page, side).tobytes("png"), text or None))

        out: list[Path] = []
        for i, (png, text) in enumerate(rendered, start=existing + 1):
            p = self.path / f"page_{i:03d}.png"
            p.write_bytes(png)
            if text:
                p.with_suffix(".txt").write_text(text, encoding="utf-8")
            out.append(p)
        self._bytes += len(data)
        return out

    def delete(self) -> None:
        shutil.rmtree(self.path, ignore_errors=True)


def _is_session_dir(d: Path) -> bool:
    """A real (non-symlink) directory named by a UUID4: only ever our own sessions."""
    if d.is_symlink() or not d.is_dir():
        return False
    try:
        return str(uuid.UUID(d.name, version=4)) == d.name
    except ValueError:
        return False


def sweep(max_age_s: int = 3600) -> int:
    """Delete session folders whose mtime is older than max_age_s; returns the count."""
    root = session_root()
    if not root.is_dir():
        return 0
    cutoff, n = time.time() - max_age_s, 0
    for d in root.iterdir():
        if _is_session_dir(d) and d.stat().st_mtime < cutoff:
            shutil.rmtree(d, ignore_errors=True)
            n += 1
    return n
