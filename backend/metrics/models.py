import secrets

from django.db import models


def generate_api_key() -> str:
    return secrets.token_urlsafe(32)


class Source(models.Model):
    """A producer of metrics, e.g. a service or device. Authenticates ingest with its key."""

    slug = models.SlugField(max_length=64, unique=True)
    name = models.CharField(max_length=128)
    description = models.TextField(blank=True)
    api_key = models.CharField(max_length=64, unique=True, default=generate_api_key)
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["slug"]

    def __str__(self) -> str:
        return self.slug

    def rotate_key(self) -> str:
        self.api_key = generate_api_key()
        self.save(update_fields=["api_key"])
        return self.api_key


class MetricPoint(models.Model):
    """A single observation of a named metric at a point in time."""

    source = models.ForeignKey(Source, on_delete=models.CASCADE, related_name="points")
    name = models.CharField(max_length=128)
    value = models.FloatField()
    timestamp = models.DateTimeField(db_index=True)
    tags = models.JSONField(default=dict, blank=True)

    class Meta:
        ordering = ["-timestamp"]
        indexes = [
            models.Index(fields=["source", "name", "-timestamp"], name="point_src_name_ts"),
        ]

    def __str__(self) -> str:
        return f"{self.source_id}:{self.name}={self.value}@{self.timestamp.isoformat()}"


class Dashboard(models.Model):
    slug = models.SlugField(max_length=64, unique=True)
    title = models.CharField(max_length=128)
    description = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["title"]

    def __str__(self) -> str:
        return self.title


class Widget(models.Model):
    class Kind(models.TextChoices):
        LINE = "line", "Line chart"
        STAT = "stat", "Single stat"
        BAR = "bar", "Bar chart"

    class Aggregation(models.TextChoices):
        AVG = "avg", "Average"
        SUM = "sum", "Sum"
        MIN = "min", "Minimum"
        MAX = "max", "Maximum"
        COUNT = "count", "Count"

    dashboard = models.ForeignKey(Dashboard, on_delete=models.CASCADE, related_name="widgets")
    title = models.CharField(max_length=128)
    kind = models.CharField(max_length=8, choices=Kind.choices, default=Kind.LINE)
    source = models.ForeignKey(Source, on_delete=models.CASCADE, related_name="widgets")
    metric_name = models.CharField(max_length=128)
    aggregation = models.CharField(
        max_length=8, choices=Aggregation.choices, default=Aggregation.AVG
    )
    window_minutes = models.PositiveIntegerField(default=15)
    bucket_seconds = models.PositiveIntegerField(default=10)
    position = models.PositiveIntegerField(default=0)

    class Meta:
        ordering = ["dashboard", "position", "id"]

    def __str__(self) -> str:
        return f"{self.dashboard.slug}/{self.title}"
