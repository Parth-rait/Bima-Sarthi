import json

import httpx
import pytest
import respx
from pydantic import BaseModel, ConfigDict

from sarthi.llm.client import ModelUnavailable, SpendCapExceeded, chat
from sarthi.llm.pricing import cost_usd

PRIMARY = "http://primary.test/v1/chat/completions"
HPC = "http://hpc.test/v1/chat/completions"
TXT = "http://txt.test/v1/chat/completions"

MODELS_YAML = """
hpc24:
  base_url_env: HPC_URL
  model: glimmer-hpc
  key_env: HPC_KEY
  vision: true
nojs:
  base_url_env: HPC_URL
  model: no-json-schema
  key_env: HPC_KEY
  vision: true
  json_schema: false
  min_max_tokens: 4000
textonly:
  base_url_env: TXT_URL
  model: small-text
  key_env: TXT_KEY
  vision: false
"""


def completion(content, finish="stop", pin=10, pout=5, model="m"):
    return {
        "id": "x", "object": "chat.completion", "created": 0, "model": model,
        "choices": [{"index": 0, "finish_reason": finish,
                     "message": {"role": "assistant", "content": content}}],
        "usage": {"prompt_tokens": pin, "completion_tokens": pout, "total_tokens": pin + pout},
    }


@pytest.fixture(autouse=True)
def env(tmp_path, monkeypatch):
    models = tmp_path / "models.yaml"
    models.write_text(MODELS_YAML)
    monkeypatch.setenv("SARTHI_DATA_DIR", str(tmp_path / "data"))
    monkeypatch.setenv("SARTHI_MODELS_YAML", str(models))
    monkeypatch.setenv("READER_BASE_URL", "http://primary.test/v1")
    monkeypatch.setenv("READER_MODEL", "primary-model")
    monkeypatch.setenv("READER_KEY", "k")
    monkeypatch.setenv("READER_FALLBACKS", "")
    monkeypatch.setenv("HPC_URL", "http://hpc.test/v1")
    monkeypatch.setenv("HPC_KEY", "k")
    monkeypatch.setenv("TXT_URL", "http://txt.test/v1")
    monkeypatch.setenv("TXT_KEY", "k")
    monkeypatch.delenv("SPEND_CAP_USD", raising=False)
    from sarthi.llm import client
    client._benched.clear()  # benches are per process; every test starts with none
    return tmp_path


MSG = [{"role": "user", "content": "hi"}]


@respx.mock
def test_cache_hit_second_call():
    route = respx.post(PRIMARY).mock(return_value=httpx.Response(200, json=completion("hello")))
    a = chat("reader", MSG)
    b = chat("reader", MSG)
    assert route.call_count == 1
    assert a.cache_hit is False and b.cache_hit is True
    assert b.text == "hello" and b.cost_usd == 0 and b.backend == "primary"


@respx.mock
def test_cache_off_never_writes(env):
    route = respx.post(PRIMARY).mock(return_value=httpx.Response(200, json=completion("hello")))
    chat("reader", MSG, cache=False)
    chat("reader", MSG, cache=False)
    assert route.call_count == 2
    assert not list((env / "data" / "llm_cache").glob("*.json"))


class Out(BaseModel):
    n: int


@respx.mock
def test_schema_retry_then_needs_review():
    route = respx.post(PRIMARY).mock(return_value=httpx.Response(200, json=completion("not json")))
    r = chat("reader", MSG, schema=Out)
    assert route.call_count == 3
    assert r.needs_review is True and r.parsed is None
    second = json.loads(route.calls[1].request.content)["messages"]
    assert second[-1]["role"] == "user" and "valid" in second[-1]["content"].lower()


@respx.mock
def test_schema_retry_recovers():
    route = respx.post(PRIMARY).mock(side_effect=[
        httpx.Response(200, json=completion("nope")),
        httpx.Response(200, json=completion('{"n": 4}')),
    ])
    r = chat("reader", MSG, schema=Out)
    assert route.call_count == 2
    assert r.parsed == Out(n=4) and r.needs_review is False
    assert r.tokens_in == 20 and r.tokens_out == 10


