"""Plain-language explanations: template first (source of truth), optional model
rephrase, then verification. Any failure falls back to the template."""
import os
import re
from dataclasses import dataclass
from datetime import date, datetime
from decimal import Decimal
from functools import lru_cache
from pathlib import Path
from typing import Literal

import yaml

from sarthi.app.labels import label, value_label
from sarthi.app.verify import kind_of_key, parse_iso, verify
from sarthi.core.models import Finding
from sarthi.llm.client import chat

Lang = Literal["en", "hi"]
_DIR = Path(__file__).parent / "templates"
_ORDER = {"CHALLENGEABLE": 0, "NEED_INFO": 1, "CONSISTENT": 2}


@dataclass
class Explanation:
    text: str
    used_model: bool


@lru_cache(maxsize=None)
def _tpl(lang: str) -> dict:
    return yaml.safe_load((_DIR / f"{lang}.yaml").read_text(encoding="utf-8"))


def _inr(n) -> str:
    """Exact rupees with Indian grouping; paise shown when non-zero, never rounded."""
    d = Decimal(str(n))
    neg = d < 0
    whole, _, frac = f"{abs(d):f}".partition(".")
    frac = frac.rstrip("0")
    s = whole
    if len(s) > 3:
        head, tail = s[:-3], s[-3:]
        parts = []
        while len(head) > 2:
            parts.insert(0, head[-2:])
            head = head[:-2]
        if head:
            parts.insert(0, head)
        s = ",".join(parts + [tail])
    if frac:
        s += "." + frac.ljust(2, "0")
    return ("-" if neg else "") + "₹" + s


def _human(k) -> str:
    return str(k).replace("_", " ")


def _value(name: str, v, lb: dict, lang: str = "en") -> str:
    if isinstance(v, bool):
        return lb["yes"] if v else lb["no"]
    if isinstance(v, str) and (dt := parse_iso(v)):
        v = dt if ":" in v else dt.date()
    if isinstance(v, datetime):
        return v.strftime("%d/%m/%Y") if v.time() == datetime.min.time() else v.strftime("%d/%m/%Y %H:%M")
    if isinstance(v, date):
        return v.strftime("%d/%m/%Y")
    if isinstance(v, (int, float)) and (kk := kind_of_key(name)):
        if kk[0] == "inr":
            return _inr(v)
        if kk[0] == "pct":
            return f"{v}%"
        return f'{v} {lb["units"][kk[2]]}'
    if isinstance(v, dict):
        return _dict(v, lb, lang)
    if isinstance(v, (list, tuple)):
        return "; ".join(_value(name, x, lb, lang) for x in v)
    return value_label(v, lang) if name == "rejection_ground" and isinstance(v, str) else str(v)


def _dict(d: dict, lb: dict, lang: str = "en") -> str:
    if d.get("item") is None:
        return ", ".join(f"{label(k, lang)}: {_value(str(k), x, lb, lang)}" for k, x in d.items() if x is not None)
    s = str(d["item"])
    amt = d.get("amount")
    if isinstance(amt, (int, float)) and not isinstance(amt, bool):
        s += f" — {_value('amount', amt, lb, lang)}"
    tags = []
    if d.get("nonpayable_listed") is True:
        tags.append(lb["nonpayable"])
    elif d.get("reason"):
        r = _human(d["reason"]).strip().lower().replace("-", " ")
        tags.append(lb["nonpayable"] if r == "non payable" else str(d["reason"]))
    return s + (f" ({', '.join(tags)})" if tags else "")


def _facts_block(f: Finding, lb: dict, lang: str = "en") -> str:
    lines = []
    for name, fv in f.facts_used.items():
        v = fv.get("value")
        if v is None:
            continue
        line = f"- {label(name, lang)}: {_value(name, v, lb, lang)}"
        extra = []
        if fv.get("quote"):
            extra.append(f'{lb["fact_quote"]}: "{fv["quote"]}"')
        if fv.get("page_no") is not None:
            extra.append(f'{lb["page"]} {fv["page_no"]}')
        if extra:
            line += " (" + ", ".join(extra) + ")"
        lines.append(line)
    if not lines:
        return ""
    return lb["facts_intro"] + ":\n" + "\n".join(lines)


