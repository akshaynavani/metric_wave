from django.urls import include, path
from rest_framework.routers import DefaultRouter

from . import views

router = DefaultRouter()
router.register("sources", views.SourceViewSet)
router.register("dashboards", views.DashboardViewSet)
router.register("widgets", views.WidgetViewSet)

urlpatterns = [
    path("", include(router.urls)),
    path("ingest/", views.IngestView.as_view(), name="ingest"),
    path("query/series/", views.series_view, name="series"),
    path("query/summary/", views.summary_view, name="summary"),
    path("health/", views.health_view, name="health"),
]
