"""Anthropic per-token pricing, USD per million tokens (input, output).
Update this table when models change — nothing else in the codebase
hardcodes a price. Unknown models estimate at $0 rather than raising, so a
model-string typo degrades to "unknown cost", not a failed extraction.
"""

_PRICING_PER_MTOK: dict[str, tuple[float, float]] = {
    "claude-opus-5": (5.00, 25.00),
}


def estimate_cost_usd(model: str, input_tokens: int, output_tokens: int) -> float:
    input_price, output_price = _PRICING_PER_MTOK.get(model, (0.0, 0.0))
    return (input_tokens / 1_000_000) * input_price + (output_tokens / 1_000_000) * output_price
