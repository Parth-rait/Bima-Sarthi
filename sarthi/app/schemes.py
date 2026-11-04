"""Deterministic scheme finder for agriculture workers in Maharashtra.

The catalogue is a reviewed YAML file; this module only matches four answers
against the conditions stated on each scheme's official source. It returns a
status and a plain-language reason. It does not score, rank by a hidden number,
or decide eligibility: the office or insurer does.
"""
from __future__ import annotations

import os
from functools import lru_cache
from pathlib import Path
from typing import Callable

import yaml

_DEFAULT = Path(__file__).resolve().parents[1] / "data" / "schemes_mh_agri.yaml"
STATUS_ORDER = {"likely": 0, "check": 1, "not_eligible": 2}
STATUS_GROUP = {"likely": "start", "check": "ask", "not_eligible": "not_now"}
REQUIRED = ("work", "age", "bank", "ration")

Answers = dict[str, str]
Rule = Callable[[Answers], tuple[str, str]]


@lru_cache(maxsize=4)
def _load(path: str) -> dict:
    with open(path, encoding="utf-8") as fh:
        return yaml.safe_load(fh)


def load_catalogue(path: str | None = None) -> dict:
    """The reviewed catalogue. SARTHI_SCHEMES_FILE overrides the file for tests."""
    p = path or os.environ.get("SARTHI_SCHEMES_FILE") or str(_DEFAULT)
    return _load(str(Path(p).resolve()))


def _iso(value) -> str:
    return value.isoformat() if hasattr(value, "isoformat") else str(value)


def _check_answers(cat: dict, answers: Answers) -> None:
    allowed = {q["id"]: {o["value"] for o in q["options"]} for q in cat["questions"]}
    missing = [k for k in REQUIRED if k not in answers]
    if missing:
        raise ValueError(f"Answer these questions: {', '.join(missing)}")
    for key in REQUIRED:
        if answers[key] not in allowed[key]:
            raise ValueError(f"Unknown answer for {key}")


def _gopinath(a: Answers) -> tuple[str, str]:
    if a["work"] == "own_land":
        if a["age"] in {"18_50", "51_70"}:
            return "likely", "land_ok"
        return "check", "age_check"
    if a["work"] == "both":
        return "check", "land_check"
    return "not_eligible", "no_712"


def _pmsby(a: Answers) -> tuple[str, str]:
    if a["age"] == "under_18":
        return "not_eligible", "age_minor"
    if a["age"] == "over_70":
        return "not_eligible", "age_senior"
    if a["bank"] == "no":
        return "not_eligible", "no_account"
    if a["bank"] == "unsure":
        return "check", "unsure_account"
    return "likely", "ok"


def _pmjjby(a: Answers) -> tuple[str, str]:
    if a["age"] == "under_18":
        return "not_eligible", "age_minor"
    if a["age"] in {"51_70", "over_70"}:
        return "not_eligible", "age_senior"
    if a["bank"] == "no":
        return "not_eligible", "no_account"
    if a["bank"] == "unsure":
        return "check", "unsure_account"
    return "likely", "ok"


def _pmfby(a: Answers) -> tuple[str, str]:
    if a["work"] == "other":
        return "not_eligible", "not_farm"
    return "check", "farm"


def _pmjay(a: Answers) -> tuple[str, str]:
    return "check", "no_ration" if a["ration"] == "no" else "check"


def _pmkisan(a: Answers) -> tuple[str, str]:
    if a["work"] in {"farm_labour", "other"}:
        return "check", "land_check"
    if a["bank"] == "no":
        return "check", "no_account"
    if a["bank"] == "unsure":
        return "check", "unsure_account"
    if a["age"] == "under_18":
        return "check", "minor_family"
    return "likely", "land_ok"


def _mgnrega(a: Answers) -> tuple[str, str]:
    return "check", "job_card"


RULES: dict[str, Rule] = {
    "gopinath_munde": _gopinath,
    "pmsby": _pmsby,
    "pmjjby": _pmjjby,
    "pmfby": _pmfby,
    "pmjay": _pmjay,
    "pmkisan": _pmkisan,
    "mgnrega": _mgnrega,
}


def _status_meta(cat: dict) -> dict:
    return {sid: {"label": s["label"], "sentence": s["sentence"]} for sid, s in cat["statuses"].items()}


def public_catalogue(cat: dict | None = None) -> dict:
    """Everything the page needs to ask the questions; no answers, no PII."""
    cat = cat or load_catalogue()
    return {
        "version": cat["version"],
        "checked_on": _iso(cat["checked_on"]),
        "state": cat["state"],
        "audience": cat["audience"],
        "disclaimer": cat["disclaimer"],
        "questions": cat["questions"],
        "statuses": _status_meta(cat),
        "groups": cat["groups"],
        "scheme_count": len(cat["schemes"]),
    }


def match_schemes(answers: Answers, cat: dict | None = None) -> dict:
    cat = cat or load_catalogue()
    _check_answers(cat, answers)
    statuses = _status_meta(cat)
    schemes = sorted(cat["schemes"], key=lambda s: s["priority"])
    results = []
    for s in schemes:
        rule = RULES.get(s["id"])
        if rule is None:
            raise ValueError(f"No matching rule for scheme {s['id']}")
        status, reason_id = rule(answers)
        reason = s["reasons"].get(reason_id)
        if reason is None:
            raise ValueError(f"Missing reason {reason_id} for scheme {s['id']}")
        item = {
            "id": s["id"],
            "name": s["name"],
            "short": s["short"],
            "status": status,
            "status_label": statuses[status]["label"],
            "status_sentence": statuses[status]["sentence"],
            "group": STATUS_GROUP[status],
            "why": reason,
            "what": s["what"],
            "cover": s["cover"],
            "eligibility": s["eligibility"],
            "steps": s["steps"],
            "fails": s["fails"],
            "official_url": s["official_url"],
            "source": s["source"],
            "verified_on": _iso(s.get("verified_on") or cat["checked_on"]),
        }
        if s.get("premium"):
            item["premium"] = s["premium"]
        if s.get("deadline"):
            item["deadline"] = s["deadline"]
        if s.get("claim_product_line"):
            # Only insurance policies: the finder links them to the claim check with this type preset.
            item["claim_product_line"] = s["claim_product_line"]
        results.append(item)
    priority = {s["id"]: s["priority"] for s in schemes}
    results.sort(key=lambda r: (STATUS_ORDER[r["status"]], priority[r["id"]]))
    return {
        "checked_on": _iso(cat["checked_on"]),
        "state": cat["state"],
        "disclaimer": cat["disclaimer"],
        "groups": cat["groups"],
        "statuses": statuses,
        "results": results,
    }
