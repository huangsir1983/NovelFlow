"""Concurrent task quota limiter (global / tenant / project)."""

from __future__ import annotations

import threading
from dataclasses import dataclass

from config import settings

_lock = threading.Lock()
_local_counts: dict[str, int] = {}


@dataclass
class QuotaLease:
    keys: list[str]


def _redis_client():
    try:
        from services.event_bus import _get_redis

        return _get_redis()
    except Exception:
        return None


def _norm_tenant(tenant_id: str | None) -> str:
    return (tenant_id or "default").strip() or "default"


def _keys(task_type: str, tenant_id: str, project_id: str) -> tuple[str, str, str]:
    return (
        f"quota:{task_type}:global",
        f"quota:{task_type}:tenant:{tenant_id}",
        f"quota:{task_type}:project:{project_id}",
    )


def acquire_quota(task_type: str, *, tenant_id: str | None, project_id: str) -> tuple[bool, dict, QuotaLease | None]:
    tenant = _norm_tenant(tenant_id)
    gk, tk, pk = _keys(task_type, tenant, project_id)

    if settings.limit_global_tasks <= 0 or settings.limit_tenant_tasks <= 0 or settings.limit_project_tasks <= 0:
        return False, {
            "scope": "config",
            "limit": 0,
            "current": 0,
            "message": "Quota limits must be > 0",
        }, None

    r = _redis_client()
    if r is not None:
        return _acquire_redis(r, [gk, tk, pk])
    return _acquire_local([gk, tk, pk])


def release_quota(lease: QuotaLease | None):
    if lease is None:
        return
    r = _redis_client()
    if r is not None:
        _release_redis(r, lease.keys)
    else:
        _release_local(lease.keys)


def _acquire_redis(r, keys: list[str]) -> tuple[bool, dict, QuotaLease | None]:
    limits = [settings.limit_global_tasks, settings.limit_tenant_tasks, settings.limit_project_tasks]

    try:
        pipe = r.pipeline()
        for k in keys:
            pipe.get(k)
        vals = pipe.execute()

        counts = [int(v or 0) for v in vals]
        for idx, (count, limit) in enumerate(zip(counts, limits)):
            if count >= limit:
                scope = ["global", "tenant", "project"][idx]
                return False, {
                    "scope": scope,
                    "limit": limit,
                    "current": count,
                    "message": f"{scope} concurrent limit reached ({limit})",
                }, None

        pipe = r.pipeline()
        for k in keys:
            pipe.incr(k)
            pipe.expire(k, 7200)
        pipe.execute()
        return True, {"scope": "ok", "limit": -1, "current": -1, "message": "ok"}, QuotaLease(keys=keys)
    except Exception:
        return _acquire_local(keys)


def _release_redis(r, keys: list[str]) -> None:
    try:
        for k in keys:
            v = r.decr(k)
            if v is not None and int(v) < 0:
                r.set(k, 0)
                r.expire(k, 7200)
    except Exception:
        _release_local(keys)


def _acquire_local(keys: list[str]) -> tuple[bool, dict, QuotaLease | None]:
    limits = [settings.limit_global_tasks, settings.limit_tenant_tasks, settings.limit_project_tasks]
    with _lock:
        for idx, (k, limit) in enumerate(zip(keys, limits)):
            if _local_counts.get(k, 0) >= limit:
                scope = ["global", "tenant", "project"][idx]
                current = _local_counts.get(k, 0)
                return False, {
                    "scope": scope,
                    "limit": limit,
                    "current": current,
                    "message": f"{scope} concurrent limit reached ({limit})",
                }, None
        for k in keys:
            _local_counts[k] = _local_counts.get(k, 0) + 1
    return True, {"scope": "ok", "limit": -1, "current": -1, "message": "ok"}, QuotaLease(keys=keys)


def _release_local(keys: list[str]) -> None:
    with _lock:
        for k in keys:
            cur = _local_counts.get(k, 0)
            _local_counts[k] = max(0, cur - 1)


def get_quota_usage_snapshot() -> dict:
    """Return current quota usage snapshot for health/monitoring."""
    result = {
        "global": 0,
        "tenants": {},
        "projects": {},
    }

    r = _redis_client()
    if r is not None:
        try:
            keys = r.keys("quota:*") or []
            for raw in keys:
                key = raw.decode() if isinstance(raw, bytes) else str(raw)
                parts = key.split(":")
                if len(parts) < 4:
                    continue
                # quota:{task_type}:{scope}[:id]
                scope = parts[2]
                val = int(r.get(key) or 0)
                if scope == "global":
                    result["global"] += val
                elif scope == "tenant" and len(parts) >= 4:
                    result["tenants"][parts[3]] = result["tenants"].get(parts[3], 0) + val
                elif scope == "project" and len(parts) >= 4:
                    result["projects"][parts[3]] = result["projects"].get(parts[3], 0) + val
            return result
        except Exception:
            pass

    with _lock:
        for key, val in _local_counts.items():
            parts = key.split(":")
            if len(parts) < 4:
                continue
            scope = parts[2]
            if scope == "global":
                result["global"] += val
            elif scope == "tenant" and len(parts) >= 4:
                result["tenants"][parts[3]] = result["tenants"].get(parts[3], 0) + val
            elif scope == "project" and len(parts) >= 4:
                result["projects"][parts[3]] = result["projects"].get(parts[3], 0) + val

    return result
