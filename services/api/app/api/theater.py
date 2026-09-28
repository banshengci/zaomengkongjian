"""剧场 API v0.3：分支、记忆、世界、导演、章节、分享、名场面、协作。"""

from __future__ import annotations

import asyncio
import json
import uuid
from typing import Any

from fastapi import APIRouter, HTTPException, Query
from fastapi.responses import StreamingResponse

from app.domain.schemas import (
    BranchRequest,
    ChapterCreateRequest,
    ChapterRead,
    ChapterRewriteRequest,
    DirectorOption,
    DirectorRequest,
    HighlightCardRead,
    HighlightCardRequest,
    MemoryCreateRequest,
    MemoryRead,
    SeatClaimRequest,
    SessionCreateRequest,
    SessionMemberRead,
    SessionRead,
    SessionTreeNode,
    ShareCreateRequest,
    ShareLinkRead,
    TurnCreateRequest,
    TurnMessage,
    TurnRead,
    utc_now,
)
from app.llm.client import LlmClient, LlmMessage
from app.store.memory import get_store

router = APIRouter()


def _session_or_404(session_id: str) -> SessionRead:
    session = get_store().get_session(session_id)
    if session is None:
        raise HTTPException(status_code=404, detail={"error": "session not found"})
    return session


def _sse(event: str, data: dict[str, Any]) -> str:
    return f"event: {event}\ndata: {json.dumps(data, ensure_ascii=False)}\n\n"


# ---------- sessions / branch ----------


@router.get("/sessions/tree", response_model=list[SessionTreeNode])
async def session_tree(book_id: str = Query(...)) -> list[SessionTreeNode]:
    return get_store().session_tree(book_id)


@router.get("/sessions", response_model=list[SessionRead])
async def list_sessions(book_id: str = "") -> list[SessionRead]:
    return get_store().list_sessions(book_id or None)


@router.post("/sessions", response_model=SessionRead, status_code=201)
async def create_session(payload: SessionCreateRequest) -> SessionRead:
    store = get_store()
    if store.get_book(payload.book_id) is None:
        raise HTTPException(status_code=404, detail={"error": "book not found"})
    known = {c.name for c in store.list_characters(payload.book_id)}
    if known:
        missing = [p for p in payload.participants if p not in known]
        if missing:
            raise HTTPException(
                status_code=400, detail={"error": f"unknown participants: {missing}"}
            )
    return store.create_session(payload)


@router.get("/sessions/{session_id}", response_model=SessionRead)
async def get_session(session_id: str) -> SessionRead:
    return _session_or_404(session_id)


@router.delete("/sessions/{session_id}")
async def delete_session(session_id: str) -> dict[str, str]:
    if not get_store().delete_session(session_id):
        raise HTTPException(status_code=404, detail={"error": "session not found"})
    return {"status": "deleted"}


@router.get("/sessions/{session_id}/messages")
async def session_messages(session_id: str, limit: int = 200) -> dict[str, Any]:
    _session_or_404(session_id)
    transcript = get_store().session_transcript(session_id)
    items = transcript[-max(1, min(limit, 500)) :]
    return {
        "items": [m.model_dump() for m in items],
        "total": len(transcript),
    }


@router.post(
    "/sessions/{session_id}/branch", response_model=SessionRead, status_code=201
)
async def branch_session(session_id: str, payload: BranchRequest) -> SessionRead:
    store = get_store()
    parent = _session_or_404(session_id)
    if payload.turn_id:
        turns = store.list_turns(session_id)
        idx = next((i for i, t in enumerate(turns) if t.id == payload.turn_id), -1)
        cutoff = turns[: idx + 1] if idx >= 0 else turns
    else:
        cutoff = store.list_turns(session_id)

    child = store.create_session(
        SessionCreateRequest(
            book_id=parent.book_id,
            mode=parent.mode,
            participants=list(parent.participants),
            controlled_character=parent.controlled_character,
            scene_card_id=parent.scene_card_id,
            self_card_id=parent.self_card_id,
            title=payload.label or f"{parent.title}·支线",
            branch_of=parent.id,
            branch_label=payload.label,
        )
    )
    store.update_session(
        child.id,
        is_mainline=payload.is_mainline,
        locked_event_ids=list(payload.locked_event_ids),
    )
    for turn in cutoff:
        clone = turn.model_copy(
            update={"id": f"turn-{uuid.uuid4().hex[:10]}", "session_id": child.id}
        )
        store.append_turn(child.id, clone)
    for mem in store.list_memories(session_id):
        store.add_memory(
            child.id,
            MemoryCreateRequest(
                text=mem.text,
                category=mem.category,
                pinned=mem.pinned,
                enabled=mem.enabled,
            ),
            source="inherited",
        )
    return store.get_session(child.id) or child


