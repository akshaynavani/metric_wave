import pytest
from django.contrib.auth import get_user_model
from django.core.cache import cache
from rest_framework.test import APIClient

from metrics.models import Dashboard, Source, Widget


@pytest.fixture(autouse=True)
def _clear_cache():
    cache.clear()
    yield
    cache.clear()


@pytest.fixture
def source(db) -> Source:
    return Source.objects.create(slug="checkout", name="Checkout")


@pytest.fixture
def client() -> APIClient:
    return APIClient()


@pytest.fixture
def source_client(source) -> APIClient:
    api = APIClient()
    api.credentials(HTTP_X_SOURCE_KEY=source.api_key)
    return api


@pytest.fixture
def staff_client(db) -> APIClient:
    user = get_user_model().objects.create_user("admin", password="pw", is_staff=True)
    api = APIClient()
    api.force_authenticate(user)
    return api


@pytest.fixture
def dashboard(source) -> Dashboard:
    board = Dashboard.objects.create(slug="ops", title="Ops")
    Widget.objects.create(
        dashboard=board, title="Latency", source=source, metric_name="latency_ms"
    )
    return board
