"""Bima Sarthi web app: upload -> confirm -> verdicts, explanation, letter, deadlines.

Privacy: session state lives in memory and the session folder only. Logs carry request
paths (session ids) and counts, never document content or fact values.
"""
import asyncio
import json
import logging
import math
import os
import time
from contextlib import asynccontextmanager
from datetime import date, datetime
from pathlib import Path
from typing import Literal

import duckdb
from fastapi import FastAPI, File, HTTPException, Query, Request, Response, UploadFile
from fastapi.encoders import jsonable_encoder
from fastapi.exceptions import RequestValidationError
from fastapi.responses import FileResponse, HTMLResponse, JSONResponse
from pydantic import BaseModel
from starlette.exceptions import HTTPException as StarletteHTTPException
from starlette.middleware.gzip import DEFAULT_EXCLUDED_CONTENT_TYPES, GZipMiddleware

from sarthi.app import checklist as checklist_mod
from sarthi.app import gallery as gallery_mod
from sarthi.app import policy as policy_mod
from sarthi.app import schemes as schemes_mod
from sarthi.app.explain import explain
from sarthi.app.extract import extract_user_facts, ready_for_rules
from sarthi.app.labels import label, labels_json
from sarthi.app.plan import (PRODUCT_LINE_KEYS, finalize, general_plan, health_plan, product_label,
                             product_line_hint)
from sarthi.app.letter import LETTER_FACT_KEYS, build_letter, deadline_sources, deadlines, to_pdf
from sarthi.app import session as session_mod
from sarthi.app.session import Session, UnsupportedUpload, UploadTooLarge, sweep
from sarthi.core.derive import FACT_KEYS
from sarthi.core.engine import run_rules
from sarthi.core.inputs import REJECTION_GROUNDS
from sarthi.core.models import FactValue, RuleCard, missing_grievance_params
from sarthi.core.parse_values import parse_date_in, parse_inr
from sarthi.core.store import Store
from sarthi.data.case_facts import BOOL_FIELDS, DATE_FIELDS, DATETIME_FIELDS, parse_field
from sarthi.data.rule_cards import approved_cards
from sarthi.llm.client import SPARK_OPEN

log = logging.getLogger("sarthi.app")

NOTICE = "This is a rules check, not legal or medical advice."
INDEPENDENT = "Bima Sarthi is an independent project, not affiliated with IRDAI, LIC or any insurer."
GRIEVANCE_MSG = "Deadlines need the grievance-route rule card to be approved"
STATIC = Path(__file__).parent / "static"
PRODUCT_LINE = "product_line"  # session-level, chosen by the user on the confirm screen
ALLOWED_KEYS = set(FACT_KEYS) | set(LETTER_FACT_KEYS) | {PRODUCT_LINE}
NEEDS_PRODUCT_LINE = "Please choose the type of insurance before the check runs."
STATUS_ORDER = {"needs_confirmation": 0, "verified": 1, "user_confirmed": 2}

_SESSIONS: dict[str, dict] = {}
SESSION_TTL_S = 3600
SWEEP_EVERY_S = 300
MAX_UPLOAD_BYTES = session_mod.MAX_BYTES
MULTIPART_OVERHEAD = 256 * 1024
TOO_BIG = "Uploads are limited to 25 MB in total."
TRUE_WORDS = {"yes", "y", "true", "haan", "हाँ", "हां", "हाँ।", "हां।"}
FALSE_WORDS = {"no", "n", "false", "nahi", "नहीं", "नही"}


def sweep_sessions() -> None:
    """Delete expired folders and drop expired in-memory entries."""
    sweep()
    now = time.time()
    for sid, st in list(_SESSIONS.items()):
        gone = not st["purged"] and not st["session"].path.exists()
        if gone or now - st["created"] > SESSION_TTL_S:
            st["session"].delete()
            _SESSIONS.pop(sid, None)


async def _sweeper() -> None:
    while True:
        await asyncio.sleep(SWEEP_EVERY_S)
        try:
            await asyncio.to_thread(sweep_sessions)
        except Exception as e:
            log.error("sweep failed type=%s", type(e).__name__)


@asynccontextmanager
async def lifespan(_: FastAPI):
    sweep()
    task = asyncio.create_task(_sweeper())
    yield
    task.cancel()