@router.post("/sessions/{session_id}/branch-meta", response_model=SessionRead)
async def patch_branch_meta(session_id: str, payload: dict[str, Any]) -> SessionRead:
    allowed = {
        k: v
        for k, v in payload.items()
        if k in {"branch_label", "is_mainline", "locked_event_ids", "title"}
    }
    updated = get_store().update_session(session_id, **allowed)
    if updated is None:
        raise HTTPException(status_code=404, detail={"error": "session not found"})
    return updated


# ---------- turns / SSE ----------


@router.post("/sessions/{session_id}/turns", response_model=TurnRead, status_code=201)
async def create_turn(session_id: str, payload: TurnCreateRequest) -> TurnRead:
    session = _session_or_404(session_id)
    turn = await _generate_turn(session, payload)
    await _broadcast_turn(session_id, turn)
    return turn


@router.get("/sessions/{session_id}/events")
async def session_events(session_id: str) -> StreamingResponse:
    """协作实时流：peer_turn / seat_claimed 等广播。"""
    _session_or_404(session_id)
    from app.events import get_bus

    async def event_gen():
        bus = await get_bus()
        yield _sse("status", {"phase": "listening", "message": "subscribed"})
        try:
            async for ev in bus.stream(session_id):
                yield _sse(ev.event, ev.data)
        except asyncio.CancelledError:
            raise
        except Exception as exc:  # noqa: BLE001
            yield _sse("error", {"message": str(exc), "retryable": True})

    return StreamingResponse(event_gen(), media_type="text/event-stream")


@router.get("/sessions/{session_id}/turns/{turn_id}/events")
async def stream_turn(session_id: str, turn_id: str) -> StreamingResponse:
    _session_or_404(session_id)
    store = get_store()
    turn = store.get_turn(session_id, turn_id)
    if turn is None:
        raise HTTPException(status_code=404, detail={"error": "turn not found"})

    async def event_gen():
        yield _sse("status", {"phase": "generating", "message": "generating"})
        for index, msg in enumerate(turn.messages):
            yield _sse(
                "delta",
                {
                    "index": index,
                    "speaker": msg.speaker,
                    "role": msg.role,
                    "field": "message",
                    "text": msg.message,
                },
            )
        session_obj = store.get_session(session_id)
        yield _sse(
            "complete",
            {
                "session": session_obj.model_dump(mode="json") if session_obj else {},
                "appended_transcript": [m.model_dump() for m in turn.messages],
                "replayed": True,
            },
        )

    return StreamingResponse(event_gen(), media_type="text/event-stream")


