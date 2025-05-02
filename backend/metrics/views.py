from django.shortcuts import get_object_or_404
from django.utils import timezone
from rest_framework import permissions, status, viewsets
from rest_framework.authentication import BasicAuthentication, SessionAuthentication
from rest_framework.decorators import action, api_view, authentication_classes, permission_classes
from rest_framework.request import Request
from rest_framework.response import Response
from rest_framework.views import APIView

from . import services
from .auth import SourceKeyAuthentication
from .models import Dashboard, Source, Widget
from .serializers import (
    DashboardSerializer,
    IngestSerializer,
    SeriesParamsSerializer,
    SourceSerializer,
    SourceWithKeySerializer,
    SummaryParamsSerializer,
    WidgetSerializer,
)

STAFF_AUTH = [SessionAuthentication, BasicAuthentication]


class StaffWriteOrReadOnly(permissions.BasePermission):
    def has_permission(self, request, view) -> bool:
        if request.method in permissions.SAFE_METHODS:
            return True
        return bool(request.user and request.user.is_staff)


class SourceViewSet(viewsets.ModelViewSet):
    queryset = Source.objects.all()
    lookup_field = "slug"
    authentication_classes = STAFF_AUTH
    permission_classes = [StaffWriteOrReadOnly]

    def get_serializer_class(self):
        if self.action == "create":
            return SourceWithKeySerializer
        return SourceSerializer

    @action(detail=True, methods=["post"], url_path="rotate-key")
    def rotate_key(self, request, slug=None):
        source = self.get_object()
        source.rotate_key()
        return Response(SourceWithKeySerializer(source).data)

    @action(detail=True, methods=["get"])
    def metrics(self, request, slug=None):
        return Response({"source": slug, "metrics": services.metric_names(self.get_object())})


class DashboardViewSet(viewsets.ModelViewSet):
    queryset = Dashboard.objects.prefetch_related("widgets__source")
    serializer_class = DashboardSerializer
    lookup_field = "slug"
    authentication_classes = STAFF_AUTH
    permission_classes = [StaffWriteOrReadOnly]


class WidgetViewSet(viewsets.ModelViewSet):
    queryset = Widget.objects.select_related("source", "dashboard")
    serializer_class = WidgetSerializer
    authentication_classes = STAFF_AUTH
    permission_classes = [StaffWriteOrReadOnly]

    def get_queryset(self):
        qs = super().get_queryset()
        dashboard = self.request.query_params.get("dashboard")
        return qs.filter(dashboard__slug=dashboard) if dashboard else qs


class IngestView(APIView):
    authentication_classes = [SourceKeyAuthentication]
    permission_classes = [permissions.IsAuthenticated]

    def post(self, request: Request) -> Response:
        serializer = IngestSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        created = services.ingest_points(request.auth, serializer.validated_data["points"])
        return Response({"accepted": len(created)}, status=status.HTTP_202_ACCEPTED)


def _cache_header(response: Response, hit: bool) -> Response:
    response["X-Cache"] = "HIT" if hit else "MISS"
    return response


@api_view(["GET"])
@authentication_classes([])
@permission_classes([permissions.AllowAny])
def series_view(request: Request) -> Response:
    params = SeriesParamsSerializer(data=request.query_params)
    params.is_valid(raise_exception=True)
    data = params.validated_data
    source = get_object_or_404(Source, slug=data["source"])
    query = services.SeriesQuery(
        source=source,
        metric=data["metric"],
        window_minutes=data["window"],
        bucket_seconds=data["bucket"],
        aggregation=data["agg"],
    )
    try:
        points, hit = services.series(query)
    except ValueError as exc:
        return Response({"detail": str(exc)}, status=status.HTTP_400_BAD_REQUEST)
    body = {
        "source": source.slug,
        "metric": data["metric"],
        "aggregation": data["agg"],
        "bucket_seconds": data["bucket"],
        "points": points,
    }
    return _cache_header(Response(body), hit)


@api_view(["GET"])
@authentication_classes([])
@permission_classes([permissions.AllowAny])
def summary_view(request: Request) -> Response:
    params = SummaryParamsSerializer(data=request.query_params)
    params.is_valid(raise_exception=True)
    data = params.validated_data
    source = get_object_or_404(Source, slug=data["source"])
    body, hit = services.summary(source, data["metric"], data["window"])
    return _cache_header(Response(body), hit)


@api_view(["GET"])
@authentication_classes([])
@permission_classes([permissions.AllowAny])
def health_view(request: Request) -> Response:
    return Response({"status": "ok", "time": timezone.now().isoformat()})
