"""Clause index for standard (Arogya Sanjeevani) wordings and a cross-insurer uniformity check."""
import hashlib
import logging
import re
from dataclasses import dataclass

from sarthi.core.models import PolicyClause
from sarthi.core.store import Store
from sarthi.data.parse_docs import normalise_ws

log = logging.getLogger(__name__)

HEADING = re.compile(r"^(\d+(?:\.\d+)*)(?:[.)]\s*|\s+)(.*)$")  # "4 X", "4. X", "4) X", "4.1. X"
STARTS_HEADING = re.compile(r"[A-Z(]")  # real headings begin with a capital letter or "("
PAGE_NO_ONLY = re.compile(r"(?:page\s+)?\d+(?:\s+of\s+\d+)?|-\s*\d+\s*-|\d+\s*\|\s*page", re.I)
CODE = re.compile(r"excl\s*(\d{2})", re.I)  # a code anywhere in clause text (find_clause)
NUMBER = re.compile(r"\d+(?:\.\d+)*")
BARE_HEADING_NO = re.compile(r"\d+(?:\.\d+)+\.?|\d+\.")  # a heading number alone on its line ("6.2.")
# An enumerator is layout only when it is a letter or roman marker ("a. ", "(ii) ", "A) ") at the
# start of a line and followed by text. Digit markers are never stripped: a wrapped line that
# starts "(30) days" is content, and "1) x" vs "2) x" must differ.
LIST_MARKER = re.compile(r"^\(?(?:[a-z]|[ivx]{1,4})[.)]\s+(?=\S)", re.I)
LEADING_MARKER = re.compile(r"^\s*(?:\(?(?:[a-z]|[ivx]{1,4}|\d{1,2}(?:\.\d+)*)[.)]?\s+)?", re.I)
# The printed IRDAI standard exclusion code: "Code- Excl01", "(Code - Excl 18)", "Code- (Excl10)".
# Dashes may be hyphen, en or em dash; one or two digits.
CODE_PREFIXED = re.compile(
    r"\(?\s*code\s*[-\u2013\u2014:]?\s*\(?\s*excl\s*[-\u2013\u2014]?\s*(\d{1,2})(?!\d)\s*\)?", re.I)
# Bare form: zero-padded "Excl01".."Excl19" (title may follow), or any digits when end/punctuation follows.
CODE_BARE = re.compile(
    r"excl\s*[-\u2013\u2014]?\s*(?:(0\d|1\d)(?!\d)|(\d{1,2})(?!\d)(?=\s*(?:[:.)\u2013\u2014-]|$)))", re.I)
CODE_TAIL = re.compile(r"[\s:.,;)\u2013\u2014-]*")


def code_hits(line: str) -> list[tuple[int, int, str]]:
    """Printed exclusion codes in heading position on one line: (start, end, "Excl01").

    Rule (R91): a "Code"-prefixed code counts when it begins the line (after an optional
    list/number marker), or is parenthesised "(Code- Excl05)", or ends the line
    ("Breach of law: Code- (Excl10)"). A bare "Excl01" counts only at the start of the line and
    only when the digits are followed by end of line or punctuation. A reference in the middle
    of a sentence ("as in Code-Excl02 note", "see Excl 2 above", "excl 5 years") never counts.
    """
    hits = []
    for m in CODE_PREFIXED.finditer(line):
        text = m.group(0).strip()
        begins = LEADING_MARKER.fullmatch(line[:m.start()]) is not None
        ends = CODE_TAIL.fullmatch(line[m.end():]) is not None
        bracketed = text.startswith("(") and text.endswith(")")
        if begins or ends or bracketed:
            hits.append((m.start(), m.end(), f"Excl{int(m.group(1)):02d}"))
    lead = LEADING_MARKER.match(line).end()
    m = CODE_BARE.match(line, lead)
    if m and not any(h[0] <= m.start() < h[1] for h in hits):
        hits.append((m.start(), m.end(), f"Excl{int(m.group(1) or m.group(2)):02d}"))
    return sorted(hits)