app = FastAPI(title="Bima Sarthi", docs_url=None, redoc_url=None, openapi_url=None, lifespan=lifespan)
app.add_middleware(
    GZipMiddleware,
    minimum_size=1024,
    exclude_content_types=DEFAULT_EXCLUDED_CONTENT_TYPES + ("application/pdf", "application/octet-stream"),
)


# ---------- data access ----------

def data_dir() -> Path:
    return Path(os.environ.get("SARTHI_DATA_DIR", Path(__file__).resolve().parents[2] / "data"))


def load_cards() -> list[RuleCard]:
    """Approved, quote-verified rule cards from the read-only database ([] if absent)."""
    path = data_dir() / "bima_sarthi.duckdb"
    if not path.is_file():
        return []
    store = Store.__new__(Store)  # Store() would open read-write
    store.path = path
    try:
        store.con = duckdb.connect(str(path), read_only=True)
    except duckdb.IOException:  # e.g. an Airflow task holds the single writer lock
        raise HTTPException(503, "The rules are not available right now. Please try again later.")
    try:
        return approved_cards(store)
    finally:
        store.close()


# ---------- HTML shell ----------

def uses_spark() -> bool:
    return SPARK_OPEN in (os.environ.get("WRITER_MODEL"), os.environ.get("READER_MODEL"))


def footer_html() -> str:
    spark = "<p>Built with Muse Spark Open</p>" if uses_spark() else ""
    return (f"<p>{NOTICE}</p><p>{INDEPENDENT}</p>{spark}")


def frontend_dist() -> Path:
    """Where the built React app lives (override with SARTHI_FRONTEND_DIST)."""
    raw = os.environ.get("SARTHI_FRONTEND_DIST", "").strip()
    return Path(raw) if raw else Path(__file__).resolve().parents[2] / "frontend" / "dist"


def _react_index() -> Path | None:
    """The React shell, unless SARTHI_UI=legacy forces the old page or no build exists."""
    if os.environ.get("SARTHI_UI", "").strip().lower() == "legacy":
        return None
    p = frontend_dist() / "index.html"
    return p if p.is_file() else None


def _legacy_page() -> HTMLResponse:
    page = (STATIC / "index.html").read_text(encoding="utf-8")
    return HTMLResponse(page.replace("<!--FOOTER-->", footer_html()), headers={"Cache-Control": "no-cache"})


@app.get("/", response_class=HTMLResponse)
def index() -> HTMLResponse:
    react = _react_index()
    if react is not None:
        return HTMLResponse(react.read_text(encoding="utf-8"), headers={"Cache-Control": "no-cache"})
    return _legacy_page()


# Client-side (React Router) pages: a browser refresh or deep link must get the app shell.
CLIENT_ROUTES = ("about", "how-it-works", "check-claim", "action-plan", "cases", "privacy",
                 "help", "schemes", "evidence", "dev/components")


def _client_page() -> HTMLResponse:
    react = _react_index()
    if react is None:
        return _legacy_page()
    return HTMLResponse(react.read_text(encoding="utf-8"), headers={"Cache-Control": "no-cache"})


def _register_client_routes() -> None:
    for name in CLIENT_ROUTES:
        app.add_api_route(f"/{name}", lambda: _client_page(), methods=["GET"],
                          response_class=HTMLResponse, include_in_schema=False)
    app.add_api_route("/results/{report_id}", lambda report_id: _client_page(), methods=["GET"],
                      response_class=HTMLResponse, include_in_schema=False)


_register_client_routes()


@app.get("/legacy", response_class=HTMLResponse)
def legacy_index() -> HTMLResponse:
    """The previous single-file page, kept as the rollback."""
    return _legacy_page()


@app.get("/assets/{path:path}")
def frontend_asset(path: str):
    root = (frontend_dist() / "assets").resolve()
    target = (root / path).resolve()
    if root not in target.parents or not target.is_file():
        raise HTTPException(404, "Not found.")
    return FileResponse(target, headers={"Cache-Control": "public, max-age=31536000, immutable"})


@app.get("/favicon.svg", include_in_schema=False)
def favicon():
    target = frontend_dist() / "favicon.svg"
    if not target.is_file():
        raise HTTPException(404, "Not found.")
    return FileResponse(target, media_type="image/svg+xml",
                        headers={"Cache-Control": "public, max-age=86400"})


