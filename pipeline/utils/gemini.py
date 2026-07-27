"""Shared Gemini helpers: client construction and quota-error classification.

Every network call the pipeline makes must be bounded. Without an explicit
timeout the SDK can block indefinitely, which is how the daily CI job used to
sit for 6 hours before the runner killed it.
"""
from __future__ import annotations

import math
import re

from google import genai

from utils.rate_limiter import QuotaExhausted

REQUEST_TIMEOUT_MS = 60_000

# A 429 carries a quotaId naming which ceiling was hit, e.g.
#   GenerateRequestsPerDayPerProjectPerModel-FreeTier     (until midnight Pacific)
#   GenerateRequestsPerMinutePerProjectPerModel-FreeTier  (clears in seconds)
# Only the first is worth abandoning the run over. Matching on softer markers
# like "free_tier" is wrong — they appear in both.
_DAILY_MARKERS = ("perday", "requestsperday")
_PER_MINUTE_MARKERS = ("perminute", "requestsperminute")


def json_config(max_output_tokens: int = 8192):
    """Config forcing a raw-JSON response with no thinking budget.

    Thinking tokens add nothing to a bulk classification task and only make the
    free-tier quota run out faster. Returns None on SDKs that lack these knobs.
    """
    try:
        from google.genai import types

        return types.GenerateContentConfig(
            response_mime_type="application/json",
            max_output_tokens=max_output_tokens,
            thinking_config=types.ThinkingConfig(thinking_budget=0),
        )
    except Exception:  # pragma: no cover - depends on installed SDK
        return None


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
    """True only for an exhausted *daily* quota.

    Anything unrecognised is treated as per-minute throttling, i.e. worth
    retrying — callers bound their retries, so guessing wrong here costs a
    short backoff rather than a stalled run.
    """
    lowered = msg.lower().replace("-", "").replace("_", "").replace(" ", "")
    if any(m in lowered for m in _DAILY_MARKERS):
        return True
    if any(m in lowered for m in _PER_MINUTE_MARKERS):
        return False
    return False


def is_auth_error(msg: str) -> bool:
    """API key revoked, project disabled, API not enabled — never retryable."""
    lowered = msg.lower()
    return any(
        s in lowered
        for s in ("401", "403", "permission_denied", "unauthenticated", "api key not valid",
                  "api_key_invalid", "has not been used in project", "is disabled")
    )


def retry_delay_seconds(msg: str, default: int = 30, cap: int = 65) -> int:
    """Parse the server-suggested retry delay from a 429, clamped to `cap`.

    The delay may be fractional ("Please retry in 30.2s"), so the whole number
    has to be captured — matching bare digits picks up the ".2" and waits 2s.
    """
    match = re.search(r"retry[^0-9]*(\d+(?:\.\d+)?)\s*s", msg, re.I)
    delay = math.ceil(float(match.group(1))) + 2 if match else default
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
        # Keep plenty of the payload: the quota metric and limit value in the
        # error details are the only way to tell which ceiling was hit.
        return QuotaExhausted(f"Gemini daily quota exhausted: {msg[:1200]}")
    return None
