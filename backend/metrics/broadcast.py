"""Fan-out of freshly ingested points to WebSocket subscribers via the channel layer."""
from __future__ import annotations

import logging
import re
from collections import defaultdict
from typing import Iterable

from asgiref.sync import async_to_sync
from channels.layers import get_channel_layer

from .models import MetricPoint

logger = logging.getLogger(__name__)

_GROUP_SAFE = re.compile(r"[^A-Za-z0-9_.\-]")


def group_name(source_slug: str, metric: str) -> str:
    """Channels group names must be ASCII alnum/-/_/. and shorter than 100 chars."""
    name = f"metric.{_GROUP_SAFE.sub('_', source_slug)}.{_GROUP_SAFE.sub('_', metric)}"
    return name[:99]


def serialize_point(point: MetricPoint, source_slug: str) -> dict:
    return {
        "source": source_slug,
        "metric": point.name,
        "value": point.value,
        "t": point.timestamp.isoformat(),
        "tags": point.tags,
    }


def broadcast_points(source_slug: str, points: Iterable[MetricPoint]) -> int:
    """Send one message per (source, metric) group. Returns number of groups notified."""
    layer = get_channel_layer()
    if layer is None:
        return 0
    grouped: dict[str, list[dict]] = defaultdict(list)
    for point in points:
        grouped[group_name(source_slug, point.name)].append(serialize_point(point, source_slug))
    for group, payload in grouped.items():
        try:
            async_to_sync(layer.group_send)(group, {"type": "metric.points", "points": payload})
        except Exception:  # pragma: no cover - a down channel layer must not fail ingest
            logger.exception("failed to broadcast to %s", group)
    return len(grouped)