@app.exception_handler(StarletteHTTPException)
async def http_error(request: Request, exc: StarletteHTTPException):
    if "text/html" in request.headers.get("accept", ""):
        msg = exc.detail if isinstance(exc.detail, str) else "Something went wrong."
        body = (f'<!doctype html><html lang="en"><head><meta charset="utf-8">'
                f'<meta name="viewport" content="width=device-width, initial-scale=1">'
                f"<title>Bima Sarthi</title></head><body><main><h1>Bima Sarthi</h1>"
                f'<p>{exc.status_code}: {_esc(msg)}</p><p><a href="/">Back to start</a></p></main>'
                f"<footer>{footer_html()}</footer></body></html>")
        return HTMLResponse(body, status_code=exc.status_code)
    return JSONResponse({"detail": exc.detail}, status_code=exc.status_code)


@app.middleware("http")
async def security_headers(request: Request, call_next):
    response = await call_next(request)
    response.headers.setdefault("X-Content-Type-Options", "nosniff")
    response.headers.setdefault("Referrer-Policy", "strict-origin-when-cross-origin")
    response.headers.setdefault("X-Frame-Options", "DENY")
    return response


@app.exception_handler(RequestValidationError)
async def validation_error(request: Request, exc: RequestValidationError):
    # Python parses NaN and Infinity, but JSON cannot serialise them back in the error echo.
    def finite(v):
        if isinstance(v, float) and not math.isfinite(v):
            return repr(v)
        if isinstance(v, dict):
            return {k: finite(x) for k, x in v.items()}
        if isinstance(v, list):
            return [finite(x) for x in v]
        return v
    return JSONResponse({"detail": finite(jsonable_encoder(exc.errors()))}, status_code=422)


def _esc(s: str) -> str:
    return s.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")


@app.middleware("http")
async def cap_upload_size(request: Request, call_next):
    if request.method == "POST" and request.url.path.endswith("/extract"):
        cl = request.headers.get("content-length")
        if cl is None or not cl.isdigit():
            return JSONResponse({"detail": "Content-Length is required."}, status_code=411)
        if int(cl) > MAX_UPLOAD_BYTES + MULTIPART_OVERHEAD:
            return JSONResponse({"detail": TOO_BIG}, status_code=413)
    return await call_next(request)


@app.get("/health")
def health() -> dict:
    return {"status": "ok"}


# ---------- sessions ----------

def _state(sid: str) -> dict:
    sweep_sessions()
    st = _SESSIONS.get(sid)
    if st is None:
        raise HTTPException(404, "This session has expired or does not exist. Please start again.")
    return st


@app.post("/session")
def create_session() -> dict:
    sweep_sessions()
    s = Session.create()
    sid = s.path.name
    _SESSIONS[sid] = {"session": s, "facts": {}, "findings": None, "created": time.time(),
                      "insurer_reply_date": None, "purged": False, "reader_backend": None,
                      "policy": None}
    return {"session_id": sid}


@app.delete("/session/{sid}")
def delete_session(sid: str) -> dict:
    st = _state(sid)
    st["session"].delete()
    _SESSIONS.pop(sid, None)
    return {"deleted": True}


# ---------- facts ----------

def fact_json(key: str, f: FactValue) -> dict:
    v = f.value
    if isinstance(v, datetime):
        v = v.strftime("%d/%m/%Y %H:%M")
    elif isinstance(v, date):
        v = v.strftime("%d/%m/%Y")
    elif isinstance(v, list):
        v = [dict(x) if isinstance(x, dict) else x for x in v]
    return {"key": key, "label": {"en": label(key, "en"), "hi": label(key, "hi")},
            "value": v, "quote": f.quote, "page_no": f.page_no,
            "confidence": f.confidence, "status": f.status}


def facts_json(facts: dict[str, FactValue]) -> dict:
    ordered = sorted(facts.items(), key=lambda kv: (STATUS_ORDER.get(kv[1].status, 1), kv[0]))
    return {k: fact_json(k, f) for k, f in ordered}


def pending(facts: dict[str, FactValue]) -> list[str]:
    return [k for k, f in facts.items() if f.status == "needs_confirmation"]