@router.post("/sessions/{session_id}/reply/stream")
async def reply_stream(
    session_id: str, payload: TurnCreateRequest
) -> StreamingResponse:
    session = _session_or_404(session_id)
    store = get_store()
    turn_id = f"turn-{uuid.uuid4().hex[:10]}"
    operation_id = payload.operation_id or turn_id

    async def event_gen():
        yield _sse("status", {"phase": "generating", "message": "generating"})
        try:
            buffer: dict[str, dict[str, Any]] = {}
            client = LlmClient()
            messages = _build_llm_messages(session, payload)
            async for row in client.stream_ndjson(messages):
                speaker = str(row.get("speaker") or "旁白").strip()
                text = str(row.get("message") or "")
                if not text:
                    continue
                if speaker not in buffer:
                    buffer[speaker] = {
                        "speaker": speaker,
                        "message": "",
                        "role": "character",
                    }
                buffer[speaker]["message"] += text
                yield _sse(
                    "delta",
                    {
                        "index": len(buffer) - 1,
                        "speaker": speaker,
                        "role": "character",
                        "field": "message",
                        "text": text,
                    },
                )

            collected = [
                TurnMessage(
                    speaker=v["speaker"], message=v["message"], role="character"
                )
                for v in buffer.values()
            ]
            if not collected:
                collected = [
                    TurnMessage(
                        speaker="旁白", message="（本轮无输出）", role="narration"
                    )
                ]
                yield _sse("reset", {"message": "empty output"})

            turn = TurnRead(
                id=turn_id,
                session_id=session_id,
                operation_id=operation_id,
                status="committed",
                messages=collected,
                created_at=utc_now(),
            )
            store.append_turn(session_id, turn)
            await _broadcast_turn(session_id, turn)
            session_obj = store.get_session(session_id)
            yield _sse(
                "complete",
                {
                    "turn_id": turn_id,
                    "session": session_obj.model_dump(mode="json")
                    if session_obj
                    else {},
                    "appended_transcript": [m.model_dump() for m in collected],
                    "replayed": False,
                    "transcript_count": session_obj.transcript_count
                    if session_obj
                    else 0,
                },
            )
        except Exception as exc:  # noqa: BLE001
            yield _sse("error", {"message": str(exc), "retryable": True})

    return StreamingResponse(event_gen(), media_type="text/event-stream")


# ---------- memories ----------


@router.get("/sessions/{session_id}/memories", response_model=list[MemoryRead])
async def list_memories(session_id: str) -> list[MemoryRead]:
    _session_or_404(session_id)
    return get_store().list_memories(session_id)


@router.post(
    "/sessions/{session_id}/memories", response_model=MemoryRead, status_code=201
)
async def create_memory(session_id: str, payload: MemoryCreateRequest) -> MemoryRead:
    _session_or_404(session_id)
    return get_store().add_memory(session_id, payload)


@router.put("/sessions/{session_id}/memories/{memory_id}", response_model=MemoryRead)
async def update_memory(
    session_id: str, memory_id: str, payload: dict[str, Any]
) -> MemoryRead:
    _session_or_404(session_id)
    allowed = {
        k: v
        for k, v in payload.items()
        if k in {"text", "category", "pinned", "enabled", "status"}
    }
    updated = get_store().update_memory(session_id, memory_id, **allowed)
    if updated is None:
        raise HTTPException(status_code=404, detail={"error": "memory not found"})
    return updated


@router.delete("/sessions/{session_id}/memories/{memory_id}")
async def delete_memory(session_id: str, memory_id: str) -> dict[str, str]:
    _session_or_404(session_id)
    if not get_store().delete_memory(session_id, memory_id):
        raise HTTPException(status_code=404, detail={"error": "memory not found"})
    return {"status": "deleted"}


@router.post("/sessions/{session_id}/memory-quality/merge-duplicates")
async def merge_memories(session_id: str) -> dict[str, Any]:
    _session_or_404(session_id)
    store = get_store()
    items = store.list_memories(session_id)
    seen: set[str] = set()
    merged = 0
    for mem in items:
        key = mem.text.strip()
        if key in seen:
            store.delete_memory(session_id, mem.id)
            merged += 1
        else:
            seen.add(key)
    return {"merged": merged, "remaining": len(store.list_memories(session_id))}


# ---------- world facts 会话视图（CRUD 在 books 路由） ----------


@router.get("/sessions/{session_id}/world-memory")
async def session_world_view(session_id: str) -> dict[str, Any]:
    session = _session_or_404(session_id)
    facts = get_store().list_world_facts(session.book_id)
    return {
        "facts": [f.model_dump(mode="json") for f in facts],
        "timeline": [
            {
                "time_hint": f.time_hint,
                "location": f.location,
                "summary": f.summary,
                "locked": f.locked,
            }
            for f in facts
        ],
    }


# ---------- director / chapters ----------


@router.post("/sessions/{session_id}/director")
async def director_options(session_id: str, payload: DirectorRequest) -> dict[str, Any]:
    session = _session_or_404(session_id)
    options = _director_options(payload, session.participants)
    return {"session_id": session.id, "action": payload.action, "options": options}


