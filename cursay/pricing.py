from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Mapping


XAI_PRICING_URL = "https://docs.x.ai/developers/pricing"
XAI_STT_REST_USD_PER_HOUR = 0.10
USD_TICKS_PER_DOLLAR = 10_000_000_000


@dataclass(frozen=True)
class TranscriptionRate:
    provider: str
    usd_per_hour: float
    label: str
    source_url: str | None = None


def _normalized(value: object) -> str:
    return str(value or "").strip().lower()


def transcription_rate(provider: object, model: object) -> TranscriptionRate | None:
    """Return a published duration-based rate for a known transcription service."""
    normalized_provider = _normalized(provider)
    normalized_model = _normalized(model)
    if normalized_provider in {"cursay-local", "local", "whisper-local"}:
        return TranscriptionRate(provider="Local Whisper", usd_per_hour=0.0, label="No provider fee")
    if normalized_provider in {"xai", "x.ai", "grok"} or normalized_model.startswith(
        "grok-voice-transcribe-"
    ):
        return TranscriptionRate(
            provider="xAI",
            usd_per_hour=XAI_STT_REST_USD_PER_HOUR,
            label="$0.10/hour REST",
            source_url=XAI_PRICING_URL,
        )
    return None


def estimate_transcription_cost(provider: object, model: object, duration_seconds: object) -> float | None:
    rate = transcription_rate(provider, model)
    if rate is None:
        return None
    try:
        seconds = max(0.0, float(duration_seconds))
    except (TypeError, ValueError):
        return None
    return seconds / 3600.0 * rate.usd_per_hour


def _non_negative_number(value: object) -> float | None:
    if isinstance(value, bool):
        return None
    try:
        number = float(value)
    except (TypeError, ValueError):
        return None
    return number if number >= 0 else None


def reported_cost_usd(response: Mapping[str, Any]) -> float | None:
    """Extract an exact provider-reported request cost when a gateway supplies one."""
    usage = response.get("usage")
    usage_mapping = usage if isinstance(usage, Mapping) else {}

    for value in (response.get("cost_usd"), usage_mapping.get("cost_usd")):
        cost = _non_negative_number(value)
        if cost is not None:
            return cost

    ticks = _non_negative_number(usage_mapping.get("cost_in_usd_ticks"))
    if ticks is not None:
        return ticks / USD_TICKS_PER_DOLLAR
    return None


def summarize_costs(groups: list[Mapping[str, Any]]) -> dict[str, Any]:
    total_usd = 0.0
    estimated = False
    has_reported = False
    has_priced = False
    unpriced_seconds = 0.0
    breakdown: list[dict[str, Any]] = []

    for group in groups:
        provider = str(group.get("provider") or "Unknown provider")
        model = str(group.get("model") or "Unknown model")
        seconds = max(0.0, float(group.get("seconds") or 0.0))
        estimated_seconds = max(0.0, float(group.get("estimated_seconds") or 0.0))
        reported_usd = max(0.0, float(group.get("reported_cost_usd") or 0.0))
        reported_count = int(group.get("reported_count") or 0)
        rate = transcription_rate(provider, model)
        estimated_usd = estimate_transcription_cost(provider, model, estimated_seconds)

        if reported_count:
            has_reported = True
        if estimated_seconds and estimated_usd is not None and rate and rate.usd_per_hour > 0:
            estimated = True
        if estimated_usd is None:
            unpriced_seconds += estimated_seconds
            known_usd = reported_usd if reported_count else None
        else:
            known_usd = reported_usd + estimated_usd

        if known_usd is not None:
            total_usd += known_usd
            has_priced = True

        if reported_count and estimated_seconds:
            kind = "mixed" if estimated_usd is not None else "partial"
        elif reported_count:
            kind = "reported"
        elif estimated_usd is not None and rate and rate.usd_per_hour > 0:
            kind = "estimated"
        elif estimated_usd is not None:
            kind = "local"
        else:
            kind = "unavailable"

        breakdown.append(
            {
                "provider": rate.provider if rate else provider,
                "model": model,
                "dictations": int(group.get("dictations") or 0),
                "words": int(group.get("words") or 0),
                "seconds": seconds,
                "cost_usd": known_usd,
                "kind": kind,
                "rate_label": rate.label if rate else "Rate unavailable",
                "source_url": rate.source_url if rate else None,
            }
        )

    return {
        "usd": total_usd,
        "estimated": estimated,
        "has_reported": has_reported,
        "has_priced": has_priced,
        "complete": unpriced_seconds == 0.0,
        "unpriced_seconds": unpriced_seconds,
        "breakdown": breakdown,
    }


def format_usd(value: float) -> str:
    if value == 0:
        return "$0.00"
    if value < 0.01:
        return f"${value:.4f}"
    if value < 1:
        return f"${value:.3f}"
    return f"${value:,.2f}"
