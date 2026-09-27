"""Versioned API-equivalent token prices; no network lookup during a run."""

from __future__ import annotations

import hashlib
import json
from collections.abc import Mapping
from dataclasses import asdict, dataclass
from decimal import Decimal
from typing import Any

PRICE_TABLE_VERSION = "openai-standard-2026-09-26-v1"
PRICING_SOURCE = "https://developers.openai.com/api/docs/pricing"


@dataclass(frozen=True)
class ModelPrice:
    input: str
    cached_input: str
    output: str
    cache_write: str | None = None
    context_threshold: int | None = None
    context_scope: str = "request"
    long_input_multiplier: str = "2"
    long_output_multiplier: str = "1.5"
    source: str = PRICING_SOURCE


MODEL_PRICES = {
    "gpt-6-astra": ModelPrice(
        "10",
        "1",
        "50",
        "12.5",
        272000,
        source="https://developers.openai.com/api/docs/models/gpt-6-astra",
    ),
    "gpt-6-sol": ModelPrice("2", ".2", "10", "2.5", 272000),
    "gpt-6-luna": ModelPrice(".1", ".01", ".5", ".125", 272000),
    "gpt-5.4": ModelPrice(
        "2.5",
        ".25",
        "15",
        context_threshold=272000,
        context_scope="session",
        source="https://developers.openai.com/api/docs/models/gpt-5.4",
    ),
    "gpt-5.4-2026-03-05": ModelPrice(
        "2.5",
        ".25",
        "15",
        context_threshold=272000,
        context_scope="session",
        source="https://developers.openai.com/api/docs/models/gpt-5.4",
    ),
    "gpt-5.3-codex": ModelPrice(
        "1.75", ".175", "14", source="https://developers.openai.com/api/docs/models/gpt-5.3-codex"
    ),
    "gpt-5.2-codex": ModelPrice(
        "1.75", ".175", "14", source="https://developers.openai.com/api/docs/models/gpt-5.2-codex"
    ),
}
ASSUMPTIONS = (
    "API-equivalent standard processing USD, not the subscription charge",
    "Text-token rates; no regional, batch, flex, fast-mode or hosted-tool fees",
    "Reasoning output is already included in output tokens, never charged twice",
    "Input tokens include cache reads and writes, which are disjoint categories",
    "GPT-5.4 uses the published session-context rule; GPT-6 uses per-request context",
    "Model names are native observations, not attestations of provider-side identity",
)


def price_table_metadata(prices: Mapping[str, ModelPrice] = MODEL_PRICES) -> dict[str, Any]:
    rows = {name: asdict(price) for name, price in sorted(prices.items())}
    encoded = json.dumps(rows, sort_keys=True, separators=(",", ":")).encode()
    return {
        "version": PRICE_TABLE_VERSION,
        "sha256": hashlib.sha256(encoded).hexdigest(),
        "currency": "USD",
        "unit": "per_1000000_tokens",
        "models": rows,
        "assumptions": list(ASSUMPTIONS),
    }


def price_requests(
    requests: list[dict[str, Any]], prices: Mapping[str, ModelPrice] = MODEL_PRICES
) -> list[dict[str, Any]]:
    session_max: dict[tuple[str, str], int] = {}
    for request in requests:
        count = request.get("usage", {}).get("input_tokens")
        if type(count) is int and count >= 0:
            key = (request.get("thread_id", ""), request.get("model", ""))
            session_max[key] = max(session_max.get(key, 0), count)
    return [_price(request, prices, session_max) for request in requests]


def _price(
    request: dict[str, Any],
    prices: Mapping[str, ModelPrice],
    session_max: Mapping[tuple[str, str], int],
) -> dict[str, Any]:
    result = {
        "response_id": request["response_id"],
        "model": request.get("model"),
        "usd": None,
        "reasons": [],
    }
    rate = prices.get(request.get("model", ""))
    if rate is None:
        result["reasons"] = ["model_price_unavailable"]
        return result
    usage = request.get("usage", {})
    keys = ("input_tokens", "cached_input_tokens", "output_tokens")
    if any(type(usage.get(key)) is not int or usage[key] < 0 for key in keys):
        result["reasons"] = ["required_token_observation_missing_or_invalid"]
        return result
    written = usage.get("cache_write_input_tokens")
    if written is None and rate.cache_write is None:
        written = 0
    if type(written) is not int or written < 0:
        result["reasons"] = ["cache_write_observation_missing_or_invalid"]
        return result
    uncached = usage["input_tokens"] - usage["cached_input_tokens"] - written
    if uncached < 0:
        result["reasons"] = ["cache_categories_exceed_input"]
        return result
    context = usage["input_tokens"]
    if rate.context_scope == "session":
        context = session_max[(request.get("thread_id", ""), request.get("model", ""))]
    long = rate.context_threshold is not None and context > rate.context_threshold
    input_factor = Decimal(rate.long_input_multiplier) if long else Decimal(1)
    output_factor = Decimal(rate.long_output_multiplier) if long else Decimal(1)
    total = (
        Decimal(uncached) * Decimal(rate.input)
        + Decimal(usage["cached_input_tokens"]) * Decimal(rate.cached_input)
        + Decimal(written) * Decimal(rate.cache_write or rate.input)
    ) * input_factor
    total += Decimal(usage["output_tokens"]) * Decimal(rate.output) * output_factor
    result.update(
        usd=format(total / Decimal(1000000), "f"),
        context_input_tokens=context,
        long_context=long,
        context_scope=rate.context_scope,
        source=rate.source,
    )
    return result
