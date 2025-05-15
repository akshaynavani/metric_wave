from datetime import datetime, timedelta, timezone

import pytest

from metrics import services
from metrics.models import MetricPoint

NOW = datetime(2026, 1, 1, 0, 0, 7, tzinfo=timezone.utc)


def add(source, name, value, at):
    return MetricPoint.objects.create(source=source, name=name, value=value, timestamp=at)


@pytest.fixture
def seeded(source):
    add(source, "latency_ms", 10, datetime(2025, 12, 31, 23, 59, 15, tzinfo=timezone.utc))
    add(source, "latency_ms", 20, datetime(2026, 1, 1, 0, 0, 1, tzinfo=timezone.utc))
    add(source, "latency_ms", 40, datetime(2026, 1, 1, 0, 0, 5, tzinfo=timezone.utc))
    # Outside the one-minute window and a different metric: both must be ignored.
    add(source, "latency_ms", 999, datetime(2025, 12, 31, 23, 50, 0, tzinfo=timezone.utc))
    add(source, "orders", 3, datetime(2026, 1, 1, 0, 0, 2, tzinfo=timezone.utc))
    return source


@pytest.mark.parametrize(
    "agg,expected",
    [("avg", [10, 30]), ("sum", [10, 60]), ("min", [10, 20]), ("max", [10, 40]), ("count", [1, 2])],
)
def test_compute_series_buckets_and_aggregates(seeded, agg, expected):
    query = services.SeriesQuery(seeded, "latency_ms", window_minutes=1, bucket_seconds=10, aggregation=agg)
    result = services.compute_series(query, now=NOW)
    assert [b["value"] for b in result] == expected
    assert [b["t"] for b in result] == [
        "2025-12-31T23:59:10+00:00",
        "2026-01-01T00:00:00+00:00",
    ]
    assert [b["count"] for b in result] == [1, 2]


@pytest.mark.parametrize(
    "kwargs,message",
    [
        ({"aggregation": "median"}, "unknown aggregation"),
        ({"window_minutes": 0}, "window_minutes"),
        ({"bucket_seconds": 0}, "bucket_seconds"),
        ({"window_minutes": 600, "bucket_seconds": 1}, "buckets"),
    ],
)
def test_series_query_validation(source, kwargs, message):
    with pytest.raises(ValueError, match=message):
        services.SeriesQuery(source, "m", **kwargs).validate()


def test_series_is_cached_until_ingest(seeded, django_capture_on_commit_callbacks, monkeypatch):
    monkeypatch.setattr(services, "broadcast_points", lambda *a, **k: 0)
    query = services.SeriesQuery(seeded, "latency_ms", window_minutes=1, bucket_seconds=10)
    first, hit1 = services.series(query, now=NOW)
    _, hit2 = services.series(query, now=NOW)
    assert (hit1, hit2) == (False, True)

    with django_capture_on_commit_callbacks(execute=True):
        services.ingest_points(seeded, [{"name": "latency_ms", "value": 60, "timestamp": NOW}])
    updated, hit3 = services.series(query, now=NOW)
    assert hit3 is False
    assert updated[-1]["count"] == first[-1]["count"] + 1


def test_summary_reports_stats_and_latest(source, monkeypatch):
    from django.utils import timezone as dj_tz

    # Pin the cache slot so the test cannot straddle a 5s boundary.
    monkeypatch.setattr(services, "floor_time", lambda moment, seconds: NOW)

    now = dj_tz.now()
    add(source, "cpu", 1, now - timedelta(minutes=1))
    add(source, "cpu", 3, now)
    data, hit = services.summary(source, "cpu", 5)
    assert hit is False
    assert data["avg"] == 2 and data["sum"] == 4 and data["min"] == 1 and data["max"] == 3
    assert data["count"] == 2 and data["latest"] == 3
    _, hit = services.summary(source, "cpu", 5)
    assert hit is True


def test_summary_without_data_and_bad_window(source):
    data, _ = services.summary(source, "nothing", 5)
    assert data["latest"] is None and data["count"] == 0
    with pytest.raises(ValueError):
        services.summary(source, "nothing", 0)


def test_metric_names_lists_distinct_sorted(seeded):
    assert services.metric_names(seeded) == ["latency_ms", "orders"]


def test_ingest_defaults_timestamp_and_broadcasts(source, django_capture_on_commit_callbacks, monkeypatch):
    sent = []
    monkeypatch.setattr(services, "broadcast_points", lambda slug, pts: sent.append((slug, len(pts))))
    with django_capture_on_commit_callbacks(execute=True):
        created = services.ingest_points(source, [{"name": "a", "value": "1.5"}, {"name": "b", "value": 2}])
    assert len(created) == 2
    assert all(p.timestamp is not None for p in MetricPoint.objects.all())
    assert sent == [("checkout", 2)]


def test_ingest_empty_is_noop(source):
    assert services.ingest_points(source, []) == []
