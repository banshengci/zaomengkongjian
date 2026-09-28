"""端到端 API 冒烟：书卷 → 蒸馏 → 剧场 → 章节 → 分享。"""

from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

from app.main import create_app
from app.store.memory import reset_store


@pytest.fixture()
def client() -> TestClient:
    reset_store()
    app = create_app()
    return TestClient(app)


def test_health(client: TestClient) -> None:
    resp = client.get("/api/v1/health")
    assert resp.status_code == 200
    assert resp.json()["status"] == "ok"


def test_full_theater_flow(client: TestClient) -> None:
    # 创建书卷并写入原文
    resp = client.post(
        "/api/v1/books",
        json={
            "title": "测试小说",
            "source": "upload",
            "novel_id": "demo",
            "content": "林黛玉在园中拭泪。贾宝玉赶来劝慰。两人争执后又和解。",
        },
    )
    assert resp.status_code == 201
    book = resp.json()
    book_id = book["id"]

    # 蒸馏（mock LLM）
    resp = client.post(
        f"/api/v1/books/{book_id}/distill",
        json={"characters": ["林黛玉", "贾宝玉"]},
    )
    assert resp.status_code == 202
    job = resp.json()
    assert job["stage"] == "done"

    resp = client.get(f"/api/v1/books/{book_id}/characters")
    assert resp.status_code == 200
    chars = resp.json()["items"]
    assert {c["name"] for c in chars} == {"林黛玉", "贾宝玉"}

    resp = client.get(f"/api/v1/books/{book_id}/relations")
    assert resp.status_code == 200
    assert resp.json()["total"] >= 1

    # 创建剧场会话
    resp = client.post(
        "/api/v1/theater/sessions",
        json={
            "book_id": book_id,
            "mode": "observe",
            "participants": ["林黛玉", "贾宝玉"],
            "title": "雨夜对话",
        },
    )
    assert resp.status_code == 201
    session = resp.json()

    # 非流式回合
    resp = client.post(
        f"/api/v1/theater/sessions/{session['id']}/turns",
        json={
            "message": "你们怎么看这事？",
            "message_kind": "dialogue",
            "operation_id": "op-1",
        },
    )
    assert resp.status_code == 201
    turn = resp.json()
    assert turn["status"] == "committed"
    assert turn["messages"]

    # SSE 流式回合
    with client.stream(
        "POST",
        f"/api/v1/theater/sessions/{session['id']}/reply/stream",
        json={"message": "再靠近一点说。", "operation_id": "op-2"},
    ) as resp:
        assert resp.status_code == 200
        body = "".join(resp.iter_text())
    assert "event: complete" in body
    assert "event: delta" in body

    # 导演
    resp = client.post(
        f"/api/v1/theater/sessions/{session['id']}/director",
        json={"goal": "揭示旧宅秘密", "action": "advance", "option_count": 3},
    )
    assert resp.status_code == 200
    assert len(resp.json()["options"]) == 3

    # 归档章节
    resp = client.post(
        f"/api/v1/theater/sessions/{session['id']}/archive",
        json={"session_id": session["id"], "title": "第一章"},
    )
    assert resp.status_code == 200
    chapter = resp.json()
    assert "林黛玉" in chapter["content_md"] or "旁白" in chapter["content_md"]

    resp = client.get(f"/api/v1/theater/chapters/{chapter['id']}/export")
    assert resp.status_code == 200
    assert resp.json()["format"] == "markdown"

    # 分享
    resp = client.post(
        "/api/v1/theater/share",
        json={
            "resource_type": "session",
            "resource_id": session["id"],
            "expires_hours": 24,
        },
    )
    assert resp.status_code == 201
    share = resp.json()
    resp = client.get(f"/api/v1/theater/share/{share['token']}")
    assert resp.status_code == 200
    assert resp.json()["readonly"] is True


def test_model_settings_and_bridge_guard(client: TestClient) -> None:
    resp = client.get("/api/v1/settings/model")
    assert resp.status_code == 200
    assert resp.json()["api_key_configured"] is False

    resp = client.put(
        "/api/v1/settings/model",
        json={
            "model": "gpt-test",
            "base_url": "https://api.example.com/v1",
            "api_key": "sk-x",
        },
    )
    assert resp.status_code == 200
    assert resp.json()["api_key_configured"] is True
    assert "api_key" not in resp.json()

    # 桥接只允许 localhost
    resp = client.post(
        "/api/v1/bridge/health",
        json={"base_url": "http://evil.example.com", "token": "t"},
    )
    assert resp.status_code == 502
