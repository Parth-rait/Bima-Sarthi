"""Single entry point for every model call: roles, fallback rungs, cache, spend cap.

Message contents are never logged (user documents must not reach logs).
"""

import argparse
import logging
import os
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Literal

import httpx
import openai
import yaml
from pydantic import BaseModel, ValidationError

from sarthi.llm import cache as _cache
from sarthi.llm.pricing import cost_usd

log = logging.getLogger("sarthi.llm")

Role = Literal["reader", "writer", "judge_glimmer", "judge_spark"]
SPARK_OPEN = "meta-models/muse-spark-open"
JUDGE_ROLES = ("judge_glimmer", "judge_spark")
SCHEMA_RETRIES = 2
RUNG_ATTEMPTS = 2
RETRY_S = 1.0
MAX_RETRY_WAIT_S = 20.0
TIMEOUT_S = 120.0
# A rung that just failed is benched so the next call (the next page of the same upload) goes straight to a rung
# that answers, instead of paying the same refusal or timeout again. A refused key (401/402/403) will not heal
# within a session; an overloaded or timed-out provider (5xx/429/timeout/refused connection) often does.
KEY_BENCH_S = 1800.0
SICK_BENCH_S = 300.0
_benched: dict[tuple[str, str], float] = {}  # (base_url, model) -> monotonic time the bench ends


def _bench(rung: "_Rung", seconds: float, reason: str) -> None:
    _benched[(rung.base_url, rung.model)] = time.monotonic() + seconds
    log.warning("benched rung=%s for %.0fs after %s", rung.name, seconds, reason)


def _on_bench(rung: "_Rung") -> bool:
    until = _benched.get((rung.base_url, rung.model))
    return until is not None and until > time.monotonic()


class SpendCapExceeded(RuntimeError):
    pass


class ModelUnavailable(RuntimeError):
    pass


@dataclass
class ChatResult:
    text: str | None
    parsed: BaseModel | None
    tool_calls: list
    tokens_in: int
    tokens_out: int
    cost_usd: float
    cache_hit: bool
    needs_review: bool
    backend: str


@dataclass
class _Rung:
    name: str
    base_url: str
    model: str
    key: str
    vision: bool = True
    json_schema: bool = True
    min_max_tokens: int | None = None
    timeout_s: float | None = None


def _models_yaml_path() -> Path:
    env = os.environ.get("SARTHI_MODELS_YAML")
    return Path(env) if env else Path(__file__).resolve().parents[2] / "models.yaml"


def _rungs(role: str) -> list[_Rung]:
    p = role.upper()
    if role in JUDGE_ROLES and os.environ.get("ALLOW_JUDGE_FALLBACK") != "1":
        # an evaluation judge must never be answered by another model (spark_only stays Spark)
        fallbacks = ""
    else:
        fallbacks = os.environ.get(f"{p}_FALLBACKS", "")
    rungs = [_Rung("primary", os.environ.get(f"{p}_BASE_URL", ""),
                   os.environ.get(f"{p}_MODEL", ""), os.environ.get(f"{p}_KEY", "") or "none")]
    names = [n.strip() for n in fallbacks.split(",") if n.strip()]
    if names:
        table = yaml.safe_load(_models_yaml_path().read_text()) or {}
        for n in names:
            if n not in table:
                raise KeyError(f"{p}_FALLBACKS names unknown rung {n!r} (not in models.yaml)")
            e = table[n]
            default_url = e.get("default_base_url", "")
            rungs.append(_Rung(n, os.environ.get(e["base_url_env"]) or default_url, e["model"],
                               os.environ.get(e["key_env"], "") or "none", bool(e.get("vision", True)),
                               bool(e.get("json_schema", True)), e.get("min_max_tokens"),
                               float(e["timeout_s"]) if e.get("timeout_s") else None))
    return rungs


def _has_image(messages: list[dict]) -> bool:
    for m in messages:
        c = m.get("content")
        if isinstance(c, list) and any(isinstance(x, dict) and x.get("type") == "image_url" for x in c):
            return True
    return False


