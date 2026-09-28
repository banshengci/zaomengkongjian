"""场景卡 API。"""

from __future__ import annotations

from typing import Any

from fastapi import APIRouter
from pydantic import BaseModel

from app.domain.schemas import SceneCardRead
from app.store.memory import get_store

router = APIRouter()


class SceneCardWrite(BaseModel):
    title: str
    fields: dict[str, Any] = {}


@router.get("")
async def list_scene_cards() -> dict[str, Any]:
    return {"items": get_store().list_scene_cards()}


@router.post("", response_model=SceneCardRead)
async def create_scene_card(payload: SceneCardWrite) -> SceneCardRead:
    import uuid

    card = get_store().upsert_scene_card(
        card_id=f"scene-{uuid.uuid4().hex[:8]}",
        title=payload.title,
        fields=payload.fields,
    )
    return card


@router.post("/recommend")
async def recommend(payload: dict[str, Any]) -> dict[str, Any]:
    cards = get_store().list_scene_cards()
    return {"items": cards[:3], "mode": payload.get("mode", "observe")}
