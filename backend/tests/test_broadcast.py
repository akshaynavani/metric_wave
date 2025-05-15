from django.utils import timezone

from metrics import broadcast
from metrics.models import MetricPoint


class RecordingLayer:
    def __init__(self):
        self.sent = []

    async def group_send(self, group, message):
        self.sent.append((group, message))


def test_group_name_sanitises_and_truncates():
    assert broadcast.group_name("checkout", "latency_ms") == "metric.checkout.latency_ms"
    assert broadcast.group_name("we ird", "a/b") == "metric.we_ird.a_b"
    assert len(broadcast.group_name("s", "x" * 200)) == 99


def test_broadcast_groups_points_per_metric(source, monkeypatch):
    layer = RecordingLayer()
    monkeypatch.setattr(broadcast, "get_channel_layer", lambda: layer)
    now = timezone.now()
    points = [
        MetricPoint(source=source, name="a", value=1, timestamp=now, tags={"region": "eu"}),
        MetricPoint(source=source, name="a", value=2, timestamp=now),
        MetricPoint(source=source, name="b", value=3, timestamp=now),
    ]
    assert broadcast.broadcast_points("checkout", points) == 2
    groups = dict(layer.sent)
    assert groups["metric.checkout.a"]["type"] == "metric.points"
    assert [p["value"] for p in groups["metric.checkout.a"]["points"]] == [1, 2]
    assert groups["metric.checkout.a"]["points"][0]["tags"] == {"region": "eu"}


def test_broadcast_without_layer_is_noop(monkeypatch):
    monkeypatch.setattr(broadcast, "get_channel_layer", lambda: None)
    assert broadcast.broadcast_points("x", []) == 0
