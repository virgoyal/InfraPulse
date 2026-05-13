import time
from collections import deque


class GeminiRateLimiter:
    """Token bucket: allows at most `rpm` calls per 60-second window."""

    def __init__(self, rpm: int = 15):
        self.rpm = rpm
        self.timestamps: deque = deque()

    def wait(self):
        now = time.time()
        while self.timestamps and now - self.timestamps[0] > 60:
            self.timestamps.popleft()
        if len(self.timestamps) >= self.rpm:
            sleep_for = 60 - (now - self.timestamps[0]) + 0.1
            print(f"[rate limiter] sleeping {sleep_for:.1f}s")
            time.sleep(sleep_for)
        self.timestamps.append(time.time())
