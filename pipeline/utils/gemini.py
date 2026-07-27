"""Shared Gemini helpers: client construction and quota-error classification.

Every network call the pipeline makes must be bounded. Without an explicit
timeout the SDK can block indefinitely, which is how the daily CI job used to
sit for 6 hours before the runner killed it.
"""
from __future__ import annotations

import re

from google import genai

from utils.rate_limiter import QuotaExhausted

REQUEST_TIMEOUT_MS = 60_000

# A 429 that names a *daily* limit will not clear until midnight Pacific —
# retrying within the same run is pointless.
_DAILY_QUOTA_MARKERS = (
    "perday",
    "per_day",
    "per day",
    "requests_per_day",
    "generaterequestsperdayperproject",
    "quota_exceeded",
    "free_tier",
    "billing",
)


def make_client(api_key: str):
    """Build a genai client with a hard request timeout.

    Falls back to a plain client on older SDKs that don't accept http_options.
    """
    try:
        from google.genai import types

        return genai.Client(
            api_key=api_key,
            http_options=types.HttpOptions(timeout=REQUEST_TIMEOUT_MS),
        )
    except Exception as exc:  # pragma: no cover - depends on installed SDK
        print(f"[gemini] could not set request timeout ({exc}); using defaults", flush=True)
        return genai.Client(api_key=api_key)


def is_rate_limit(msg: str) -> bool:
    return "429" in msg or "RESOURCE_EXHAUSTED" in msg.upper()


def is_daily_quota(msg: str) -> bool:
    """True when the error looks like an exhausted daily/free-tier quota."""
    lowered = msg.lower().replace("-", "").replace(" ", "")
    return any(marker.replace(" ", "") in lowered for marker in _DAILY_QUOTA_MARKERS)


def is_auth_error(msg: str) -> bool:
    """API key revoked, project disabled, API not enabled — never retryable."""
    lowered = msg.lower()
    return any(
        s in lowered
        for s in ("401", "403", "permission_denied", "unauthenticated", "api key not valid",
                  "api_key_invalid", "has not been used in project", "is disabled")
    )


def retry_delay_seconds(msg: str, default: int = 30, cap: int = 65) -> int:
    """Parse the server-suggested retry delay from a 429, clamped to `cap`."""
    match = re.search(r"retry.*?(\d+)\s*s", msg, re.I)
    delay = int(match.group(1)) + 2 if match else default
    return min(delay, cap)


def classify(exc: Exception) -> Exception | None:
    """Return QuotaExhausted if this error means 'stop calling Gemini', else None."""
    msg = str(exc)
    if is_auth_error(msg):
        return QuotaExhausted(
            f"Gemini credentials/project rejected the request: {msg[:200]}",
            retry_tomorrow=False,
        )
    if is_rate_limit(msg) and is_daily_quota(msg):
        return QuotaExhausted(f"Gemini daily quota exhausted: {msg[:200]}")
    return None