@router.post("/sessions/{session_id}/archive", response_model=ChapterRead)
async def archive_session(
    session_id: str, payload: ChapterCreateRequest
) -> ChapterRead:
    store = get_store()
    session = _session_or_404(session_id)
    transcript = store.session_transcript(session_id)
    lines = [f"# {payload.title or session.title}", ""]
    for msg in transcript:
        prefix = "旁白" if msg.role == "narration" else msg.speaker
        if msg.inner_thought:
            lines.append(f"（{msg.inner_thought}）")
        lines.append(f"**{prefix}**：{msg.message}")
        lines.append("")
    return store.create_chapter(payload, session.book_id, "\n".join(lines))


@router.get("/chapters")
async def list_chapters(book_id: str = "") -> dict[str, Any]:
    return {"items": get_store().list_chapters(book_id or None)}


@router.get("/chapters/{chapter_id}", response_model=ChapterRead)
async def get_chapter(chapter_id: str) -> ChapterRead:
    chapter = get_store().get_chapter(chapter_id)
    if chapter is None:
        raise HTTPException(status_code=404, detail={"error": "chapter not found"})
    return chapter


@router.get("/chapters/{chapter_id}/export")
async def export_chapter(
    chapter_id: str, format: str = Query(default="markdown")
) -> dict[str, str]:
    chapter = get_store().get_chapter(chapter_id)
    if chapter is None:
        raise HTTPException(status_code=404, detail={"error": "chapter not found"})
    if format not in {"markdown", "text", "md"}:
        raise HTTPException(
            status_code=400, detail={"error": "format must be markdown|text"}
        )
    body = (
        chapter.content_md if format != "text" else chapter.content_md.replace("**", "")
    )
    return {
        "format": format,
        "filename": f"{chapter.title}.md",
        "content": body,
    }


@router.post("/chapters/{chapter_id}/rewrite", response_model=ChapterRead)
async def rewrite_chapter(
    chapter_id: str, payload: ChapterRewriteRequest
) -> ChapterRead:
    store = get_store()
    chapter = store.get_chapter(chapter_id)
    if chapter is None:
        raise HTTPException(status_code=404, detail={"error": "chapter not found"})
    client = LlmClient()
    prompt = (
        "请按下列指令改写章节，保持人物口吻，只输出改写后的 markdown。\n"
        f"指令：{payload.instruction}\n"
        f"背景：{payload.context_summary}\n"
        f"原文：\n{chapter.content_md[:6000]}"
    )
    text = await client.complete_text([LlmMessage(role="user", content=prompt)])
    revisions = list(chapter.revisions)
    revisions.append(
        {"content": chapter.content_md, "instruction": payload.instruction}
    )
    updated = store.update_chapter(
        chapter_id,
        content_md=text
        if text.strip().startswith("#")
        else f"# {chapter.title}\n\n{text}",
        revisions=revisions,
    )
    return updated or chapter


@router.post(
    "/chapters/{chapter_id}/continue", response_model=SessionRead, status_code=201
)
async def continue_chapter(chapter_id: str) -> SessionRead:
    store = get_store()
    chapter = store.get_chapter(chapter_id)
    if chapter is None:
        raise HTTPException(status_code=404, detail={"error": "chapter not found"})
    names = [c.name for c in store.list_characters(chapter.book_id)] or ["角色"]
    session = store.create_session(
        SessionCreateRequest(
            book_id=chapter.book_id,
            mode="observe",
            participants=names[:6],
            title=f"续写·{chapter.title}",
        )
    )
    store.append_turn(
        session.id,
        TurnRead(
            id=f"turn-{uuid.uuid4().hex[:8]}",
            session_id=session.id,
            status="committed",
            messages=[
                TurnMessage(
                    speaker="旁白",
                    message=f"（承前）{chapter.content_md[:400]}",
                    role="narration",
                )
            ],
        ),
    )
    return store.get_session(session.id) or session


# ---------- share / highlight ----------