@respx.mock
def test_spend_cap_blocks(env, monkeypatch):
    monkeypatch.setenv("SPEND_CAP_USD", "0.0001")
    ledger = env / "data" / "llm_spend.jsonl"
    ledger.parent.mkdir(parents=True)
    ledger.write_text(json.dumps({"cost_usd": 0.5}) + "\n")
    route = respx.post(PRIMARY).mock(return_value=httpx.Response(200, json=completion("x")))
    with pytest.raises(SpendCapExceeded):
        chat("reader", MSG)
    assert route.call_count == 0


@respx.mock
def test_spend_is_logged_for_spark(env, monkeypatch):
    monkeypatch.setenv("READER_MODEL", "meta-models/muse-spark-open")
    route = respx.post(PRIMARY).mock(
        return_value=httpx.Response(200, json=completion("x", pin=1_000_000, pout=1_000_000)))
    r = chat("reader", MSG)
    assert r.cost_usd == pytest.approx(5.5)
    body = json.loads(route.calls[0].request.content)
    assert body["reasoning_effort"] == "low"
    lines = (env / "data" / "llm_spend.jsonl").read_text().splitlines()
    assert json.loads(lines[0])["cost_usd"] == pytest.approx(5.5)


@respx.mock
def test_extra_body_override(monkeypatch):
    monkeypatch.setenv("READER_MODEL", "meta-models/muse-spark-open")
    route = respx.post(PRIMARY).mock(return_value=httpx.Response(200, json=completion("x")))
    chat("reader", MSG, extra_body={"reasoning_effort": "high"})
    assert json.loads(route.calls[0].request.content)["reasoning_effort"] == "high"


@respx.mock
def test_none_content_reasoning_model():
    respx.post(PRIMARY).mock(return_value=httpx.Response(200, json=completion(None, finish="length")))
    r = chat("reader", MSG)
    assert r.text is None and r.needs_review is True


@respx.mock
def test_fallback_to_next_rung(monkeypatch):
    monkeypatch.setenv("READER_FALLBACKS", "hpc24")
    p = respx.post(PRIMARY).mock(side_effect=httpx.ConnectError("refused"))
    h = respx.post(HPC).mock(return_value=httpx.Response(200, json=completion("ok")))
    r = chat("reader", MSG)
    assert r.backend == "hpc24" and p.call_count == 1 and h.call_count == 1


@respx.mock
def test_5xx_falls_back_but_4xx_raises(monkeypatch):
    import openai
    monkeypatch.setenv("READER_FALLBACKS", "hpc24")
    respx.post(PRIMARY).mock(return_value=httpx.Response(503, json={"error": "down"}))
    h = respx.post(HPC).mock(return_value=httpx.Response(200, json=completion("ok")))
    assert chat("reader", MSG, cache=False).backend == "hpc24"
    from sarthi.llm import client
    client._benched.clear()  # the 503 benched primary; this half is about how a 400 is treated
    respx.post(PRIMARY).mock(return_value=httpx.Response(400, json={"error": "bad"}))
    with pytest.raises(openai.BadRequestError):
        chat("reader", MSG, cache=False)
    assert h.call_count == 1


IMG = [{"role": "user", "content": [
    {"type": "text", "text": "read"},
    {"type": "image_url", "image_url": {"url": "data:image/png;base64,AAAA"}}]}]


@respx.mock
def test_vision_skips_text_only_rung(monkeypatch):
    monkeypatch.setenv("READER_FALLBACKS", "textonly,hpc24")
    p = respx.post(PRIMARY).mock(side_effect=httpx.ConnectError("refused"))
    t = respx.post(TXT).mock(return_value=httpx.Response(200, json=completion("no")))
    h = respx.post(HPC).mock(return_value=httpx.Response(200, json=completion("yes")))
    r = chat("reader", IMG)
    assert r.backend == "hpc24" and t.call_count == 0 and h.call_count == 1


