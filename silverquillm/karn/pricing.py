"""Versioned API-equivalent token prices; no network lookup during a run."""

from __future__ import annotations

import hashlib
import json
from collections.abc import Mapping
from dataclasses import asdict, dataclass
from decimal import Decimal
from typing import Any

PRICE_TABLE_VERSION = "openai-anthropic-standard-2026-09-28-v4"
PRICING_SOURCE = "https://developers.openai.com/api/docs/pricing"
ANTHROPIC_PRICING_SOURCE = "https://platform.claude.com/docs/en/about-claude/pricing"
# The per-type rows of a request's cost breakdown, in the order they are reported.
COST_TYPES = ("uncached_input", "cache_read", "cache_write", "cache_write_1h", "output")


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
    # Anthropic prices a 1-hour cache write above the 5-minute one billed as cache_write.
    cache_write_1h: str | None = None


def _anthropic(input: str, write: str, write_1h: str, read: str, output: str) -> ModelPrice:
    # Claude 4.6 and later bill the whole 1M context at standard rates (no long-context tier).
    return ModelPrice(
        input, read, output, write, cache_write_1h=write_1h, source=ANTHROPIC_PRICING_SOURCE
    )


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
    "claude-fable-5-1": _anthropic("10", "12.5", "20", ".25", "50"),
    "claude-opus-5-5": _anthropic("4", "5", "8", ".2", "20"),
    "claude-sonnet-5-5": _anthropic("2", "2.5", "4", ".2", "10"),
    "claude-haiku-4-5": _anthropic("1", "1.25", "2", ".1", "5"),
    "claude-haiku-4-5-20251001": _anthropic("1", "1.25", "2", ".1", "5"),
}
ASSUMPTIONS = (
    "API-equivalent standard processing USD, not the subscription charge",
    "Text-token rates; no regional, batch or hosted-tool fees",
    "Reasoning output is already included in output tokens, never charged twice",
    "Input tokens include cache reads and writes, which are disjoint categories",
    "Anthropic's native input count excludes cache reads and writes, so they are added back",
    "Anthropic 5-minute cache writes use cache_write and 1-hour writes use cache_write_1h",
    (
        "Every request is priced at standard rates, whatever speed or service tier served it; "
        "flex, fast mode and priority are standard-rate equivalents, with the tier kept on the request"
    ),
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
        # Standard rates apply whatever tier served the request (grilling 2026-09-28).
        "rate_basis": "standard",
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
    # Absent means the provider has no 1-hour tier; a priced 1-hour tier needs the observed split.
    written_1h = usage.get("cache_write_1h_input_tokens")
    if written_1h is None and (rate.cache_write_1h is None or not written):
        written_1h = 0
    if type(written_1h) is not int or not 0 <= written_1h <= written:
        result["reasons"] = ["cache_write_split_missing_or_invalid"]
        return result
    if written_1h and rate.cache_write_1h is None:
        result["reasons"] = ["cache_write_1h_price_unavailable"]
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
    rows = {
        "uncached_input": (uncached, rate.input, input_factor),
        "cache_read": (usage["cached_input_tokens"], rate.cached_input, input_factor),
        "cache_write": (written - written_1h, rate.cache_write or rate.input, input_factor),
        "cache_write_1h": (written_1h, rate.cache_write_1h or rate.input, input_factor),
        "output": (usage["output_tokens"], rate.output, output_factor),
    }
    breakdown = {
        name: {
            "tokens": tokens,
            "usd": format(Decimal(tokens) * Decimal(price) * factor / Decimal(1000000), "f"),
        }
        for name, (tokens, price, factor) in rows.items()
    }
    total = sum(
        (Decimal(tokens) * Decimal(price) * factor for tokens, price, factor in rows.values()),
        Decimal(0),
    )
    result.update(
        usd=format(total / Decimal(1000000), "f"),
        breakdown=breakdown,
        context_input_tokens=context,
        long_context=long,
        context_scope=rate.context_scope,
        source=rate.source,
    )
    return result


def total_breakdown(priced: list[dict[str, Any]]) -> dict[str, dict[str, Any]]:
    """Per-type token and USD tallies over the requests that could be priced."""
    totals = {name: {"tokens": 0, "usd": Decimal(0)} for name in COST_TYPES}
    for row in priced:
        for name, part in (row.get("breakdown") or {}).items():
            totals[name]["tokens"] += part["tokens"]
            totals[name]["usd"] += Decimal(part["usd"])
    return {
        name: {"tokens": part["tokens"], "usd": format(part["usd"], "f")}
        for name, part in totals.items()
    }
