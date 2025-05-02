"""WebSocket consumer implementing a small subscribe/unsubscribe protocol.

Client -> server messages::

    {"action": "subscribe",   "source": "checkout", "metric": "latency_ms"}
    {"action": "unsubscribe", "source": "checkout", "metric": "latency_ms"}
    {"action": "ping"}

Server -> client messages::

    {"type": "hello", "max_subscriptions": 50}
    {"type": "subscribed",   "source": ..., "metric": ...}
    {"type": "unsubscribed", "source": ..., "metric": ...}
    {"type": "points", "points": [{"source", "metric", "value", "t", "tags"}, ...]}
    {"type": "pong"}
    {"type": "error", "message": ...}
"""
from __future__ import annotations

import re

from channels.db import database_sync_to_async
from channels.generic.websocket import AsyncJsonWebsocketConsumer

from .broadcast import group_name
from .models import Source

MAX_SUBSCRIPTIONS = 50
METRIC_RE = re.compile(r"^[A-Za-z0-9_.\-]{1,128}$")


@database_sync_to_async
def source_exists(slug: str) -> bool:
    return Source.objects.filter(slug=slug, is_active=True).exists()


class StreamConsumer(AsyncJsonWebsocketConsumer):
    async def connect(self) -> None:
        self.subscriptions: set[str] = set()
        await self.accept()
        await self.send_json({"type": "hello", "max_subscriptions": MAX_SUBSCRIPTIONS})

    async def disconnect(self, code: int) -> None:
        for group in getattr(self, "subscriptions", set()):
            await self.channel_layer.group_discard(group, self.channel_name)
        self.subscriptions = set()

    async def receive_json(self, content, **kwargs) -> None:
        if not isinstance(content, dict):
            await self._error("message must be a JSON object")
            return
        action = content.get("action")
        if action == "ping":
            await self.send_json({"type": "pong"})
        elif action in {"subscribe", "unsubscribe"}:
            await self._handle_subscription(action, content)
        else:
            await self._error(f"unknown action '{action}'")

    async def _handle_subscription(self, action: str, content: dict) -> None:
        source = content.get("source")
        metric = content.get("metric")
        if not isinstance(source, str) or not isinstance(metric, str) or not METRIC_RE.match(metric):
            await self._error("source and metric are required")
            return
        group = group_name(source, metric)
        if action == "unsubscribe":
            if group in self.subscriptions:
                await self.channel_layer.group_discard(group, self.channel_name)
                self.subscriptions.discard(group)
            await self.send_json({"type": "unsubscribed", "source": source, "metric": metric})
            return
        if group not in self.subscriptions:
            if len(self.subscriptions) >= MAX_SUBSCRIPTIONS:
                await self._error("subscription limit reached")
                return
            if not await source_exists(source):
                await self._error(f"unknown source '{source}'")
                return
            await self.channel_layer.group_add(group, self.channel_name)
            self.subscriptions.add(group)
        await self.send_json({"type": "subscribed", "source": source, "metric": metric})

    async def metric_points(self, event: dict) -> None:
        """Handler for ``{"type": "metric.points"}`` group messages."""
        await self.send_json({"type": "points", "points": event["points"]})

    async def _error(self, message: str) -> None:
        await self.send_json({"type": "error", "message": message})
