from __future__ import annotations

import threading
import time
from collections import deque
from dataclasses import dataclass

import requests

from logging_utils import get_logger
from settings import SETTINGS

logger = get_logger(__name__)


SEC_BASE_URL = "https://data.sec.gov"
SEC_WWW_BASE_URL = "https://www.sec.gov"


class SecEdgarApiError(RuntimeError):
    pass


@dataclass(frozen=True)
class SecResponse:
    url: str
    status_code: int
    content: bytes
    content_type: str | None

    def text(self, encoding: str | None = None) -> str:
        if encoding is not None:
            return self.content.decode(encoding, errors="replace")
        return self.content.decode("utf-8", errors="replace")


def _safe_preview_bytes(data: bytes | None, *, limit: int = 2000) -> str:
    """Best-effort, log-safe preview of response body.

    Truncates to `limit` bytes and decodes with replacement.
    """

    if not data:
        return ""
    try:
        return data[:limit].decode("utf-8", errors="replace")
    except Exception:
        # Fall back to repr-like preview.
        try:
            return repr(data[:limit])
        except Exception:
            return ""


def _headers_for_log(headers: dict[str, str]) -> dict[str, str]:
    """Return a redacted copy of headers for logging."""

    redacted: dict[str, str] = {}
    for k, v in (headers or {}).items():
        lk = str(k).lower()
        if (
            lk in {"authorization", "x-api-key", "api-key"}
            or "token" in lk
            or "secret" in lk
        ):
            redacted[str(k)] = "<redacted>"
        else:
            redacted[str(k)] = str(v)
    return redacted


class SlidingWindowRateLimiter:
    """Thread-safe sliding-window rate limiter.

    Enforces at most `max_requests` in any `window_seconds` wall-clock window.

    Default for SEC EDGAR: 9 requests per 1 second (stays under 10 req/s).
    """

    def __init__(self, *, max_requests: int = 9, window_seconds: float = 1.0):
        if max_requests <= 0:
            raise ValueError("max_requests must be > 0")
        if window_seconds <= 0:
            raise ValueError("window_seconds must be > 0")

        self._max_requests = int(max_requests)
        self._window_seconds = float(window_seconds)
        self._lock = threading.Lock()
        self._events: deque[float] = deque()  # monotonic timestamps

    def acquire(self) -> None:
        """Block until a request token is available."""
        while True:
            sleep_for = 0.0
            now = time.monotonic()

            with self._lock:
                # Drop events outside the window.
                cutoff = now - self._window_seconds
                while self._events and self._events[0] <= cutoff:
                    self._events.popleft()

                if len(self._events) < self._max_requests:
                    self._events.append(now)
                    return

                # Need to wait until the oldest event exits window.
                oldest = self._events[0]
                sleep_for = max((oldest + self._window_seconds) - now, 0.001)

            time.sleep(sleep_for)


_default_rate_limiter = SlidingWindowRateLimiter(max_requests=9, window_seconds=1.0)


def _sec_user_agent() -> str:
    """Resolve User-Agent for SEC requests.

    SEC requires a descriptive UA that includes contact info.

    Configure via:
      SETTINGS["SEC_USER_AGENT"] = "AppName your@email.com"

    If missing, falls back to a safe placeholder, but callers should set it.
    """

    ua = SETTINGS.get("SEC_USER_AGENT")
    if isinstance(ua, str) and ua.strip():
        return ua.strip()
    return "InvestorGuide (contact: unset)"


def _parse_retry_after_seconds(value: str | None) -> float | None:
    if not value:
        return None
    v = value.strip()
    if not v:
        return None

    # Retry-After can be integer seconds or an HTTP date. For now handle the common
    # integer-seconds case robustly.
    try:
        return float(int(v))
    except Exception:
        return None


def _sleep_backoff(
    attempt_index: int, *, base_seconds: float = 0.5, cap_seconds: float = 8.0
) -> None:
    # Basic exponential backoff: 0.5, 1, 2 ... capped
    delay = min(base_seconds * (2**attempt_index), cap_seconds)
    time.sleep(delay)


