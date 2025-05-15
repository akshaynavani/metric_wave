from datetime import timedelta

import pytest
from django.utils import timezone

from metrics import services
from metrics.models import MetricPoint, Source


@pytest.fixture(autouse=True)
def _no_broadcast(monkeypatch):
    monkeypatch.setattr(services, "broadcast_points", lambda *a, **k: 0)


class TestIngest:
    url = "/api/ingest/"

    def test_requires_source_key(self, api_client, db):
        response = api_client.post(self.url, {"name": "a", "value": 1}, format="json")
        assert response.status_code == 401

    def test_rejects_bad_key(self, api_client, source):
        api_client.credentials(HTTP_X_SOURCE_KEY="nope")
        response = api_client.post(self.url, {"name": "a", "value": 1}, format="json")
        assert response.status_code == 401

    def test_rejects_inactive_source(self, source_client, source):
        Source.objects.filter(pk=source.pk).update(is_active=False)
        response = source_client.post(self.url, {"name": "a", "value": 1}, format="json")
        assert response.status_code == 401

    def test_accepts_single_point(self, source_client, django_capture_on_commit_callbacks):
        with django_capture_on_commit_callbacks(execute=True):
            response = source_client.post(self.url, {"name": "cpu", "value": 0.5}, format="json")
        assert response.status_code == 202
        assert response.json() == {"accepted": 1}
        assert MetricPoint.objects.get().name == "cpu"

    @pytest.mark.parametrize("wrap", [lambda pts: {"points": pts}, lambda pts: pts])
    def test_accepts_batches(self, source_client, wrap):
        points = [{"name": "cpu", "value": i, "tags": {"host": "a"}} for i in range(3)]
        response = source_client.post(self.url, wrap(points), format="json")
        assert response.status_code == 202
        assert MetricPoint.objects.count() == 3

    def test_enforces_batch_limit(self, source_client):
        points = [{"name": "cpu", "value": i} for i in range(6)]
        response = source_client.post(self.url, {"points": points}, format="json")
        assert response.status_code == 400

    def test_validates_metric_name(self, source_client):
        response = source_client.post(self.url, {"name": "bad name!", "value": 1}, format="json")
        assert response.status_code == 400


class TestQueries:
    def _seed(self, source):
        now = timezone.now()
        for i, v in enumerate([5, 7, 9]):
            MetricPoint.objects.create(
                source=source, name="latency_ms", value=v, timestamp=now - timedelta(seconds=i)
            )

    def test_series_miss_then_hit(self, api_client, source):
        self._seed(source)
        url = "/api/query/series/?source=checkout&metric=latency_ms&window=5&bucket=60&agg=max"
        first = api_client.get(url)
        assert first.status_code == 200
        assert first["X-Cache"] == "MISS"
        body = first.json()
        assert body["aggregation"] == "max"
        assert max(p["value"] for p in body["points"]) == 9
        assert api_client.get(url)["X-Cache"] == "HIT"

    def test_series_invalidated_by_ingest(self, api_client, source, source_client, django_capture_on_commit_callbacks):
        url = "/api/query/series/?source=checkout&metric=latency_ms&bucket=60"
        api_client.get(url)
        with django_capture_on_commit_callbacks(execute=True):
            source_client.post("/api/ingest/", {"name": "latency_ms", "value": 1}, format="json")
        response = api_client.get(url)
        assert response["X-Cache"] == "MISS"
        assert sum(p["count"] for p in response.json()["points"]) == 1

    def test_series_rejects_too_many_buckets(self, api_client, source):
        response = api_client.get("/api/query/series/?source=checkout&metric=m&window=600&bucket=1")
        assert response.status_code == 400

    def test_series_bad_params_and_unknown_source(self, api_client, db):
        assert api_client.get("/api/query/series/?metric=m").status_code == 400
        assert api_client.get("/api/query/series/?source=ghost&metric=m").status_code == 404

    def test_summary(self, api_client, source):
        self._seed(source)
        response = api_client.get("/api/query/summary/?source=checkout&metric=latency_ms&window=5")
        assert response.status_code == 200
        body = response.json()
        assert body["count"] == 3 and body["latest"] == 5
        assert response["X-Cache"] in {"MISS", "HIT"}

    def test_health(self, api_client):
        assert api_client.get("/api/health/").json()["status"] == "ok"


class TestManagementApi:
    def test_anonymous_can_read_but_not_write(self, api_client, dashboard):
        listing = api_client.get("/api/dashboards/")
        assert listing.status_code == 200
        assert listing.json()["results"][0]["widgets"][0]["source_slug"] == "checkout"
        assert api_client.post("/api/dashboards/", {"slug": "x", "title": "X"}).status_code in {401, 403}

    def test_source_listing_hides_key(self, api_client, source):
        body = api_client.get("/api/sources/").json()
        assert "api_key" not in body["results"][0]

    def test_staff_creates_source_and_sees_key_once(self, staff_client):
        response = staff_client.post("/api/sources/", {"slug": "edge", "name": "Edge"}, format="json")
        assert response.status_code == 201
        assert response.json()["api_key"]
        detail = staff_client.get("/api/sources/edge/").json()
        assert "api_key" not in detail

    def test_staff_rotates_key(self, staff_client, source):
        old = source.api_key
        response = staff_client.post(f"/api/sources/{source.slug}/rotate-key/")
        assert response.status_code == 200
        assert response.json()["api_key"] != old

    def test_source_metric_names(self, api_client, source):
        MetricPoint.objects.create(source=source, name="cpu", value=1, timestamp=timezone.now())
        body = api_client.get(f"/api/sources/{source.slug}/metrics/").json()
        assert body == {"source": "checkout", "metrics": ["cpu"]}

    def test_staff_manages_widgets(self, staff_client, dashboard):
        payload = {
            "dashboard": dashboard.id,
            "title": "Orders",
            "kind": "bar",
            "source_slug": "checkout",
            "metric_name": "orders",
            "aggregation": "sum",
            "window_minutes": 30,
            "bucket_seconds": 30,
        }
        created = staff_client.post("/api/widgets/", payload, format="json")
        assert created.status_code == 201
        filtered = staff_client.get(f"/api/widgets/?dashboard={dashboard.slug}").json()
        assert filtered["count"] == 2
        assert staff_client.get("/api/widgets/?dashboard=nope").json()["count"] == 0

    @pytest.mark.parametrize(
        "overrides",
        [{"window_minutes": 0}, {"window_minutes": 600, "bucket_seconds": 1}],
    )
    def test_widget_validation(self, staff_client, dashboard, overrides):
        payload = {
            "dashboard": dashboard.id,
            "title": "Bad",
            "source_slug": "checkout",
            "metric_name": "m",
            **overrides,
        }
        assert staff_client.post("/api/widgets/", payload, format="json").status_code == 400
