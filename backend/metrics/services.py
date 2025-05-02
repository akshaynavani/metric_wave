"""Query and ingest logic shared by the REST API, WebSocket layer and management commands."""
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta, timezone as dt_timezone
from typing import Any, Iterable

from django.db import transaction
from django.db.models import Avg, Count, Max, Min, Sum
from django.utils import timezone

from . import cache as metric_cache
from .broadcast import broadcast_points
from .models import MetricPoint, Source

AGGREGATES = {"avg": Avg, "sum": Sum, "min": Min, "max": Max, "count": Count}

MAX_WINDOW_MINUTES = 24 * 60
MAX_BUCKETS = 1500


@dataclass(frozen=True)
class SeriesQuery:
    source: Source
    metric: str
    window_minutes: int = 15
    bucket_seconds: int = 10
    aggregation: str = "avg"

    def validate(self) -> None:
        if self.aggregation not in AGGREGATES:
            raise ValueError(f"unknown aggregation '{self.aggregation}'")
        if not 1 <= self.window_minutes <= MAX_WINDOW_MINUTES:
            raise ValueError(f"window_minutes must be between 1 and {MAX_WINDOW_MINUTES}")
        if self.bucket_seconds < 1:
            raise ValueError("bucket_seconds must be positive")
        if (self.window_minutes * 60) / self.bucket_seconds > MAX_BUCKETS:
            raise ValueError(f"query would produce more than {MAX_BUCKETS} buckets")


def floor_time(moment: datetime, seconds: int) -> datetime:
    epoch = int(moment.timestamp())
    return datetime.fromtimestamp(epoch - epoch % seconds, tz=dt_timezone.utc)


def _reduce(values: list[float], aggregation: str) -> float:
    if aggregation == "count":
        return float(len(values))
    if aggregation == "sum":
        return float(sum(values))
    if aggregation == "min":
        return float(min(values))
    if aggregation == "max":
        return float(max(values))
    return float(sum(values) / len(values))


def compute_series(query: SeriesQuery, now: datetime | None = None) -> list[dict[str, Any]]:
    """Bucket raw points into fixed-width intervals ending at ``now`` (floored)."""
    query.validate()
    end = floor_time(now or timezone.now(), query.bucket_seconds) + timedelta(
        seconds=query.bucket_seconds
    )
    start = end - timedelta(minutes=query.window_minutes)
    rows = (
        MetricPoint.objects.filter(
            source=query.source, name=query.metric, timestamp__gte=start, timestamp__lt=end
        )
        .order_by("timestamp")
        .values_list("timestamp", "value")
    )
    buckets: dict[int, list[float]] = {}
    start_epoch = int(start.timestamp())
    for ts, value in rows.iterator():
        index = (int(ts.timestamp()) - start_epoch) // query.bucket_seconds
        buckets.setdefault(index, []).append(value)
    return [
        {
            "t": datetime.fromtimestamp(
                start_epoch + index * query.bucket_seconds, tz=dt_timezone.utc
            ).isoformat(),
            "value": _reduce(values, query.aggregation),
            "count": len(values),
        }
        for index, values in sorted(buckets.items())
    ]


def series(query: SeriesQuery, now: datetime | None = None) -> tuple[list[dict[str, Any]], bool]:
    query.validate()
    moment = now or timezone.now()
    params = {
        "window": query.window_minutes,
        "bucket": query.bucket_seconds,
        "agg": query.aggregation,
        "end": floor_time(moment, query.bucket_seconds).isoformat(),
    }
    return metric_cache.cached_query(
        "series",
        query.source.pk,
        query.metric,
        params,
        lambda: compute_series(query, now=moment),
    )


def compute_summary(source: Source, metric: str, window_minutes: int) -> dict[str, Any]:
    since = timezone.now() - timedelta(minutes=window_minutes)
    qs = MetricPoint.objects.filter(source=source, name=metric, timestamp__gte=since)
    stats = qs.aggregate(
        avg=Avg("value"), sum=Sum("value"), min=Min("value"), max=Max("value"), count=Count("id")
    )
    latest = qs.order_by("-timestamp").values("value", "timestamp").first()
    return {
        "source": source.slug,
        "metric": metric,
        "window_minutes": window_minutes,
        **stats,
        "latest": latest["value"] if latest else None,
        "latest_at": latest["timestamp"].isoformat() if latest else None,
    }


def summary(source: Source, metric: str, window_minutes: int = 15) -> tuple[dict[str, Any], bool]:
    if not 1 <= window_minutes <= MAX_WINDOW_MINUTES:
        raise ValueError(f"window_minutes must be between 1 and {MAX_WINDOW_MINUTES}")
    # Summary keys are coarse (per 5s) so dashboards polling at high frequency share entries.
    params = {"window": window_minutes, "slot": floor_time(timezone.now(), 5).isoformat()}
    return metric_cache.cached_query(
        "summary",
        source.pk,
        metric,
        params,
        lambda: compute_summary(source, metric, window_minutes),
    )


def metric_names(source: Source) -> list[str]:
    def compute() -> list[str]:
        return sorted(
            MetricPoint.objects.filter(source=source).values_list("name", flat=True).distinct()
        )

    value, _ = metric_cache.cached_query("names", source.pk, "*", {}, compute, ttl=60)
    return value


def ingest_points(source: Source, points: Iterable[dict[str, Any]]) -> list[MetricPoint]:
    """Persist points, invalidate caches and schedule live broadcast after commit."""
    objects = [
        MetricPoint(
            source=source,
            name=p["name"],
            value=float(p["value"]),
            timestamp=p.get("timestamp") or timezone.now(),
            tags=p.get("tags") or {},
        )
        for p in points
    ]
    if not objects:
        return []
    with transaction.atomic():
        created = MetricPoint.objects.bulk_create(objects)
        touched = {(source.pk, obj.name) for obj in created}
        transaction.on_commit(lambda: _after_ingest(source, created, touched))
    return created


def _after_ingest(
    source: Source,
    created: list[MetricPoint],
    touched: set[tuple[int, str]],
) -> None:
    metric_cache.invalidate(touched)
    # The metric name list only changes when a never-seen name arrives; bumping its
    # version unconditionally is cheap and keeps the logic simple.
    metric_cache.bump_version(source.pk, "*")
    broadcast_points(source.slug, created)
