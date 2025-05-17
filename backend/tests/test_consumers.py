import pytest
from channels.layers import get_channel_layer
from channels.testing import WebsocketCommunicator

from metrics.consumers import MAX_SUBSCRIPTIONS, StreamConsumer
from metrics.models import Source

pytestmark = [pytest.mark.asyncio, pytest.mark.django_db(transaction=True)]


async def connect():
    communicator = WebsocketCommunicator(StreamConsumer.as_asgi(), "/ws/stream/")
    connected, _ = await communicator.connect()
    assert connected
    hello = await communicator.receive_json_from()
    assert hello == {"type": "hello", "max_subscriptions": MAX_SUBSCRIPTIONS}
    return communicator


async def make_source(slug="checkout", active=True):
    from channels.db import database_sync_to_async

    return await database_sync_to_async(Source.objects.create)(slug=slug, name=slug, is_active=active)


async def test_subscribe_receives_group_messages():
    await make_source()
    ws = await connect()
    await ws.send_json_to({"action": "subscribe", "source": "checkout", "metric": "latency_ms"})
    assert (await ws.receive_json_from())["type"] == "subscribed"

    point = {"source": "checkout", "metric": "latency_ms", "value": 1.0, "t": "now", "tags": {}}
    await get_channel_layer().group_send(
        "metric.checkout.latency_ms", {"type": "metric.points", "points": [point]}
    )
    assert await ws.receive_json_from() == {"type": "points", "points": [point]}
    await ws.disconnect()


async def test_unsubscribe_stops_delivery():
    await make_source()
    ws = await connect()
    await ws.send_json_to({"action": "subscribe", "source": "checkout", "metric": "m"})
    await ws.receive_json_from()
    await ws.send_json_to({"action": "unsubscribe", "source": "checkout", "metric": "m"})
    assert (await ws.receive_json_from())["type"] == "unsubscribed"
    await get_channel_layer().group_send("metric.checkout.m", {"type": "metric.points", "points": []})
    assert await ws.receive_nothing(timeout=0.2)
    await ws.disconnect()


async def test_duplicate_subscribe_is_idempotent():
    await make_source()
    ws = await connect()
    for _ in range(2):
        await ws.send_json_to({"action": "subscribe", "source": "checkout", "metric": "m"})
        assert (await ws.receive_json_from())["type"] == "subscribed"
    await ws.disconnect()


@pytest.mark.parametrize(
    "message,error",
    [
        ({"action": "subscribe", "source": "ghost", "metric": "m"}, "unknown source"),
        ({"action": "subscribe", "source": "checkout"}, "required"),
        ({"action": "subscribe", "source": "checkout", "metric": "bad metric"}, "required"),
        ({"action": "dance"}, "unknown action"),
        (["not", "an", "object"], "JSON object"),
    ],
)
async def test_protocol_errors(message, error):
    await make_source()
    ws = await connect()
    await ws.send_json_to(message)
    response = await ws.receive_json_from()
    assert response["type"] == "error" and error in response["message"]
    await ws.disconnect()


async def test_inactive_source_is_rejected():
    await make_source("old", active=False)
    ws = await connect()
    await ws.send_json_to({"action": "subscribe", "source": "old", "metric": "m"})
    assert (await ws.receive_json_from())["type"] == "error"
    await ws.disconnect()


async def test_ping_pong():
    ws = await connect()
    await ws.send_json_to({"action": "ping"})
    assert await ws.receive_json_from() == {"type": "pong"}
    await ws.disconnect()


async def test_subscription_limit(monkeypatch):
    import metrics.consumers as consumers

    monkeypatch.setattr(consumers, "MAX_SUBSCRIPTIONS", 1)
    await make_source()
    communicator = WebsocketCommunicator(StreamConsumer.as_asgi(), "/ws/stream/")
    await communicator.connect()
    await communicator.receive_json_from()
    await communicator.send_json_to({"action": "subscribe", "source": "checkout", "metric": "a"})
    await communicator.receive_json_from()
    await communicator.send_json_to({"action": "subscribe", "source": "checkout", "metric": "b"})
    response = await communicator.receive_json_from()
    assert response == {"type": "error", "message": "subscription limit reached"}
    await communicator.disconnect()
