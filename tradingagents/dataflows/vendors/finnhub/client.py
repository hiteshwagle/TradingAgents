"""Shared authenticated, cached and rate-limited Finnhub HTTP client."""

from __future__ import annotations

import contextlib
import hashlib
import json
import os
import threading
import time
from collections import deque
from contextlib import contextmanager
from contextvars import ContextVar
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import certifi
import requests

from tradingagents.dataflows.config import get_config
from tradingagents.dataflows.errors import (
    VendorError,
    VendorNotConfiguredError,
    VendorRateLimitError,
)

BASE_URL = "https://finnhub.io/api/v1"
REQUEST_TIMEOUT_SECONDS = 30

_rate_lock = threading.Lock()
_request_times: deque[float] = deque()
_key_locks_guard = threading.Lock()
_key_locks: dict[str, threading.Lock] = {}
_semaphores_guard = threading.Lock()
_semaphores: dict[int, threading.BoundedSemaphore] = {}


@dataclass
class _RunBudget:
    """Mutable so copied LangGraph contexts share one counter for the run."""

    max_calls: int
    used_calls: int = 0
    lock: threading.Lock = field(default_factory=threading.Lock)

    def consume(self) -> None:
        with self.lock:
            if self.used_calls >= self.max_calls:
                raise VendorRateLimitError(
                    f"Finnhub per-run call budget reached ({self.max_calls})"
                )
            self.used_calls += 1


_run_budget: ContextVar[_RunBudget | None] = ContextVar(
    "finnhub_run_budget", default=None
)


@contextmanager
def finnhub_run_budget(max_calls: int):
    """Limit uncached Finnhub HTTP calls made by one graph execution."""
    budget = _RunBudget(_positive_int(max_calls, "finnhub_max_calls_per_run"))
    token = _run_budget.set(budget)
    try:
        yield budget
    finally:
        _run_budget.reset(token)


def _consume_run_budget() -> None:
    budget = _run_budget.get()
    if budget is not None:
        budget.consume()


def require_api_key() -> str:
    key = os.getenv("FINNHUB_API_KEY", "").strip()
    if not key:
        raise VendorNotConfiguredError("Finnhub requires FINNHUB_API_KEY")
    return key


def _positive_int(value: object, name: str) -> int:
    try:
        parsed = int(value)
    except (TypeError, ValueError) as exc:
        raise ValueError(f"{name} must be a positive integer") from exc
    if parsed < 1:
        raise ValueError(f"{name} must be a positive integer")
    return parsed


def _cache_path(endpoint: str, params: dict[str, Any]) -> Path:
    canonical = json.dumps(
        {"endpoint": endpoint, "params": params},
        sort_keys=True,
        separators=(",", ":"),
        default=str,
    )
    digest = hashlib.sha256(canonical.encode("utf-8")).hexdigest()
    root = Path(get_config()["data_cache_dir"]).expanduser() / "finnhub"
    root.mkdir(parents=True, exist_ok=True)
    return root / f"{digest}.json"


def _read_cache(path: Path, ttl_seconds: int) -> Any | None:
    try:
        if time.time() - path.stat().st_mtime >= ttl_seconds:
            return None
        return json.loads(path.read_text(encoding="utf-8"))
    except (FileNotFoundError, json.JSONDecodeError, OSError):
        return None


def _write_cache(path: Path, payload: Any) -> None:
    temporary = path.with_name(
        f".{path.name}.{os.getpid()}.{threading.get_ident()}.tmp"
    )
    try:
        temporary.write_text(json.dumps(payload, separators=(",", ":")), encoding="utf-8")
        temporary.replace(path)
    except OSError:
        # Cache failure must not discard valid market data.
        with contextlib.suppress(OSError):
            temporary.unlink()


def _lock_for(key: str) -> threading.Lock:
    with _key_locks_guard:
        return _key_locks.setdefault(key, threading.Lock())


def _semaphore(limit: int) -> threading.BoundedSemaphore:
    with _semaphores_guard:
        return _semaphores.setdefault(limit, threading.BoundedSemaphore(limit))


def _wait_for_rate_slot(requests_per_minute: int) -> None:
    while True:
        with _rate_lock:
            now = time.monotonic()
            while _request_times and now - _request_times[0] >= 60:
                _request_times.popleft()
            if len(_request_times) < requests_per_minute:
                _request_times.append(now)
                return
            wait = max(0.01, 60 - (now - _request_times[0]))
        time.sleep(min(wait, 60))


def _api_error(payload: Any) -> str:
    if isinstance(payload, dict) and payload.get("error"):
        return str(payload["error"])
    return ""


def _request(endpoint: str, params: dict[str, Any], api_key: str) -> Any:
    config = get_config()
    requests_per_minute = _positive_int(
        config["finnhub_requests_per_minute"], "finnhub_requests_per_minute"
    )
    max_concurrency = _positive_int(
        config["finnhub_max_concurrency"], "finnhub_max_concurrency"
    )

    _consume_run_budget()
    _wait_for_rate_slot(requests_per_minute)
    try:
        with _semaphore(max_concurrency):
            response = requests.get(
                f"{BASE_URL}/{endpoint.lstrip('/')}",
                headers={"X-Finnhub-Token": api_key, "Accept": "application/json"},
                params=params,
                timeout=REQUEST_TIMEOUT_SECONDS,
                verify=certifi.where(),
            )
    except requests.RequestException as exc:
        raise VendorRateLimitError(f"Finnhub request failed ({type(exc).__name__})") from None

    if response.status_code in {401, 403}:
        raise VendorNotConfiguredError(
            f"Finnhub credentials or endpoint entitlement were rejected (HTTP {response.status_code})"
        )
    if response.status_code == 429:
        retry_after = response.headers.get("Retry-After")
        detail = f"; retry after {retry_after}s" if retry_after else ""
        raise VendorRateLimitError(f"Finnhub rate limit reached (HTTP 429{detail})")
    if response.status_code >= 500:
        raise VendorRateLimitError(f"Finnhub is temporarily unavailable (HTTP {response.status_code})")
    if response.status_code >= 400:
        raise VendorError(f"Finnhub rejected the request (HTTP {response.status_code})")

    try:
        payload = response.json()
    except (requests.JSONDecodeError, ValueError) as exc:
        raise VendorRateLimitError("Finnhub returned an unreadable response") from exc

    error = _api_error(payload)
    if error:
        lowered = error.lower()
        if "limit" in lowered or "too many" in lowered:
            raise VendorRateLimitError("Finnhub rate limit reached")
        if any(word in lowered for word in ("token", "api key", "permission", "premium")):
            raise VendorNotConfiguredError("Finnhub key does not permit this endpoint")
        raise VendorError(f"Finnhub returned an API error: {error[:200]}")
    return payload


def get_json(
    endpoint: str,
    params: dict[str, Any] | None = None,
    *,
    cache_ttl_seconds: int | None = None,
) -> Any:
    """Fetch one Finnhub endpoint with shared auth, cache and single-flight locking."""
    api_key = require_api_key()
    params = {key: value for key, value in (params or {}).items() if value is not None}
    config = get_config()
    ttl = _positive_int(
        cache_ttl_seconds or config["finnhub_cache_ttl_seconds"],
        "finnhub_cache_ttl_seconds",
    )
    path = _cache_path(endpoint, params)
    cached = _read_cache(path, ttl)
    if cached is not None:
        return cached

    lock = _lock_for(path.name)
    with lock:
        cached = _read_cache(path, ttl)
        if cached is not None:
            return cached
        payload = _request(endpoint, params, api_key)
        _write_cache(path, payload)
        return payload
