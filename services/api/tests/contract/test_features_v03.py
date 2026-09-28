"""v0.3 功能契约测试：分支、记忆、世界、章节、导出、名场面、协作、演进、配额、Crossover。"""

from __future__ import annotations

import io
import json
import zipfile

import pytest
from fastapi.testclient import TestClient

from app.main import create_app
from app.store.memory import reset_store


@pytest.fixture()
def client() -> TestClient:
    reset_store()
    app = create_app()
    return TestClient(app)


def _make_book_with_cast(client: TestClient) -> str:
    resp = client.post(
        "/api/v1/books",
        json={
            "title": "红楼",
            "source": "upload",
            "novel_id": "hl",
            "content": "林黛玉拭泪。贾宝玉劝慰。",
        },
    )
    book_id = resp.json()["id"]
    client.post(
        f"/api/v1/books/{book_id}/distill", json={"characters": ["林黛玉", "贾宝玉"]}
    )
    return book_id


def _make_session(client: TestClient, book_id: str) -> dict:
    resp = client.post(
        "/api/v1/theater/sessions",
        json={
            "book_id": book_id,
            "mode": "observe",
            "participants": ["林黛玉", "贾宝玉"],
            "title": "主线",
        },
    )
    return resp.json()


def test_branch_timeline(client: TestClient) -> None:
    book_id = _make_book_with_cast(client)
    session = _make_session(client, book_id)
    turn = client.post(
        f"/api/v1/theater/sessions/{session['id']}/turns",
        json={"message": "你们怎么看？", "operation_id": "op-1"},
    ).json()

    resp = client.post(
        f"/api/v1/theater/sessions/{session['id']}/branch",
        json={"turn_id": turn["id"], "label": "如果当时没有离开"},
    )
    assert resp.status_code == 201
    child = resp.json()
    assert child["branch_of"] == session["id"]
    assert child["branch_label"] == "如果当时没有离开"
    assert child["is_mainline"] is False

    tree = client.get(
        "/api/v1/theater/sessions/tree", params={"book_id": book_id}
    ).json()
    assert len(tree) == 1
    assert tree[0]["id"] == session["id"]
    assert any(c["id"] == child["id"] for c in tree[0]["children"])


def test_memory_panel_and_prompt_injection(client: TestClient) -> None:
    book_id = _make_book_with_cast(client)
    session = _make_session(client, book_id)

    resp = client.post(
        f"/api/v1/theater/sessions/{session['id']}/memories",
        json={"text": "两人约定三日后再会", "category": "story", "pinned": True},
    )
    assert resp.status_code == 201
    mem_id = resp.json()["id"]

    resp = client.post(
        f"/api/v1/theater/sessions/{session['id']}/memories",
        json={"text": "两人约定三日后再会", "category": "story", "pinned": False},
    )
    assert resp.status_code == 201

    resp = client.post(
        f"/api/v1/theater/sessions/{session['id']}/memory-quality/merge-duplicates"
    )
    assert resp.json()["merged"] == 1

    items = client.get(f"/api/v1/theater/sessions/{session['id']}/memories").json()
    assert len(items) == 1

    updated = client.put(
        f"/api/v1/theater/sessions/{session['id']}/memories/{mem_id}",
        json={"enabled": False},
    ).json()
    assert updated["enabled"] is False


def test_world_memory_locked(client: TestClient) -> None:
    book_id = _make_book_with_cast(client)
    resp = client.post(
        f"/api/v1/books/{book_id}/world-memory/facts",
        json={
            "category": "event",
            "summary": "旧宅十年前失火",
            "location": "旧宅",
            "time_hint": "十年前",
            "locked": True,
        },
    )
    assert resp.status_code == 201
    fact = resp.json()
    assert fact["locked"] is True

    # 锁定事实不可删
    resp = client.delete(f"/api/v1/books/{book_id}/world-memory/facts/{fact['id']}")
    assert resp.status_code == 404

    session = _make_session(client, book_id)
    view = client.get(f"/api/v1/theater/sessions/{session['id']}/world-memory").json()
    assert any("失火" in t["summary"] for t in view["timeline"])


def test_chapter_rewrite_and_continue(client: TestClient) -> None:
    book_id = _make_book_with_cast(client)
    session = _make_session(client, book_id)
    client.post(
        f"/api/v1/theater/sessions/{session['id']}/turns",
        json={"message": "开始吧", "operation_id": "op-1"},
    )
    chapter = client.post(
        f"/api/v1/theater/sessions/{session['id']}/archive",
        json={"session_id": session["id"], "title": "第一章"},
    ).json()

    rewritten = client.post(
        f"/api/v1/theater/chapters/{chapter['id']}/rewrite",
        json={"instruction": "加强环境描写", "context_summary": "雨夜"},
    ).json()
    assert rewritten["id"] == chapter["id"]
    assert rewritten["content_md"]
    assert rewritten["revisions"]

    new_session = client.post(
        f"/api/v1/theater/chapters/{chapter['id']}/continue"
    ).json()
    assert new_session["book_id"] == book_id
    assert new_session["transcript_count"] >= 1