def _call(rung: _Rung, messages, tools, max_tokens, extra_body, schema=None):
    # Legacy httpx client on purpose: openai 3.x defaults to the httpx2 fork, which respx cannot mock.
    with httpx.Client(timeout=rung.timeout_s or TIMEOUT_S) as http, openai.OpenAI(
            base_url=rung.base_url, api_key=rung.key, max_retries=0, http_client=http) as client:
        return _create(client, rung, messages, tools, max_tokens, extra_body, schema)


def _create(client, rung, messages, tools, max_tokens, extra_body, schema=None):
    if rung.min_max_tokens:
        max_tokens = max(max_tokens, rung.min_max_tokens)  # reasoning models need room to think
    kwargs = {"model": rung.model, "messages": messages, "max_tokens": max_tokens}
    if schema is not None and rung.json_schema:
        kwargs["response_format"] = {"type": "json_schema", "json_schema": {
            "name": schema.__name__, "schema": schema.model_json_schema(), "strict": False}}
    if tools:
        kwargs["tools"] = tools
    if extra_body:
        kwargs["extra_body"] = extra_body
    return client.chat.completions.create(**kwargs)


def _to_dict(r: ChatResult) -> dict:
    d = dict(r.__dict__)
    d["parsed"] = r.parsed.model_dump(mode="json") if r.parsed is not None else None
    return d


def _retry_after(e: Exception, cap: float = MAX_RETRY_WAIT_S) -> float:
    try:
        wait = float(e.response.headers.get("retry-after", ""))  # type: ignore[attr-defined]
    except (AttributeError, TypeError, ValueError):
        return RETRY_S
    return min(max(wait, 0.0), cap)


MAX_RATE_LIMIT_WAIT_S = 60.0  # free-tier RPM windows are ~1 min; a short wait just re-trips the limit


def chat(role: Role, messages: list[dict], *, schema: type[BaseModel] | None = None,
         tools: list[dict] | None = None, cache: bool = True, max_tokens: int = 2000,
         extra_body: dict | None = None) -> ChatResult:
    rungs = _rungs(role)
    key = _cache.cache_key(rungs[0].model, messages, tools, schema.__name__ if schema else None, max_tokens)
    if cache and (hit := _cache.cache_get(key)) is not None:
        hit["parsed"] = schema.model_validate(hit["parsed"]) if schema and hit["parsed"] is not None else None
        hit.update(cache_hit=True, cost_usd=0.0)
        log.info("role=%s backend=%s model=%s tokens_in=0 tokens_out=0 cost=0 cache_hit=True",
                 role, hit["backend"], rungs[0].model)
        return ChatResult(**hit)

    cap = float(os.environ.get("SPEND_CAP_USD", "10"))
    spent = _cache.total_spend()
    if spent >= cap:
        raise SpendCapExceeded(f"spent ${spent:.4f} >= cap ${cap:.4f}")

    needs_images = _has_image(messages)
    tried: list[str] = []
    # if every usable rung is benched, try them all anyway (a bench is a shortcut, never a reason to give up)
    usable = [r for r in rungs if r.vision or not needs_images]
    all_benched = bool(usable) and all(_on_bench(r) for r in usable)
    for rung in rungs:
        if needs_images and not rung.vision:
            tried.append(f"{rung.name} (skipped: no vision)")
            continue
        if not all_benched and _on_bench(rung):
            tried.append(f"{rung.name} (skipped: failed recently)")
            continue
        body = extra_body
        if body is None and rung.model == SPARK_OPEN:
            body = {"reasoning_effort": "low"}
        result = None
        reason = ""
        for attempt in range(RUNG_ATTEMPTS):
            wait = RETRY_S
            try:
                result = _run_rung(role, rung, messages, schema, tools, max_tokens, body)
                break
            except openai.APIStatusError as e:
                # 401/402/403: key unpaid or invalid = rung unavailable
                if not (e.status_code >= 500 or e.status_code in (401, 402, 403, 429)):
                    raise
                reason = f"HTTP {e.status_code}"
                transient = e.status_code == 429 or e.status_code >= 500
                if e.status_code == 429:
                    wait = _retry_after(e, MAX_RATE_LIMIT_WAIT_S)
            except openai.APITimeoutError as e:
                reason, transient = type(e).__name__, True
            except openai.APIConnectionError as e:
                reason, transient = type(e).__name__, False  # a refused connection will not heal in a second
            if not transient or attempt + 1 == RUNG_ATTEMPTS:
                tried.append(f"{rung.name} ({reason})")
                _bench(rung, KEY_BENCH_S if reason in ("HTTP 401", "HTTP 402", "HTTP 403") else SICK_BENCH_S, reason)
                break
            time.sleep(wait)  # a flaky 503/429 on one rung should not cost the reader the page
        if result is None:
            continue
        if cache and not result.needs_review:
            _cache.cache_put(key, _to_dict(result))
        return result
    raise ModelUnavailable("no model rung answered; tried: " + ", ".join(tried))


