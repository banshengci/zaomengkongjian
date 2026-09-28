"""队列行为与配额/错误边界测试。"""

from __future__ import annotations

import asyncio

import pytest
from fastapi.testclient import TestClient

from app.main import create_app
from app.queue import TaskQueue, get_queue
from app.store.memory import reset_store


async def test_queue_runs_and_resolves() -> None:
    queue = TaskQueue(workers=1)
    await queue.start()
    try:
        ran: list[str] = []

        async def work() -> str:
            await asyncio.sleep(0.01)
            ran.append("ok")
            return "done"

        handle = queue.submit("t1", work)
        result = await queue.wait(handle.id)
        assert result == "done"
        assert ran == ["ok"]
        got = queue.get(handle.id)
        assert got is not None
        assert got.status == "done"
    finally:
        await queue.stop()


async def test_queue_records_failure() -> None:
    queue = TaskQueue(workers=1)
    await queue.start()
    try:

        async def boom() -> None:
            raise ValueError("nope")

        handle = queue.submit("t2", boom)
        with pytest.raises(ValueError):
            await queue.wait(handle.id)
        got = queue.get(handle.id)
        assert got is not None
        assert got.status == "failed"
    finally:
        await queue.stop()


@pytest.fixture()
def client() -> TestClient:
    reset_store()
    app = create_app()
    return TestClient(app)


def test_quota_enforced(client: TestClient) -> None:
    token = client.post("/api/v1/auth/anon", json={"display_name": "限流"}).json()[
        "token"
    ]
    headers = {"Authorization": f"Bearer {token}"}
    book = client.post(
        "/api/v1/books",
        json={"title": "配额书", "content": "甲出场。"},
        headers=headers,
    ).json()

    # 超限后应 429
    for i in range(20):
        resp = client.post(
            f"/api/v1/books/{book['id']}/distill",
            json={"characters": [f"甲{i}"]},
            headers=headers,
        )
        assert resp.status_code == 202
    resp = client.post(
        f"/api/v1/books/{book['id']}/distill",
        json={"characters": ["超限"]},
        headers=headers,
    )
    assert resp.status_code == 429
    body = resp.json()
    text = str(body)
    assert "quota" in text or "429" in text or "配额" in text or "error" in text


def test_session_messages_empty(client: TestClient) -> None:
    book = client.post("/api/v1/books", json={"title": "空会话", "content": "x"}).json()
    client.post(f"/api/v1/books/{book['id']}/distill", json={"characters": ["甲"]})
    ses = client.post(
        "/api/v1/theater/sessions",
        json={"book_id": book["id"], "mode": "observe", "participants": ["甲"]},
    ).json()
    msgs = client.get(f"/api/v1/theater/sessions/{ses['id']}/messages").json()
    assert msgs["items"] == []
    assert msgs["total"] == 0


def test_scene_cards_list(client: TestClient) -> None:
    resp = client.get("/api/v1/scene-cards")
    assert resp.status_code == 200
    assert len(resp.json()["items"]) >= 1


def test_model_test_incomplete(client: TestClient) -> None:
    # 未配置模型时应返回 ok=false，而不是 500
    resp = client.post(
        "/api/v1/settings/model/test",
        json={"model": "m", "base_url": "http://127.0.0.1:9/v1", "api_key": ""},
    )
    assert resp.status_code == 200
    assert resp.json()["ok"] is False


def test_queue_singleton() -> None:
    q = get_queue()
    assert q is get_queue()
