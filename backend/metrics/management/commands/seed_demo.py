from django.core.management.base import BaseCommand

from metrics.models import Dashboard, Source, Widget

DEMO_WIDGETS = [
    ("Request latency (avg)", Widget.Kind.LINE, "latency_ms", Widget.Aggregation.AVG),
    ("Peak latency", Widget.Kind.STAT, "latency_ms", Widget.Aggregation.MAX),
    ("Orders per bucket", Widget.Kind.BAR, "orders", Widget.Aggregation.SUM),
    ("Error rate", Widget.Kind.LINE, "error_rate", Widget.Aggregation.AVG),
    ("Active users", Widget.Kind.STAT, "active_users", Widget.Aggregation.MAX),
]


class Command(BaseCommand):
    help = "Create a demo source and dashboard wired to the simulator's metrics."

    def handle(self, *args, **options):
        source, created = Source.objects.get_or_create(
            slug="checkout", defaults={"name": "Checkout service"}
        )
        dashboard, _ = Dashboard.objects.get_or_create(
            slug="checkout-overview",
            defaults={"title": "Checkout overview", "description": "Live checkout health"},
        )
        for position, (title, kind, metric, agg) in enumerate(DEMO_WIDGETS):
            Widget.objects.update_or_create(
                dashboard=dashboard,
                title=title,
                defaults={
                    "kind": kind,
                    "source": source,
                    "metric_name": metric,
                    "aggregation": agg,
                    "window_minutes": 10,
                    "bucket_seconds": 5,
                    "position": position,
                },
            )
        self.stdout.write(self.style.SUCCESS(f"Dashboard '{dashboard.slug}' ready."))
        if created:
            self.stdout.write(f"Source key for '{source.slug}': {source.api_key}")