def _provider_cannot_emit_json(e: openai.BadRequestError) -> bool:
    """Groq rejects the request when its constrained decoder cannot build the schema."""
    return "failed to generate json" in str(e).lower()


def _run_rung(role, rung, messages, schema, tools, max_tokens, body) -> ChatResult:
    msgs = list(messages)
    tokens_in = tokens_out = 0
    text = None
    parsed = None
    tool_calls: list = []
    needs_review = False
    send_schema = schema is not None and rung.json_schema
    attempt = 0
    while attempt <= SCHEMA_RETRIES:
        try:
            resp = _call(rung, msgs, tools, max_tokens, body, schema if send_schema else None)
        except openai.BadRequestError as e:
            if not send_schema or not _provider_cannot_emit_json(e):
                raise
            # Ask again without response_format and validate the JSON here instead of losing the rung.
            send_schema = False
            continue
        if resp.usage:
            tokens_in += resp.usage.prompt_tokens
            tokens_out += resp.usage.completion_tokens
        choice = resp.choices[0]
        text = choice.message.content
        tool_calls = [tc.model_dump() for tc in (choice.message.tool_calls or [])]
        if text is None and not tool_calls:
            needs_review = True  # reasoning model ran out of tokens before answering
            break
        if schema is None or text is None:
            break
        try:
            parsed = schema.model_validate_json(text)
            break
        except ValidationError as e:
            if attempt == SCHEMA_RETRIES:
                needs_review = True
                parsed = None
                break
            msgs = msgs + [{"role": "assistant", "content": text},
                           {"role": "user", "content": "Your reply was not valid for the required "
                            f"JSON schema. Reply again with only valid JSON. Error: {e}"}]
        attempt += 1
    cost = cost_usd(rung.model, tokens_in, tokens_out)
    if cost or tokens_in or tokens_out:
        _cache.record_spend({"ts": time.time(), "role": role, "backend": rung.name,
                             "model": rung.model, "tokens_in": tokens_in,
                             "tokens_out": tokens_out, "cost_usd": cost})
    log.info("role=%s backend=%s model=%s tokens_in=%d tokens_out=%d cost=%.6f cache_hit=False needs_review=%s",
             role, rung.name, rung.model, tokens_in, tokens_out, cost, needs_review)
    return ChatResult(text, parsed, tool_calls, tokens_in, tokens_out, cost, False, needs_review, rung.name)


def main(argv: list[str] | None = None) -> None:
    ap = argparse.ArgumentParser(prog="python -m sarthi.llm.client")
    ap.add_argument("--role", required=True, choices=["reader", "writer", "judge_glimmer", "judge_spark"])
    ap.add_argument("--ping", action="store_true", help="send a one-sentence test prompt")
    args = ap.parse_args(argv)
    if not args.ping:
        ap.error("nothing to do; pass --ping")
    r = chat(args.role, [{"role": "user", "content": "Reply with one short sentence confirming you are online."}],
             cache=False, max_tokens=200)
    print(f"[{r.backend}] {r.text}")
    print(f"cost: ${r.cost_usd:.6f} (in={r.tokens_in}, out={r.tokens_out})")


if __name__ == "__main__":
    main()