def parse_input(key: str, raw):
    """Server-side parse of a user-entered value; raises ValueError with a clear message."""
    if key in DATE_FIELDS or key == "complaint_sent_date":
        if isinstance(raw, datetime):
            return raw.date()
        if isinstance(raw, date):
            return raw
        d, _ = parse_date_in(raw, from_photo=False) if isinstance(raw, str) else (None, False)
        if d is None and isinstance(raw, str):
            try:
                d = date.fromisoformat(raw.strip())
            except ValueError:
                pass
        if d is None:
            raise ValueError("Enter a real date as DD/MM/YYYY, for example 05/03/2024.")
        return d
    if key in DATETIME_FIELDS:
        if isinstance(raw, datetime):
            return raw
        v, ok = parse_field(key, raw)
        if not ok:
            raise ValueError("Enter a real date and time, for example 05/03/2024 14:30.")
        return datetime.fromisoformat(v)
    if key == PRODUCT_LINE:
        if not isinstance(raw, str) or raw.strip() not in PRODUCT_LINE_KEYS:
            raise ValueError("Choose the type of insurance from the list: "
                             + ", ".join(product_label(k) for k in PRODUCT_LINE_KEYS))
        return raw.strip()
    if key == "rejection_ground":
        if not isinstance(raw, str) or raw.strip() not in REJECTION_GROUNDS:
            raise ValueError("Choose the rejection reason from the list: " + ", ".join(REJECTION_GROUNDS))
        return raw.strip()
    if key in BOOL_FIELDS or key in ("continuity_confirmed", "cited_clause_found"):
        if isinstance(raw, bool):
            return raw
        word = raw.strip().lower() if isinstance(raw, str) else ""
        if word in TRUE_WORDS:
            return True
        if word in FALSE_WORDS:
            return False
        raise ValueError("Answer Yes or No.")
    if key == "renewal_gap_days":
        n = int(raw) if isinstance(raw, str) and raw.strip().isdigit() else raw
        if isinstance(n, bool) or not isinstance(n, int) or n < 0:
            raise ValueError("Enter a whole number of days, 0 or more.")
        return n
    if key == "deductions":
        v, ok = parse_field(key, raw)
        if not ok:
            raise ValueError("Each deduction needs an item and a readable amount.")
        return v
    if key == "disclosed_conditions":
        if isinstance(raw, str):
            raw = [x.strip() for x in raw.split(",") if x.strip()]
        if not isinstance(raw, list) or not all(isinstance(x, str) for x in raw):
            raise ValueError("Enter conditions separated by commas.")
        return raw
    if key == "claim_amount_inr":
        n = parse_inr(raw) if isinstance(raw, str) else raw
        if isinstance(n, bool) or not isinstance(n, (int, float)) or n <= 0:
            raise ValueError("Enter a rupee amount, for example 1,20,000 or 1.2 lakh.")
        return int(n)
    if not isinstance(raw, str) or not raw.strip() or len(raw) > 300:
        raise ValueError("Enter some text (up to 300 characters).")
    return raw.strip()


class FactEdit(BaseModel):
    value: object = None
    confirm: bool = False
    clear: bool = False


class FactsBody(BaseModel):
    facts: dict[str, FactEdit] = {}
    insurer_reply_date: str | None = None


