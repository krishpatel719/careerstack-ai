from app.rate_limit import FixedWindowRateLimiter, RateLimit


class FakeClock:
    def __init__(self) -> None:
        self.now = 0.0

    def __call__(self) -> float:
        return self.now

    def advance(self, seconds: float) -> None:
        self.now += seconds


def test_clients_have_independent_fixed_windows() -> None:
    clock = FakeClock()
    limiter = FixedWindowRateLimiter(
        {"resume_analysis": RateLimit(1, 60)}, clock=clock
    )

    first = limiter.check("192.0.2.1", "resume_analysis")
    second_client = limiter.check("192.0.2.2", "resume_analysis")

    assert first == (True, 0)
    assert second_client == (True, 0)

    blocked = limiter.check("192.0.2.1", "resume_analysis")
    assert blocked.allowed is False
    assert blocked.retry_after == 60


def test_window_resets_after_configured_duration() -> None:
    clock = FakeClock()
    limiter = FixedWindowRateLimiter({"discovery_start": RateLimit(1, 30)}, clock=clock)

    assert limiter.check("198.51.100.7", "discovery_start") == (True, 0)
    clock.advance(29)
    assert limiter.check("198.51.100.7", "discovery_start").allowed is False

    clock.advance(1)
    assert limiter.check("198.51.100.7", "discovery_start") == (True, 0)


def test_blocked_requests_report_remaining_retry_seconds() -> None:
    clock = FakeClock()
    limiter = FixedWindowRateLimiter({"auth_login": RateLimit(2, 10)}, clock=clock)

    assert limiter.check("203.0.113.4", "auth_login").allowed is True
    assert limiter.check("203.0.113.4", "auth_login").allowed is True
    clock.advance(4.2)
    result = limiter.check("203.0.113.4", "auth_login")

    assert result.allowed is False
    assert result.retry_after == 6
