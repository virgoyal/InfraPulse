import time
from collections import deque


class QuotaExhausted(Exception):
    """Raised when Gemini is unavailable for the rest of this run.

    Callers should stop making requests rather than retrying.

    `retry_tomorrow` distinguishes the two reasons this happens:
      True  — daily quota / call budget spent. A later run gets a fresh quota,
              so unfinished work is best left for then.
      False — the key or project was rejected outright. No future run will do
              any better until a human intervenes, so callers should fall back
              to local processing instead of deferring indefinitely.
    """

    def __init__(self, message: str, retry_tomorrow: bool = True):
        super().__init__(message)
        self.retry_tomorrow = retry_tomorrow


class GeminiRateLimiter:
    """Token bucket: allows at most `rpm` calls per 60-second window.

    Also enforces a hard per-run call budget so a single run can never burn
    through the whole free-tier daily quota (and so a runaway loop can't
    silently spend hours retrying).
    """

    def __init__(self, rpm: int = 15, budget: int | None = None):
        self.rpm = rpm
        self.budget = budget
        self.calls_made = 0
        self.timestamps: deque = deque()

    @property
    def budget_left(self) -> int | None:
        return None if self.budget is None else max(0, self.budget - self.calls_made)

    def wait(self):
        if self.budget is not None and self.calls_made >= self.budget:
            raise QuotaExhausted(f"per-run call budget of {self.budget} reached")

        now = time.time()
        while self.timestamps and now - self.timestamps[0] > 60:
            self.timestamps.popleft()
        if len(self.timestamps) >= self.rpm:
            sleep_for = 60 - (now - self.timestamps[0]) + 0.1
            print(f"[rate limiter] sleeping {sleep_for:.1f}s", flush=True)
            time.sleep(sleep_for)
            # Re-expire after sleeping so the window stays accurate.
            now = time.time()
            while self.timestamps and now - self.timestamps[0] > 60:
                self.timestamps.popleft()

        self.timestamps.append(time.time())
        self.calls_made += 1