def _drop_codes(line: str, repl: str = " ") -> str:
    for start, end, _ in reversed(code_hits(line)):
        line = line[:start] + repl + line[end:]
    return line


NUMBER = re.compile(r"\d+(?:\.\d+)*")


@dataclass(frozen=True)
class UniformityRow:
    insurer: str
    clause_no: str
    matches_reference: bool


MAX_SKIP = 3  # a next sibling may skip up to this many numbers (4.2 -> 4.6 ok, 4.7 not)


def _plausible_next(prev: tuple[int, ...] | None, cand: tuple[int, ...]) -> bool:
    """Is `cand` a plausible next heading number after `prev`?

    Accepts: any first heading; a top-level "1" (restart, e.g. the body after a contents
    list); the first child (4 -> 4.1); or the next sibling of the previous heading or of any
    of its ancestors, skipping at most MAX_SKIP numbers (4.2.3 -> 4.2.4..4.2.7, 4.3.., 5..).
    """
    if prev is None or cand == (1,):
        return True
    if cand == prev + (1,):
        return True
    return any(cand == prev[:k - 1] + (prev[k - 1] + d,)
               for k in range(1, len(prev) + 1) for d in range(1, MAX_SKIP + 2))


def _furniture(pages: list[tuple[int, str]]) -> set[str]:
    """Normalised lines repeated on at least half (and at least two) of the pages."""
    if len(pages) < 2:
        return set()
    seen: dict[str, int] = {}
    for _, text in pages:
        for ln in {normalise_ws(x) for x in (text or "").splitlines()} - {""}:
            seen[ln] = seen.get(ln, 0) + 1
    need = max(2, (len(pages) + 1) // 2)
    # Numbered heading lines are never furniture: a contents list repeats them on another page.
    return {ln for ln, n in seen.items()
            if n >= need and not (HEADING.match(ln) and STARTS_HEADING.match(HEADING.match(ln).group(2)))}


def _segment(store: Store, wording_sha256: str) -> tuple[list[dict], int]:
    pages = store.con.execute(
        "SELECT page_no, text FROM document_page WHERE sha256=? ORDER BY page_no",
        [wording_sha256]).fetchall()
    junk = _furniture(pages)
    prev: tuple[int, ...] | None = None
    rejected = 0
    # A number seen again (after a restart at "1") overwrites the earlier one, so a contents
    # list is replaced by the body.
    clauses: dict[str, dict] = {}
    cur = None
    for page_no, text in pages:
        for line in (text or "").splitlines():
            norm = normalise_ws(line)
            if norm in junk or PAGE_NO_ONLY.fullmatch(norm):
                continue
            m = HEADING.match(norm)
            num = tuple(int(x) for x in m.group(1).split(".")) if m else None
            if m and STARTS_HEADING.match(m.group(2)) and _plausible_next(prev, num):
                prev = num
                cur = {"clause_no": m.group(1), "heading": m.group(2).strip(),
                       "page_no": page_no, "body": []}
                clauses[cur["clause_no"]] = cur
            elif cur is not None:
                if m:
                    rejected += 1
                cur["body"].append(line)
            elif m:
                rejected += 1
    return list(clauses.values()), rejected


def build_index(product_id: str, wording_sha256: str, store: Store) -> int:
    segs, rejected = _segment(store, wording_sha256)
    if rejected:
        log.warning("%s: %d numbered line(s) rejected as headings (kept as body text)",
                    wording_sha256[:12], rejected)
    exists = store.con.execute(
        "SELECT 1 FROM policy_product WHERE product_id=?", [product_id]).fetchone()
    if exists:
        store.con.execute("UPDATE policy_product SET wording_sha256=? WHERE product_id=?",
                          [wording_sha256, product_id])
    else:
        store.upsert("policy_product", [{
            "product_id": product_id, "insurer": None, "product_name": None, "uin": None,
            "wording_sha256": wording_sha256, "cis_sha256": None, "is_standard_product": True,
        }], key=["product_id"])
    store.con.execute("DELETE FROM policy_clause WHERE product_id=?", [product_id])
    rows = []
    for s in segs:
        text = normalise_ws(" ".join(s["body"]))
        rows.append({"product_id": product_id, "clause_no": s["clause_no"],
                     "heading": s["heading"], "text": text, "page_no": s["page_no"],
                     "normalised_hash": hashlib.sha256(text.encode("utf-8")).hexdigest()})
    return store.upsert("policy_clause", rows, key=["product_id", "clause_no"])


def _row(r) -> PolicyClause:
    return PolicyClause(product_id=r[0], clause_no=r[1], heading=r[2], text=r[3],
                        page_no=r[4], normalised_hash=r[5])


def _clauses(store: Store, product_id: str) -> list[PolicyClause]:
    rows = store.con.execute(
        "SELECT product_id, clause_no, heading, text, page_no, normalised_hash "
        "FROM policy_clause WHERE product_id=? ORDER BY page_no, clause_no", [product_id]).fetchall()
    return [_row(r) for r in rows]


def _has_code(c: PolicyClause, code: str) -> bool:
    return any(m.group(1) == code for m in CODE.finditer(f"{c.heading or ''} {c.text}"))


def find_clause(product_id: str, clause_ref: str, store: Store) -> PolicyClause | None:
    code_m = CODE.search(clause_ref)
    code = code_m.group(1) if code_m else None
    rest = CODE.sub(" ", clause_ref)
    num_m = NUMBER.search(rest)
    number = num_m.group(0) if num_m else None
    clauses = _clauses(store, product_id)
    if number:
        c = next((c for c in clauses if c.clause_no == number), None)
        if c is None or (code and not _has_code(c, code)):
            return None
        return c
    if code:
        hits = [c for c in clauses if _has_code(c, code)]
        # prefer the clause whose heading carries the code over one merely mentioning it
        hits.sort(key=lambda c: not CODE.search(c.heading or ""))
        return hits[0] if hits else None
    return None


@dataclass(frozen=True)
class CodeText:
    code: str  # "Excl01"
    text: str
    page_no: int
    text_hash: str


@dataclass(frozen=True)
class CodeRow:
    code: str
    product_id: str
    insurer: str
    status: str  # "match" | "differs" | "missing" | "empty" (code found, no text)


def _code_hash(text: str) -> str:
    """Hash of the text with case and all whitespace removed (spacing is layout, not content)."""
    return hashlib.sha256(re.sub(r"\s+", "", text).casefold().encode("utf-8")).hexdigest()


def _unlist(part: str) -> str:
    """A line with its leading letter/roman enumerator dropped, and the one right after a printed
    code (a segment start too). Digits and numbers inside a sentence are left alone."""
    part = _drop_codes(part, " \x00 ")
    part = re.sub(r"\x00\s*(?=\(?(?:[a-z]|[ivx]{1,4})[.)]\s+\S)", "\x00", part, flags=re.I)
    part = re.sub(r"\x00" + LIST_MARKER.pattern.lstrip("^").replace("(?=\\S)", ""), " ", part, flags=re.I)
    return LIST_MARKER.sub("", normalise_ws(part.replace("\x00", " ")))


def _is_heading_line(ln: str) -> bool:
    h = HEADING.match(ln)
    return bool(BARE_HEADING_NO.fullmatch(ln) or (h and STARTS_HEADING.match(h.group(2))))


def _strip_heading_no(ln: str) -> str:
    h = HEADING.match(ln)
    if BARE_HEADING_NO.fullmatch(ln):
        return ""
    return h.group(2) if h and STARTS_HEADING.match(h.group(2)) else ln


def exclusion_texts(store: Store, wording_sha256: str) -> dict[str, CodeText]:
    """Text of each standard exclusion code in a wording.

    The wordings print the code either after the exclusion's heading (body follows) or at the
    end of a one-line exclusion (body precedes). So an exclusion runs from its heading (the
    nearest numbered heading line at or just before the code line) through to the next numbered
    heading or the next code's heading. The heading number and the printed code are dropped
    (numbers differ by wording; the code is the key). A code printed twice (contents list, then
    body) keeps its last occurrence.
    """
    pages = store.con.execute(
        "SELECT page_no, text FROM document_page WHERE sha256=? ORDER BY page_no",
        [wording_sha256]).fetchall()
    junk = _furniture(pages)
    lines: list[tuple[int, str]] = []
    for page_no, text in pages:
        for line in (text or "").splitlines():
            norm = normalise_ws(line)
            if norm and norm not in junk and not PAGE_NO_ONLY.fullmatch(norm):
                lines.append((page_no, norm))
    hits = [(i, code) for i, (_, ln) in enumerate(lines) for _, _, code in code_hits(ln)]
    out: dict[str, CodeText] = {}
    prev_i = -1
    for k, (i, code) in enumerate(hits):
        start = i
        for j in range(i, max(prev_i, i - 4), -1):
            start = j
            if _is_heading_line(lines[j][1]):
                break
        else:
            start = i
        stop = len(lines)
        for j in range(i + 1, len(lines)):
            if _is_heading_line(lines[j][1]) or (k + 1 < len(hits) and j >= hits[k + 1][0]):
                stop = j
                break
        parts_raw = [_strip_heading_no(ln) for _, ln in lines[start:stop]]
        parts = [_drop_codes(p) for p in parts_raw]
        text = normalise_ws(" ".join(parts)).strip(" :-")
        # line-start enumerators are layout: drop them from the compared form only
        compared = " ".join(_unlist(p) for p in parts_raw)
        out[code] = CodeText(code, text, lines[start][0], _code_hash(compared))
        prev_i = i
    return out


def code_uniformity_report(store: Store, reference_product_id: str | None = None) -> list[CodeRow]:
    """Per standard exclusion code and per wording: match / differs / missing.

    The baseline for a code is the reference wording's text; where the reference lacks the
    code, the first wording that has it. The baseline wording itself reads "match".
    """
    prods = store.con.execute(
        "SELECT product_id, insurer, wording_sha256 FROM policy_product ORDER BY product_id").fetchall()
    if not prods:
        return []
    ref = reference_product_id or prods[0][0]
    prods.sort(key=lambda p: p[0] != ref)  # reference first, rest keep their order
    texts = {p[0]: exclusion_texts(store, p[2]) for p in prods}
    codes = sorted({c for t in texts.values() for c in t})
    rows = []
    for code in codes:
        base = next((t[code].text_hash for t in texts.values() if code in t and t[code].text), None)
        for pid, insurer, _ in prods:
            ct = texts[pid].get(code)
            if ct is None:
                status = "missing"
            elif not ct.text:
                status = "empty"
            else:
                status = "match" if ct.text_hash == base else "differs"
            rows.append(CodeRow(code, pid, insurer or pid, status))
    return rows


def uniformity_report(store: Store, reference_product_id: str | None = None) -> list[UniformityRow]:
    prods = store.con.execute(
        "SELECT product_id, insurer FROM policy_product ORDER BY product_id").fetchall()
    ids = [p[0] for p in prods]
    ref = reference_product_id or (ids[0] if ids else None)
    if ref is None:
        return []
    ref_clauses = _clauses(store, ref)
    out = []
    for pid, insurer in prods:
        if pid == ref:
            continue
        theirs = {c.clause_no: c.normalised_hash for c in _clauses(store, pid)}
        for rc in ref_clauses:
            out.append(UniformityRow(insurer or pid, rc.clause_no,
                                     theirs.get(rc.clause_no) == rc.normalised_hash))
    return out