@respx.mock
def test_all_rungs_down_raises(monkeypatch):
    monkeypatch.setenv("READER_FALLBACKS", "textonly,hpc24")
    respx.post(PRIMARY).mock(side_effect=httpx.ConnectError("refused"))
    respx.post(TXT).mock(side_effect=httpx.ConnectTimeout("slow"))
    respx.post(HPC).mock(return_value=httpx.Response(500))
    with pytest.raises(ModelUnavailable) as e:
        chat("reader", MSG)
    for name in ("primary", "textonly", "hpc24"):
        assert name in str(e.value)


@respx.mock
def test_logs_do_not_contain_message_content(caplog):
    respx.post(PRIMARY).mock(return_value=httpx.Response(200, json=completion("reply")))
    with caplog.at_level("INFO", logger="sarthi.llm"):
        chat("reader", [{"role": "user", "content": "SECRET-DOC-TEXT"}])
    assert "primary" in caplog.text and "primary-model" in caplog.text
    assert "SECRET-DOC-TEXT" not in caplog.text and "reply" not in caplog.text


def test_pricing():
    assert cost_usd("meta-models/muse-spark-open", 1_000_000, 0) == pytest.approx(1.25)
    assert cost_usd("meta-models/muse-spark-open", 0, 1_000_000) == pytest.approx(4.25)
    assert cost_usd("glimmer", 10**6, 10**6) == 0


@respx.mock
def test_ping_cli(capsys, monkeypatch):
    from sarthi.llm.client import main
    respx.post(PRIMARY).mock(return_value=httpx.Response(200, json=completion("Pong.")))
    monkeypatch.setenv("WRITER_BASE_URL", "http://primary.test/v1")
    monkeypatch.setenv("WRITER_MODEL", "w")
    monkeypatch.setenv("WRITER_KEY", "k")
    main(["--role", "writer", "--ping"])
    out = capsys.readouterr().out
    assert "Pong." in out and "cost" in out.lower()


class Strict(BaseModel):
    model_config = ConfigDict(extra="forbid")
    n: int


@respx.mock
def test_request_body_carries_json_schema():
    route = respx.post(PRIMARY).mock(return_value=httpx.Response(200, json=completion('{"n": 1}')))
    chat("reader", MSG, schema=Strict)
    rf = json.loads(route.calls[0].request.content)["response_format"]
    assert rf["type"] == "json_schema"
    assert rf["json_schema"]["name"] == "Strict"
    assert rf["json_schema"]["schema"] == Strict.model_json_schema()
    assert rf["json_schema"]["strict"] is False


@respx.mock
def test_no_response_format_without_schema():
    route = respx.post(PRIMARY).mock(return_value=httpx.Response(200, json=completion("hi")))
    chat("reader", MSG)
    assert "response_format" not in json.loads(route.calls[0].request.content)


@respx.mock
def test_rung_with_json_schema_false_omits_response_format(monkeypatch):
    monkeypatch.setenv("READER_FALLBACKS", "nojs")
    respx.post(PRIMARY).mock(side_effect=httpx.ConnectError("refused"))
    h = respx.post(HPC).mock(return_value=httpx.Response(200, json=completion('{"n": 2}')))
    r = chat("reader", MSG, schema=Strict)
    assert r.backend == "nojs" and r.parsed == Strict(n=2)
    assert "response_format" not in json.loads(h.calls[0].request.content)


@respx.mock
def test_off_shape_reply_is_retried_then_needs_review():
    route = respx.post(PRIMARY).mock(
        return_value=httpx.Response(200, json=completion('{"m": 1, "n": 2}')))
    r = chat("reader", MSG, schema=Strict)
    assert route.call_count == 3
    assert r.needs_review is True and r.parsed is None


