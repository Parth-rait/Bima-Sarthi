"""models.yaml must load through the client's own loader and encode the fallback ladder."""
from pathlib import Path

import yaml

from sarthi.llm import client

YAML = Path(__file__).resolve().parents[2] / "models.yaml"
LADDER = ["hpc48", "hpc24", "kaggle", "baseten", "nemotron_ultra", "deepseek_v4_flash", "kimi_k3",
          "ollama_dev"]


def test_rung_order_matches_fallback_ladder():
    assert list(yaml.safe_load(YAML.read_text())) == LADDER


def test_every_rung_has_required_fields():
    for name, e in yaml.safe_load(YAML.read_text()).items():
        for f in ("base_url_env", "model", "key_env", "vision"):
            assert f in e, f"{name} missing {f}"
        assert isinstance(e["vision"], bool)


def test_client_loader_resolves_ladder(monkeypatch):
    monkeypatch.setenv("SARTHI_MODELS_YAML", str(YAML))
    monkeypatch.setenv("READER_FALLBACKS", ",".join(LADDER))
    rungs = client._rungs("reader")[1:]
    assert [r.name for r in rungs] == LADDER


def test_ollama_dev_is_text_only_llama32_3b():
    e = yaml.safe_load(YAML.read_text())["ollama_dev"]
    assert e["vision"] is False
    assert e["model"] == "llama3.2:3b"


def test_glimmer_rungs_and_spark_see_images():
    t = yaml.safe_load(YAML.read_text())
    assert all(t[n]["vision"] is True for n in ("hpc48", "hpc24", "kaggle", "baseten"))


def test_baseten_fallback_rungs():
    t = yaml.safe_load(YAML.read_text())
    expect = {"nemotron_ultra": ("nvidia/NVIDIA-Nemotron-3-Ultra-550B-A55B", "NEMOTRON_ULTRA"),
              "deepseek_v4_flash": ("deepseek-ai/DeepSeek-V4-Flash-0731", "DEEPSEEK_V4_FL"),
              "kimi_k3": ("moonshotai/Kimi-K3", "KIMI_K3_KEY")}
    for name, (model, key) in expect.items():
        e = t[name]
        assert (e["model"], e["key_env"], e["vision"]) == (model, key, False)
        assert e["default_base_url"] == "https://inference.baseten.co/v1"
    assert t["kimi_k3"]["min_max_tokens"] == 4000 and t["deepseek_v4_flash"]["min_max_tokens"] == 4000
    assert "min_max_tokens" not in t["nemotron_ultra"]
    assert list(t)[-1] == "ollama_dev"