def _request(
    *,
    url: str,
    session: requests.Session | None = None,
    headers: dict[str, str] | None = None,
    timeout_seconds: float = 30.0,
    rate_limiter: SlidingWindowRateLimiter | None = None,
    max_attempts: int = 3,
) -> SecResponse:
    """HTTP GET with SEC constraints (UA + throttling + retry/backoff)."""

    if max_attempts <= 0:
        raise ValueError("max_attempts must be >= 1")

    s = session or requests.Session()
    rl = rate_limiter or _default_rate_limiter

    merged_headers = {"User-Agent": _sec_user_agent(), "Accept-Encoding": "gzip"}
    if headers:
        merged_headers.update(headers)

    last_exc: Exception | None = None

    for attempt in range(max_attempts):
        rl.acquire()
        try:
            resp = s.get(url, headers=merged_headers, timeout=timeout_seconds)
        except Exception as e:  # requests exceptions
            last_exc = e
            logger.warning(
                "SEC request failed | url=%s attempt=%s err=%s",
                url,
                attempt + 1,
                e,
            )
            if attempt < max_attempts - 1:
                _sleep_backoff(attempt)
                continue
            raise

        # Success
        if 200 <= resp.status_code < 300:
            return SecResponse(
                url=url,
                status_code=resp.status_code,
                content=resp.content,
                content_type=resp.headers.get("Content-Type"),
            )

        retry_after_raw = resp.headers.get("Retry-After")
        retry_after = _parse_retry_after_seconds(retry_after_raw)

        # Detailed error diagnostics (safe previews only)
        try:
            logger.warning(
                "SEC non-2xx response | status=%s url=%s attempt=%s/%s content_type=%s retry_after=%s headers=%s body_preview=%s",
                resp.status_code,
                url,
                attempt + 1,
                max_attempts,
                resp.headers.get("Content-Type"),
                retry_after_raw,
                _headers_for_log(merged_headers),
                _safe_preview_bytes(getattr(resp, "content", b"")),
            )
        except Exception:
            # Never let logging break the request flow.
            logger.debug("SEC response logging failed", exc_info=True)

        # Retryable
        if resp.status_code in (429, 500, 502, 503, 504):
            if attempt < max_attempts - 1:
                if retry_after is not None:
                    time.sleep(retry_after)
                else:
                    _sleep_backoff(attempt)
                continue

        # Non-retryable or final attempt
        msg = f"SEC request failed status={resp.status_code} url={url}"
        raise SecEdgarApiError(msg)

    # Should not reach
    if last_exc is not None:
        raise last_exc
    raise SecEdgarApiError(f"SEC request failed url={url}")


def fetch_companyfacts(cik: str, *, session: requests.Session | None = None) -> dict:
    """Fetch SEC companyfacts JSON for a CIK.

    Endpoint:
      https://data.sec.gov/api/xbrl/companyfacts/CIK##########.json
    """

    cik10 = str(int(str(cik))).zfill(10)
    url = f"{SEC_BASE_URL}/api/xbrl/companyfacts/CIK{cik10}.json"
    r = _request(url=url, session=session, headers={"Accept": "application/json"})
    return requests.models.complexjson.loads(r.content.decode("utf-8"))


def fetch_submissions(cik: str, *, session: requests.Session | None = None) -> dict:
    """Fetch SEC submissions JSON for a CIK.

    Endpoint:
      https://data.sec.gov/submissions/CIK##########.json
    """

    cik10 = str(int(str(cik))).zfill(10)
    url = f"{SEC_BASE_URL}/submissions/CIK{cik10}.json"
    r = _request(url=url, session=session, headers={"Accept": "application/json"})
    return requests.models.complexjson.loads(r.content.decode("utf-8"))


def fetch_filing_index(
    cik: str,
    accession_number: str,
    *,
    session: requests.Session | None = None,
) -> str:
    """Fetch the filing index HTML page for an accession number."""

    cik_nozeros = str(int(str(cik)))
    acc_raw = str(accession_number).strip()
    acc_nodash = acc_raw.replace("-", "")
    url = f"{SEC_WWW_BASE_URL}/Archives/edgar/data/{cik_nozeros}/{acc_nodash}/{acc_raw}-index.htm"
    r = _request(
        url=url, session=session, headers={"Accept": "text/html,application/xhtml+xml"}
    )
    return r.text()


def fetch_filing_document(
    *,
    cik: str,
    accession_number: str,
    document_name: str,
    session: requests.Session | None = None,
) -> bytes:
    """Fetch a specific filing document (raw bytes)."""

    cik_nozeros = str(int(str(cik)))
    acc_nodash = str(accession_number).strip().replace("-", "")
    doc = str(document_name).lstrip("/")
    url = f"{SEC_WWW_BASE_URL}/Archives/edgar/data/{cik_nozeros}/{acc_nodash}/{doc}"
    r = _request(url=url, session=session)
    return r.content


def fetch_rss_feed(
    *,
    url: str = "https://www.sec.gov/Archives/edgar/usgaap.rss.xml",
    session: requests.Session | None = None,
) -> bytes:
    """Fetch an EDGAR RSS/Atom feed (raw bytes)."""

    r = _request(
        url=url,
        session=session,
        headers={
            "Accept": "application/rss+xml,application/atom+xml,application/xml,text/xml"
        },
    )
    return r.content