@respx.mock
def test_429_falls_back(monkeypatch):
    monkeypatch.setenv("READER_FALLBACKS", "hpc24")
    respx.post(PRIMARY).mock(return_value=httpx.Response(429, json={"error": "slow down"}))
    h = respx.post(HPC).mock(return_value=httpx.Response(200, json=completion("ok")))
    assert chat("reader", MSG, cache=False).backend == "hpc24" and h.call_count == 1


@respx.mock
def test_5xx_is_retried_on_the_same_rung(monkeypatch):
    monkeypatch.setattr("sarthi.llm.client.time.sleep", lambda s: None)
    route = respx.post(PRIMARY).mock(side_effect=[httpx.Response(503),
                                                  httpx.Response(200, json=completion("ok"))])
    r = chat("reader", MSG, cache=False)
    assert r.backend == "primary" and route.call_count == 2


@respx.mock
def test_429_honors_retry_after_beyond_the_5xx_cap(monkeypatch):
    waits: list[float] = []
    monkeypatch.setattr("sarthi.llm.client.time.sleep", waits.append)
    route = respx.post(PRIMARY).mock(side_effect=[
        httpx.Response(429, headers={"retry-after": "45"}),
        httpx.Response(200, json=completion("ok"))])
    r = chat("reader", MSG, cache=False)
    assert r.backend == "primary" and route.call_count == 2
    assert waits == [45.0]


@respx.mock
def test_provider_json_generation_400_retries_without_response_format():
    route = respx.post(PRIMARY).mock(side_effect=[
        httpx.Response(400, json={"error": {"message": "Failed to generate JSON. Please adjust your prompt."}}),
        httpx.Response(200, json=completion('{"n": 4}'))])
    r = chat("reader", MSG, cache=False, schema=Strict)
    assert r.parsed == Strict(n=4) and route.call_count == 2
    assert "response_format" in json.loads(route.calls[0].request.content)
    assert "response_format" not in json.loads(route.calls[1].request.content)


@respx.mock
@pytest.mark.parametrize("status", [401, 402, 403])
def test_billing_or_auth_failure_falls_back(monkeypatch, status):
    """A rung whose key is unpaid/invalid (402/401/403) is unavailable, not a request bug."""
    monkeypatch.setenv("READER_FALLBACKS", "hpc24")
    respx.post(PRIMARY).mock(return_value=httpx.Response(status, json={"error": "payment required"}))
    h = respx.post(HPC).mock(return_value=httpx.Response(200, json=completion("ok")))
    assert chat("reader", MSG, cache=False).backend == "hpc24" and h.call_count == 1


@respx.mock
def test_judge_roles_ignore_fallbacks_by_default(monkeypatch):
    monkeypatch.setenv("JUDGE_SPARK_BASE_URL", "http://primary.test/v1")
    monkeypatch.setenv("JUDGE_SPARK_MODEL", "spark")
    monkeypatch.setenv("JUDGE_SPARK_FALLBACKS", "hpc24")
    respx.post(PRIMARY).mock(side_effect=httpx.ConnectError("refused"))
    h = respx.post(HPC).mock(return_value=httpx.Response(200, json=completion("other")))
    with pytest.raises(ModelUnavailable):
        chat("judge_spark", MSG, cache=False)
    assert h.call_count == 0


@respx.mock
def test_judge_fallback_allowed_with_env(monkeypatch):
    monkeypatch.setenv("JUDGE_SPARK_BASE_URL", "http://primary.test/v1")
    monkeypatch.setenv("JUDGE_SPARK_MODEL", "spark")
    monkeypatch.setenv("JUDGE_SPARK_FALLBACKS", "hpc24")
    monkeypatch.setenv("ALLOW_JUDGE_FALLBACK", "1")
    respx.post(PRIMARY).mock(side_effect=httpx.ConnectError("refused"))
    respx.post(HPC).mock(return_value=httpx.Response(200, json=completion("other")))
    assert chat("judge_spark", MSG, cache=False).backend == "hpc24"


