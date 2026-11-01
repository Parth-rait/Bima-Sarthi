"""Generate tests/fixtures/two_page.pdf (run once; the PDF is committed)."""
from pathlib import Path

import pymupdf

doc = pymupdf.open()
doc.new_page().insert_text((72, 72), "Page one. General conditions of the policy.")
doc.new_page().insert_text((72, 72), "Clause 4.1 Moratorium period applies after 60 months.")
doc.save(Path(__file__).with_name("two_page.pdf"))
