import random
from io import StringIO

import pytest
from django.core.management import CommandError, call_command

from metrics import services
from metrics.management.commands.simulate_metrics import Command as SimulateCommand
from metrics.models import Dashboard, MetricPoint, Source


def test_seed_demo_is_idempotent(db):
    out = StringIO()
    call_command("seed_demo", stdout=out)
    assert "Source key" in out.getvalue()
    call_command("seed_demo", stdout=StringIO())
    dashboard = Dashboard.objects.get(slug="checkout-overview")
    assert dashboard.widgets.count() == 5
    assert Source.objects.filter(slug="checkout").count() == 1


def test_simulate_metrics_ingests_ticks(db, monkeypatch, django_capture_on_commit_callbacks):
    monkeypatch.setattr(services, "broadcast_points", lambda *a, **k: 0)
    call_command("seed_demo", stdout=StringIO())
    out = StringIO()
    with django_capture_on_commit_callbacks(execute=True):
        call_command("simulate_metrics", "--ticks", "3", "--interval", "0", "--seed", "1", stdout=out)
    assert MetricPoint.objects.count() == 12
    assert "Sent 3 ticks" in out.getvalue()


def test_simulate_metrics_requires_source(db):
    with pytest.raises(CommandError):
        call_command("simulate_metrics", "--source", "ghost", "--ticks", "1")


def test_generate_produces_bounded_values():
    for tick in range(200):
        points = SimulateCommand.generate(random.Random(tick), tick, 100.0)
        values = {p["name"]: p["value"] for p in points}
        assert values["latency_ms"] >= 5
        assert values["error_rate"] >= 0
        assert values["active_users"] >= 0