@app.put("/session/{sid}/facts")
def put_facts(sid: str, body: FactsBody) -> dict:
    st = _state(sid)
    facts: dict[str, FactValue] = st["facts"]
    errors: dict[str, str] = {}
    updates: dict[str, FactValue | None] = {}
    for key, edit in body.facts.items():
        if key not in ALLOWED_KEYS:
            errors[key] = "Unknown fact."
        elif edit.clear:
            updates[key] = None
        elif "value" in edit.model_fields_set and edit.value is not None:
            try:
                value = parse_input(key, edit.value)
            except ValueError as e:
                errors[key] = str(e)
                continue
            old = facts.get(key)
            same = old is not None and old.value == value
            updates[key] = FactValue(
                value=value, quote=old.quote if same else None,
                page_no=old.page_no if same else None, confidence="high", status="user_confirmed")
        elif edit.confirm:
            old = facts.get(key)
            if old is None:
                errors[key] = "There is no value to confirm yet."
                continue
            try:
                value = parse_input(key, old.value)
            except ValueError as e:
                errors[key] = "This value could not be read, so it cannot be confirmed as it is. Please edit it. " + str(e)
                continue
            updates[key] = old.model_copy(update={"value": value, "status": "user_confirmed"})
        else:
            errors[key] = "Send a value, or confirm."
    today = date.today()  # once per request
    reply = None
    if body.insurer_reply_date:
        d, _ = parse_date_in(body.insurer_reply_date, from_photo=False)
        if d is None:
            errors["insurer_reply_date"] = "Enter a real date as DD/MM/YYYY."
        reply = d
    if "complaint_sent_date" in updates:
        c = updates["complaint_sent_date"]
        complaint = c.value if c is not None else None
    else:
        old_c = facts.get("complaint_sent_date")
        complaint = old_c.value if old_c is not None else None
    if complaint is not None and complaint > today and "complaint_sent_date" not in errors:
        errors["complaint_sent_date"] = _bi(
            "The date you sent your complaint cannot be in the future.",
            "शिकायत भेजने की तारीख़ भविष्य की नहीं हो सकती।")
    eff_reply = reply or st["insurer_reply_date"]
    if eff_reply is not None and "insurer_reply_date" not in errors:
        if eff_reply > today:
            errors["insurer_reply_date"] = _bi(
                "The date the insurer replied cannot be in the future.",
                "बीमाकर्ता के जवाब की तारीख़ भविष्य की नहीं हो सकती।")
        elif complaint is not None and eff_reply < complaint:
            errors["insurer_reply_date"] = _bi(
                "The insurer's reply cannot be dated before the day you sent your complaint.",
                "बीमाकर्ता का जवाब शिकायत भेजने की तारीख़ से पहले का नहीं हो सकता।")
    if errors:
        raise HTTPException(422, {"message": "Some entries could not be read.", "errors": errors})
    for k, v in updates.items():
        if v is None:
            facts.pop(k, None)
        else:
            facts[k] = v
    if reply:
        st["insurer_reply_date"] = reply
    st["findings"] = None
    log.info("facts updated session=%s n=%d", sid, len(updates))
    return {"facts": facts_json(facts), "needs_confirmation": pending(facts)}


def _add_uploads(session: Session, files: list[UploadFile]) -> None:
    """Read the uploaded files into the session folder, enforcing the size and page limits."""
    total = 0
    try:
        for f in files:
            buf = bytearray()
            while chunk := f.file.read(1024 * 1024):
                total += len(chunk)
                if total > MAX_UPLOAD_BYTES:
                    raise UploadTooLarge(TOO_BIG)
                buf += chunk
            session.add_upload((f.filename or "upload", bytes(buf)))
    except UploadTooLarge as e:
        raise HTTPException(413, str(e))
    except UnsupportedUpload as e:
        raise HTTPException(415, str(e))


@app.post("/session/{sid}/extract")
def extract(sid: str, files: list[UploadFile] = File(...)) -> dict:
    st = _state(sid)
    if st["purged"]:  # files were deleted after the previous result; start a fresh folder
        st["session"], st["purged"] = Session.create(), False
    session: Session = st["session"]
    _add_uploads(session, files)
    try:
        extracted = extract_user_facts(session)
    except Exception as e:
        log.error("extraction failed session=%s type=%s", sid, type(e).__name__)
        raise HTTPException(502, "We could not read these documents right now. Please try again.")
    # New extraction goes UNDER what the user has already confirmed or entered: never overwrite it.
    kept = {k: v for k, v in st["facts"].items()
            if v.status == "user_confirmed" or k in LETTER_FACT_KEYS or k in ("continuity_confirmed", PRODUCT_LINE)}
    st["facts"] = {**extracted, **kept}
    backends = {b for b in (st["reader_backend"], getattr(extracted, "backend", None)) if b}
    st["reader_backend"] = ", ".join(sorted(backends)) or None
    st["findings"] = None
    log.info("extracted session=%s pages=%d fields=%d", sid, len(session.pages()), len(extracted))
    return {"facts": facts_json(st["facts"]), "needs_confirmation": pending(st["facts"]),
            "pages": len(session.pages()), "reader_backend": st["reader_backend"],
            "product_line_hint": product_line_hint(st["facts"])}


