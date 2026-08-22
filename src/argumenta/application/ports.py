"""Ports no single feature owns. A port here is one that a second feature
already needed, not one that might be shared some day."""

from typing import Protocol


class RateLimiter(Protocol):
    def check(self, key: str) -> bool:
        """Register one attempt for the key; False when over the limit. The key
        is namespaced by the caller, so two features never share a window."""
        ...

    def reset(self, key: str) -> None: ...
