"""Thread-safe, in-memory fixed-window rate limiting.

The limiter is intentionally small and dependency-free.  It is appropriate for a
single application process; state is not shared between worker processes, so a
multi-process deployment needs a shared store (for example Redis) if limits
must apply globally.
"""

from __future__ import annotations

from dataclasses import dataclass
from math import ceil
from threading import Lock
from time import monotonic
from typing import Callable, Mapping, NamedTuple


class RateLimitResult(NamedTuple):
    """The result of checking a request.

    It is a tuple so callers can use either ``result.allowed`` /
    ``result.retry_after`` or unpack it as ``allowed, retry_after``.
    """

    allowed: bool
    retry_after: int


@dataclass(frozen=True)
class RateLimit:
    """A request allowance and fixed window size, in seconds."""

    requests: int
    window_seconds: int

    def __post_init__(self) -> None:
        if self.requests < 1:
            raise ValueError("requests must be at least 1")
        if self.window_seconds < 1:
            raise ValueError("window_seconds must be at least 1")


DEFAULT_LIMITS: Mapping[str, RateLimit] = {
    "auth_register": RateLimit(30, 60),
    "auth_login": RateLimit(30, 60),
    "resume_analysis": RateLimit(10, 60),
    "discovery_start": RateLimit(30, 3600),
}


class FixedWindowRateLimiter:
    """A thread-safe fixed-window limiter keyed by client IP and route bucket.

    Each ``(client_ip, route_bucket)`` pair has its own fixed window.  The
    first request starts the window.  Once the configured request count is
    reached, requests are denied until that window expires.

    Args:
        limits: Optional mapping of route bucket names to :class:`RateLimit`
            values.  The default mapping covers auth registration/login, resume
            analysis, and discovery start operations.
        clock: Monotonic clock function, injectable for deterministic tests.
    """

    def __init__(
        self,
        limits: Mapping[str, RateLimit] | None = None,
        *,
        clock: Callable[[], float] = monotonic,
    ) -> None:
        self._limits = dict(DEFAULT_LIMITS if limits is None else limits)
        if not self._limits:
            raise ValueError("limits must not be empty")
        for bucket, limit in self._limits.items():
            if not isinstance(bucket, str) or not bucket:
                raise ValueError("limit bucket names must be non-empty strings")
            if not isinstance(limit, RateLimit):
                raise TypeError(f"limit for {bucket!r} must be a RateLimit")
        self._clock = clock
        self._state: dict[tuple[str, str], tuple[float, int]] = {}
        self._lock = Lock()

    def reset(self) -> None:
        """Clear all in-memory windows, primarily for isolated test runs."""
        with self._lock:
            self._state.clear()

    def check(self, client_ip: str, route_bucket: str) -> RateLimitResult:
        """Return whether a request is allowed and seconds until retry.

        ``retry_after`` is zero for an allowed request.  For a blocked request
        it is a positive, rounded-up number of seconds until the current fixed
        window resets.
        """
        if not isinstance(client_ip, str) or not client_ip:
            raise ValueError("client_ip must be a non-empty string")
        if not isinstance(route_bucket, str) or not route_bucket:
            raise ValueError("route_bucket must be a non-empty string")
        limit = self._limits.get(route_bucket)
        if limit is None:
            raise ValueError(f"unknown route bucket: {route_bucket!r}")

        now = self._clock()
        key = (client_ip, route_bucket)
        with self._lock:
            # Prune expired windows so a long-lived public process does not
            # retain one entry for every IP it has ever seen.
            for state_key, (state_start, _state_count) in list(self._state.items()):
                state_limit = self._limits.get(state_key[1])
                if state_limit is not None and now - state_start >= state_limit.window_seconds:
                    self._state.pop(state_key, None)

            window_start, count = self._state.get(key, (now, 0))
            elapsed = now - window_start
            if elapsed >= limit.window_seconds:
                window_start = now
                count = 0

            if count < limit.requests:
                self._state[key] = (window_start, count + 1)
                return RateLimitResult(True, 0)

            remaining = limit.window_seconds - elapsed
            # ``elapsed`` can be negative with an injected/custom clock, so
            # keep the public result positive even in that unusual case.
            retry_after = max(1, ceil(remaining))
            return RateLimitResult(False, retry_after)

    def is_allowed(self, client_ip: str, route_bucket: str) -> RateLimitResult:
        """Alias for :meth:`check` for callers that prefer the boolean name."""
        return self.check(client_ip, route_bucket)

    def allow(self, client_ip: str, route_bucket: str) -> RateLimitResult:
        """Alias for :meth:`check`."""
        return self.check(client_ip, route_bucket)
