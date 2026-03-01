from __future__ import annotations

from types import SimpleNamespace

import pytest

import utils.sec_edgar_api as api


class _FakeResponse:
    def __init__(
        self, *, status_code: int, content: bytes = b"ok", headers: dict | None = None
    ):
        self.status_code = status_code
        self.content = content
        self.headers = headers or {}


class _FakeSession:
    def __init__(self, responses):
        self._responses = list(responses)
        self.calls = []

    def get(self, url, headers=None, timeout=None):
        self.calls.append({"url": url, "headers": headers or {}, "timeout": timeout})
        if not self._responses:
            raise RuntimeError("No more fake responses")
        r = self._responses.pop(0)
        if isinstance(r, Exception):
            raise r
        return r


class _FakeLimiter:
    def __init__(self):
        self.acquires = 0

    def acquire(self):
        self.acquires += 1


def test_user_agent_is_always_present(monkeypatch):
    monkeypatch.setitem(api.SETTINGS, "SEC_USER_AGENT", "UnitTest UA test@example.com")

    s = _FakeSession(
        [
            _FakeResponse(
                status_code=200,
                content=b"{}",
                headers={"Content-Type": "application/json"},
            )
        ]
    )
    limiter = _FakeLimiter()

    api._request(url="https://example.test/", session=s, rate_limiter=limiter)

    assert s.calls
    assert "User-Agent" in s.calls[0]["headers"]
    assert "UnitTest UA" in s.calls[0]["headers"]["User-Agent"]


def test_rate_limiter_invoked(monkeypatch):
    monkeypatch.setitem(api.SETTINGS, "SEC_USER_AGENT", "UnitTest UA test@example.com")

    s = _FakeSession([_FakeResponse(status_code=200, content=b"ok")])
    limiter = _FakeLimiter()

    api._request(url="https://example.test/", session=s, rate_limiter=limiter)
    assert limiter.acquires == 1


@pytest.mark.parametrize("status_code", [429, 500, 502, 503, 504])
def test_retry_on_retryable_status_codes(monkeypatch, status_code):
    monkeypatch.setitem(api.SETTINGS, "SEC_USER_AGENT", "UnitTest UA test@example.com")

    # first attempt retryable, second attempt success
    s = _FakeSession(
        [
            _FakeResponse(
                status_code=status_code, content=b"nope", headers={"Retry-After": "0"}
            ),
            _FakeResponse(status_code=200, content=b"ok"),
        ]
    )
    limiter = _FakeLimiter()

    # Avoid real sleeping
    monkeypatch.setattr(api.time, "sleep", lambda _x: None)

    r = api._request(
        url="https://example.test/", session=s, rate_limiter=limiter, max_attempts=3
    )
    assert r.status_code == 200
    assert len(s.calls) == 2
    assert limiter.acquires == 2


def test_non_retryable_status_raises(monkeypatch):
    monkeypatch.setitem(api.SETTINGS, "SEC_USER_AGENT", "UnitTest UA test@example.com")

    s = _FakeSession([_FakeResponse(status_code=403, content=b"no")])
    limiter = _FakeLimiter()

    with pytest.raises(api.SecEdgarApiError):
        api._request(
            url="https://example.test/", session=s, rate_limiter=limiter, max_attempts=3
        )