# ---------- policy key terms (display only: never facts, never findings) ----------

class PolicyBody(BaseModel):
    terms: dict[str, FactEdit] = {}


def policy_view(st: dict) -> dict | None:
    return None if st["policy"] is None else policy_mod.policy_json(st["policy"])


@app.post("/session/{sid}/policy/extract")
def policy_extract(sid: str, files: list[UploadFile] = File(...)) -> dict:
    """Read the policy document in its own temporary folder, which is deleted as soon as the
    reading is done. The terms live in memory only and never enter the case facts."""
    st = _state(sid)
    folder = Session.create()
    try:
        _add_uploads(folder, files)
        pages = len(folder.pages())
        try:
            read = policy_mod.extract_policy_terms(folder)
        except Exception as e:
            log.error("policy reading failed session=%s type=%s", sid, type(e).__name__)
            raise HTTPException(502, "We could not read this policy right now. Please try again.")
    finally:
        folder.delete()
    kept = {k: v for k, v in (st["policy"] or {}).items() if v.status == "user_confirmed"}
    st["policy"] = {**read, **kept}
    log.info("policy read session=%s pages=%d terms=%d", sid, pages, len(read))
    return {"policy": policy_view(st), "pages": pages, "reader_backend": read.backend}


@app.get("/session/{sid}/policy")
def policy_get(sid: str) -> dict:
    return {"policy": policy_view(_state(sid))}


@app.put("/session/{sid}/policy")
def policy_put(sid: str, body: PolicyBody) -> dict:
    st = _state(sid)
    terms: dict = dict(st["policy"] or {})
    errors: dict[str, str] = {}
    updates: dict[str, policy_mod.PolicyTerm | None] = {}
    for key, edit in body.terms.items():
        old = terms.get(key)
        if key not in policy_mod.TERM_KEYS:
            errors[key] = "Unknown policy term."
        elif edit.clear:
            updates[key] = None
        elif "value" in edit.model_fields_set and edit.value is not None:
            try:
                value = policy_mod.parse_term_input(key, edit.value)
            except ValueError as e:
                errors[key] = str(e)
                continue
            same = old is not None and old.status != "needs_confirmation" and old.value == value
            updates[key] = policy_mod.PolicyTerm(
                value=value, quote=old.quote if same else None, page_no=old.page_no if same else None,
                confidence="high", status="user_confirmed")
        elif edit.confirm:
            if old is None or old.status == "needs_confirmation":
                errors[key] = "There is no value read from your document to confirm. Enter the value instead."
                continue
            updates[key] = old.model_copy(update={"status": "user_confirmed"})
        else:
            errors[key] = "Send a value, or confirm."
    if errors:
        raise HTTPException(422, {"message": "Some entries could not be read.", "errors": errors})
    for k, v in updates.items():
        if v is None:
            terms.pop(k, None)
        else:
            terms[k] = v
    st["policy"] = terms   # st["findings"] is deliberately untouched: the policy view never feeds a check
    log.info("policy terms updated session=%s n=%d", sid, len(updates))
    return {"policy": policy_view(st)}


@app.delete("/session/{sid}/policy")
def policy_delete(sid: str) -> dict:
    _state(sid)["policy"] = None
    return {"deleted": True}


# ---------- check / explain / letter ----------

OMB_NEEDS_COMPLAINT = "Add the date you sent your complaint to see your Ombudsman dates"


def _bi(en: str, hi: str) -> str:
    return f"{en} / {hi}"


def _complaint_date(st: dict) -> date | None:
    f = st["facts"].get("complaint_sent_date")
    return f.value if f is not None and isinstance(f.value, date) else None


def grievance_card(cards: list[RuleCard]) -> RuleCard | None:
    # An approved card is served only with all five params sourced (nested); flat numbers never.
    versions = [c for c in cards if c.rule_id == "GRIEVANCE_ROUTE" and c.status == "approved"
                and not missing_grievance_params(c)]
    return max(versions, key=lambda c: c.version) if versions else None


def grievance_params(cards: list[RuleCard]) -> dict | None:
    card = grievance_card(cards)
    return card.params if card else None


