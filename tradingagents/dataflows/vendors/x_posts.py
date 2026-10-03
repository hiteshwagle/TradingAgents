"""X API v2 recent-Post search for the Sentiment Analyst.

The source is optional: without ``X_BEARER_TOKEN`` the formatted fetcher returns
an explicit unavailable marker. Raw search helpers raise ``XAPIError`` so
programmatic callers can distinguish authentication/API failures from an empty
result. Responses are cached to avoid charging repeatedly for the same Posts.
"""

from __future__ import annotations

import hashlib
import html
import json
import logging
import os
import random
import re
import time
from datetime import date, datetime, time as datetime_time, timedelta, timezone
from pathlib import Path

import certifi
import requests

from tradingagents.dataflows.config import get_config

logger = logging.getLogger(__name__)

X_RECENT_SEARCH_URL = "https://api.x.com/2/tweets/search/recent"
POST_FIELDS = "id,text,created_at,lang,public_metrics,possibly_sensitive,source"
MARKET_EVENT_TERMS = (
    "earnings",
    "revenue",
    "guidance",
    "acquisition",
    "partnership",
    "SEC",
    "downgrade",
    "upgrade",
)
DEFAULT_LIMIT = 20
DEFAULT_CACHE_TTL_SECONDS = 86_400
MAX_LIMIT = 100
_RETRYABLE_STATUSES = {429, 500, 502, 503, 504}
_SYMBOL_RE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._=^-]{0,31}$")


class XAPIError(RuntimeError):
    """Raised when X cannot return a usable recent-search response."""


def _positive_int_env(name: str, default: int) -> int:
    raw = os.getenv(name)
    if not raw:
        return default
    try:
        value = int(raw)
    except ValueError as exc:
        raise ValueError(f"{name} must be an integer, got {raw!r}") from exc
    if value <= 0:
        raise ValueError(f"{name} must be greater than zero")
    return value


def _cache_dir() -> Path:
    configured = os.getenv("X_API_CACHE_DIR")
    if configured:
        root = Path(configured).expanduser()
    else:
        root = Path(get_config()["data_cache_dir"]).expanduser() / "x"
    return root


def _cashtag(symbol: str) -> str:
    value = symbol.strip().upper()
    if not _SYMBOL_RE.fullmatch(value):
        raise ValueError(
            "symbol must be 1-32 characters containing only letters, numbers, '.', '_', "
            "'-', '=', '^'"
        )
    # Exchange and quote suffixes are not normally part of an X cashtag:
    # BHP.AX -> $BHP, BTC-USD -> $BTC, EURUSD=X -> $EURUSD.
    return re.split(r"[.=-]", value, maxsplit=1)[0]


def build_symbol_query(
    symbol: str,
    company_name: str | None = None,
    *,
    language: str = "en",
) -> str:
    """Build an X query for market-moving English Posts about a symbol."""
    if not re.fullmatch(r"[A-Za-z]{2,8}", language):
        raise ValueError("language must be a 2-8 letter X language code")

    terms = [f"${_cashtag(symbol)}"]
    if company_name:
        cleaned = " ".join(company_name.split()).replace("\\", "").replace('"', "")
        if not cleaned or len(cleaned) > 100:
            raise ValueError("company_name must contain 1-100 characters")
        terms.append(f'"{cleaned}"')

    event_filter = " OR ".join(MARKET_EVENT_TERMS)
    return f"({' OR '.join(terms)}) ({event_filter}) lang:{language.lower()} -is:retweet"


def _with_engagement_score(post: dict) -> dict:
    """Return a Post copy with likes + 2*reposts + replies."""
    metrics = post.get("public_metrics")
    if not isinstance(metrics, dict):
        metrics = {}

    def metric(name: str) -> int:
        value = metrics.get(name, 0)
        return value if isinstance(value, int) and not isinstance(value, bool) else 0

    # X renamed this metric from retweet_count to repost_count. Accept the old
    # name as a fallback so previously cached responses remain usable.
    reposts = metric("repost_count")
    if "repost_count" not in metrics:
        reposts = metric("retweet_count")

    scored_post = dict(post)
    scored_post["score"] = metric("like_count") + reposts * 2 + metric("reply_count")
    return scored_post


