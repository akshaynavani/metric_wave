from metrics.models import Dashboard, MetricPoint, Source, Widget


def test_source_gets_unique_api_key(db):
    a = Source.objects.create(slug="a", name="A")
    b = Source.objects.create(slug="b", name="B")
    assert a.api_key and b.api_key and a.api_key != b.api_key
    assert str(a) == "a"


def test_rotate_key_changes_and_persists(source):
    old = source.api_key
    new = source.rotate_key()
    source.refresh_from_db()
    assert new != old
    assert source.api_key == new


def test_string_representations(source, dashboard):
    from django.utils import timezone

    point = MetricPoint.objects.create(
        source=source, name="latency_ms", value=1.5, timestamp=timezone.now()
    )
    widget = Widget.objects.get(dashboard=dashboard)
    assert "latency_ms=1.5" in str(point)
    assert str(dashboard) == "Ops"
    assert str(widget) == "ops/Latency"
    assert Dashboard.objects.count() == 1
