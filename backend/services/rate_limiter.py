"""Global AI API rate limiter — Redis sliding window with in-process fallback.

Enforces RPM (requests per minute) and TPM (tokens per minute) limits
across all workers. Falls back to a single-process Lock + counter when
Redis is unavailable.
"""

import logging
import threading
import time

from config import settings

logger = logging.getLogger(__name__)

# In-process fallback state
_lock = threading.Lock()
_request_timestamps: list[float] = []
_token_timestamps: list[tuple[float, int]] = []  # (timestamp, token_count)


def _get_redis():
    """Reuse the event_bus Redis connection."""
    try:
        from services.event_bus import _get_redis as _eb_redis
        return _eb_redis()
    except Exception:
        return None


def acquire(estimated_tokens: int = 0) -> float:
    """Check rate limits and return seconds to wait before proceeding.

    Args:
        estimated_tokens: Estimated token count for this request.

    Returns:
        Seconds the caller should sleep before making the API call.
        0.0 means proceed immediately.
    """
    r = _get_redis()
    if r is not None:
        return _acquire_redis(r, estimated_tokens)
    return _acquire_local(estimated_tokens)


def _acquire_redis(r, estimated_tokens: int) -> float:
    """Redis-backed sliding window rate limiter."""
    now = time.time()
    window_start = now - 60.0
    wait = 0.0

    try:
        pipe = r.pipeline()

        # RPM check
        rpm_key = "ai_rate:rpm"
        pipe.zremrangebyscore(rpm_key, 0, window_start)
        pipe.zcard(rpm_key)
        pipe.zadd(rpm_key, {f"{now}:{id(pipe)}": now})
        pipe.expire(rpm_key, 120)

        # TPM check
        tpm_key = "ai_rate:tpm"
        pipe.zremrangebyscore(tpm_key, 0, window_start)
        pipe.zrangebyscore(tpm_key, window_start, "+inf", withscores=True)

        results = pipe.execute()

        # RPM: results[1] = current count before our add
        rpm_count = results[1]
        if rpm_count >= settings.ai_rpm_limit:
            # Find oldest entry to determine wait
            oldest = r.zrange(rpm_key, 0, 0, withscores=True)
            if oldest:
                wait = max(wait, oldest[0][1] + 60.0 - now)

        # TPM: results[5] = list of (member, score) tuples in window
        tpm_entries = results[5]
        current_tokens = sum(
            int(member.split(":")[1]) if isinstance(member, str) and ":" in member else 0
            for member, score in tpm_entries
        )
        if current_tokens + estimated_tokens > settings.ai_tpm_limit:
            # Find oldest to determine wait
            if tpm_entries:
                wait = max(wait, tpm_entries[0][1] + 60.0 - now)

        # Record token usage
        if estimated_tokens > 0:
            r.zadd(tpm_key, {f"{now}:{estimated_tokens}": now})
            r.expire(tpm_key, 120)

    except Exception as e:
        logger.warning(f"Redis rate limiter failed, proceeding without limit: {e}")
        return 0.0

    if wait > 0:
        logger.info(f"Rate limiter: waiting {wait:.1f}s (rpm={rpm_count}, tpm~{current_tokens})")
    return max(0.0, wait)


def _acquire_local(estimated_tokens: int) -> float:
    """In-process fallback rate limiter using Lock + timestamps."""
    now = time.time()
    window_start = now - 60.0
    wait = 0.0

    with _lock:
        # Clean old entries
        while _request_timestamps and _request_timestamps[0] < window_start:
            _request_timestamps.pop(0)
        while _token_timestamps and _token_timestamps[0][0] < window_start:
            _token_timestamps.pop(0)

        # RPM check
        if len(_request_timestamps) >= settings.ai_rpm_limit:
            wait = max(wait, _request_timestamps[0] + 60.0 - now)

        # TPM check
        current_tokens = sum(t for _, t in _token_timestamps)
        if current_tokens + estimated_tokens > settings.ai_tpm_limit:
            if _token_timestamps:
                wait = max(wait, _token_timestamps[0][0] + 60.0 - now)

        # Record
        _request_timestamps.append(now)
        if estimated_tokens > 0:
            _token_timestamps.append((now, estimated_tokens))

    if wait > 0:
        logger.info(f"Rate limiter (local): waiting {wait:.1f}s")
    return max(0.0, wait)


def record_actual_tokens(input_tokens: int, output_tokens: int) -> None:
    """Record actual token usage after a call completes (for more accurate TPM tracking)."""
    r = _get_redis()
    now = time.time()
    total = input_tokens + output_tokens

    if r is not None:
        try:
            tpm_key = "ai_rate:tpm"
            r.zadd(tpm_key, {f"{now}:actual:{total}": now})
            r.expire(tpm_key, 120)
        except Exception:
            pass
    else:
        with _lock:
            _token_timestamps.append((now, total))
