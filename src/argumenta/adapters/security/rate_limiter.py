import time
from collections import defaultdict
from collections.abc import Callable
from threading import Lock


class SlidingWindowRateLimiter:
    """In-memory sliding window, good enough for a single-process beta API.

    Not shared across workers or restarts; a Redis-backed limiter replaces this
    when the API scales past one container.
    """

    def __init__(
        self,
        max_attempts: int,
        window_seconds: int,
        clock: Callable[[], float] = time.monotonic,
    ) -> None:
        self._max_attempts = max_attempts
        self._window = window_seconds
        self._clock = clock
        self._attempts: dict[str, list[float]] = defaultdict(list)
        self._lock = Lock()

    def check(self, key: str) -> bool:
        now = self._clock()
        with self._lock:
            attempts = [t for t in self._attempts[key] if now - t < self._window]
            if len(attempts) >= self._max_attempts:
                self._attempts[key] = attempts
                return False
            attempts.append(now)
            self._attempts[key] = attempts
            return True

    def reset(self, key: str) -> None:
        with self._lock:
            self._attempts.pop(key, None)
