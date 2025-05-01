from django.conf import settings
from rest_framework import serializers

from .models import Dashboard, Source, Widget
from .services import AGGREGATES, MAX_WINDOW_MINUTES


class SourceSerializer(serializers.ModelSerializer):
    class Meta:
        model = Source
        fields = ["id", "slug", "name", "description", "is_active", "created_at"]
        read_only_fields = ["created_at"]


class SourceWithKeySerializer(SourceSerializer):
    """Only returned on creation / key rotation so the key is shown exactly once."""

    class Meta(SourceSerializer.Meta):
        fields = SourceSerializer.Meta.fields + ["api_key"]
        read_only_fields = SourceSerializer.Meta.read_only_fields + ["api_key"]


class WidgetSerializer(serializers.ModelSerializer):
    source_slug = serializers.SlugRelatedField(
        source="source", slug_field="slug", queryset=Source.objects.all()
    )

    class Meta:
        model = Widget
        fields = [
            "id",
            "dashboard",
            "title",
            "kind",
            "source_slug",
            "metric_name",
            "aggregation",
            "window_minutes",
            "bucket_seconds",
            "position",
        ]

    def validate_window_minutes(self, value: int) -> int:
        if not 1 <= value <= MAX_WINDOW_MINUTES:
            raise serializers.ValidationError(f"must be between 1 and {MAX_WINDOW_MINUTES}")
        return value

    def validate(self, attrs):
        window = attrs.get("window_minutes", getattr(self.instance, "window_minutes", 15))
        bucket = attrs.get("bucket_seconds", getattr(self.instance, "bucket_seconds", 10))
        if bucket < 1 or (window * 60) / bucket > 1500:
            raise serializers.ValidationError(
                {"bucket_seconds": "too many buckets for the selected window"}
            )
        return attrs


class DashboardSerializer(serializers.ModelSerializer):
    widgets = WidgetSerializer(many=True, read_only=True)

    class Meta:
        model = Dashboard
        fields = ["id", "slug", "title", "description", "created_at", "updated_at", "widgets"]
        read_only_fields = ["created_at", "updated_at"]


class PointInSerializer(serializers.Serializer):
    name = serializers.RegexField(r"^[A-Za-z0-9_.\-]{1,128}$")
    value = serializers.FloatField()
    timestamp = serializers.DateTimeField(required=False)
    tags = serializers.DictField(child=serializers.CharField(max_length=128), required=False)


class IngestSerializer(serializers.Serializer):
    points = PointInSerializer(many=True, allow_empty=False)

    def validate_points(self, value):
        if len(value) > settings.INGEST_MAX_BATCH:
            raise serializers.ValidationError(
                f"batch exceeds limit of {settings.INGEST_MAX_BATCH} points"
            )
        return value

    def to_internal_value(self, data):
        # Accept either {"points": [...]} or a single bare point for convenience.
        if isinstance(data, dict) and "points" not in data:
            data = {"points": [data]}
        elif isinstance(data, list):
            data = {"points": data}
        return super().to_internal_value(data)


class SeriesParamsSerializer(serializers.Serializer):
    source = serializers.SlugField()
    metric = serializers.CharField(max_length=128)
    window = serializers.IntegerField(default=15, min_value=1, max_value=MAX_WINDOW_MINUTES)
    bucket = serializers.IntegerField(default=10, min_value=1)
    agg = serializers.ChoiceField(choices=list(AGGREGATES), default="avg")


class SummaryParamsSerializer(serializers.Serializer):
    source = serializers.SlugField()
    metric = serializers.CharField(max_length=128)
    window = serializers.IntegerField(default=15, min_value=1, max_value=MAX_WINDOW_MINUTES)