def deadlines_json(st: dict, cards: list[RuleCard]) -> dict:
    if not any(f.verdict == "CHALLENGEABLE" for f in st["findings"]):
        return {"available": False, "note": "Deadlines apply when a finding shows a possible inconsistency to raise."}
    card = grievance_card(cards)
    if card is None:
        return {"available": False, "note": GRIEVANCE_MSG}
    today = date.today()
    sent, reply = _complaint_date(st), st["insurer_reply_date"]
    if reply and sent is None:
        # Counting from today would overstate the real limit (12 months run from the reply).
        return {"available": True, "letter_available": False, "letter_date": None,
                "insurer_reply_by": None, "ombudsman_earliest": None, "ombudsman_latest": None,
                "ombudsman_note": OMB_NEEDS_COMPLAINT, "sources": {},
                "rule_id": card.rule_id, "rule_quote": card.quote, "page_no": card.page_no,
                "source_sha256": card.source_sha256, "note": OMB_NEEDS_COMPLAINT}
    letter_date = sent or today
    d = deadlines(letter_date, reply, params=card.params)
    fmt = lambda x: {"iso": x.isoformat(), "display": x.strftime("%d/%m/%Y")}
    return {"available": True, "letter_available": True, "letter_date": fmt(letter_date),
            "insurer_reply_by": fmt(d.insurer_reply_by),
            "ombudsman_earliest": fmt(d.ombudsman_earliest),
            "ombudsman_latest": fmt(d.ombudsman_latest),
            "rule_id": card.rule_id, "rule_quote": card.quote, "page_no": card.page_no,
            "source_sha256": card.source_sha256,
            "sources": deadline_sources(card.params, letter_date, reply),
            "note": ("Counted from the date you sent your complaint; see the rule quote for the source."
                     if sent else "Counted from today's date; see the rule quote for the source.")}


def _product_line(facts: dict[str, FactValue]) -> str | None:
    f = facts.get(PRODUCT_LINE)
    return f.value if f is not None and f.value in PRODUCT_LINE_KEYS else None


def _claim_amount(st: dict):
    f = st["facts"].get("claim_amount_inr")
    return f.value if f is not None and isinstance(f.value, (int, float)) else None


def health_plan_json(st: dict, cards: list[RuleCard]) -> dict | None:
    """"Your plan" for a health check: fixed templates over the findings, the approved
    grievance card and the user's own dates. None if its text fails the verify() self-check."""
    card = grievance_card(cards)
    plan, extras = health_plan(st["findings"], params=card.params if card else None,
                               complaint_date=_complaint_date(st), reply_date=st["insurer_reply_date"],
                               claim_amount=_claim_amount(st), facts=st["facts"])
    return finalize(plan, extras, st["findings"])


def _general_check(st: dict, line: str) -> dict:
    """Types of insurance without a checked rules engine: no findings, no verdict, a general plan."""
    try:
        cards = load_cards()
    except HTTPException:  # the plan needs no rule card; dates are simply omitted
        cards = []
    card = grievance_card(cards)
    plan, extras = general_plan(line, params=card.params if card else None,
                                complaint_date=_complaint_date(st), reply_date=st["insurer_reply_date"],
                                facts=st["facts"])
    st["findings"] = None
    st["session"].delete()  # page images are no longer needed; results live in memory only
    st["purged"] = True
    return {"supported": False, "product_line": line, "findings": [],
            "plan": finalize(plan, extras, []), "labels": labels_json(),
            "request_checklist": checklist_mod.build([], st["facts"]),
            "deadlines": {"available": False, "note": "Dates, where the sources apply, are shown in your plan."},
            "reader_backend": st["reader_backend"]}