def _pick(f: Finding, t: dict):
    if f.verdict != "NEED_INFO":
        return t[f.verdict]
    r = (f.reason or "").split(":", 1)[0].strip()
    if r == "missing_inputs" and not (f.reason or "").partition(":")[2].strip():
        r = ""
    if r in ("rule_not_in_force", "missing_inputs", "condition_not_automated"):
        return t["NEED_INFO"][r]
    if r.startswith("missing_"):
        return t["NEED_INFO"]["missing_date"]
    return t["NEED_INFO"]["default"]


def _localised(f: Finding, lang: str, kind: str, marker: str) -> str | None:
    en, loc = getattr(f, f"{kind}_en"), getattr(f, f"{kind}_hi")
    if lang == "en":
        return en
    if loc:
        return loc
    return f"{en} {marker}".strip() if en else None


def _block(f: Finding, lang: str, helper: bool) -> str:
    t = _tpl(lang)
    lb = t["labels"]
    tpl = _pick(f, t)["helper" if helper else "self"]
    reason = f.reason or ""
    if reason.startswith("missing_inputs"):
        missing = ", ".join(label(n.strip(), lang) for n in reason.partition(":")[2].split(",") if n.strip())
    else:
        missing = label(reason.removeprefix("missing_"), lang)
    parts = [tpl.format(rule_id=f.rule_id, missing=missing)]
    if f.rule_quote:
        q = f'{lb["quote_intro"]} ({f.rule_id}'
        if f.page_no is not None:
            q += f', {lb["page"]} {f.page_no}'
        parts.append(f'{q}):\n"{f.rule_quote}"')
    if fb := _facts_block(f, lb, lang):
        parts.append(fb)
    if f.verdict == "NEED_INFO":
        if qn := _localised(f, lang, "question", lb["english_marker"]):
            parts.append(f'{lb["question_label"]}: {qn}')
    if f.verdict != "CONSISTENT":
        if ac := _localised(f, lang, "action", lb["english_marker"]):
            parts.append(f'{lb["action_label"]}: {ac}')
    return "\n\n".join(parts)


def templated(findings: list[Finding], lang: Lang, helper_mode: bool) -> str:
    ordered = sorted(findings, key=lambda f: _ORDER[f.verdict])
    blocks = [_block(f, lang, helper_mode) for f in ordered]
    if not blocks:  # nothing was checked: say so, never imply the decision is fine
        blocks.append(_tpl(lang)["labels"]["no_rule"])
    blocks.append(_tpl(lang)["labels"]["footer"])
    return "\n\n".join(blocks)


_SYSTEM = (
    "You rewrite an explanation of an insurance-claim rule check into simple, friendly language in {lang}. "
    "Keep EVERY number, date, amount, rule ID (like ABC_DEF) and every text in double quotes exactly unchanged. "
    "Add no new facts, numbers, rule IDs, advice, promises or predictions. Do not say the claim will succeed or fail. "
    "Do not comment on treatment or diagnosis. Return only the rewritten text.")


def rephrase(text: str, findings: list[Finding], lang: Lang) -> str:
    """Model rewording. cache=False: the text embeds the user's facts, which must not enter the LLM cache."""
    try:
        r = chat("writer", [
            {"role": "system", "content": _SYSTEM.format(lang="Hindi" if lang == "hi" else "English")},
            {"role": "user", "content": text}], cache=False, max_tokens=1500)
    except Exception:
        return text
    if r is None or r.needs_review or not r.text or not r.text.strip():
        return text
    return r.text.strip()


def explain(findings: list[Finding], lang: Lang, helper_mode: bool) -> Explanation:
    base = templated(findings, lang, helper_mode)
    # Model rephrasing is OFF unless SARTHI_REPHRASE=1, and never for Hindi (fixed templates only).
    if lang == "hi" or os.environ.get("SARTHI_REPHRASE") != "1":
        return Explanation(base, False)
    out = rephrase(base, findings, lang)
    if out == base:
        return Explanation(base, False)
    footer = _tpl(lang)["labels"]["footer"]
    if footer not in out:  # the whole disclaimer is mandatory: drop any partial copy, re-append in full
        out = out.replace(re.split(r"(?<=[.।])\s", footer)[0], " ").rstrip() + "\n\n" + footer
    quotes = [f.rule_quote for f in findings if f.rule_quote]
    quotes += [fv["quote"] for f in findings for fv in f.facts_used.values() if fv.get("quote")]
    if verify(out, findings).ok and all(q in out for q in quotes):
        return Explanation(out, True)
    return Explanation(base, False)
