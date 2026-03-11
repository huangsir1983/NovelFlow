"""Redis-backed event bus for import pipeline SSE events.

Provides cross-worker event delivery via Redis lists + pub/sub.
Falls back to in-memory lists when Redis is unavailable (dev mode).
"""

import json
import logging
import threading
import time
from typing import Any

from config import settings

logger = logging.getLogger(__name__)

# Redis key prefix and TTL
_KEY_PREFIX = "import_events"
_CHANNEL_PREFIX = "import_notify"
_TTL_SECONDS = 7200  # 2 hours

# In-memory fallback storage
_mem_events: dict[str, list[dict]] = {}
_mem_lock = threading.Lock()
_mem_subscribers: dict[str, list[threading.Event]] = {}


def _redis_client():
    """Lazy-create a Redis client. Returns None if unavailable."""
    try:
        import redis
        client = redis.Redis.from_url(settings.redis_url, decode_responses=True)
        client.ping()
        return client
    except Exception:
        return None


# Module-level cached Redis client (lazy init)
_redis: Any = None
_redis_checked = False


def _get_redis():
    global _redis, _redis_checked
    if not _redis_checked:
        _redis = _redis_client()
        _redis_checked = True
        if _redis is None:
            logger.warning("Redis unavailable — event bus falling back to in-memory mode")
        else:
            logger.info("Event bus connected to Redis")
    return _redis


def push_event(task_id: str, event: dict) -> None:
    """Push an event for a task. Stores in Redis list + publishes notification."""
    event_json = json.dumps(event, ensure_ascii=False)
    r = _get_redis()

    if r is not None:
        try:
            key = f"{_KEY_PREFIX}:{task_id}"
            r.rpush(key, event_json)
            r.expire(key, _TTL_SECONDS)
            r.publish(f"{_CHANNEL_PREFIX}:{task_id}", "new")
            return
        except Exception as e:
            logger.warning(f"Redis push failed, falling back to memory: {e}")

    # In-memory fallback
    with _mem_lock:
        _mem_events.setdefault(task_id, []).append(event)
        for evt in _mem_subscribers.get(task_id, []):
            evt.set()


def get_events(task_id: str, since: int = 0) -> list[dict]:
    """Get events for a task starting from index `since`."""
    r = _get_redis()

    if r is not None:
        try:
            key = f"{_KEY_PREFIX}:{task_id}"
            raw_list = r.lrange(key, since, -1)
            return [json.loads(item) for item in raw_list]
        except Exception as e:
            logger.warning(f"Redis get_events failed: {e}")

    # In-memory fallback
    with _mem_lock:
        events = _mem_events.get(task_id, [])
        return list(events[since:])


def event_count(task_id: str) -> int:
    """Get total event count for a task."""
    r = _get_redis()

    if r is not None:
        try:
            return r.llen(f"{_KEY_PREFIX}:{task_id}")
        except Exception:
            pass

    with _mem_lock:
        return len(_mem_events.get(task_id, []))


def subscribe(task_id: str, timeout: float = 15.0) -> bool:
    """Block until a new event is available or timeout.

    Returns True if notified, False on timeout.
    Uses Redis SUBSCRIBE in Redis mode, threading.Event in memory mode.
    """
    r = _get_redis()

    if r is not None:
        try:
            import redis
            pubsub = r.pubsub()
            pubsub.subscribe(f"{_CHANNEL_PREFIX}:{task_id}")
            try:
                msg = pubsub.get_message(timeout=timeout)
                # Skip the subscription confirmation message
                while msg and msg["type"] == "subscribe":
                    msg = pubsub.get_message(timeout=timeout)
                return msg is not None
            finally:
                pubsub.unsubscribe()
                pubsub.close()
        except Exception as e:
            logger.warning(f"Redis subscribe failed: {e}")

    # In-memory fallback: use threading.Event
    evt = threading.Event()
    with _mem_lock:
        _mem_subscribers.setdefault(task_id, []).append(evt)
    try:
        return evt.wait(timeout=timeout)
    finally:
        with _mem_lock:
            subs = _mem_subscribers.get(task_id, [])
            if evt in subs:
                subs.remove(evt)


def cleanup(task_id: str) -> None:
    """Remove all events for a task (called after completion + TTL)."""
    r = _get_redis()
    if r is not None:
        try:
            r.delete(f"{_KEY_PREFIX}:{task_id}")
            return
        except Exception:
            pass

    with _mem_lock:
        _mem_events.pop(task_id, None)
        _mem_subscribers.pop(task_id, None)
