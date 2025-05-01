"""Redis-backed caching for metric queries.

Rather than deleting individual keys when new data arrives (which would require scanning
Redis), every (source, metric) pair has a monotonically increasing *version* number. Cache
keys embed the current version, so bumping the version on ingest instantly orphans all stale
entries; Redis evicts them once their TTL expires.
"""
from __future__ import annotations

import hashlib
import json
import logging
from typing import Any, Callable, TypeVar

from django.conf import settings
from django.core.cache import cache

logger = logging.getLogger(__name__)

T = TypeVar("T")

VERSION_KEY = "ver:{source_id}:{metric}"
# Version counters must outlive any cached value that references them.
VERSION_TTL = 60 * 60 * 24


def _version_key(source_id: int, metric: str) -> str:
    return VERSION_KEY.format(source_id=source_id, metric=metric)


def get_version(source_id: int, metric: str) -> int:
    version = cache.get(_version_key(source_id, metric))
    if version is None:
        cache.add(_version_key(source_id, metric), 1, VERSION_TTL)
        return 1
    return int(version)


def bump_version(source_id: int, metric: str) -> int:
    key = _version_key(source_id, metric)
    try:
        return int(cache.incr(key))
    except ValueError:
        # Key missing (never read, or expired). Start a fresh counter above 1 so any
        # entries written under the implicit version 1 become unreachable.
        cache.set(key, 2, VERSION_TTL)
        return 2


def build_key(kind: str, source_id: int, metric: str, params: dict[str, Any]) -> str:
    version = get_version(source_id, metric)
    digest = hashlib.sha1(
        json.dumps(params, sort_keys=True, default=str).encode()
    ).hexdigest()[:16]
    return f"q:{kind}:{source_id}:{metric}:v{version}:{digest}"


def cached_query(
    kind: str,
    source_id: int,
    metric: str,
    params: dict[str, Any],
    compute: Callable[[], T],
    ttl: int | None = None,
) -> tuple[T, bool]:
    """Return ``(value, hit)``; computes and stores the value on a miss."""
    key = build_key(kind, source_id, metric, params)
    sentinel = object()
    value = cache.get(key, sentinel)
    if value is not sentinel:
        return value, True
    value = compute()
    cache.set(key, value, settings.METRIC_CACHE_TTL if ttl is None else ttl)
    logger.debug("cache miss for %s", key)
    return value, False


def invalidate(pairs: set[tuple[int, str]]) -> None:
    for source_id, metric in pairs:
        bump_version(source_id, metric)
