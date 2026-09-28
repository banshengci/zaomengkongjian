"""跨作品 Crossover 剧场。"""

from __future__ import annotations

from typing import Any

from fastapi import APIRouter, HTTPException

from app.domain.schemas import (
    CrossoverCreateRequest,
    CrossoverSpaceRead,
    SessionCreateRequest,
)
from app.store.memory import get_store

router = APIRouter()


@router.post("/crossover-spaces", response_model=CrossoverSpaceRead, status_code=201)
async def create_crossover(payload: CrossoverCreateRequest) -> CrossoverSpaceRead:
    store = get_store()
    # 校验参与者引用的书卷
    names: list[str] = []
    books_seen: set[str] = set()
    for p in payload.participants:
        run_id = str(p.get("run_id") or p.get("book_id") or "")
        character = str(p.get("character") or "")
        if not run_id or not character:
            raise HTTPException(
                status_code=400,
                detail={"error": "participant needs run_id and character"},
            )
        if store.get_book(run_id) is None:
            raise HTTPException(
                status_code=404, detail={"error": f"book not found: {run_id}"}
            )
        books_seen.add(run_id)
        names.append(f"{character}({run_id})")
    if len(books_seen) < 2:
        raise HTTPException(
            status_code=400, detail={"error": "crossover needs at least 2 books"}
        )

    # 用第一本书挂会话，participants 记录来源
    first_book = payload.participants[0]["run_id"]
    session = store.create_session(
        SessionCreateRequest(
            book_id=first_book,
            mode="observe",
            participants=[str(p.get("character") or "") for p in payload.participants],
            title=payload.title,
        )
    )
    store.update_session(
        session.id,
        x_dreamspace_crossover=True,
    )
    space = store.create_crossover(payload, session_id=session.id)
    return space


@router.get("/crossover-spaces/{space_id}")
async def get_crossover(space_id: str) -> dict[str, Any]:
    store = get_store()
    space = store.get_crossover(space_id)
    if space is None:
        raise HTTPException(status_code=404, detail={"error": "space not found"})
    session = store.get_session(space.session_id)
    return {
        "space": space.model_dump(mode="json"),
        "session": session.model_dump(mode="json") if session else None,
    }


@router.get("/crossover-spaces")
async def list_crossovers() -> dict[str, Any]:
    return {"items": [], "hint": "MVP: created spaces are addressable by id"}