@respx.mock
def test_min_max_tokens_raises_budget_only_when_below(monkeypatch):
    monkeypatch.setenv("READER_FALLBACKS", "nojs")
    respx.post(PRIMARY).mock(side_effect=httpx.ConnectError("refused"))
    h = respx.post(HPC).mock(return_value=httpx.Response(200, json=completion("ok")))
    chat("reader", MSG, max_tokens=500, cache=False)
    assert json.loads(h.calls[0].request.content)["max_tokens"] == 4000
    chat("reader", MSG, max_tokens=9000, cache=False)
    assert json.loads(h.calls[1].request.content)["max_tokens"] == 9000


def test_new_fallback_prices():
    assert cost_usd("moonshotai/Kimi-K3", 1_000_000, 1_000_000) == pytest.approx(18.0)
    assert cost_usd("nvidia/NVIDIA-Nemotron-3-Ultra-550B-A55B", 1_000_000, 1_000_000) == pytest.approx(3.0)
    assert cost_usd("deepseek-ai/DeepSeek-V4-Flash-0731", 1_000_000, 1_000_000) == pytest.approx(0.39)


def test_rung_timeout_comes_from_models_yaml(monkeypatch, tmp_path):
    """A slow local rung can declare its own timeout_s; other rungs keep the default."""
    from sarthi.llm import client
    y = tmp_path / "m.yaml"
    y.write_text("slow:\n  base_url_env: SLOW_URL\n  model: m\n  key_env: SLOW_KEY\n  timeout_s: 300\n"
                 "fast:\n  base_url_env: FAST_URL\n  model: m\n  key_env: FAST_KEY\n")
    monkeypatch.setenv("SARTHI_MODELS_YAML", str(y))
    monkeypatch.setenv("READER_FALLBACKS", "slow,fast")
    rungs = client._rungs("reader")
    assert [r.timeout_s for r in rungs] == [None, 300.0, None]


@respx.mock
def test_a_failed_rung_is_skipped_on_the_next_call(monkeypatch):
    """The second page of an upload must not wait on the rung that just refused or timed out on the first."""
    monkeypatch.setattr("sarthi.llm.client.time.sleep", lambda s: None)
    monkeypatch.setenv("READER_FALLBACKS", "hpc24")
    p = respx.post(PRIMARY).mock(return_value=httpx.Response(503, json={"error": "overloaded"}))
    h = respx.post(HPC).mock(return_value=httpx.Response(200, json=completion("ok")))
    assert chat("reader", MSG, cache=False).backend == "hpc24"
    assert p.call_count == 2  # retried once, then benched
    assert chat("reader", MSG, cache=False).backend == "hpc24"
    assert p.call_count == 2 and h.call_count == 2


@respx.mock
def test_a_refused_key_is_benched_for_the_session(monkeypatch):
    monkeypatch.setenv("READER_FALLBACKS", "hpc24")
    p = respx.post(PRIMARY).mock(return_value=httpx.Response(403, json={"error": "forbidden"}))
    respx.post(HPC).mock(return_value=httpx.Response(200, json=completion("ok")))
    for _ in range(3):
        assert chat("reader", MSG, cache=False).backend == "hpc24"
    assert p.call_count == 1


@respx.mock
def test_when_every_rung_is_benched_they_are_all_tried_again(monkeypatch):
    from sarthi.llm import client
    monkeypatch.setenv("READER_FALLBACKS", "hpc24")
    respx.post(PRIMARY).mock(side_effect=httpx.ConnectError("refused"))
    respx.post(HPC).mock(side_effect=httpx.ConnectError("refused"))
    with pytest.raises(ModelUnavailable):
        chat("reader", MSG, cache=False)
    assert len(client._benched) == 2
    p = respx.post(PRIMARY).mock(return_value=httpx.Response(200, json=completion("back")))
    assert chat("reader", MSG, cache=False).backend == "primary"
    assert p.call_count == 2  # respx keeps one route per URL: the refused call, then this one
