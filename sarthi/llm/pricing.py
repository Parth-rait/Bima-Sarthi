"""Per-million-token prices in USD, keyed by model id. Unlisted models cost $0."""

# (input, output) USD per million tokens. Source: docs/ground-truth/GROUND_TRUTH.md
PRICES_PER_M: dict[str, tuple[float, float]] = {
    "meta-models/muse-spark-open": (1.25, 4.25),
    # Baseten dashboard, pasted by Parth, 1 Nov 2026 (cached-input price ignored)
    "moonshotai/Kimi-K3": (3.00, 15.00),
    "nvidia/NVIDIA-Nemotron-3-Ultra-550B-A55B": (0.60, 2.40),
    "deepseek-ai/DeepSeek-V4-Flash-0731": (0.13, 0.26),
}


def cost_usd(model: str, tokens_in: int, tokens_out: int) -> float:
    price_in, price_out = PRICES_PER_M.get(model, (0.0, 0.0))
    return (tokens_in * price_in + tokens_out * price_out) / 1_000_000
