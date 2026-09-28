"""协作实时广播测试。"""

from __future__ import annotations

import asyncio

import pytest

from app.events import BusEvent, EventBus


async def test_event_bus_pub_sub() -> None:
    bus = EventBus()
    queue = await bus.subscribe("ses-1")
    await bus.publish(
        BusEvent(session_id="ses-1", event="peer_turn", data={"turn_id": "t1"})
    )
    ev = await asyncio.wait_for(queue.get(), timeout=1)
    assert ev.event == "peer_turn"
    assert ev.data["turn_id"] == "t1"
    await bus.unsubscribe("ses-1", queue)


async def test_event_bus_isolates_sessions() -> None:
    bus = EventBus()
    q1 = await bus.subscribe("ses-a")
    q2 = await bus.subscribe("ses-b")
    await bus.publish(BusEvent(session_id="ses-a", event="peer_turn", data={}))
    assert q2.empty()
    assert q1.qsize() == 1
    await bus.unsubscribe("ses-a", q1)
    await bus.unsubscribe("ses-b", q2)


async def test_event_bus_stream_yields() -> None:
    bus = EventBus()
    task = asyncio.create_task(_consume_one(bus, "ses-s"))
    await asyncio.sleep(0.05)
    await bus.publish(
        BusEvent(session_id="ses-s", event="seat_claimed", data={"character": "甲"})
    )
    ev = await asyncio.wait_for(task, timeout=1)
    assert ev.event == "seat_claimed"


async def _consume_one(bus: EventBus, sid: str) -> BusEvent:
    async for ev in bus.stream(sid):
        return ev
    raise AssertionError("stream ended early")


@pytest.mark.asyncio
async def test_broadcast_turn_endpoint_exists() -> None:
    # 路由层存在 /events
    from app.main import create_app

    app = create_app()
    schema = app.openapi()
    paths = schema.get("paths", {})
    assert any(p.endswith("/sessions/{session_id}/events") for p in paths)