@router.post("/share", response_model=ShareLinkRead, status_code=201)
async def create_share(payload: ShareCreateRequest) -> ShareLinkRead:
    store = get_store()
    if payload.resource_type == "session":
        if store.get_session(payload.resource_id) is None:
            raise HTTPException(status_code=404, detail={"error": "session not found"})
    elif (
        payload.resource_type == "chapter"
        and store.get_chapter(payload.resource_id) is None
    ):
        raise HTTPException(status_code=404, detail={"error": "chapter not found"})
    return store.create_share(payload)


@router.get("/share/{token}")
async def read_share(token: str) -> dict[str, Any]:
    store = get_store()
    link = store.get_share(token)
    if link is None:
        raise HTTPException(
            status_code=404, detail={"error": "share not found or expired"}
        )
    if link.resource_type == "session":
        session = store.get_session(link.resource_id)
        if session is None:
            raise HTTPException(status_code=404, detail={"error": "resource missing"})
        return {
            "kind": "session",
            "session": session.model_dump(mode="json"),
            "transcript": [
                m.model_dump() for m in store.session_transcript(link.resource_id)
            ],
            "readonly": True,
        }
    if link.resource_type == "highlight":
        card = store.get_highlight(link.resource_id)
        if card is None:
            raise HTTPException(status_code=404, detail={"error": "resource missing"})
        return {
            "kind": "highlight",
            "title": card.title,
            "lines": [m.model_dump() for m in card.lines],
            "readonly": True,
        }
    chapter = store.get_chapter(link.resource_id)
    if chapter is None:
        raise HTTPException(status_code=404, detail={"error": "resource missing"})
    return {
        "kind": "chapter",
        "chapter": chapter.model_dump(mode="json"),
        "readonly": True,
    }


@router.delete("/share/{token}")
async def revoke_share(token: str) -> dict[str, str]:
    if not get_store().revoke_share(token):
        raise HTTPException(status_code=404, detail={"error": "share not found"})
    return {"status": "revoked"}


@router.post("/highlights", response_model=HighlightCardRead, status_code=201)
async def create_highlight(payload: HighlightCardRequest) -> HighlightCardRead:
    store = get_store()
    _session_or_404(payload.session_id)
    transcript = store.session_transcript(payload.session_id)
    lines: list[TurnMessage] = []
    for idx in payload.message_indexes:
        if 0 <= idx < len(transcript):
            lines.append(transcript[idx])
    if not lines:
        raise HTTPException(status_code=400, detail={"error": "no messages selected"})
    card = HighlightCardRead(
        id=f"hl-{uuid.uuid4().hex[:8]}",
        session_id=payload.session_id,
        title=payload.title,
        lines=lines,
        created_at=utc_now(),
    )
    share = store.create_share(
        ShareCreateRequest(
            resource_type="highlight", resource_id=card.id, expires_hours=72
        )
    )
    card = card.model_copy(update={"share_token": share.token})
    return store.add_highlight(card)


# ---------- collaboration ----------


@router.get("/sessions/{session_id}/members", response_model=list[SessionMemberRead])
async def list_members(session_id: str) -> list[SessionMemberRead]:
    _session_or_404(session_id)
    return get_store().list_members(session_id)


@router.post(
    "/sessions/{session_id}/members",
    response_model=SessionMemberRead,
    status_code=201,
)
async def claim_seat(
    session_id: str, payload: SeatClaimRequest, user_id: str = "anon"
) -> SessionMemberRead:
    _session_or_404(session_id)
    store = get_store()
    session = store.get_session(session_id)
    assert session is not None
    if payload.character not in session.participants:
        raise HTTPException(
            status_code=400, detail={"error": "character not in participants"}
        )
    try:
        member = store.claim_seat(
            session_id,
            user_id,
            payload.display_name or payload.character,
            payload.character,
        )
    except ValueError as exc:
        raise HTTPException(status_code=409, detail={"error": str(exc)}) from exc
    from app.events import BusEvent, get_bus

    bus = await get_bus()
    await bus.publish(
        BusEvent(
            session_id=session_id,
            event="seat_claimed",
            data=member.model_dump(mode="json"),
        )
    )
    return member


# ---------- helpers ----------