def _cache_key(params: dict[str, str]) -> str:
    encoded = json.dumps(params, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(encoded.encode()).hexdigest()


def _read_cache(path: Path, ttl_seconds: int) -> dict | None:
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
        fetched_at = datetime.fromisoformat(payload["fetched_at"].replace("Z", "+00:00"))
    except (OSError, ValueError, KeyError, TypeError, json.JSONDecodeError):
        return None

    age = datetime.now(timezone.utc) - fetched_at.astimezone(timezone.utc)
    if age.total_seconds() < ttl_seconds:
        payload["cached"] = True
        return payload
    return None


def _write_cache(path: Path, payload: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.parent.chmod(0o700)
    temporary = path.with_suffix(".tmp")
    temporary.write_text(json.dumps(payload, ensure_ascii=False), encoding="utf-8")
    temporary.chmod(0o600)
    temporary.replace(path)


def _error_detail(body: bytes, status: int) -> str:
    try:
        payload = json.loads(body.decode("utf-8", errors="replace"))
        detail = payload.get("detail") or payload.get("title") or payload.get("errors")
        return f"X API HTTP {status}: {detail}"
    except (ValueError, AttributeError):
        return f"X API HTTP {status}"


def _safe_error_message(exc: Exception, *, limit: int = 500) -> str:
    """Return a single-line error detail that cannot expose the bearer token."""
    detail = " ".join(str(exc).split()) or type(exc).__name__
    token = os.getenv("X_BEARER_TOKEN")
    if token:
        detail = detail.replace(token, "[REDACTED]")
    if len(detail) > limit:
        return detail[: limit - 1] + "…"
    return detail


def _request_json(params: dict[str, str], bearer_token: str) -> dict:
    backoff = 1.0
    for attempt in range(3):
        try:
            response = requests.get(
                X_RECENT_SEARCH_URL,
                params=params,
                headers={
                    "Authorization": f"Bearer {bearer_token}",
                    "Accept": "application/json",
                    "User-Agent": "TradingAgents-X-Sentiment/1.0",
                },
                timeout=20,
                verify=certifi.where(),
            )
            if response.status_code >= 400:
                if response.status_code not in _RETRYABLE_STATUSES or attempt == 2:
                    raise XAPIError(_error_detail(response.content, response.status_code))
                try:
                    wait = min(30.0, max(0.0, float(response.headers.get("Retry-After"))))
                except (TypeError, ValueError):
                    wait = backoff * random.uniform(0.8, 1.2)
            else:
                return response.json()
        except requests.exceptions.JSONDecodeError as exc:
            if attempt == 2:
                detail = _safe_error_message(exc)
                raise XAPIError(f"X API returned invalid JSON: {detail}") from None
            wait = backoff * random.uniform(0.8, 1.2)
        except requests.exceptions.RequestException as exc:
            if attempt == 2:
                detail = _safe_error_message(exc)
                raise XAPIError(f"X API request failed: {detail}") from None
            wait = backoff * random.uniform(0.8, 1.2)
        time.sleep(wait)
        backoff *= 2
    raise XAPIError("X API request failed")


def search_recent_posts(
    query: str,
    *,
    limit: int | None = None,
    start_time: str | None = None,
    end_time: str | None = None,
    bearer_token: str | None = None,
    use_cache: bool = True,
    cache_only: bool = False,
    cache_ttl_seconds: int | None = None,
) -> dict:
    """Return a JSON-serializable collection of recent X Posts."""
    token = bearer_token or os.getenv("X_BEARER_TOKEN")

    resolved_limit = (
        limit if limit is not None else _positive_int_env("X_POST_LIMIT_PER_SYMBOL", DEFAULT_LIMIT)
    )
    if not 10 <= resolved_limit <= MAX_LIMIT:
        raise ValueError(f"limit must be between 10 and {MAX_LIMIT}, as required by X")
    if not query.strip() or len(query) > 512:
        raise ValueError("query must contain 1-512 characters")

    params = {
        "query": query.strip(),
        "max_results": str(resolved_limit),
        "post.fields": POST_FIELDS,
        "expansions": "author_id",
    }
    if start_time:
        params["start_time"] = start_time
    if end_time:
        params["end_time"] = end_time

    ttl = cache_ttl_seconds or _positive_int_env("X_CACHE_TTL_SECONDS", DEFAULT_CACHE_TTL_SECONDS)
    cache_path = _cache_dir() / f"{_cache_key(params)}.json"
    if use_cache:
        cached = _read_cache(cache_path, ttl)
        if cached is not None:
            cached["posts"] = [
                _with_engagement_score(post)
                for post in cached.get("posts", [])[:resolved_limit]
                if isinstance(post, dict)
            ]
            cached["count"] = len(cached["posts"])
            return cached

    if cache_only:
        raise XAPIError("No matching X response is available in the local cache")
    if not token:
        raise XAPIError("X_BEARER_TOKEN is not set")

    response = _request_json(params, token)
    posts = response.get("data") or []
    if not isinstance(posts, list):
        raise XAPIError("X API returned malformed Post data")
    posts = [
        _with_engagement_score(post) for post in posts[:resolved_limit] if isinstance(post, dict)
    ]

    payload = {
        "ok": True,
        "source": "x_api_v2_recent_search",
        "query": query.strip(),
        "fetched_at": datetime.now(timezone.utc).isoformat().replace("+00:00", "Z"),
        "cached": False,
        "count": len(posts),
        "posts": posts,
        "meta": response.get("meta", {}),
    }
    if use_cache:
        _write_cache(cache_path, payload)
    return payload


def search_symbol_posts(
    symbol: str,
    company_name: str | None = None,
    **kwargs,
) -> dict:
    """Search recent English Posts for a symbol and optional company name."""
    return search_recent_posts(build_symbol_query(symbol, company_name), **kwargs)


def _date_bounds(start_date: str | None, end_date: str | None) -> tuple[str | None, str | None]:
    """Convert a historical inclusive date window to X API UTC timestamps.

    A live run leaves the bounds unset and lets the recent-search endpoint use
    its native retention window. This avoids sending a midnight start that is
    slightly older than the endpoint permits later in the current day.
    """
    if not (start_date and end_date):
        return None, None
    start_day = datetime.strptime(start_date, "%Y-%m-%d").date()
    end_day = datetime.strptime(end_date, "%Y-%m-%d").date()
    if start_day > end_day:
        raise ValueError("start_date must not be after end_date")
    if end_day > date.today():
        raise ValueError("end_date must not be in the future")
    if end_day == date.today():
        return None, None
    start = datetime.combine(start_day, datetime_time.min, tzinfo=timezone.utc)
    end = datetime.combine(
        end_day,
        datetime_time.max,
        tzinfo=timezone.utc,
    )
    return (
        start.isoformat().replace("+00:00", "Z"),
        end.isoformat(timespec="seconds").replace("+00:00", "Z"),
    )


def fetch_x_posts(
    ticker: str,
    company_name: str | None = None,
    *,
    limit: int | None = None,
    start_date: str | None = None,
    end_date: str | None = None,
    screen=None,
    mode: str = "recent",
) -> str:
    """Return recent X Posts as a prompt-ready, score-ordered text block."""
    if mode not in {"disabled", "recent", "cache_only"}:
        return "<X unavailable: unsupported X access mode>"
    if mode == "disabled":
        return "<X disabled for this historical validation>"
    if mode != "cache_only" and not os.getenv("X_BEARER_TOKEN"):
        return "<X unavailable: X_BEARER_TOKEN is not set>"

    try:
        start_time, end_time = _date_bounds(start_date, end_date)
        # Recent search cannot reconstruct an old historical window. Skip the
        # network request instead of spending quota on a request that cannot
        # produce point-in-time evidence. A matching saved response remains
        # usable in cache-only mode.
        if mode == "recent" and end_date:
            end_day = datetime.strptime(end_date, "%Y-%m-%d").date()
            if end_day < date.today() - timedelta(days=7):
                return "<X unavailable: selected date is outside recent-search retention>"
        result = search_symbol_posts(
            ticker,
            company_name,
            limit=limit,
            start_time=start_time,
            end_time=end_time,
            cache_only=mode == "cache_only",
        )
    except (XAPIError, ValueError) as exc:
        detail = _safe_error_message(exc)
        logger.warning("X fetch failed for %s: %s", ticker, detail)
        return f"<X unavailable: {type(exc).__name__}: {detail}>"

    posts = sorted(result["posts"], key=lambda post: post.get("score", 0), reverse=True)
    if not posts:
        return f"<no X Posts found for ${ticker.upper()}>"

    note = ""
    if screen:
        keep, note = screen([str(post.get("text") or "") for post in posts])
        screened = len(posts)
        posts = [post for post, kept in zip(posts, keep, strict=True) if kept]
        if not posts:
            return f"{note}\n\n<none of the {screened} X Posts is about ${ticker.upper()}>"

    lines = []
    for post in posts:
        metrics = post.get("public_metrics") or {}
        reposts = metrics.get("repost_count", metrics.get("retweet_count", 0))
        text = html.unescape(str(post.get("text") or "")).replace("\n", " ").strip()
        if len(text) > 500:
            text = text[:500] + "…"
        lines.append(
            f"[{post.get('created_at', '')} · author {post.get('author_id', '?')} · "
            f"score {post.get('score', 0)} · likes {metrics.get('like_count', 0)} · "
            f"reposts {reposts} · replies "
            f"{metrics.get('reply_count', 0)}] {text}"
        )

    summary = f"{len(posts)} X Posts ordered by engagement score (likes + 2×reposts + replies)."
    return (f"{note}\n\n" if note else "") + summary + "\n\n" + "\n".join(lines)
