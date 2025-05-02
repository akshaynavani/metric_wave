"""Generate realistic-looking traffic for a source so the dashboard has something to show."""
import math
import random
import time

from django.core.management.base import BaseCommand, CommandError
from django.utils import timezone

from metrics.models import Source
from metrics.services import ingest_points


class Command(BaseCommand):
    help = "Continuously ingest synthetic metrics for a source."

    def add_arguments(self, parser):
        parser.add_argument("--source", default="checkout")
        parser.add_argument("--interval", type=float, default=1.0, help="seconds between ticks")
        parser.add_argument("--ticks", type=int, default=0, help="stop after N ticks (0 = forever)")
        parser.add_argument("--seed", type=int, default=None)

    def handle(self, *args, source: str, interval: float, ticks: int, seed, **options):
        try:
            src = Source.objects.get(slug=source)
        except Source.DoesNotExist as exc:
            raise CommandError(f"source '{source}' does not exist; run seed_demo first") from exc

        rng = random.Random(seed)
        users = 120.0
        tick = 0
        self.stdout.write(f"Simulating metrics for '{src.slug}' every {interval}s (Ctrl+C to stop)")
        try:
            while ticks == 0 or tick < ticks:
                points = self.generate(rng, tick, users)
                users = points[-1]["value"]
                ingest_points(src, points)
                tick += 1
                if ticks == 0 or tick < ticks:
                    time.sleep(interval)
        except KeyboardInterrupt:
            pass
        self.stdout.write(self.style.SUCCESS(f"Sent {tick} ticks."))

    @staticmethod
    def generate(rng: random.Random, tick: int, users: float) -> list[dict]:
        now = timezone.now()
        wave = math.sin(tick / 30.0)
        latency = max(5.0, rng.gauss(120 + 40 * wave, 15))
        if rng.random() < 0.02:  # occasional latency spike
            latency *= rng.uniform(3, 6)
        users = max(0.0, users + rng.gauss(0, 4) + 2 * wave)
        return [
            {"name": "latency_ms", "value": round(latency, 2), "timestamp": now},
            {"name": "orders", "value": float(rng.randint(0, int(3 + users / 40))), "timestamp": now},
            {"name": "error_rate", "value": round(max(0.0, rng.gauss(0.8, 0.3)), 3), "timestamp": now},
            {"name": "active_users", "value": round(users), "timestamp": now},
        ]