@app.post("/session/{sid}/check")
def check(sid: str) -> dict:
    st = _state(sid)
    facts = st["facts"]
    line = _product_line(facts)
    if line is None:
        raise HTTPException(409, {"message": NEEDS_PRODUCT_LINE, "needs_product_line": True,
                                  "needs_confirmation": pending(facts)})
    if line != "health":
        return _general_check(st, line)
    cards = load_cards()
    if not cards:
        raise HTTPException(503, "The rules are not available right now. Please try again later.")
    if not ready_for_rules(facts, cards):
        need = pending(facts)
        gr = facts.get("rejection_ground")
        if (gr is None or gr.value is None) and "rejection_ground" not in need:
            need.insert(0, "rejection_ground")
        raise HTTPException(409, {"message": "Please confirm these facts before the check runs.",
                                  "needs_confirmation": need})
    st["findings"] = run_rules(facts, cards)
    st["session"].delete()  # page images are no longer needed; results live in memory only
    st["purged"] = True
    return {"supported": True, "product_line": "health",
            "findings": [f.model_dump(mode="json") for f in st["findings"]],
            "deadlines": deadlines_json(st, cards), "plan": health_plan_json(st, cards),
            "request_checklist": checklist_mod.build(st["findings"], st["facts"]),
            "labels": labels_json(), "reader_backend": st["reader_backend"]}


@app.post("/session/{sid}/explain")
def explain_route(sid: str, lang: str = Query("en", pattern="^(en|hi)$"),
                  helper: int = Query(0, ge=0, le=1)) -> dict:
    st = _state(sid)
    if st["findings"] is None:
        raise HTTPException(409, "Run the check first.")
    out = explain(st["findings"], lang, bool(helper))
    cards = load_cards()
    return {"text": out.text, "used_model": out.used_model,
            "findings": [f.model_dump(mode="json") for f in st["findings"]],
            "deadlines": deadlines_json(st, cards), "plan": health_plan_json(st, cards),
            "request_checklist": checklist_mod.build(st["findings"], st["facts"]),
            "labels": labels_json(), "reader_backend": st["reader_backend"]}


@app.get("/session/{sid}/letter.pdf")
def letter_pdf(sid: str, lang: str = Query("en", pattern="^(en|hi)$")) -> Response:
    st = _state(sid)
    if st["findings"] is None:
        raise HTTPException(409, "Run the check first.")
    params = grievance_params(load_cards())
    if params is None:
        raise HTTPException(409, GRIEVANCE_MSG)
    sent = _complaint_date(st)
    if st["insurer_reply_date"] and sent is None:
        raise HTTPException(409, OMB_NEEDS_COMPLAINT)
    try:
        text = build_letter(st["facts"], st["findings"], lang, params=params,
                            letter_date=sent or date.today(),
                            insurer_reply_date=st["insurer_reply_date"])
    except ValueError:
        raise HTTPException(409, "There is no challengeable finding, so there is no letter to write.")
    return Response(to_pdf(text), media_type="application/pdf",
                    headers={"Content-Disposition": 'attachment; filename="grievance-letter.pdf"'})


# ---------- scheme finder (stateless: four answers in, a ranked list out) ----------

class SchemeAnswers(BaseModel):
    work: Literal["own_land", "both", "farm_labour", "other"]
    age: Literal["under_18", "18_50", "51_70", "over_70"]
    bank: Literal["yes", "no", "unsure"] = "unsure"
    ration: Literal["yes", "no", "unsure"] = "unsure"


@app.get("/api/schemes")
def schemes_catalogue() -> dict:
    return schemes_mod.public_catalogue()


@app.post("/api/schemes/match")
def schemes_match(body: SchemeAnswers) -> dict:
    try:
        return schemes_mod.match_schemes(body.model_dump())
    except ValueError as e:
        raise HTTPException(422, str(e))


# ---------- evidence (the published evaluation summary; no DB, no model) ----------

def evidence_file() -> Path:
    raw = os.environ.get("SARTHI_EVIDENCE_FILE", "").strip()
    return Path(raw) if raw else Path(__file__).resolve().parents[2] / "docs" / "eval" / "summary.json"


@app.get("/api/evidence")
def evidence() -> dict:
    p = evidence_file()
    if not p.is_file():
        raise HTTPException(404, "No evaluation has been published yet.")
    return json.loads(p.read_text(encoding="utf-8"))


# ---------- gallery (reads precomputed JSON only) ----------

@app.get("/gallery")
def gallery_list() -> dict:
    return {"attribution": gallery_mod.ATTRIBUTION, "cases": gallery_mod.list_cases()}


@app.get("/gallery/{case_id}")
def gallery_case(case_id: str) -> dict:
    data = gallery_mod.load_case(case_id)
    if data is None:
        raise HTTPException(404, "This case is not in the gallery.")
    return data