def test_export_package_roundtrip(client: TestClient) -> None:
    book_id = _make_book_with_cast(client)
    session = _make_session(client, book_id)
    client.post(
        f"/api/v1/theater/sessions/{session['id']}/turns",
        json={"message": "导出测试", "operation_id": "op-x"},
    )

    resp = client.get(f"/api/v1/books/{book_id}/export", params={"include_dialogue": 1})
    assert resp.status_code == 200
    raw = resp.content
    with zipfile.ZipFile(io.BytesIO(raw)) as zf:
        names = zf.namelist()
        assert "package_manifest.json" in names
        manifest = json.loads(zf.read("package_manifest.json"))
        assert manifest["schema_version"] == 1
        assert manifest["character_count"] == 2
        blob = json.dumps(manifest)
        assert "api_key" not in blob
        assert ":\\" not in blob

    # 再导入
    import base64 as b64

    resp = client.post(
        "/api/v1/books/import",
        json={
            "filename": "out.zaomeng.zip",
            "content_base64": b64.b64encode(raw).decode(),
        },
    )
    assert resp.status_code == 201
    assert resp.json()["source"] == "import"


def test_highlight_card_share(client: TestClient) -> None:
    book_id = _make_book_with_cast(client)
    session = _make_session(client, book_id)
    client.post(
        f"/api/v1/theater/sessions/{session['id']}/turns",
        json={"message": "名场面", "operation_id": "op-h"},
    )
    transcript = client.get(
        f"/api/v1/theater/sessions/{session['id']}"
    )  # ensure session exists
    assert transcript.status_code == 200

    card = client.post(
        "/api/v1/theater/highlights",
        json={"session_id": session["id"], "message_indexes": [0, 1], "title": "对峙"},
    ).json()
    assert card["lines"]
    assert card["share_token"]

    shared = client.get(f"/api/v1/theater/share/{card['share_token']}").json()
    assert shared["kind"] == "highlight"
    assert shared["readonly"] is True


def test_collab_seat_claim(client: TestClient) -> None:
    book_id = _make_book_with_cast(client)
    session = _make_session(client, book_id)

    resp = client.post(
        f"/api/v1/theater/sessions/{session['id']}/members",
        json={"character": "林黛玉", "display_name": "玩家A"},
    )
    assert resp.status_code == 201
    assert resp.json()["character"] == "林黛玉"

    resp = client.post(
        f"/api/v1/theater/sessions/{session['id']}/members",
        json={"character": "林黛玉", "display_name": "玩家B"},
    )
    assert resp.status_code == 409

    members = client.get(f"/api/v1/theater/sessions/{session['id']}/members").json()
    assert any(m["character"] == "林黛玉" for m in members)


def test_persona_evolve(client: TestClient) -> None:
    book_id = _make_book_with_cast(client)
    session = _make_session(client, book_id)
    client.post(
        f"/api/v1/theater/sessions/{session['id']}/turns",
        json={"message": "两人争执起来", "operation_id": "op-e"},
    )
    proposal = client.post(
        f"/api/v1/books/{book_id}/personas/林黛玉/evolve/proposal",
        json={"session_id": session["id"], "focus": "信任变化"},
    ).json()
    assert proposal["fields"]
    assert proposal["status"] == "proposed"

    applied = client.post(
        f"/api/v1/books/{book_id}/personas/林黛玉/evolve/apply",
        json={"proposal_id": proposal["id"], "note": "接受"},
    ).json()
    assert applied["status"] == "applied"


def test_auth_quota(client: TestClient) -> None:
    resp = client.post("/api/v1/auth/anon", json={"display_name": "旅人甲"})
    assert resp.status_code == 200
    token = resp.json()["token"]
    headers = {"Authorization": f"Bearer {token}"}

    me = client.get("/api/v1/auth/me", headers=headers).json()
    assert me["display_name"] == "旅人甲"

    quota = client.get("/api/v1/quota", headers=headers).json()
    assert quota["distill_limit"] == 20
    assert quota["distill_used"] == 0

    book = client.post(
        "/api/v1/books",
        json={"title": "配额书", "content": "测试"},
        headers=headers,
    ).json()
    job = client.post(
        f"/api/v1/books/{book['id']}/distill",
        json={"characters": ["甲"]},
        headers=headers,
    )
    assert job.status_code == 202

    quota = client.get("/api/v1/quota", headers=headers).json()
    assert quota["distill_used"] == 1


def test_crossover_requires_two_books(client: TestClient) -> None:
    b1 = _make_book_with_cast(client)
    resp = client.post(
        "/api/v1/books", json={"title": "三国", "content": "诸葛亮出山。"}
    )
    b2 = resp.json()["id"]
    client.post(f"/api/v1/books/{b2}/distill", json={"characters": ["诸葛亮"]})

    resp = client.post(
        "/api/v1/theater/crossover-spaces",
        json={
            "title": "群英会",
            "world_setting": "客栈相遇",
            "participants": [
                {"run_id": b1, "character": "林黛玉"},
                {"run_id": b2, "character": "诸葛亮"},
            ],
        },
    )
    assert resp.status_code == 201
    space = resp.json()
    assert space["title"] == "群英会"

    detail = client.get(f"/api/v1/theater/crossover-spaces/{space['id']}").json()
    assert detail["session"]["title"] == "群英会"


def test_bridge_sync_rejects_external(client: TestClient) -> None:
    resp = client.post(
        "/api/v1/bridge/sync",
        json={"base_url": "http://evil.com", "token": "t"},
    )
    assert resp.status_code == 502