def _build_llm_messages(
    session: SessionRead, payload: TurnCreateRequest
) -> list[LlmMessage]:
    store = get_store()
    participants = "、".join(session.participants)
    history = store.session_transcript(session.id)
    history_lines = [f"{m.speaker}: {m.message}" for m in history[-12:]]
    mem_lines = [f"- {m.text}" for m in store.active_prompt_memories(session.id)]
    locked = [f"- {f.summary}" for f in store.locked_facts(session.book_id)]
    kind_note = {
        "dialogue": "以角色口吻对话",
        "narration": "以旁白推进",
        "plot": "推进剧情事件",
        "fourth_wall": "作者在故事之外下指令",
    }.get(payload.message_kind, "对话")
    pacing = {
        "brief": "每人一两句，简短",
        "normal": "正常节奏",
        "detailed": "展开动作与环境",
    }.get(payload.pacing, "正常节奏")
    system_parts = [
        "你是多角色小说对话引擎。输出 NDJSON，每行一个 JSON 对象，字段 speaker/message，可选 inner_thought。",
        f"参与角色：{participants}。本回合要求：{kind_note}；{pacing}。",
        "禁止 markdown 代码块，禁止多余说明。",
    ]
    if session.branch_label:
        system_parts.append(f"当前分支：{session.branch_label}。")
    if mem_lines:
        system_parts.append("必须遵守的记忆：\n" + "\n".join(mem_lines))
    if locked:
        system_parts.append("不可改写的锁定事实：\n" + "\n".join(locked))
    user = (
        "会话历史：\n"
        + "\n".join(history_lines)
        + f"\n用户输入：{payload.message}\n请生成下一轮多角色回复。"
    )
    return [
        LlmMessage(role="system", content="\n".join(system_parts)),
        LlmMessage(role="user", content=user),
    ]


async def _generate_turn(session: SessionRead, payload: TurnCreateRequest) -> TurnRead:
    store = get_store()
    turn_id = f"turn-{uuid.uuid4().hex[:10]}"
    client = LlmClient()
    messages = _build_llm_messages(session, payload)
    buffer: dict[str, str] = {}
    async for row in client.stream_ndjson(messages):
        speaker = str(row.get("speaker") or "旁白").strip()
        text = str(row.get("message") or "")
        if text:
            buffer[speaker] = buffer.get(speaker, "") + text
    collected = [
        TurnMessage(speaker=s, message=m, role="character") for s, m in buffer.items()
    ]
    if not collected:
        collected = [
            TurnMessage(speaker="旁白", message="（本轮无输出）", role="narration")
        ]
    turn = TurnRead(
        id=turn_id,
        session_id=session.id,
        operation_id=payload.operation_id or turn_id,
        status="committed",
        messages=collected,
        created_at=utc_now(),
    )
    store.append_turn(session.id, turn)
    return turn


async def _broadcast_turn(session_id: str, turn: TurnRead) -> None:
    """向同会话订阅者广播 peer_turn（协作实时）。"""
    from app.events import BusEvent, get_bus

    bus = await get_bus()
    await bus.publish(
        BusEvent(
            session_id=session_id,
            event="peer_turn",
            data={
                "turn_id": turn.id,
                "operation_id": turn.operation_id,
                "messages": [m.model_dump() for m in turn.messages],
            },
        )
    )


def _director_options(
    payload: DirectorRequest, participants: list[str]
) -> list[DirectorOption]:
    presets = {
        "advance": ("推进", "让情节向前一步"),
        "slow_emotion": ("情绪放缓", "聚焦内心与关系温度"),
        "conflict": ("制造冲突", "抛出分歧或对立"),
        "viewpoint": ("切换视角", "换一人主视叙述"),
        "fourth_wall": ("第四面墙", "作者直接向角色下令"),
    }
    title, detail = presets.get(payload.action, presets["advance"])
    return [
        DirectorOption(
            id=f"dir-{payload.action}-{i}",
            action=payload.action,
            title=f"{title}-{i + 1}",
            detail=f"{detail}；目标：{payload.goal or '保持张力'}",
            message_kind="fourth_wall"
            if payload.action == "fourth_wall"
            else "dialogue",
        )
        for i in range(payload.option_count)
    ]
