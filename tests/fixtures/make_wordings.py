"""Generate tests/fixtures/wording_a.pdf and wording_b.pdf (run once; PDFs are committed).

Obviously-fake fixture wordings: three pages, each with a running header, footer and page
number that differ between insurers. The bodies are identical except clause 4.2. Clause 4.1
contains body lines starting with digits and spans the page 2 / page 3 break.
"""
from pathlib import Path

import pymupdf

PAGES = [
    [
        "FIXTURE WORDING - not real policy text",
        "1 Definitions",
        "1.1 Hospital means a fixture institution with ten beds.",
        "2 Coverage",
        "2.1 Inpatient care is covered up to the fixture sum insured.",
        "3 Benefits",
        "3.1 Day care procedures are covered as listed in the fixture annexure.",
    ],
    [
        "4 Exclusions",
        "4.1 Pre-existing diseases (Code Excl01)",
        "Expenses related to a fixture condition present before the start date are",
        "excluded until continuous cover of",
        "24 months has been completed and, for listed ailments, a further period of",
        "2 Years of fixture waiting time has passed without a break in the policy,",
        "and until the insurer has received the fixture proposal form in full",
    ],
    [
        "and the fixture declaration has been accepted.",
        None,  # clause 4.2 goes here (differs per wording)
        "5 Claims",
        "5.1 Notice of claim must reach the fixture insurer in 48 hours.",
    ],
]
CLAUSE_42 = {
    "a": ["4.2 Specified disease waiting period (Code Excl02)",
          "Expenses for listed fixture ailments are excluded for 24 months."],
    "b": ["4.2 Specified disease waiting period (Code Excl02)",
          "Expenses for listed fixture ailments are excluded for 36 months."],
}
FURNITURE = {
    "a": ("ACME FIXTURE INSURANCE - Arogya Sanjeevani Policy Wording", "Acme Tower, Fixture City 000001"),
    "b": ("ZETA FIXTURE GENERAL - Arogya Sanjeevani Policy Wording", "Zeta House, Sample Town 000002"),
}


def make(name: str, variant: str) -> None:
    header, footer = FURNITURE[variant]
    doc = pymupdf.open()
    for n, body in enumerate(PAGES, start=1):
        lines = []
        for line in body:
            lines.extend(CLAUSE_42[variant] if line is None else [line])
        page = doc.new_page()
        page.insert_text((72, 40), header)
        for i, line in enumerate(lines):
            page.insert_text((72, 90 + 18 * i), line)
        page.insert_text((72, 790), footer)
        page.insert_text((72, 805), f"Page {n} of {len(PAGES)}")
        page.insert_text((300, 820), f"- {n} -")
    doc.save(Path(__file__).with_name(name))


if __name__ == "__main__":
    make("wording_a.pdf", "a")
    make("wording_b.pdf", "b")
